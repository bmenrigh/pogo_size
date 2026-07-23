#!/usr/bin/env python3
"""List direct evolutions whose source and target use different XXL classes."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TextIO

from read_pokemon_stats_from_gm import PokemonStats, extract_pokemon_stats


EVOLUTION_AUDIT_SKIPS = frozenset(("PUMPKABOO", "GOURGEIST"))


@dataclass(frozen=True)
class EvolutionClassChange:
    source: PokemonStats
    target: PokemonStats


class StatsIndex:
    """Resolve raw Game Master form names to validated, possibly collapsed stats."""

    def __init__(self, rows: Iterable[PokemonStats]) -> None:
        self.by_name: dict[str, PokemonStats] = {}
        self.by_pokemon_id: dict[str, list[PokemonStats]] = {}
        for row in rows:
            self.by_name[row.name] = row
            self.by_pokemon_id.setdefault(row.pokemon_id, []).append(row)

    def resolve(self, pokemon_id: str, form: str | None) -> PokemonStats | None:
        names: list[str] = []
        if form:
            names.append(form)
            if form == f"{pokemon_id}_NORMAL":
                names.append(pokemon_id)
        else:
            names.append(pokemon_id)
        names.append(f"{pokemon_id}_ALL")

        for name in names:
            row = self.by_name.get(name)
            if row is not None:
                return row

        candidates = self.by_pokemon_id.get(pokemon_id, [])
        return candidates[0] if len(candidates) == 1 else None


def _evolution_targets(
    pokemon: Mapping[str, Any],
) -> set[tuple[str, str | None]]:
    """Return (Pokémon ID, form) pairs for every direct evolution."""
    targets: set[tuple[str, str | None]] = set()
    branch_target_ids: set[str] = set()

    branches = pokemon.get("evolutionBranch")
    if isinstance(branches, list):
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            evolution = branch.get("evolution")
            if not isinstance(evolution, str) or not evolution:
                continue
            form_value = branch.get("form")
            form = form_value if isinstance(form_value, str) and form_value else None
            targets.add((evolution, form))
            branch_target_ids.add(evolution)

    evolution_ids = pokemon.get("evolutionIds")
    if isinstance(evolution_ids, list):
        for evolution in evolution_ids:
            if (
                isinstance(evolution, str)
                and evolution
                and evolution not in branch_target_ids
            ):
                targets.add((evolution, None))

    return targets


def find_xxl_class_changes(
    game_master: object,
) -> tuple[list[EvolutionClassChange], list[str]]:
    """Find every resolvable direct evolution that changes XXL height class."""
    if not isinstance(game_master, list):
        raise ValueError("GAME_MASTER root must be a JSON array")

    # Zorua is excluded from the probability app because its generated sizes
    # are buggy, but its canonical Game Master XXL class is still relevant to
    # an exhaustive evolution audit. Pumpkaboo and Gourgeist do not use the
    # ordinary XXL-class system and therefore cannot be classified here.
    stats, stats_problems = extract_pokemon_stats(
        game_master, skipped_pokemon=EVOLUTION_AUDIT_SKIPS
    )
    index = StatsIndex(stats)
    problems = [f"stats: {problem}" for problem in stats_problems]
    changes: dict[tuple[str, str], EvolutionClassChange] = {}
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
        if not isinstance(pokemon_id, str) or not pokemon_id:
            continue
        if pokemon_id in EVOLUTION_AUDIT_SKIPS:
            continue
        targets = _evolution_targets(pokemon)
        if not targets:
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
            target = index.resolve(target_id, target_form)
            if target is None:
                unresolved.add(
                    f"{template_id}: cannot resolve validated target stats for "
                    f"{target_form or target_id}"
                )
                continue
            if source.xxl_class == target.xxl_class:
                continue
            key = (source.name, target.name)
            changes[key] = EvolutionClassChange(source=source, target=target)

    problems.extend(sorted(unresolved))
    ordered = sorted(
        changes.values(),
        key=lambda change: (
            change.source.pokedex_number,
            change.source.name,
            change.target.pokedex_number,
            change.target.name,
        ),
    )
    return ordered, problems


def write_table(
    changes: Iterable[EvolutionClassChange], output: TextIO
) -> None:
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(
        (
            "source_pokedex_number",
            "source_name",
            "source_mean_height_m",
            "source_mean_weight_kg",
            "source_xxl_class",
            "target_pokedex_number",
            "target_name",
            "target_mean_height_m",
            "target_mean_weight_kg",
            "target_xxl_class",
            "class_change",
        )
    )
    for change in changes:
        source = change.source
        target = change.target
        writer.writerow(
            (
                source.pokedex_number,
                source.name,
                f"{source.mean_height_m:.15g}",
                f"{source.mean_weight_kg:.15g}",
                f"{source.xxl_class:.12g}",
                target.pokedex_number,
                target.name,
                f"{target.mean_height_m:.15g}",
                f"{target.mean_weight_kg:.15g}",
                f"{target.xxl_class:.12g}",
                f"{source.xxl_class:g}->{target.xxl_class:g}",
            )
        )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read a Pokémon GO JSON Game Master and write every direct "
            "evolution whose source and target use different XXL height "
            "classes as a tab-separated table. Warnings are written to stderr."
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
        changes, problems = find_xxl_class_changes(game_master)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    write_table(changes, sys.stdout)
    for problem in problems:
        print(f"WARNING: {problem}", file=sys.stderr)
    print(
        f"Found {len(changes)} direct evolution(s) that change XXL height "
        f"class; found {len(problems)} warning(s).",
        file=sys.stderr,
    )
    return 1 if args.strict and problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
