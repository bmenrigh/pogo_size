#!/usr/bin/env python3
"""Compress an equally spaced CDF into monotone fifth-order polynomial pieces."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TextIO

import numpy as np


DEGREE = 5
DEFAULT_RELATIVE_ERROR = 1.0 / 1_000_000.0
ZERO_WEIGHT_FLOOR = 1e-15
INITIAL_SEARCH_SPAN = 32


@dataclass(frozen=True)
class PolynomialSegment:
    kind: str
    start_index: int
    end_index: int
    coefficients: np.ndarray
    maximum_relative_error: float


def read_cdf(path: Path | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read an equally spaced CDF with an optional explicit survival column."""
    source = str(path) if path is not None else "<stdin>"
    try:
        if path is None:
            values = np.loadtxt(sys.stdin, dtype=np.float64, comments="#")
        else:
            values = np.loadtxt(path, dtype=np.float64, comments="#")
    except (OSError, ValueError) as error:
        raise ValueError(f"{source}: could not read CDF table: {error}") from error

    if values.ndim != 2 or values.shape[1] not in (2, 3) or values.shape[0] < 2:
        raise ValueError(
            f"{source}: CDF must contain at least two rows with 2 or 3 columns"
        )
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{source}: all coordinates and CDF values must be finite")

    coordinates = values[:, 0]
    cumulatives = values[:, 1]
    survivals = values[:, 2] if values.shape[1] == 3 else 1.0 - cumulatives
    widths = np.diff(coordinates)
    if np.any(widths <= 0.0):
        raise ValueError(f"{source}: coordinates must be strictly increasing")
    width = widths[0]
    spacing_tolerance = max(abs(width) * 1e-8, np.finfo(float).eps * 16)
    if not np.all(np.abs(widths - width) <= spacing_tolerance):
        raise ValueError(f"{source}: coordinates must be equally spaced")
    if np.any(cumulatives < 0.0) or np.any(cumulatives > 1.0):
        raise ValueError(f"{source}: CDF values must be between zero and one")
    if np.any(np.diff(cumulatives) < 0.0):
        raise ValueError(f"{source}: CDF values must be nondecreasing")
    if np.any(survivals < 0.0) or np.any(survivals > 1.0):
        raise ValueError(f"{source}: survival values must be between zero and one")
    if np.any(np.diff(survivals) > 0.0):
        raise ValueError(f"{source}: survival values must be nonincreasing")
    if not np.allclose(cumulatives + survivals, 1.0, rtol=0.0, atol=1e-12):
        raise ValueError(f"{source}: CDF and survival values must sum to one")
    return coordinates, cumulatives, survivals


