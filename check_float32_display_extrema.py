#!/usr/bin/env python3
"""Find two-decimal extrema changed by IEEE-754 float32 transmission."""

from __future__ import annotations

import argparse
import csv
import math
import struct
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, Sequence, TextIO


DISPLAY_QUANTUM = Decimal("0.01")
MAXIMUM_WEIGHT_MULTIPLIER = Decimal("2.75")
REQUIRED_COLUMNS = (
    "pokedex_number",
    "name",
    "mean_height_m",
    "mean_weight_kg",
    "xxs_class",
    "xxl_class",
)

CATEGORY_ORDER = (
    ("minimum_height", "lower"),
    ("minimum_height", "higher"),
    ("maximum_height", "lower"),
    ("maximum_height", "higher"),
    ("maximum_weight", "lower"),
    ("maximum_weight", "higher"),
)

CATEGORY_TITLES = {
    ("minimum_height", "lower"): (
        "Minimum height reaches a LOWER displayed value after float32 conversion"
    ),
    ("minimum_height", "higher"): (
        "Minimum height fails to reach its nominal minimum display "
        "(float32 displays HIGHER)"
    ),
    ("maximum_height", "lower"): (
        "Maximum height fails to reach its nominal maximum display "
        "(float32 displays LOWER)"
    ),
    ("maximum_height", "higher"): (
        "Maximum height reaches a HIGHER displayed value after float32 conversion"
    ),
    ("maximum_weight", "lower"): (
        "Maximum weight fails to reach its nominal maximum display "
        "(float32 displays LOWER)"
    ),
    ("maximum_weight", "higher"): (
        "Maximum weight reaches a HIGHER displayed value after float32 conversion"
    ),
}


@dataclass(frozen=True)
class PokemonStats:
    pokedex_number: int
    name: str
    mean_height: Decimal
    mean_weight: Decimal
    xxs_class: Decimal
    xxl_class: Decimal


@dataclass(frozen=True)
class DisplayAnomaly:
    pokedex_number: int
    name: str
    extremum: str
    direction: str
    nominal_value: Decimal
    float32_value: Decimal
    nominal_display: Decimal
    float32_display: Decimal


def read_stats(path: Path) -> list[PokemonStats]:
    rows: list[PokemonStats] = []
    with path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file, delimiter="\t")
        if reader.fieldnames != list(REQUIRED_COLUMNS):
            raise ValueError(
                f"{path}: expected columns " + ", ".join(REQUIRED_COLUMNS)
            )
        for line_number, record in enumerate(reader, start=2):
            try:
                row = PokemonStats(
                    pokedex_number=int(record["pokedex_number"]),
                    name=record["name"],
                    mean_height=Decimal(record["mean_height_m"]),
                    mean_weight=Decimal(record["mean_weight_kg"]),
                    xxs_class=Decimal(record["xxs_class"]),
                    xxl_class=Decimal(record["xxl_class"]),
                )
            except (InvalidOperation, TypeError, ValueError) as error:
                raise ValueError(f"{path}:{line_number}: invalid stats row") from error
            if (
                row.pokedex_number <= 0
                or not row.name
                or any(
                    not value.is_finite() or value <= 0
                    for value in (
                        row.mean_height,
                        row.mean_weight,
                        row.xxs_class,
                        row.xxl_class,
                    )
                )
            ):
                raise ValueError(f"{path}:{line_number}: invalid stats row")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no Pokémon stats rows")
    return rows


def to_float32_decimal(value: Decimal) -> Decimal:
    """Round a decimal through float32 and return its exact decimal value."""
    try:
        float32 = struct.unpack(">f", struct.pack(">f", float(value)))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError(f"{value} cannot be represented as float32") from error
    if not math.isfinite(float32):
        raise ValueError(f"{value} cannot be represented as finite float32")
    return Decimal.from_float(float32)


def displayed_value(value: Decimal) -> Decimal:
    """Round a positive value to the game's two-decimal display."""
    return value.quantize(DISPLAY_QUANTUM, rounding=ROUND_HALF_UP)


