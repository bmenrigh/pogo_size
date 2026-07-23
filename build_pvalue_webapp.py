#!/usr/bin/env python3
"""Build the standalone Pokémon size p-value web application."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import math
import struct
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from check_float32_display_extrema import (
    find_anomalies,
    read_stats as read_extrema_stats,
)


CDF_FILES = {
    "full155": "full_155.txt",
    "full175": "full_175.txt",
    "full200": "full_200.txt",
    "fullScatterbug": "full_scatterbug.txt",
    "xxs": "single_xxs.txt",
    "xxsScatterbug": "single_xxs_scatterbug.txt",
    "xs": "single_xs.txt",
    "average": "single_avg.txt",
    "xl": "single_xl.txt",
    "xxl155": "single_xxl_155.txt",
    "xxl175": "single_xxl_175.txt",
    "xxl200": "single_xxl_200.txt",
}

STATS_COLUMNS = (
    "pokedex_number",
    "name",
    "mean_height_m",
    "mean_weight_kg",
    "xxs_class",
    "xxl_class",
)


@dataclass(frozen=True)
class PokemonRow:
    pokedex_number: int
    name: str
    height: float
    weight: float
    xxs: float
    xxl: float


def read_stats(path: Path) -> list[PokemonRow]:
    with path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file, delimiter="\t")
        if reader.fieldnames != list(STATS_COLUMNS):
            raise ValueError(
                f"{path}: expected columns " + ", ".join(STATS_COLUMNS)
            )
        rows: list[PokemonRow] = []
        for line_number, record in enumerate(reader, start=2):
            try:
                row = PokemonRow(
                    int(record["pokedex_number"]),
                    record["name"],
                    float(record["mean_height_m"]),
                    float(record["mean_weight_kg"]),
                    float(record["xxs_class"]),
                    float(record["xxl_class"]),
                )
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}:{line_number}: invalid value") from error
            if (
                row.pokedex_number <= 0
                or not row.name
                or not all(
                    math.isfinite(value) and value > 0
                    for value in (row.height, row.weight, row.xxs, row.xxl)
                )
                or row.xxs not in (0.25, 0.49)
                or row.xxl not in (1.55, 1.75, 2.0)
            ):
                raise ValueError(f"{path}:{line_number}: invalid Pokémon stats")
            if row.xxs == 0.25 and row.xxl != 1.75:
                raise ValueError(
                    f"{path}:{line_number}: the Scatterbug XXS class requires "
                    "the 1.75 XXL class"
                )
            if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in row.name):
                raise ValueError(
                    f"{path}:{line_number}: unexpected character in Pokémon name"
                )
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no Pokémon rows")
    return rows


def pack_cdf(path: Path) -> tuple[str, int]:
    """Pack each v3 segment as one kind byte and eight little-endian doubles."""
    packed = bytearray()
    previous_end: float | None = None
    count = 0
    version_found = False
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                if stripped.startswith("# cdf-poly-v3"):
                    version_found = True
                continue
            columns = stripped.split()
            if len(columns) != 9 or columns[0] not in ("C", "S"):
                raise ValueError(f"{path}:{line_number}: invalid v3 segment")
            try:
                numbers = tuple(float(value) for value in columns[1:])
            except ValueError as error:
                raise ValueError(
                    f"{path}:{line_number}: segment values must be numbers"
                ) from error
            start, end = numbers[:2]
            if (
                not all(math.isfinite(value) for value in numbers)
                or end <= start
                or (previous_end is not None and start != previous_end)
            ):
                raise ValueError(f"{path}:{line_number}: invalid segment range")
            packed.extend(
                struct.pack("<B8d", 0 if columns[0] == "C" else 1, *numbers)
            )
            previous_end = end
            count += 1
    if not version_found:
        raise ValueError(f"{path}: expected cdf-poly-v3 input")
    if not count:
        raise ValueError(f"{path}: no polynomial segments")
    return base64.b64encode(packed).decode("ascii"), count


def compact_stats(rows: list[PokemonRow]) -> tuple[str, str]:
    """Return compact name and columnar numeric JavaScript data."""
    heights = sorted({row.height for row in rows})
    weights = sorted({row.weight for row in rows})
    height_indexes = {value: index for index, value in enumerate(heights)}
    weight_indexes = {value: index for index, value in enumerate(weights)}
    names = "\n".join(row.name for row in rows)
    columns = [
        heights,
        weights,
        [row.pokedex_number for row in rows],
        [height_indexes[row.height] for row in rows],
        [weight_indexes[row.weight] for row in rows],
        "".join("1" if row.xxs == 0.25 else "0" for row in rows),
        "".join({1.55: "0", 1.75: "1", 2.0: "2"}[row.xxl] for row in rows),
    ]
    return (
        json.dumps(names, ensure_ascii=True, separators=(",", ":")),
        json.dumps(columns, ensure_ascii=True, separators=(",", ":")),
    )


def compact_display_extrema(stats_path: Path, rows: list[PokemonRow]) -> str:
    """Encode display anomalies by compact Pokémon-row and extremum indexes."""
    row_indexes = {
        (row.pokedex_number, row.name): index for index, row in enumerate(rows)
    }
    extremum_codes = {
        "minimum_height": 0,
        "maximum_height": 1,
        "maximum_weight": 2,
    }
    encoded = []
    for anomaly in find_anomalies(read_extrema_stats(stats_path)):
        encoded.append(
            [
                row_indexes[(anomaly.pokedex_number, anomaly.name)],
                extremum_codes[anomaly.extremum],
                format(anomaly.nominal_value, "f"),
                format(anomaly.float32_value, "f"),
                f"{anomaly.nominal_display:.2f}",
                f"{anomaly.float32_display:.2f}",
            ]
        )
    return json.dumps(encoded, ensure_ascii=True, separators=(",", ":"))


def build_html(
    stats_path: Path,
    cdf_directory: Path,
    template_path: Path,
    build_date: date | None = None,
) -> tuple[str, int, int]:
    if build_date is None:
        build_date = date.today()
    rows = read_stats(stats_path)
    names_json, columns_json = compact_stats(rows)
    display_extrema_json = compact_display_extrema(stats_path, rows)
    packed_tables: dict[str, str] = {}
    segment_count = 0
    for key, filename in CDF_FILES.items():
        encoded, count = pack_cdf(cdf_directory / filename)
        packed_tables[key] = encoded
        segment_count += count

    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "@@POKEMON_NAMES@@": names_json,
        "@@POKEMON_COLUMNS@@": columns_json,
        "@@DISPLAY_EXTREMA@@": display_extrema_json,
        "@@CDF_TABLES@@": json.dumps(packed_tables, separators=(",", ":")),
        "@@CDF_SEGMENT_COUNT@@": str(segment_count),
        "@@CDF_DISTRIBUTION_COUNT@@": str(len(packed_tables)),
        "@@BUILD_DATE_ISO@@": build_date.isoformat(),
        "@@BUILD_DATE_LONG@@": (
            f"{build_date:%B} {build_date.day}, {build_date.year}"
        ),
    }
    for marker, replacement in replacements.items():
        if template.count(marker) != 1:
            raise ValueError(f"{template_path}: expected exactly one {marker} marker")
        template = template.replace(marker, replacement)
    build_year_marker = "@@BUILD_YEAR@@"
    if template.count(build_year_marker) != 2:
        raise ValueError(
            f"{template_path}: expected exactly two {build_year_marker} markers"
        )
    template = template.replace(build_year_marker, str(build_date.year))
    return template, len(rows), segment_count


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a self-contained HTML Pokémon size p-value calculator."
    )
    parser.add_argument(
        "--stats", type=Path, default=Path("pokemon_stats.tsv"), help="stats TSV"
    )
    parser.add_argument(
        "--cdfs", type=Path, default=Path("cdfs_poly"), help="CDF directory"
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("pvalue_webapp_template.html"),
        help="HTML template",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pvalue_lookup.html"),
        help="generated standalone HTML",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        html, pokemon_count, segment_count = build_html(
            args.stats, args.cdfs, args.template
        )
        args.output.write_text(html, encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(
        f"Embedded {pokemon_count} Pokémon and {segment_count} polynomial "
        f"segments in {args.output} ({len(html):,} bytes).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
