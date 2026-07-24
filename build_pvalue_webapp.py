#!/usr/bin/env python3
"""Build the standalone Pokémon size p-value web application."""

from __future__ import annotations

import argparse
import base64
import csv
import html as html_lib
import json
import math
import re
import struct
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from check_float32_display_extrema import (
    display_text,
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
EVOLUTION_COLUMNS = ("source_name", "target_name")
EQUATION_PATTERN = re.compile(
    r'<div class="equation" data-tex="([^"]+)">(.*?)</div>',
    re.DOTALL,
)

TEX_SYMBOLS = {
    "alpha": ("mi", "α"),
    "beta": ("mi", "β"),
    "mu": ("mi", "μ"),
    "Phi": ("mi", "Φ"),
    "infty": ("mo", "∞"),
    "int": ("mo", "∫"),
    "le": ("mo", "≤"),
    "ge": ("mo", "≥"),
    "times": ("mo", "×"),
    "cdot": ("mo", "⋅"),
    "mid": ("mo", "|"),
    "approx": ("mo", "≈"),
}


def _mathml_element(name: str, contents: str, **attributes: str) -> str:
    rendered_attributes = "".join(
        f' {key.replace("_", "-")}="{html_lib.escape(value, quote=True)}"'
        for key, value in attributes.items()
    )
    return f"<{name}{rendered_attributes}>{contents}</{name}>"


class _TexMathMLParser:
    """Convert the deliberately small TeX subset used by the webapp."""

    def __init__(self, source: str):
        self.source = source
        self.position = 0

    def parse(self) -> str:
        result = self._parse_expression()
        self._skip_whitespace()
        if self.position != len(self.source):
            raise ValueError(
                f"unexpected TeX at column {self.position + 1}: "
                f"{self.source[self.position:]!r}"
            )
        return _mathml_element("mrow", result)

    def _skip_whitespace(self) -> None:
        while (
            self.position < len(self.source)
            and self.source[self.position].isspace()
        ):
            self.position += 1

    def _parse_expression(self, terminator: str | None = None) -> str:
        elements: list[str] = []
        while self.position < len(self.source):
            self._skip_whitespace()
            if self.position >= len(self.source):
                break
            if terminator and self.source[self.position] == terminator:
                self.position += 1
                return "".join(elements)
            atom = self._parse_atom()
            self._skip_whitespace()
            subscript = superscript = None
            while (
                self.position < len(self.source)
                and self.source[self.position] in "_^"
            ):
                marker = self.source[self.position]
                self.position += 1
                script = self._parse_script()
                if marker == "_":
                    if subscript is not None:
                        raise ValueError("an atom cannot have two TeX subscripts")
                    subscript = script
                else:
                    if superscript is not None:
                        raise ValueError("an atom cannot have two TeX superscripts")
                    superscript = script
                self._skip_whitespace()
            mean_attributes = (
                {"class": "mean-symbol"}
                if 'class="math-mu"' in atom
                else {}
            )
            if subscript is not None and superscript is not None:
                atom = _mathml_element(
                    "msubsup",
                    atom + subscript + superscript,
                    **mean_attributes,
                )
            elif subscript is not None:
                atom = _mathml_element(
                    "msub", atom + subscript, **mean_attributes
                )
            elif superscript is not None:
                atom = _mathml_element("msup", atom + superscript)
            elements.append(atom)
        if terminator:
            raise ValueError(f"unterminated TeX group; expected {terminator!r}")
        return "".join(elements)

    def _parse_script(self) -> str:
        self._skip_whitespace()
        if self.position >= len(self.source):
            raise ValueError("missing TeX script")
        if self.source[self.position] == "{":
            self.position += 1
            return _mathml_element("mrow", self._parse_expression("}"))
        return self._parse_atom()

    def _parse_required_group_source(self) -> str:
        self._skip_whitespace()
        if self.position >= len(self.source) or self.source[self.position] != "{":
            raise ValueError("TeX command requires a braced argument")
        self.position += 1
        start = self.position
        depth = 1
        while self.position < len(self.source):
            character = self.source[self.position]
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    result = self.source[start:self.position]
                    self.position += 1
                    return result
            self.position += 1
        raise ValueError("unterminated TeX command argument")

    def _parse_required_group(self) -> str:
        source = self._parse_required_group_source()
        return _TexMathMLParser(source).parse()

    def _parse_command(self) -> str:
        self.position += 1
        start = self.position
        while (
            self.position < len(self.source)
            and self.source[self.position].isalpha()
        ):
            self.position += 1
        command = self.source[start:self.position]
        if not command:
            if self.position >= len(self.source):
                raise ValueError("trailing TeX backslash")
            escaped = self.source[self.position]
            self.position += 1
            if escaped == "%":
                return _mathml_element("mo", "%")
            if escaped in ",;:":
                widths = {",": ".17em", ":": ".22em", ";": ".28em"}
                return '<mspace width="' + widths[escaped] + '"></mspace>'
            raise ValueError(f"unsupported TeX escape \\{escaped}")
        if command == "mu":
            return '<mi class="math-mu">μ</mi>'
        if command in TEX_SYMBOLS:
            element, character = TEX_SYMBOLS[command]
            return _mathml_element(element, character)
        if command == "frac":
            numerator = self._parse_required_group()
            denominator = self._parse_required_group()
            return _mathml_element("mfrac", numerator + denominator)
        if command == "sqrt":
            return _mathml_element("msqrt", self._parse_required_group())
        if command in ("text", "operatorname"):
            contents = html_lib.escape(self._parse_required_group_source())
            element = "mtext" if command == "text" else "mi"
            attributes = {} if command == "text" else {"mathvariant": "normal"}
            return _mathml_element(element, contents, **attributes)
        if command == "mathrm":
            return _mathml_element(
                "mi",
                html_lib.escape(self._parse_required_group_source()),
                mathvariant="normal",
            )
        if command == "quad":
            return '<mspace width="1em"></mspace>'
        if command == "left":
            self._skip_whitespace()
            if self.position >= len(self.source):
                raise ValueError(r"\left requires a delimiter")
            opening = self.source[self.position]
            self.position += 1
            right = self.source.find(r"\right", self.position)
            if right == -1:
                raise ValueError(r"\left has no matching \right")
            contents = _TexMathMLParser(
                self.source[self.position:right]
            ).parse()
            self.position = right + len(r"\right")
            self._skip_whitespace()
            if self.position >= len(self.source):
                raise ValueError(r"\right requires a delimiter")
            closing = self.source[self.position]
            self.position += 1
            return _mathml_element(
                "mrow",
                _mathml_element(
                    "mo", html_lib.escape(opening), stretchy="true"
                )
                + contents
                + _mathml_element(
                    "mo", html_lib.escape(closing), stretchy="true"
                ),
            )
        if command == "right":
            raise ValueError(r"\right has no matching \left")
        if command == "displaystyle":
            return ""
        raise ValueError(f"unsupported TeX command \\{command}")

    def _parse_atom(self) -> str:
        character = self.source[self.position]
        if character == "{":
            self.position += 1
            return _mathml_element("mrow", self._parse_expression("}"))
        if character == "}":
            raise ValueError(f"unexpected TeX group terminator at {self.position + 1}")
        if character == "\\":
            return self._parse_command()
        if character.isdigit() or (
            character == "."
            and self.position + 1 < len(self.source)
            and self.source[self.position + 1].isdigit()
        ):
            start = self.position
            self.position += 1
            while (
                self.position < len(self.source)
                and (
                    self.source[self.position].isdigit()
                    or self.source[self.position] == "."
                )
            ):
                self.position += 1
            return _mathml_element("mn", self.source[start:self.position])
        self.position += 1
        if character.isalpha():
            return _mathml_element("mi", html_lib.escape(character))
        if character in "[]()":
            return _mathml_element("mo", character, stretchy="false")
        if character == ",":
            return _mathml_element("mo", ",", separator="true")
        if character in "=+-/;:|<>":
            return _mathml_element("mo", html_lib.escape(character))
        raise ValueError(
            f"unsupported TeX character {character!r} at {self.position}"
        )


def tex_to_mathml(tex: str) -> str:
    """Convert one or more TeX lines into native presentation MathML."""
    lines = tex.split(r"\\")
    parsed = [_TexMathMLParser(line.strip()).parse() for line in lines]
    if len(parsed) == 1:
        return parsed[0]
    rows = "".join(
        _mathml_element("mtr", _mathml_element("mtd", line))
        for line in parsed
    )
    return _mathml_element(
        "mtable", rows, columnalign="left", rowspacing=".45em"
    )


def render_mathml_equations(template: str, template_path: Path) -> str:
    """Compile template equations while retaining their authored fallback."""
    equation_count = template.count('<div class="equation"')
    matches = list(EQUATION_PATTERN.finditer(template))
    if equation_count != len(matches):
        raise ValueError(
            f"{template_path}: every equation must have one data-tex attribute"
        )

    def replace(match: re.Match[str]) -> str:
        tex = html_lib.unescape(match.group(1))
        fallback = match.group(2)
        try:
            expression = tex_to_mathml(tex)
        except ValueError as error:
            line = template.count("\n", 0, match.start()) + 1
            raise ValueError(f"{template_path}:{line}: {error}") from error
        annotation = _mathml_element(
            "annotation",
            html_lib.escape(tex),
            encoding="application/x-tex",
        )
        mathml = (
            '<math class="mathml" display="block" aria-hidden="true">'
            + _mathml_element("semantics", expression + annotation)
            + "</math>"
        )
        return (
            '<div class="equation">'
            + mathml
            + '<span class="math-fallback">'
            + fallback
            + "</span></div>"
        )

    return EQUATION_PATTERN.sub(replace, template)


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
                display_text(anomaly.nominal_display),
                display_text(anomaly.float32_display),
            ]
        )
    return json.dumps(encoded, ensure_ascii=True, separators=(",", ":"))


