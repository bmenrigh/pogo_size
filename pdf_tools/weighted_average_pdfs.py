#!/usr/bin/env python3
"""Combine left-edge-aligned PDFs using exact rational weights."""

from __future__ import annotations

import argparse
import hashlib
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from itertools import zip_longest
from pathlib import Path
from typing import Iterable, Iterator, Sequence, TextIO


@dataclass(frozen=True)
class PDFRow:
    coordinate_text: str
    coordinate: Decimal
    density: Decimal


@dataclass(frozen=True)
class PDFMeasurement:
    area: Decimal
    rows: int
    coordinate_digest: str


@dataclass(frozen=True)
class WeightedPDF:
    weight_text: str
    weight: Fraction
    path: Path
    measurement: PDFMeasurement
    scale: Decimal


def parse_weight(text: str) -> Fraction:
    """Parse a positive weight written strictly as ``n/m``."""
    parts = text.split("/")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid weight {text!r}; weights must use n/m form")
    numerator, denominator = map(int, parts)
    if denominator == 0:
        raise ValueError(f"invalid weight {text!r}; denominator must not be zero")
    if numerator == 0:
        raise ValueError(f"invalid weight {text!r}; weight must be greater than zero")
    return Fraction(numerator, denominator)


def read_pdf_rows(lines: Iterable[str], source: str) -> Iterator[PDFRow]:
    """Parse validated two-column ``coordinate density`` rows."""
    previous_coordinate: Decimal | None = None

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
            coordinate = Decimal(columns[0])
            density = Decimal(columns[1])
        except InvalidOperation as error:
            raise ValueError(
                f"{source}:{line_number}: both columns must be numbers"
            ) from error

        if not coordinate.is_finite():
            raise ValueError(
                f"{source}:{line_number}: coordinate must be finite"
            )
        if not density.is_finite() or density < 0:
            raise ValueError(
                f"{source}:{line_number}: density must be finite and nonnegative"
            )
        if previous_coordinate is not None and coordinate <= previous_coordinate:
            raise ValueError(
                f"{source}:{line_number}: coordinates must be strictly increasing"
            )

        previous_coordinate = coordinate
        yield PDFRow(columns[0], coordinate, density)


def measure_pdf(path: Path) -> PDFMeasurement:
    """Measure left-aligned rectangle area and fingerprint the coordinate grid."""
    with localcontext() as context:
        context.prec = 50
        area = Decimal(0)
        rows = 0
        coordinate_hash = hashlib.sha256()
        previous: PDFRow | None = None

        with path.open(encoding="utf-8") as input_file:
            for row in read_pdf_rows(input_file, str(path)):
                if previous is not None:
                    area += previous.density * (
                        row.coordinate - previous.coordinate
                    )
                canonical_coordinate = str(row.coordinate.normalize()).encode(
                    "ascii"
                )
                coordinate_hash.update(canonical_coordinate)
                coordinate_hash.update(b"\n")
                previous = row
                rows += 1

    if rows < 2:
        raise ValueError(f"{path}: PDF must contain at least two data rows")
    if area <= 0:
        raise ValueError(f"{path}: PDF area must be greater than zero")
    return PDFMeasurement(area, rows, coordinate_hash.hexdigest())


def prepare_inputs(arguments: Sequence[str]) -> list[WeightedPDF]:
    """Parse pairs, check their exact sum, then measure and scale every PDF."""
    if not arguments or len(arguments) % 2:
        raise ValueError("provide one or more WEIGHT PDF pairs")

    pairs: list[tuple[str, Fraction, Path]] = []
    for index in range(0, len(arguments), 2):
        weight_text = arguments[index]
        pairs.append(
            (weight_text, parse_weight(weight_text), Path(arguments[index + 1]))
        )

    total_weight = sum((weight for _, weight, _ in pairs), Fraction(0))
    if total_weight != 1:
        raise ValueError(
            f"weights sum to {total_weight} ({float(total_weight):.15g}), not 1"
        )

    weighted_pdfs: list[WeightedPDF] = []
    reference_measurement: PDFMeasurement | None = None
    with localcontext() as context:
        context.prec = 50
        for weight_text, weight, path in pairs:
            measurement = measure_pdf(path)
            if reference_measurement is None:
                reference_measurement = measurement
            elif (
                measurement.rows != reference_measurement.rows
                or measurement.coordinate_digest
                != reference_measurement.coordinate_digest
            ):
                raise ValueError(f"{path}: coordinate grid does not match first PDF")

            decimal_weight = Decimal(weight.numerator) / Decimal(weight.denominator)
            scale = decimal_weight / measurement.area
            weighted_pdfs.append(
                WeightedPDF(weight_text, weight, path, measurement, scale)
            )

    return weighted_pdfs


def print_summary(weighted_pdfs: Sequence[WeightedPDF], output: TextIO) -> None:
    print("Weighted PDF inputs:", file=output)
    for item in weighted_pdfs:
        print(
            f"  {item.weight_text:>9} "
            f"({float(item.weight):.9%})  {item.path}",
            file=output,
        )
        print(
            f"             raw area={item.measurement.area:.15g}  "
            f"density scale={item.scale:.15g}",
            file=output,
        )
    total = sum((item.weight for item in weighted_pdfs), Fraction(0))
    print(f"Total weight: {total} ({float(total):.9%})", file=output)
    print(f"Rows: {weighted_pdfs[0].measurement.rows}", file=output)


def write_weighted_average(
    weighted_pdfs: Sequence[WeightedPDF], output: TextIO
) -> Decimal:
    """Write the weighted PDF and return its unrounded left-rectangle area."""
    combined_area = Decimal(0)
    previous_coordinate: Decimal | None = None
    previous_density: Decimal | None = None
    missing = object()

    with localcontext() as context, ExitStack() as stack:
        context.prec = 50
        row_iterators = [
            read_pdf_rows(
                stack.enter_context(item.path.open(encoding="utf-8")), str(item.path)
            )
            for item in weighted_pdfs
        ]

        for rows in zip_longest(*row_iterators, fillvalue=missing):
            if any(row is missing for row in rows):
                raise ValueError("input PDFs have different numbers of rows")

            typed_rows = rows  # All entries are PDFRow after the check above.
            coordinate = typed_rows[0].coordinate
            if any(row.coordinate != coordinate for row in typed_rows[1:]):
                raise ValueError("input PDF coordinate grids do not match")

            density = sum(
                (
                    row.density * item.scale
                    for row, item in zip(typed_rows, weighted_pdfs)
                ),
                Decimal(0),
            )
            if previous_coordinate is not None and previous_density is not None:
                combined_area += previous_density * (
                    coordinate - previous_coordinate
                )

            print(
                f"{typed_rows[0].coordinate_text}\t{density:.15f}", file=output
            )
            previous_coordinate = coordinate
            previous_density = density

    return combined_area


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize and combine left-edge-aligned PDFs. Weights must sum "
            "exactly to one; the summary is written to stderr."
        ),
        usage="%(prog)s WEIGHT PDF [WEIGHT PDF ...]",
    )
    parser.add_argument(
        "pairs",
        metavar="WEIGHT_OR_PDF",
        nargs="+",
        help="alternating n/m weight and PDF path",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        weighted_pdfs = prepare_inputs(args.pairs)
        print_summary(weighted_pdfs, sys.stderr)
        combined_area = write_weighted_average(weighted_pdfs, sys.stdout)
        print(f"Combined unrounded area: {combined_area:.15g}", file=sys.stderr)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