def find_anomalies(rows: Iterable[PokemonStats]) -> list[DisplayAnomaly]:
    anomalies: list[DisplayAnomaly] = []
    for row in rows:
        extrema = {
            "minimum_height": row.mean_height * row.xxs_class,
            "maximum_height": row.mean_height * row.xxl_class,
            # XL has the largest possible normalized weight: 1.5² + 1.5 - 1.
            "maximum_weight": row.mean_weight * MAXIMUM_WEIGHT_MULTIPLIER,
        }
        for extremum, nominal_value in extrema.items():
            float32_value = to_float32_decimal(nominal_value)
            nominal_display = displayed_value(nominal_value)
            float32_display = displayed_value(float32_value)
            if nominal_display == float32_display:
                continue
            anomalies.append(
                DisplayAnomaly(
                    pokedex_number=row.pokedex_number,
                    name=row.name,
                    extremum=extremum,
                    direction=(
                        "lower" if float32_display < nominal_display else "higher"
                    ),
                    nominal_value=nominal_value,
                    float32_value=float32_value,
                    nominal_display=nominal_display,
                    float32_display=float32_display,
                )
            )
    anomalies.sort(
        key=lambda item: (
            CATEGORY_ORDER.index((item.extremum, item.direction)),
            item.pokedex_number,
            item.name,
        )
    )
    return anomalies


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def display_text(value: Decimal) -> str:
    """Format a rounded game measurement without unnecessary trailing zeros."""
    return format(value.normalize(), "f")


def write_report(
    rows: Sequence[PokemonStats],
    anomalies: Sequence[DisplayAnomaly],
    output: TextIO,
) -> None:
    print("Float32 display-boundary anomalies", file=output)
    print("==================================", file=output)
    print(
        "Nominal extrema use exact decimal arithmetic; float32 extrema show "
        "the exact value after IEEE-754 float32 conversion.",
        file=output,
    )
    print(
        "Display rounding is positive round-half-up to the nearest hundredth; "
        "unnecessary trailing zeros are omitted.",
        file=output,
    )
    print(
        "Formulas: min height = mean×XXS; max height = mean×XXL; "
        "max weight = mean×2.75 (the top of XL).",
        file=output,
    )

    grouped: dict[tuple[str, str], list[DisplayAnomaly]] = {
        category: [] for category in CATEGORY_ORDER
    }
    for anomaly in anomalies:
        grouped[(anomaly.extremum, anomaly.direction)].append(anomaly)

    for category in CATEGORY_ORDER:
        items = grouped[category]
        print(file=output)
        print(f"{CATEGORY_TITLES[category]} ({len(items)})", file=output)
        print("-" * (len(CATEGORY_TITLES[category]) + len(str(len(items))) + 3), file=output)
        if not items:
            print("(none)", file=output)
            continue
        print(
            "pokedex\tname\tnominal_exact\tfloat32_exact\t"
            "nominal_display\tfloat32_display",
            file=output,
        )
        for item in items:
            print(
                f"{item.pokedex_number}\t{item.name}\t"
                f"{_decimal_text(item.nominal_value)}\t"
                f"{_decimal_text(item.float32_value)}\t"
                f"{display_text(item.nominal_display)}\t"
                f"{display_text(item.float32_display)}",
                file=output,
            )

    print(file=output)
    print(
        f"Checked {len(rows)} Pokémon rows; found {len(anomalies)} changed "
        "two-decimal extrema.",
        file=output,
    )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Report minimum-height, maximum-height, and maximum-weight display "
            "boundaries changed by conversion to IEEE-754 float32."
        )
    )
    parser.add_argument(
        "stats",
        metavar="pokemon_stats.tsv",
        type=Path,
        nargs="?",
        default=Path("pokemon_stats.tsv"),
        help="Pokémon stats TSV (default: pokemon_stats.tsv)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        rows = read_stats(args.stats)
        anomalies = find_anomalies(rows)
        write_report(rows, anomalies, sys.stdout)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