def compact_evolutions(path: Path, rows: list[PokemonRow]) -> tuple[str, int]:
    """Encode direct evolutions as compact source/target Pokémon-row indexes."""
    row_indexes = {row.name: index for index, row in enumerate(rows)}
    pairs: set[tuple[int, int]] = set()
    with path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file, delimiter="\t")
        if reader.fieldnames != list(EVOLUTION_COLUMNS):
            raise ValueError(
                f"{path}: expected columns " + ", ".join(EVOLUTION_COLUMNS)
            )
        for line_number, record in enumerate(reader, start=2):
            source_name = record["source_name"]
            target_name = record["target_name"]
            if source_name not in row_indexes:
                raise ValueError(
                    f"{path}:{line_number}: unknown source {source_name!r}"
                )
            if target_name not in row_indexes:
                raise ValueError(
                    f"{path}:{line_number}: unknown target {target_name!r}"
                )
            source_index = row_indexes[source_name]
            target_index = row_indexes[target_name]
            if source_index == target_index:
                raise ValueError(
                    f"{path}:{line_number}: evolution cannot target itself"
                )
            pairs.add((source_index, target_index))
    ordered = sorted(pairs)
    return (
        json.dumps(ordered, ensure_ascii=True, separators=(",", ":")),
        len(ordered),
    )


