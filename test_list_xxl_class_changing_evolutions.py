import io
import unittest

from list_xxl_class_changing_evolutions import (
    find_xxl_class_changes,
    write_table,
)


def records(
    number,
    pokemon_id,
    *,
    form=None,
    height=1.0,
    weight=10.0,
    xxl=1.75,
    evolution_branch=None,
    evolution_ids=None,
):
    suffix = form or pokemon_id
    template_id = f"V{number:04d}_POKEMON_{suffix}"
    pokemon_settings = {
        "pokemonId": pokemon_id,
        "pokedexHeightM": height,
        "pokedexWeightKg": weight,
        **({"form": form} if form else {}),
        **(
            {"evolutionBranch": evolution_branch}
            if evolution_branch is not None
            else {}
        ),
        **({"evolutionIds": evolution_ids} if evolution_ids is not None else {}),
    }
    standard = {
        "templateId": template_id,
        "data": {"pokemonSettings": pokemon_settings},
    }
    extended = {
        "templateId": "EXTENDED_" + template_id,
        "data": {
            "pokemonExtendedSettings": {
                "uniqueId": pokemon_id,
                "sizeSettings": {
                    "xxsLowerBound": 0.49 * height,
                    "mLowerBound": 0.75 * height,
                    "mUpperBound": 1.25 * height,
                    "xxlUpperBound": xxl * height,
                },
            }
        },
    }
    return standard, extended


class ListXxlClassChangingEvolutionsTests(unittest.TestCase):
    def test_finds_branch_and_resolves_redundant_normal_target(self):
        source = records(
            451,
            "SKORUPI",
            height=0.8,
            xxl=1.75,
            evolution_branch=[
                {"evolution": "DRAPION", "form": "DRAPION_NORMAL"}
            ],
        )
        target = records(452, "DRAPION", height=1.3, xxl=1.55)
        target_normal = records(
            452, "DRAPION", form="DRAPION_NORMAL", height=1.3, xxl=1.55
        )

        changes, problems = find_xxl_class_changes(
            [*source, *target, *target_normal]
        )

        self.assertEqual(problems, [])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].source.name, "SKORUPI")
        self.assertEqual(changes[0].target.name, "DRAPION")
        self.assertEqual(changes[0].source.xxl_class, 1.75)
        self.assertEqual(changes[0].target.xxl_class, 1.55)

    def test_uses_evolution_ids_and_omits_unchanged_classes(self):
        changed = records(
            1, "SOURCE", xxl=2.0, evolution_ids=["CHANGED", "UNCHANGED"]
        )
        target_changed = records(2, "CHANGED", xxl=1.55)
        target_unchanged = records(3, "UNCHANGED", xxl=2.0)

        changes, problems = find_xxl_class_changes(
            [*changed, *target_changed, *target_unchanged]
        )

        self.assertEqual(problems, [])
        self.assertEqual(
            [(change.source.name, change.target.name) for change in changes],
            [("SOURCE", "CHANGED")],
        )

    def test_deduplicates_bare_and_normal_source_records(self):
        branch = [{"evolution": "TARGET", "form": "TARGET_NORMAL"}]
        source = records(1, "SOURCE", xxl=1.75, evolution_branch=branch)
        source_normal = records(
            1,
            "SOURCE",
            form="SOURCE_NORMAL",
            xxl=1.75,
            evolution_branch=branch,
        )
        target = records(2, "TARGET", xxl=1.55)

        changes, problems = find_xxl_class_changes(
            [*source, *source_normal, *target]
        )

        self.assertEqual(problems, [])
        self.assertEqual(len(changes), 1)

    def test_reports_unresolved_evolution_target(self):
        source = records(1, "SOURCE", evolution_ids=["MISSING"])

        changes, problems = find_xxl_class_changes(list(source))

        self.assertEqual(changes, [])
        self.assertTrue(
            any(
                "cannot resolve validated target stats for MISSING" in p
                for p in problems
            )
        )

    def test_includes_zorua_for_the_evolution_audit(self):
        source = records(
            570, "ZORUA", xxl=1.75, evolution_ids=["ZOROARK"]
        )
        target = records(571, "ZOROARK", xxl=1.55)

        changes, problems = find_xxl_class_changes([*source, *target])

        self.assertEqual(problems, [])
        self.assertEqual(
            [(change.source.name, change.target.name) for change in changes],
            [("ZORUA", "ZOROARK")],
        )

    def test_ignores_pumpkaboo_without_warning(self):
        source = records(
            710, "PUMPKABOO", xxl=1.75, evolution_ids=["GOURGEIST"]
        )
        target = records(711, "GOURGEIST", xxl=1.55)

        changes, problems = find_xxl_class_changes([*source, *target])

        self.assertEqual(changes, [])
        self.assertEqual(problems, [])

    def test_writes_tsv(self):
        source = records(
            451,
            "SKORUPI",
            height=0.8,
            xxl=1.75,
            evolution_ids=["DRAPION"],
        )
        target = records(452, "DRAPION", height=1.3, xxl=1.55)
        changes, _ = find_xxl_class_changes([*source, *target])
        output = io.StringIO()

        write_table(changes, output)

        self.assertEqual(
            output.getvalue(),
            "source_pokedex_number\tsource_name\tsource_mean_height_m\t"
            "source_mean_weight_kg\tsource_xxl_class\t"
            "target_pokedex_number\ttarget_name\ttarget_mean_height_m\t"
            "target_mean_weight_kg\ttarget_xxl_class\tclass_change\n"
            "451\tSKORUPI\t0.8\t10\t1.75\t452\tDRAPION\t1.3\t10\t1.55\t"
            "1.75->1.55\n",
        )


if __name__ == "__main__":
    unittest.main()
