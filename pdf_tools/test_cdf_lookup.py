import io
import unittest

from pdf_tools.cdf_lookup import CDFTable


EXAMPLE = """\
0.0000  0.000000000000000
0.0001  0.000000396421823
0.0002  0.000000793335765
0.0003  0.000001190537898
"""


class CDFTableTests(unittest.TestCase):
    def setUp(self):
        self.table = CDFTable.from_lines(io.StringIO(EXAMPLE))

    def test_half_bucket_interpolates_cdf(self):
        result = self.table.lookup(0.00015)

        self.assertAlmostEqual(result.density, 0.00396913942)
        self.assertAlmostEqual(result.cumulative, 0.000000594878794)

    def test_bucket_start_uses_current_rows_values(self):
        result = self.table.lookup(0.0001)

        self.assertAlmostEqual(result.density, 0.00396913942)
        self.assertEqual(result.cumulative, 0.000000396421823)

    def test_bucket_area_is_difference_between_adjacent_cdf_values(self):
        start = self.table.lookup(0.0001).cumulative
        end = self.table.lookup(0.0002).cumulative

        self.assertAlmostEqual(end - start, 0.000000396913942)

    def test_values_outside_table_are_clamped_to_the_tails(self):
        self.assertEqual(self.table.lookup(-1.0).cumulative, 0.0)
        self.assertEqual(
            self.table.lookup(1.0).cumulative, self.table.total_probability
        )

    def test_upper_tail_uses_table_total(self):
        lower = self.table.p_value(0.00015)

        self.assertAlmostEqual(
            self.table.p_value(0.00015, upper_tail=True),
            self.table.total_probability - lower,
        )

    def test_comments_and_blank_lines_are_ignored(self):
        table = CDFTable.from_lines(
            io.StringIO("# bucket cdf\n\n0 0.5\n1 1\n")
        )

        self.assertEqual(table.total_probability, 1.0)

    def test_bad_table_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            CDFTable.from_lines(io.StringIO("0 0.5\n0 1\n"))

    def test_three_column_pdf_is_integrated_quadratically(self):
        table = CDFTable.from_lines(io.StringIO("0 1 0\n1 3 1\n"))

        self.assertEqual(table.lookup(0.5).cumulative, 0.375)
        self.assertEqual(table.lookup(0.5).density, 2.0)

    def test_three_column_endpoint_preserves_density(self):
        table = CDFTable.from_lines(io.StringIO("0 1 0\n1 3 1\n"))

        self.assertEqual(table.lookup(1).density, 3.0)
        self.assertEqual(table.lookup(1).cumulative, 1.0)

    def test_mixed_two_and_three_column_rows_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot mix"):
            CDFTable.from_lines(io.StringIO("0 0\n1 1 1\n"))

    def test_explicit_survival_is_used_for_upper_tail(self):
        table = CDFTable.from_lines(
            io.StringIO(
                "# cdf-survival-v1\n"
                "0 0.0e+00 1.0e+00\n"
                "1 9.99999999994721e-01 5.279e-12\n"
                "2 1.0e+00 0.0e+00\n"
            )
        )

        self.assertEqual(table.p_value(1, upper_tail=True), 5.279e-12)


if __name__ == "__main__":
    unittest.main()
