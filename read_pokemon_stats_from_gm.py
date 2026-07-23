#!/usr/bin/env python3
"""Extract height, weight, and size-distribution classes from GAME_MASTER.json."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TextIO


TEMPLATE_RE = re.compile(r"^V(?P<number>\d+)_POKEMON_.+$")
XXS_CLASSES = (0.25, 0.49)
XXL_CLASSES = (1.55, 1.75, 2.0)
SKIPPED_POKEMON = frozenset(("PUMPKABOO", "GOURGEIST", "ZORUA"))
CLASS_REL_TOLERANCE = 1e-9
HEIGHT_REL_TOLERANCE = 1e-9


@dataclass(frozen=True)
class PokemonStats:
    pokedex_number: int
    pokemon_id: str
    name: str
    mean_height_m: float
    mean_weight_kg: float
    xxs_class: float
    xxl_class: float
    template_id: str


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _canonical_class(value: float, choices: Iterable[float]) -> float | None:
    for choice in choices:
        if math.isclose(
            value,
            choice,
            rel_tol=CLASS_REL_TOLERANCE,
            abs_tol=CLASS_REL_TOLERANCE,
        ):
            return choice
    return None


def _collect_settings(
    entries: list[object],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]], list[str]]:
    standard: dict[str, Mapping[str, Any]] = {}
    extended: dict[str, Mapping[str, Any]] = {}
    problems: list[str] = []

    for entry_number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        template_id = entry.get("templateId")
        data = entry.get("data")
        if not isinstance(template_id, str) or not isinstance(data, dict):
            continue

        pokemon_settings = data.get("pokemonSettings")
        if isinstance(pokemon_settings, dict):
            if template_id in standard:
                problems.append(f"{template_id}: duplicate pokemonSettings record")
            else:
                standard[template_id] = pokemon_settings

        extended_settings = data.get("pokemonExtendedSettings")
        if isinstance(extended_settings, dict):
            if not template_id.startswith("EXTENDED_"):
                problems.append(
                    f"entry {entry_number}: extended record has unexpected "
                    f"template ID {template_id!r}"
                )
                continue
            matching_id = template_id.removeprefix("EXTENDED_")
            if matching_id in extended:
                problems.append(
                    f"{template_id}: duplicate pokemonExtendedSettings record"
                )
            else:
                extended[matching_id] = extended_settings

    return standard, extended, problems


def extract_pokemon_stats(
    game_master: object,
    *,
    skipped_pokemon: frozenset[str] = SKIPPED_POKEMON,
) -> tuple[list[PokemonStats], list[str]]:
    """Return all complete Pokémon rows and all validation problems."""
    if not isinstance(game_master, list):
        raise ValueError("GAME_MASTER root must be a JSON array")

    standard, extended, problems = _collect_settings(game_master)
    rows: list[PokemonStats] = []
    variation_counts: dict[int, int] = {}

    for template_id, pokemon in standard.items():
        match = TEMPLATE_RE.fullmatch(template_id)
        if match is None or pokemon.get("pokemonId") in skipped_pokemon:
            continue
        pokedex_number = int(match.group("number"))
        variation_counts[pokedex_number] = variation_counts.get(pokedex_number, 0) + 1

    for template_id in sorted(set(standard) - set(extended)):
        problems.append(f"{template_id}: no matching extended size settings")
    for template_id in sorted(set(extended) - set(standard)):
        problems.append(f"{template_id}: no matching pokemonSettings record")

    for template_id in sorted(set(standard) & set(extended)):
        pokemon = standard[template_id]
        pokemon_id = pokemon.get("pokemonId")
        if pokemon_id in skipped_pokemon:
            continue

        size_settings = extended[template_id].get("sizeSettings")
        match = TEMPLATE_RE.fullmatch(template_id)
        if match is None:
            problems.append(f"{template_id}: cannot determine Pokédex number")
            continue
        if not isinstance(size_settings, dict):
            problems.append(f"{template_id}: sizeSettings is missing")
            continue

        required_size_values = (
            "xxsLowerBound",
            "mLowerBound",
            "mUpperBound",
            "xxlUpperBound",
        )
        bad_fields = [
            field
            for field in required_size_values
            if not _is_finite_number(size_settings.get(field))
        ]
        if bad_fields:
            problems.append(
                f"{template_id}: missing or invalid size value(s): "
                + ", ".join(bad_fields)
            )
            continue

        pokedex_height = pokemon.get("pokedexHeightM")
        weight = pokemon.get("pokedexWeightKg")
        if not _is_finite_number(pokedex_height):
            problems.append(f"{template_id}: missing or invalid pokedexHeightM")
            continue
        if not _is_finite_number(weight):
            problems.append(f"{template_id}: missing or invalid pokedexWeightKg")
            continue

        lower = float(size_settings["mLowerBound"])
        upper = float(size_settings["mUpperBound"])
        mean_height = (lower + upper) / 2.0
        if mean_height <= 0.0:
            problems.append(
                f"{template_id}: mean height must be positive, got {mean_height:g}"
            )
            continue

        form = pokemon.get("form")
        if not isinstance(pokemon_id, str) or not pokemon_id:
            problems.append(f"{template_id}: cannot determine Pokémon ID")
            continue
        name_value = form if isinstance(form, str) and form else pokemon_id
        if not isinstance(name_value, str) or not name_value:
            problems.append(f"{template_id}: cannot determine Pokémon name")
            continue
        name = name_value

        xxs_ratio = float(size_settings["xxsLowerBound"]) / mean_height
        xxl_ratio = float(size_settings["xxlUpperBound"]) / mean_height
        xxs_class = _canonical_class(xxs_ratio, XXS_CLASSES)
        xxl_class = _canonical_class(xxl_ratio, XXL_CLASSES)

        row_is_valid = True
        if not math.isclose(
            mean_height,
            float(pokedex_height),
            rel_tol=HEIGHT_REL_TOLERANCE,
            abs_tol=HEIGHT_REL_TOLERANCE,
        ):
            problems.append(
                f"{template_id}: size-settings mean height {mean_height:.12g} "
                f"does not match pokedexHeightM {float(pokedex_height):.12g}"
            )
            row_is_valid = False
        if xxs_class is None:
            choices = ", ".join(f"{value:g}" for value in XXS_CLASSES)
            problems.append(
                f"{template_id}: XXS ratio {xxs_ratio:.12g} does not match "
                f"an allowed class ({choices})"
            )
            row_is_valid = False
        if xxl_class is None:
            choices = ", ".join(f"{value:g}" for value in XXL_CLASSES)
            problems.append(
                f"{template_id}: XXL ratio {xxl_ratio:.12g} does not match "
                f"an allowed class ({choices})"
            )
            row_is_valid = False

        if not row_is_valid:
            continue

        rows.append(
            PokemonStats(
                pokedex_number=int(match.group("number")),
                pokemon_id=pokemon_id,
                name=name,
                mean_height_m=mean_height,
                mean_weight_kg=float(weight),
                xxs_class=xxs_class,
                xxl_class=xxl_class,
                template_id=template_id,
            )
        )

    primal_rows = _extract_primal_stats(standard, extended, problems)
    rows.extend(primal_rows)
    for row in primal_rows:
        variation_counts[row.pokedex_number] = (
            variation_counts.get(row.pokedex_number, 0) + 1
        )

    rows, omitted_normal_counts = _omit_redundant_normal_variations(rows)
    effective_variation_counts = {
        pokedex_number: count - omitted_normal_counts.get(pokedex_number, 0)
        for pokedex_number, count in variation_counts.items()
    }
    rows = _collapse_identical_variations(rows, effective_variation_counts)
    rows.sort(key=lambda row: (row.pokedex_number, row.name, row.template_id))
    return rows, problems


def _extract_primal_stats(
    standard: Mapping[str, Mapping[str, Any]],
    extended: Mapping[str, Mapping[str, Any]],
    problems: list[str],
) -> list[PokemonStats]:
    """Extract Primal means stored inside a base form's tempEvoOverrides."""
    rows: list[PokemonStats] = []
    for template_id, pokemon in sorted(standard.items()):
        # The base and _NORMAL records contain duplicate override data. Use the
        # form-less base record so each Primal form is emitted exactly once.
        if pokemon.get("form") is not None:
            continue
        overrides = pokemon.get("tempEvoOverrides")
        if not isinstance(overrides, list):
            continue
        match = TEMPLATE_RE.fullmatch(template_id)
        pokemon_id = pokemon.get("pokemonId")
        if match is None or not isinstance(pokemon_id, str) or not pokemon_id:
            continue

        for override in overrides:
            if (
                not isinstance(override, dict)
                or override.get("tempEvoId") != "TEMP_EVOLUTION_PRIMAL"
            ):
                continue

            height = override.get("averageHeightM")
            weight = override.get("averageWeightKg")
            if (
                not _is_finite_number(height)
                or not _is_finite_number(weight)
                or float(height) <= 0.0
                or float(weight) <= 0.0
            ):
                problems.append(
                    f"{template_id}: Primal override has missing or invalid "
                    "average height or weight"
                )
                continue

            size_settings = extended.get(template_id, {}).get("sizeSettings")
            if not isinstance(size_settings, dict) or any(
                not _is_finite_number(size_settings.get(field))
                for field in (
                    "xxsLowerBound",
                    "mLowerBound",
                    "mUpperBound",
                    "xxlUpperBound",
                )
            ):
                problems.append(
                    f"{template_id}: cannot determine Primal size classes "
                    "from the base extended settings"
                )
                continue

            base_mean = (
                float(size_settings["mLowerBound"])
                + float(size_settings["mUpperBound"])
            ) / 2.0
            if base_mean <= 0.0:
                problems.append(
                    f"{template_id}: cannot determine Primal size classes "
                    "from a nonpositive base mean"
                )
                continue
            xxs_ratio = float(size_settings["xxsLowerBound"]) / base_mean
            xxl_ratio = float(size_settings["xxlUpperBound"]) / base_mean
            xxs_class = _canonical_class(xxs_ratio, XXS_CLASSES)
            xxl_class = _canonical_class(xxl_ratio, XXL_CLASSES)
            if xxs_class is None or xxl_class is None:
                problems.append(
                    f"{template_id}: base size classes are invalid for the "
                    "Primal override"
                )
                continue

            rows.append(
                PokemonStats(
                    pokedex_number=int(match.group("number")),
                    pokemon_id=pokemon_id,
                    name=f"{pokemon_id}_PRIMAL",
                    mean_height_m=float(height),
                    mean_weight_kg=float(weight),
                    xxs_class=xxs_class,
                    xxl_class=xxl_class,
                    template_id=f"{template_id}#TEMP_EVOLUTION_PRIMAL",
                )
            )
    return rows


