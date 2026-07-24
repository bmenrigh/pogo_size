#!/usr/bin/env python3
"""Extract direct, size-model-compatible evolutions from GAME_MASTER.json."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, TextIO

from list_xxl_class_changing_evolutions import StatsIndex, _evolution_targets
from read_pokemon_stats_from_gm import SKIPPED_POKEMON, extract_pokemon_stats


@dataclass(frozen=True, order=True)
class PokemonEvolution:
    source_name: str
    target_name: str


def _temporary_evolution_names(pokemon_id: str, pokemon: dict) -> set[str]:
    names: set[str] = set()
    overrides = pokemon.get("tempEvoOverrides")
    if not isinstance(overrides, list):
        return names
    for override in overrides:
        if not isinstance(override, dict):
            continue
        temp_evo_id = override.get("tempEvoId")
        if not isinstance(temp_evo_id, str):
            continue
        if temp_evo_id in (
            "TEMP_EVOLUTION_MEGA",
            "TEMP_EVOLUTION_MEGA_X",
            "TEMP_EVOLUTION_MEGA_Y",
            "TEMP_EVOLUTION_PRIMAL",
        ):
            names.add(
                f"{pokemon_id}_"
                f"{temp_evo_id.removeprefix('TEMP_EVOLUTION_')}"
            )
    return names


def extract_pokemon_evolutions(
    game_master: object,
) -> tuple[list[PokemonEvolution], list[str]]:
    """Return every resolvable direct evolution represented in the stats table."""
    if not isinstance(game_master, list):
        raise ValueError("GAME_MASTER root must be a JSON array")

    stats, stats_problems = extract_pokemon_stats(game_master)
    index = StatsIndex(stats)
    evolutions: set[PokemonEvolution] = set()
    unresolved: set[str] = set()

    for entry in game_master:
        if not isinstance(entry, dict):
            continue
        template_id = entry.get("templateId")
        data = entry.get("data")
        if not isinstance(template_id, str) or not isinstance(data, dict):
            continue
        pokemon = data.get("pokemonSettings")
        if not isinstance(pokemon, dict):
            continue

        pokemon_id = pokemon.get("pokemonId")
        if (
            not isinstance(pokemon_id, str)
            or not pokemon_id
            or pokemon_id in SKIPPED_POKEMON
        ):
            continue
        targets = _evolution_targets(pokemon)
        temporary_targets = _temporary_evolution_names(pokemon_id, pokemon)
        if not targets and not temporary_targets:
            continue

        form_value = pokemon.get("form")
        source_form = (
            form_value if isinstance(form_value, str) and form_value else None
        )
        source = index.resolve(pokemon_id, source_form)
        if source is None:
            unresolved.add(
                f"{template_id}: cannot resolve validated source stats for "
                f"{source_form or pokemon_id}"
            )
            continue

        for target_id, target_form in targets:
            if target_id in SKIPPED_POKEMON:
                continue
            target = index.resolve(target_id, target_form)
            if target is None:
                unresolved.add(
                    f"{template_id}: cannot resolve validated target stats for "
                    f"{target_form or target_id}"
                )
                continue
            if source.name != target.name:
                evolutions.add(PokemonEvolution(source.name, target.name))

        for target_name in temporary_targets:
            target = index.by_name.get(target_name)
            if target is None:
                unresolved.add(
                    f"{template_id}: cannot resolve validated temporary "
                    f"evolution target {target_name}"
                )
                continue
            evolutions.add(PokemonEvolution(source.name, target.name))

    problems = [f"stats: {problem}" for problem in stats_problems]
    problems.extend(sorted(unresolved))
    return sorted(evolutions), problems


def write_table(evolutions: Iterable[PokemonEvolution], output: TextIO) -> None:
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(("source_name", "target_name"))
    for evolution in evolutions:
        writer.writerow((evolution.source_name, evolution.target_name))


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read a Pokémon GO JSON Game Master and write every direct "
            "permanent or temporary evolution whose source and target are "
            "present in the validated Pokémon stats as a tab-separated table."
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
        help="exit unsuccessfully if any validation or resolution warning occurs",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        with args.game_master.open(encoding="utf-8") as input_file:
            game_master = json.load(input_file)
        evolutions, problems = extract_pokemon_evolutions(game_master)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    write_table(evolutions, sys.stdout)
    for problem in problems:
        print(f"WARNING: {problem}", file=sys.stderr)
    print(
        f"Extracted {len(evolutions)} direct evolution(s); found "
        f"{len(problems)} warning(s).",
        file=sys.stderr,
    )
    return 1 if args.strict and problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
