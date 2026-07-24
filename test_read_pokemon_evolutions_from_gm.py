import io
import unittest

from read_pokemon_evolutions_from_gm import (
    PokemonEvolution,
    extract_pokemon_evolutions,
    write_table,
)
from test_list_xxl_class_changing_evolutions import records


class ReadPokemonEvolutionsTests(unittest.TestCase):
    def test_extracts_branches_and_deduplicates_normal_records(self):
        branches = [
            {"evolution": "VAPOREON"},
            {"evolution": "JOLTEON"},
        ]
        source = records(133, "EEVEE", evolution_branch=branches)
        source_normal = records(
            133,
            "EEVEE",
            form="EEVEE_NORMAL",
            evolution_branch=branches,
        )
        vaporeon = records(134, "VAPOREON")
        jolteon = records(135, "JOLTEON")

        evolutions, problems = extract_pokemon_evolutions(
            [*source, *source_normal, *vaporeon, *jolteon]
        )

        self.assertEqual(problems, [])
        self.assertEqual(
            [(row.source_name, row.target_name) for row in evolutions],
            [("EEVEE", "JOLTEON"), ("EEVEE", "VAPOREON")],
        )

    def test_resolves_collapsed_all_source_and_target(self):
        branch = [{"evolution": "TARGET"}]
        source = records(1, "SOURCE", evolution_branch=branch)
        source_costume = records(
            1, "SOURCE", form="SOURCE_COSTUME", evolution_branch=branch
        )
        target = records(2, "TARGET")
        target_costume = records(2, "TARGET", form="TARGET_COSTUME")

        evolutions, problems = extract_pokemon_evolutions(
            [*source, *source_costume, *target, *target_costume]
        )

        self.assertEqual(problems, [])
        self.assertEqual(
            [(row.source_name, row.target_name) for row in evolutions],
            [("SOURCE_ALL", "TARGET_ALL")],
        )

    def test_omits_excluded_size_models(self):
        zorua = records(570, "ZORUA", evolution_ids=["ZOROARK"])
        zoroark = records(571, "ZOROARK")
        pumpkaboo = records(710, "PUMPKABOO", evolution_ids=["GOURGEIST"])
        gourgeist = records(711, "GOURGEIST")

        evolutions, problems = extract_pokemon_evolutions(
            [*zorua, *zoroark, *pumpkaboo, *gourgeist]
        )

        self.assertEqual(evolutions, [])
        self.assertEqual(problems, [])

    def test_includes_mega_and_primal_temporary_evolutions(self):
        lucario_standard, lucario_extended = records(448, "LUCARIO")
        mega_standard, mega_extended = records(
            448, "LUCARIO", form="LUCARIO_MEGA", height=1.3, weight=57.5
        )
        lucario_standard["data"]["pokemonSettings"]["tempEvoOverrides"] = [
            {
                "tempEvoId": "TEMP_EVOLUTION_MEGA",
                "averageHeightM": 1.3,
                "averageWeightKg": 57.5,
            }
        ]
        lucario_extended["data"]["pokemonExtendedSettings"][
            "tempEvoOverrides"
        ] = [
            {
                "tempEvoId": "TEMP_EVOLUTION_MEGA",
                "sizeSettings": {
                    "xxsLowerBound": 0.49 * 1.3,
                    "mLowerBound": 0.75 * 1.3,
                    "mUpperBound": 1.25 * 1.3,
                    "xxlUpperBound": 1.75 * 1.3,
                },
            }
        ]
        # The temporary form is synthesized from overrides; separate ordinary
        # form records would be invalid duplicate data and are not inputs.
        del mega_standard, mega_extended

        evolutions, problems = extract_pokemon_evolutions(
            [lucario_standard, lucario_extended]
        )

        self.assertEqual(problems, [])
        self.assertEqual(
            [(row.source_name, row.target_name) for row in evolutions],
            [("LUCARIO", "LUCARIO_MEGA")],
        )

    def test_writes_compact_tsv(self):
        output = io.StringIO()

        write_table(
            [PokemonEvolution("EEVEE", "VAPOREON")],
            output,
        )

        self.assertEqual(
            output.getvalue(),
            "source_name\ttarget_name\nEEVEE\tVAPOREON\n",
        )


if __name__ == "__main__":
    unittest.main()
