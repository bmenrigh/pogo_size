#!/usr/bin/env python3
"""Build a normalized CDF from raw buckets or linear PDF control points."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, TextIO


@dataclass(frozen=True)
class PDFSample:
    coordinate_text: str
    coordinate: float
    density: float


def read_pdf(lines: Iterable[str]) -> list[PDFSample]:
    """Parse and validate two-column ``coordinate density`` input."""
    samples: list[PDFSample] = []

    for line_number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        columns = line.split()
        if len(columns) != 2:
            raise ValueError(
                f"line {line_number}: expected 2 columns, found {len(columns)}"
            )
        try:
            coordinate = float(columns[0])
            density = float(columns[1])
        except ValueError as error:
            raise ValueError(
                f"line {line_number}: both columns must be numbers"
            ) from error

        if not math.isfinite(coordinate):
            raise ValueError(f"line {line_number}: coordinate must be finite")
        if not math.isfinite(density) or density < 0:
            raise ValueError(
                f"line {line_number}: density must be finite and nonnegative"
            )
        if samples and coordinate <= samples[-1].coordinate:
            raise ValueError(
                f"line {line_number}: coordinates must be strictly increasing"
            )

        samples.append(PDFSample(columns[0], coordinate, density))

    if len(samples) < 2:
        raise ValueError("PDF must contain at least two data rows")
    return samples


def write_normalized_cdf(
    samples: Sequence[PDFSample],
    output: TextIO,
    *,
    linear_control_points: bool = False,
) -> None:
    """Write a normalized CDF using rectangles or linear-PDF trapezoids."""
    if linear_control_points:
        areas = [
            (sample.density + next_sample.density)
            * (next_sample.coordinate - sample.coordinate)
            / 2.0
            for sample, next_sample in zip(samples, samples[1:])
        ]
    else:
        areas = [
            sample.density * (next_sample.coordinate - sample.coordinate)
            for sample, next_sample in zip(samples, samples[1:])
        ]
    total_area = math.fsum(areas)
    if total_area <= 0.0:
        raise ValueError("PDF area must be greater than zero")

    if linear_control_points:
        print("# linear-pdf-cdf-v1", file=output)
        print("# coordinate normalized_pdf cdf", file=output)
    else:
        print("# cdf-survival-v1", file=output)
        print("# coordinate cdf survival", file=output)

    # Reverse compensated summation keeps tiny upper tails accurate without
    # subtracting a near-one CDF from one.
    suffix_areas = [0.0] * len(areas)
    suffix_sum = 0.0
    suffix_compensation = 0.0
    for index in range(len(areas) - 1, -1, -1):
        corrected = areas[index] - suffix_compensation
        updated = suffix_sum + corrected
        suffix_compensation = (updated - suffix_sum) - corrected
        suffix_sum = updated
        suffix_areas[index] = suffix_sum

    cumulative_area = 0.0
    cumulative_compensation = 0.0
    for index, (sample, area) in enumerate(zip(samples[:-1], areas)):
        cumulative = cumulative_area / total_area
        if linear_control_points:
            density = sample.density / total_area
            print(
                f"{sample.coordinate_text}\t{density:.17e}\t"
                f"{cumulative:.17e}",
                file=output,
            )
        else:
            survival = suffix_areas[index] / total_area
            print(
                f"{sample.coordinate_text}\t{cumulative:.17e}\t"
                f"{survival:.17e}",
                file=output,
            )

        corrected = area - cumulative_compensation
        updated = cumulative_area + corrected
        cumulative_compensation = (updated - cumulative_area) - corrected
        cumulative_area = updated

    if linear_control_points:
        final_density = samples[-1].density / total_area
        print(
            f"{samples[-1].coordinate_text}\t{final_density:.17e}\t"
            "1.00000000000000000e+00",
            file=output,
        )
    else:
        print(
            f"{samples[-1].coordinate_text}\t"
            "1.00000000000000000e+00\t0.00000000000000000e+00",
            file=output,
        )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a two-column PDF to normalized CDF and survival values. "
            "Raw convolution input uses left-aligned rectangles by default; "
            "compressed control points can be integrated linearly with an option."
        )
    )
    parser.add_argument(
        "input",
        metavar="PDF",
        type=Path,
        nargs="?",
        help="input PDF path (default: standard input)",
    )
    parser.add_argument(
        "--linear-control-points",
        action="store_true",
        help=(
            "integrate a piecewise-linear PDF with trapezoids and output "
            "three columns: coordinate, normalized PDF, CDF (instead of the "
            "default coordinate, CDF, survival format)"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)

    try:
        if args.input is None:
            samples = read_pdf(sys.stdin)
        else:
            with args.input.open(encoding="utf-8") as input_file:
                samples = read_pdf(input_file)
        write_normalized_cdf(
            samples,
            sys.stdout,
            linear_control_points=args.linear_control_points,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
