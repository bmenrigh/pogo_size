#!/usr/bin/env python3
"""Compress a sampled PDF while bounding linear-interpolation error."""

from __future__ import annotations

import argparse
import math
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Iterable, Iterator, Sequence, TextIO


DEFAULT_RELATIVE_ERROR = 1.0 / 1_000_000.0


@dataclass(frozen=True)
class PDFPoint:
    coordinate_text: str
    density_text: str
    coordinate: float
    density: float


@dataclass
class CompressionStats:
    input_points: int = 0
    output_points: int = 0


def read_pdf_points(lines: Iterable[str], source: str) -> Iterator[PDFPoint]:
    """Parse a nonnegative, strictly increasing two-column PDF."""
    previous_coordinate: float | None = None

    for line_number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        columns = line.split()
        if len(columns) != 2:
            raise ValueError(
                f"{source}:{line_number}: expected 2 columns, "
                f"found {len(columns)}"
            )
        try:
            coordinate = float(columns[0])
            density = float(columns[1])
        except ValueError as error:
            raise ValueError(
                f"{source}:{line_number}: both columns must be numbers"
            ) from error

        if not math.isfinite(coordinate):
            raise ValueError(
                f"{source}:{line_number}: coordinate must be finite"
            )
        if not math.isfinite(density) or density < 0.0:
            raise ValueError(
                f"{source}:{line_number}: density must be finite and nonnegative"
            )
        if previous_coordinate is not None and coordinate <= previous_coordinate:
            raise ValueError(
                f"{source}:{line_number}: coordinates must be strictly increasing"
            )

        previous_coordinate = coordinate
        yield PDFPoint(columns[0], columns[1], coordinate, density)


def _slope_constraint(
    anchor: PDFPoint, point: PDFPoint, relative_error: float
) -> tuple[float, float]:
    """Return slopes whose interpolated value satisfies one intermediate point."""
    delta_x = point.coordinate - anchor.coordinate
    if point.density == 0.0:
        exact_slope = -anchor.density / delta_x
        return exact_slope, exact_slope

    minimum_value = point.density * (1.0 - relative_error)
    maximum_value = point.density * (1.0 + relative_error)
    return (
        (minimum_value - anchor.density) / delta_x,
        (maximum_value - anchor.density) / delta_x,
    )


def compress_points(
    points: Iterable[PDFPoint],
    relative_error: float = DEFAULT_RELATIVE_ERROR,
    stats: CompressionStats | None = None,
) -> Iterator[PDFPoint]:
    """Yield the greedy furthest-valid linear approximation anchors."""
    if not math.isfinite(relative_error) or not 0.0 < relative_error < 1.0:
        raise ValueError("relative error must be greater than zero and less than one")

    if stats is None:
        stats = CompressionStats()

    source = iter(points)
    pending: Deque[PDFPoint] = deque()

    def next_point() -> PDFPoint | None:
        if pending:
            return pending.popleft()
        try:
            point = next(source)
        except StopIteration:
            return None
        stats.input_points += 1
        return point

    anchor = next_point()
    if anchor is None:
        raise ValueError("PDF must contain at least two data rows")

    second = next_point()
    if second is None:
        raise ValueError("PDF must contain at least two data rows")
    pending.append(second)

    stats.output_points += 1
    yield anchor

    while True:
        minimum_slope = -math.inf
        maximum_slope = math.inf
        last_valid: PDFPoint | None = None
        invalid_suffix: list[PDFPoint] = []

        while True:
            candidate = next_point()
            if candidate is None:
                if last_valid is None:
                    return

                stats.output_points += 1
                yield last_valid
                anchor = last_valid
                if not invalid_suffix:
                    return
                pending.extendleft(reversed(invalid_suffix))
                break

            candidate_slope = (candidate.density - anchor.density) / (
                candidate.coordinate - anchor.coordinate
            )
            if minimum_slope <= candidate_slope <= maximum_slope:
                last_valid = candidate
                invalid_suffix.clear()
            else:
                invalid_suffix.append(candidate)

            constraint_minimum, constraint_maximum = _slope_constraint(
                anchor, candidate, relative_error
            )
            minimum_slope = max(minimum_slope, constraint_minimum)
            maximum_slope = min(maximum_slope, constraint_maximum)

            if minimum_slope > maximum_slope:
                # Once the allowable slope intersection is empty, no later
                # endpoint can recover every point scanned from this anchor.
                if last_valid is None:  # The adjacent point is always valid.
                    raise AssertionError("compression failed to make progress")
                stats.output_points += 1
                yield last_valid
                anchor = last_valid
                pending.extendleft(reversed(invalid_suffix))
                break


def write_compressed_pdf(
    points: Iterable[PDFPoint],
    output: TextIO,
    relative_error: float = DEFAULT_RELATIVE_ERROR,
    stats: CompressionStats | None = None,
) -> CompressionStats:
    if stats is None:
        stats = CompressionStats()
    for point in compress_points(points, relative_error, stats):
        print(f"{point.coordinate_text}\t{point.density_text}", file=output)
    return stats


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Drop PDF points recoverable by linear interpolation within a "
            "relative-error bound. Zero densities must be recovered exactly."
        )
    )
    parser.add_argument(
        "input",
        metavar="PDF",
        type=Path,
        nargs="?",
        help="two-column PDF path (default: standard input)",
    )
    parser.add_argument(
        "--relative-error",
        type=float,
        default=DEFAULT_RELATIVE_ERROR,
        help="maximum relative error (default: 1e-6)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    source_name = str(args.input) if args.input is not None else "<stdin>"
    stats = CompressionStats()

    try:
        if args.input is None:
            points = read_pdf_points(sys.stdin, source_name)
            write_compressed_pdf(points, sys.stdout, args.relative_error, stats)
        else:
            with args.input.open(encoding="utf-8") as input_file:
                points = read_pdf_points(input_file, source_name)
                write_compressed_pdf(
                    points, sys.stdout, args.relative_error, stats
                )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    ratio = stats.input_points / stats.output_points
    print(
        f"Compressed {stats.input_points} points to {stats.output_points} "
        f"({ratio:.2f}:1; {stats.output_points / stats.input_points:.3%} retained)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