def build_html(
    stats_path: Path,
    cdf_directory: Path,
    template_path: Path,
    build_date: date | None = None,
    evolution_path: Path | None = None,
) -> tuple[str, int, int]:
    if build_date is None:
        build_date = date.today()
    if evolution_path is None:
        evolution_path = stats_path.with_name("pokemon_evolutions.tsv")
    rows = read_stats(stats_path)
    names_json, columns_json = compact_stats(rows)
    display_extrema_json = compact_display_extrema(stats_path, rows)
    evolutions_json, evolution_count = compact_evolutions(evolution_path, rows)
    packed_tables: dict[str, str] = {}
    segment_count = 0
    for key, filename in CDF_FILES.items():
        encoded, count = pack_cdf(cdf_directory / filename)
        packed_tables[key] = encoded
        segment_count += count

    template = render_mathml_equations(
        template_path.read_text(encoding="utf-8"), template_path
    )
    replacements = {
        "@@POKEMON_NAMES@@": names_json,
        "@@POKEMON_COLUMNS@@": columns_json,
        "@@DISPLAY_EXTREMA@@": display_extrema_json,
        "@@EVOLUTIONS@@": evolutions_json,
        "@@EVOLUTION_COUNT@@": str(evolution_count),
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
        "--evolutions",
        type=Path,
        default=Path("pokemon_evolutions.tsv"),
        help="direct-evolution TSV (default: pokemon_evolutions.tsv)",
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
            args.stats,
            args.cdfs,
            args.template,
            evolution_path=args.evolutions,
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