def _collapse_identical_variations(
    rows: list[PokemonStats], variation_counts: Mapping[int, int]
) -> list[PokemonStats]:
    grouped: dict[int, list[PokemonStats]] = {}
    for row in rows:
        grouped.setdefault(row.pokedex_number, []).append(row)

    collapsed: list[PokemonStats] = []
    for pokedex_number, variations in grouped.items():
        stat_sets = {
            (
                row.mean_height_m,
                row.mean_weight_kg,
                row.xxs_class,
                row.xxl_class,
            )
            for row in variations
        }
        pokemon_ids = {row.pokemon_id for row in variations}
        all_variations_are_present = (
            len(variations) == variation_counts.get(pokedex_number, 0)
        )
        if (
            len(variations) > 1
            and all_variations_are_present
            and len(stat_sets) == 1
            and len(pokemon_ids) == 1
        ):
            representative = variations[0]
            collapsed.append(
                PokemonStats(
                    pokedex_number=pokedex_number,
                    pokemon_id=representative.pokemon_id,
                    name=f"{representative.pokemon_id}_ALL",
                    mean_height_m=representative.mean_height_m,
                    mean_weight_kg=representative.mean_weight_kg,
                    xxs_class=representative.xxs_class,
                    xxl_class=representative.xxl_class,
                    template_id=representative.template_id,
                )
            )
        else:
            collapsed.extend(variations)
    return collapsed