def evaluate_polynomial(coefficients: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Evaluate endpoint values plus a cubic correction, totaling degree five."""
    correction = np.full_like(t, coefficients[-1], dtype=np.float64)
    for coefficient in coefficients[-2:1:-1]:
        correction = correction * t + coefficient
    return (
        (1.0 - t) * coefficients[0]
        + t * coefficients[1]
        + t * (1.0 - t) * correction
    )


def _is_monotone(coefficients: np.ndarray, *, increasing: bool) -> bool:
    """Check the polynomial derivative's sign throughout [0, 1]."""
    derivative = np.polynomial.polynomial.polyder(coefficients)
    second_derivative = np.polynomial.polynomial.polyder(derivative)
    candidates = [0.0, 1.0]
    for root in np.polynomial.polynomial.polyroots(second_derivative):
        if abs(root.imag) <= 1e-10 and 0.0 < root.real < 1.0:
            candidates.append(float(root.real))
    derivative_values = np.polynomial.polynomial.polyval(candidates, derivative)
    scale = max(1.0, float(np.max(np.abs(derivative_values))))
    if increasing:
        return bool(np.min(derivative_values) >= -1e-12 * scale)
    return bool(np.max(derivative_values) <= 1e-12 * scale)


def fit_segment(
    values: np.ndarray,
    start: int,
    end: int,
    relative_error: float,
    kind: str = "C",
    coordinates: np.ndarray | None = None,
) -> PolynomialSegment | None:
    """Fit one endpoint-constrained fifth-order polynomial and validate it."""
    count = end - start + 1
    if coordinates is None:
        t = np.linspace(0.0, 1.0, count, dtype=np.float64)
    else:
        segment_coordinates = coordinates[start : end + 1]
        t = (segment_coordinates - segment_coordinates[0]) / (
            segment_coordinates[-1] - segment_coordinates[0]
        )
    observed = values[start : end + 1]
    left = float(observed[0])
    right = float(observed[-1])
    baseline = left + (right - left) * t

    # p(t) = baseline(t) + t(1-t) q(t), where degree(q) <= 3. This
    # constrains both segment endpoints exactly while retaining degree five.
    power_coefficients = np.zeros(DEGREE + 1, dtype=np.float64)
    power_coefficients[0] = left
    power_coefficients[1] = right - left
    q_coefficients = np.zeros(DEGREE - 1, dtype=np.float64)
    if count > 2:
        interior_t = t[1:-1]
        factor = interior_t * (1.0 - interior_t)
        design = np.column_stack(
            [factor * interior_t**power for power in range(DEGREE - 1)]
        )
        residual = observed[1:-1] - baseline[1:-1]
        error_scale = np.maximum(np.abs(observed[1:-1]), ZERO_WEIGHT_FLOOR)
        weights = 1.0 / error_scale
        q_coefficients, *_ = np.linalg.lstsq(
            design * weights[:, None], residual * weights, rcond=None
        )
        for power, coefficient in enumerate(q_coefficients):
            power_coefficients[power + 1] += coefficient
            power_coefficients[power + 2] -= coefficient

    coefficients = np.concatenate(([left, right], q_coefficients))
    predicted = evaluate_polynomial(coefficients, t)
    absolute_error = np.abs(predicted - observed)
    error_denominator = np.abs(observed)
    exact_mask = error_denominator == 0.0
    if np.any(absolute_error[exact_mask] != 0.0):
        return None

    relative_mask = ~exact_mask
    relative_errors = np.zeros_like(observed)
    relative_errors[relative_mask] = (
        absolute_error[relative_mask] / error_denominator[relative_mask]
    )
    maximum_relative_error = float(np.max(relative_errors))
    # Leave a tiny margin for lookup evaluation and coefficient serialization.
    if maximum_relative_error > relative_error * (1.0 - 1e-10):
        return None
    if not _is_monotone(power_coefficients, increasing=kind == "C"):
        return None
    return PolynomialSegment(kind, start, end, coefficients, maximum_relative_error)


def find_furthest_segment(
    values: np.ndarray,
    start: int,
    final_index: int,
    relative_error: float,
    kind: str = "C",
    coordinates: np.ndarray | None = None,
) -> PolynomialSegment:
    """Find the furthest passing endpoint by exponential then binary search."""
    adjacent = fit_segment(
        values,
        start,
        start + 1,
        relative_error,
        kind,
        coordinates,
    )
    if adjacent is None:
        raise AssertionError("two endpoint values must always be exactly fit")

    best = adjacent
    span = min(INITIAL_SEARCH_SPAN, final_index - start)
    failed_end: int | None = None

    while span > best.end_index - start:
        end = start + span
        candidate = fit_segment(
            values, start, end, relative_error, kind, coordinates
        )
        if candidate is None:
            failed_end = end
            break
        best = candidate
        if end == final_index:
            return best
        span = min(span * 2, final_index - start)

    if failed_end is None:
        failed_end = min(start + span, final_index)

    low = best.end_index + 1
    high = failed_end - 1
    while low <= high:
        middle = (low + high) // 2
        candidate = fit_segment(
            values, start, middle, relative_error, kind, coordinates
        )
        if candidate is None:
            high = middle - 1
        else:
            best = candidate
            low = middle + 1
    return best


def compress_cdf(
    cumulatives: np.ndarray,
    relative_error: float,
    survivals: np.ndarray | None = None,
    preserve_both_tails: bool = True,
    coordinates: np.ndarray | None = None,
) -> list[PolynomialSegment]:
    if not math.isfinite(relative_error) or not 0.0 < relative_error < 1.0:
        raise ValueError("relative error must be greater than zero and less than one")

    final_index = len(cumulatives) - 1
    if survivals is None:
        survivals = 1.0 - cumulatives

    segments: list[PolynomialSegment] = []

    def append_range(values: np.ndarray, start: int, end: int, kind: str) -> None:
        while start < end:
            segment = find_furthest_segment(
                values, start, end, relative_error, kind, coordinates
            )
            segments.append(segment)
            start = segment.end_index

    if not preserve_both_tails:
        append_range(cumulatives, 0, final_index, "C")
        return segments

    lower_is_smaller = cumulatives <= survivals
    lower_indices = np.flatnonzero(lower_is_smaller)
    switch = int(lower_indices[-1]) if len(lower_indices) else 0
    if switch > 0:
        append_range(cumulatives, 0, switch, "C")
    if switch < final_index:
        # At the shared boundary, make the survival representation exactly the
        # complement of the preceding CDF representation. Around 0.5 this
        # subtraction is numerically harmless and guarantees continuity.
        survival_values = survivals.copy()
        survival_values[switch] = 1.0 - cumulatives[switch]
        append_range(survival_values, switch, final_index, "S")
    return segments


def write_segments(
    coordinates: np.ndarray,
    segments: Sequence[PolynomialSegment],
    output: TextIO,
) -> None:
    print("# cdf-poly-v3 degree=5 basis=endpoint-q", file=output)
    print("# t=(x-start)/(end-start)", file=output)
    print("# kind start end y0 y1 q0 q1 q2 q3", file=output)
    for segment in segments:
        fields = [
            segment.kind,
            format(float(coordinates[segment.start_index]), ".17g"),
            format(float(coordinates[segment.end_index]), ".17g"),
            *(format(float(value), ".17g") for value in segment.coefficients),
        ]
        print("\t".join(fields), file=output)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compress an equally spaced CDF/survival table into endpoint-"
            "constrained, monotone fifth-order polynomial segments."
        )
    )
    parser.add_argument(
        "input",
        metavar="CDF",
        type=Path,
        nargs="?",
        help="uncompressed CDF or CDF/survival path (default: standard input)",
    )
    parser.add_argument(
        "--cdf-relative-only",
        action="store_true",
        help=(
            "fit only CDF values and ignore the explicit survival column; this "
            "does not preserve small upper-tail p-values"
        ),
    )
    parser.add_argument(
        "--relative-error",
        type=float,
        default=DEFAULT_RELATIVE_ERROR,
        help="maximum relative error at every input point (default: 1e-6)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        coordinates, cumulatives, survivals = read_cdf(args.input)
        preserve_both_tails = not args.cdf_relative_only
        segments = compress_cdf(
            cumulatives,
            args.relative_error,
            survivals,
            preserve_both_tails,
            coordinates,
        )
        write_segments(coordinates, segments, sys.stdout)
    except ValueError as error:
        parser.error(str(error))

    maximum_error = max(segment.maximum_relative_error for segment in segments)
    print(
        f"Compressed {len(cumulatives)} CDF points into {len(segments)} "
        f"degree-{DEGREE} segments; max sampled "
        f"{'two-tail' if preserve_both_tails else 'CDF'} relative error "
        f"{maximum_error:.9g}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
