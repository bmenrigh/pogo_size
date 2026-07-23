import io
import unittest
from decimal import Decimal

from check_float32_display_extrema import (
    PokemonStats,
    displayed_value,
    find_anomalies,
    to_float32_decimal,
    write_report,
)


class CheckFloat32DisplayExtremaTests(unittest.TestCase):
    def test_kyogre_maximum_height_rounds_down_after_float32(self):
        nominal = Decimal("4.5") * Decimal("1.55")
        float32 = to_float32_decimal(nominal)

        self.assertEqual(nominal, Decimal("6.975"))
        self.assertEqual(float32, Decimal("6.974999904632568359375"))
        self.assertEqual(displayed_value(nominal), Decimal("6.98"))
        self.assertEqual(displayed_value(float32), Decimal("6.97"))

    def test_finds_height_and_weight_categories(self):
        rows = [
            PokemonStats(
                382,
                "KYOGRE",
                Decimal("4.5"),
                Decimal("352"),
                Decimal("0.49"),
                Decimal("1.55"),
            ),
            PokemonStats(
                10,
                "CATERPIE",
                Decimal("0.3"),
                Decimal("2.9"),
                Decimal("0.49"),
                Decimal("1.75"),
            ),
        ]

        anomalies = find_anomalies(rows)

        categories = {
            (item.name, item.extremum, item.direction) for item in anomalies
        }
        self.assertIn(("KYOGRE", "maximum_height", "lower"), categories)
        self.assertIn(("KYOGRE", "minimum_height", "lower"), categories)
        self.assertIn(("CATERPIE", "maximum_height", "lower"), categories)
        self.assertIn(("CATERPIE", "maximum_weight", "lower"), categories)

    def test_report_includes_empty_and_nonempty_categories(self):
        row = PokemonStats(
            382,
            "KYOGRE",
            Decimal("4.5"),
            Decimal("352"),
            Decimal("0.49"),
            Decimal("1.55"),
        )
        anomalies = find_anomalies([row])
        output = io.StringIO()

        write_report([row], anomalies, output)

        report = output.getvalue()
        self.assertIn("Maximum height fails", report)
        self.assertIn("6.975\t6.974999904632568359375\t6.98\t6.97", report)
        self.assertIn("Maximum height reaches a HIGHER", report)
        self.assertIn("(none)", report)


if __name__ == "__main__":
    unittest.main()