def _stat_values(row: PokemonStats) -> tuple[float, float, float, float]:
    return (
        row.mean_height_m,
        row.mean_weight_kg,
        row.xxs_class,
        row.xxl_class,
    )


def _omit_redundant_normal_variations(
    rows: list[PokemonStats],
) -> tuple[list[PokemonStats], dict[int, int]]:
    bare_stats = {
        (row.pokedex_number, row.pokemon_id): _stat_values(row)
        for row in rows
        if row.name == row.pokemon_id
    }
    kept: list[PokemonStats] = []
    omitted_counts: dict[int, int] = {}
    for row in rows:
        is_redundant_normal = (
            row.name.endswith("_NORMAL")
            and bare_stats.get((row.pokedex_number, row.pokemon_id))
            == _stat_values(row)
        )
        if is_redundant_normal:
            omitted_counts[row.pokedex_number] = (
                omitted_counts.get(row.pokedex_number, 0) + 1
            )
        else:
            kept.append(row)
    return kept, omitted_counts


def write_table(rows: Iterable[PokemonStats], output: TextIO) -> None:
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(
        (
            "pokedex_number",
            "name",
            "mean_height_m",
            "mean_weight_kg",
            "xxs_class",
            "xxl_class",
        )
    )
    for row in rows:
        writer.writerow(
            (
                row.pokedex_number,
                row.name,
                f"{row.mean_height_m:.15g}",
                f"{row.mean_weight_kg:.15g}",
                f"{row.xxs_class:.12g}",
                f"{row.xxl_class:.12g}",
            )
        )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract Pokémon height, weight, XXS class, and XXL class as a "
            "tab-separated table. Validation problems are written to stderr."
        )
    )
    parser.add_argument(
        "game_master",
        metavar="GAME_MASTER.json",
        type=Path,
        nargs="?",
        default=Path("GAME_MASTER.json"),
        help="GAME_MASTER input path (default: GAME_MASTER.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit unsuccessfully if any validation problems are found",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        with args.game_master.open(encoding="utf-8") as input_file:
            game_master = json.load(input_file)
        rows, problems = extract_pokemon_stats(game_master)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    write_table(rows, sys.stdout)
    for problem in problems:
        print(f"WARNING: {problem}", file=sys.stderr)
    print(
        f"Extracted {len(rows)} Pokémon records; "
        f"found {len(problems)} validation problem(s).",
        file=sys.stderr,
    )
    return 1 if args.strict and problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
