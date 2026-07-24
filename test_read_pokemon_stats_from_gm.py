import io
import unittest

from read_pokemon_stats_from_gm import extract_pokemon_stats, write_table


def records(
    number,
    pokemon_id,
    *,
    form=None,
    height=1.0,
    weight=10.0,
    xxs=0.49,
    xxl=1.75,
):
    suffix = form or pokemon_id
    template_id = f"V{number:04d}_POKEMON_{suffix}"
    standard = {
        "templateId": template_id,
        "data": {
            "pokemonSettings": {
                "pokemonId": pokemon_id,
                "pokedexHeightM": height,
                "pokedexWeightKg": weight,
                **({"form": form} if form else {}),
            }
        },
    }
    extended = {
        "templateId": "EXTENDED_" + template_id,
        "data": {
            "pokemonExtendedSettings": {
                "uniqueId": pokemon_id,
                **({"form": form} if form else {}),
                "sizeSettings": {
                    "xxsLowerBound": xxs * height,
                    "mLowerBound": 0.75 * height,
                    "mUpperBound": 1.25 * height,
                    "xxlUpperBound": xxl * height,
                },
            }
        },
    }
    return standard, extended


class ReadPokemonStatsTests(unittest.TestCase):
    def test_extracts_and_joins_standard_and_extended_records(self):
        bulbasaur = records(1, "BULBASAUR", height=0.7, weight=6.9)

        rows, problems = extract_pokemon_stats([bulbasaur[1], bulbasaur[0]])

        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].pokedex_number, 1)
        self.assertEqual(rows[0].name, "BULBASAUR")
        self.assertAlmostEqual(rows[0].mean_height_m, 0.7)
        self.assertEqual(rows[0].mean_weight_kg, 6.9)
        self.assertEqual(rows[0].xxs_class, 0.49)
        self.assertEqual(rows[0].xxl_class, 1.75)

    def test_scatterbug_uses_the_special_xxs_class(self):
        scatterbug = records(
            664, "SCATTERBUG", form="SCATTERBUG_POLAR", xxs=0.25, xxl=2.0
        )

        rows, problems = extract_pokemon_stats(list(scatterbug))

        self.assertEqual(problems, [])
        self.assertEqual(rows[0].name, "SCATTERBUG_POLAR")
        self.assertEqual(rows[0].xxs_class, 0.25)

    def test_other_scatterbug_family_members_can_use_the_special_class(self):
        spewpa = records(665, "SPEWPA", xxs=0.25)

        rows, problems = extract_pokemon_stats(list(spewpa))

        self.assertEqual(problems, [])
        self.assertEqual(rows[0].xxs_class, 0.25)

    def test_omits_a_row_with_bad_classes_and_height_mismatch(self):
        standard, extended = records(999, "INVALIDMON", xxs=0.75, xxl=1.2)
        standard["data"]["pokemonSettings"]["pokedexHeightM"] = 0.8

        rows, problems = extract_pokemon_stats([standard, extended])

        self.assertEqual(rows, [])
        self.assertTrue(any("mean height" in problem for problem in problems))
        self.assertTrue(any("XXS ratio" in problem for problem in problems))
        self.assertTrue(any("XXL ratio" in problem for problem in problems))

    def test_skips_pumpkaboo_and_gourgeist_including_forms(self):
        pumpkaboo = records(710, "PUMPKABOO", xxs=0.75, xxl=1.2)
        gourgeist = records(
            711,
            "GOURGEIST",
            form="GOURGEIST_SUPER",
            xxs=1.0,
            xxl=1.2,
        )

        rows, problems = extract_pokemon_stats([*pumpkaboo, *gourgeist])

        self.assertEqual(rows, [])
        self.assertEqual(problems, [])

    def test_skips_zorua_including_forms(self):
        base = records(570, "ZORUA")
        normal = records(570, "ZORUA", form="ZORUA_NORMAL")

        rows, problems = extract_pokemon_stats([*base, *normal])

        self.assertEqual(rows, [])
        self.assertEqual(problems, [])

    def test_extracts_primal_stats_from_temporary_evolution_override(self):
        standard, extended = records(
            382, "KYOGRE", height=4.5, weight=352.0, xxl=1.55
        )
        standard["data"]["pokemonSettings"]["tempEvoOverrides"] = [
            {
                "tempEvoId": "TEMP_EVOLUTION_PRIMAL",
                "averageHeightM": 9.8,
                "averageWeightKg": 430.0,
            }
        ]
        extended["data"]["pokemonExtendedSettings"]["tempEvoOverrides"] = [
            {
                "tempEvoId": "TEMP_EVOLUTION_PRIMAL",
                "sizeSettings": {
                    "xxsLowerBound": 0.49 * 9.8,
                    "mLowerBound": 0.75 * 9.8,
                    "mUpperBound": 1.25 * 9.8,
                    "xxlUpperBound": 1.55 * 9.8,
                },
            }
        ]

        rows, problems = extract_pokemon_stats([standard, extended])

        self.assertEqual(problems, [])
        self.assertEqual([row.name for row in rows], ["KYOGRE", "KYOGRE_PRIMAL"])
        primal = rows[1]
        self.assertEqual(primal.pokedex_number, 382)
        self.assertEqual(primal.mean_height_m, 9.8)
        self.assertEqual(primal.mean_weight_kg, 430.0)
        self.assertEqual(primal.xxs_class, 0.49)
        self.assertEqual(primal.xxl_class, 1.55)

    def test_extracts_mega_stats_using_mega_specific_size_settings(self):
        standard, extended = records(
            303, "MAWILE", height=0.61, weight=11.5, xxl=1.75
        )
        standard["data"]["pokemonSettings"]["tempEvoOverrides"] = [
            {
                "tempEvoId": "TEMP_EVOLUTION_MEGA",
                "averageHeightM": 1.0,
                "averageWeightKg": 23.5,
            }
        ]
        extended["data"]["pokemonExtendedSettings"]["tempEvoOverrides"] = [
            {
                "tempEvoId": "TEMP_EVOLUTION_MEGA",
                "sizeSettings": {
                    "xxsLowerBound": 0.49,
                    "mLowerBound": 0.75,
                    "mUpperBound": 1.25,
                    "xxlUpperBound": 1.55,
                },
            }
        ]

        rows, problems = extract_pokemon_stats([standard, extended])

        self.assertEqual(problems, [])
        self.assertEqual([row.name for row in rows], ["MAWILE", "MAWILE_MEGA"])
        mega = rows[1]
        self.assertEqual(mega.pokedex_number, 303)
        self.assertEqual(mega.mean_height_m, 1.0)
        self.assertEqual(mega.mean_weight_kg, 23.5)
        self.assertEqual(mega.xxs_class, 0.49)
        self.assertEqual(mega.xxl_class, 1.55)

    def test_extracts_mega_x_and_mega_y_as_distinct_forms(self):
        standard, extended = records(
            6, "CHARIZARD", height=1.7, weight=90.5, xxl=1.75
        )
        standard["data"]["pokemonSettings"]["tempEvoOverrides"] = []
        extended["data"]["pokemonExtendedSettings"]["tempEvoOverrides"] = []
        for suffix, height, weight, xxl in (
            ("X", 1.7, 110.5, 1.75),
            ("Y", 1.7, 100.5, 2.0),
        ):
            temp_evo_id = f"TEMP_EVOLUTION_MEGA_{suffix}"
            standard["data"]["pokemonSettings"]["tempEvoOverrides"].append(
                {
                    "tempEvoId": temp_evo_id,
                    "averageHeightM": height,
                    "averageWeightKg": weight,
                }
            )
            extended["data"]["pokemonExtendedSettings"][
                "tempEvoOverrides"
            ].append(
                {
                    "tempEvoId": temp_evo_id,
                    "sizeSettings": {
                        "xxsLowerBound": 0.49 * height,
                        "mLowerBound": 0.75 * height,
                        "mUpperBound": 1.25 * height,
                        "xxlUpperBound": xxl * height,
                    },
                }
            )

        rows, problems = extract_pokemon_stats([standard, extended])

        self.assertEqual(problems, [])
        self.assertEqual(
            [row.name for row in rows],
            ["CHARIZARD", "CHARIZARD_MEGA_X", "CHARIZARD_MEGA_Y"],
        )
        self.assertEqual(rows[1].mean_weight_kg, 110.5)
        self.assertEqual(rows[1].xxl_class, 1.75)
        self.assertEqual(rows[2].mean_weight_kg, 100.5)
        self.assertEqual(rows[2].xxl_class, 2.0)

    def test_mega_does_not_prevent_identical_variations_collapsing(self):
        standard, extended = records(
            303, "MAWILE", height=0.61, weight=11.5, xxl=1.75
        )
        costume = records(
            303,
            "MAWILE",
            form="MAWILE_COSTUME",
            height=0.61,
            weight=11.5,
            xxl=1.75,
        )
        standard["data"]["pokemonSettings"]["tempEvoOverrides"] = [
            {
                "tempEvoId": "TEMP_EVOLUTION_MEGA",
                "averageHeightM": 1.0,
                "averageWeightKg": 23.5,
            }
        ]
        extended["data"]["pokemonExtendedSettings"]["tempEvoOverrides"] = [
            {
                "tempEvoId": "TEMP_EVOLUTION_MEGA",
                "sizeSettings": {
                    "xxsLowerBound": 0.49,
                    "mLowerBound": 0.75,
                    "mUpperBound": 1.25,
                    "xxlUpperBound": 1.75,
                },
            }
        ]

        rows, problems = extract_pokemon_stats(
            [standard, extended, *costume]
        )

        self.assertEqual(problems, [])
        self.assertEqual([row.name for row in rows], ["MAWILE_ALL", "MAWILE_MEGA"])

    def test_collapses_identical_variations_into_all(self):
        base = records(664, "SCATTERBUG", xxs=0.25)
        polar = records(
            664, "SCATTERBUG", form="SCATTERBUG_POLAR", xxs=0.25
        )
        river = records(
            664, "SCATTERBUG", form="SCATTERBUG_RIVER", xxs=0.25
        )

        rows, problems = extract_pokemon_stats([*base, *polar, *river])

        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "SCATTERBUG_ALL")

    def test_bare_and_normal_alone_do_not_collapse_into_all(self):
        base = records(22, "FEAROW", height=1.2, weight=38.0)
        normal = records(
            22,
            "FEAROW",
            form="FEAROW_NORMAL",
            height=1.2,
            weight=38.0,
        )

        rows, problems = extract_pokemon_stats([*base, *normal])

        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "FEAROW")

    def test_does_not_collapse_when_one_variation_differs(self):
        base = records(19, "RATTATA", weight=3.5)
        normal = records(19, "RATTATA", form="RATTATA_NORMAL", weight=3.5)
        alola = records(19, "RATTATA", form="RATTATA_ALOLA", weight=3.8)

        rows, problems = extract_pokemon_stats([*base, *normal, *alola])

        self.assertEqual(problems, [])
        self.assertEqual(
            [row.name for row in rows],
            ["RATTATA", "RATTATA_ALOLA"],
        )

    def test_does_not_collapse_when_a_variation_was_omitted(self):
        base = records(646, "KYUREM", height=3.0)
        normal = records(646, "KYUREM", form="KYUREM_NORMAL", height=3.0)
        black_standard, black_extended = records(
            646, "KYUREM", form="KYUREM_BLACK", height=3.0
        )
        black_standard["data"]["pokemonSettings"]["pokedexHeightM"] = 3.3

        rows, problems = extract_pokemon_stats(
            [*base, *normal, black_standard, black_extended]
        )

        self.assertTrue(any("mean height" in problem for problem in problems))
        self.assertEqual([row.name for row in rows], ["KYUREM"])

    def test_keeps_normal_variation_when_its_stats_differ(self):
        base = records(999, "EXAMPLE", weight=10.0)
        normal = records(999, "EXAMPLE", form="EXAMPLE_NORMAL", weight=11.0)
        other = records(999, "EXAMPLE", form="EXAMPLE_OTHER", weight=12.0)

        rows, problems = extract_pokemon_stats([*base, *normal, *other])

        self.assertEqual(problems, [])
        self.assertEqual(
            [row.name for row in rows],
            ["EXAMPLE", "EXAMPLE_NORMAL", "EXAMPLE_OTHER"],
        )

    def test_reports_an_unmatched_record(self):
        _, extended = records(902, "BASCULEGION")

        rows, problems = extract_pokemon_stats([extended])

        self.assertEqual(rows, [])
        self.assertEqual(
            problems,
            ["V0902_POKEMON_BASCULEGION: no matching pokemonSettings record"],
        )

    def test_writes_a_tsv_table(self):
        bulbasaur = records(1, "BULBASAUR", height=0.7, weight=6.9)
        rows, _ = extract_pokemon_stats(list(bulbasaur))
        output = io.StringIO()

        write_table(rows, output)

        self.assertEqual(
            output.getvalue(),
            "pokedex_number\tname\tmean_height_m\tmean_weight_kg\t"
            "xxs_class\txxl_class\n"
            "1\tBULBASAUR\t0.7\t6.9\t0.49\t1.75\n",
        )


if __name__ == "__main__":
    unittest.main()
