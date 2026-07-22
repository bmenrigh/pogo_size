import io
import unittest

from pdf_tools.cdf_poly_lookup import PolynomialCDF


TABLE = """\
# cdf-poly-v1 degree=5 basis=t
0 1 0 1 0 0 0 0
1 2 1 0 0 0 0 0
"""

SURVIVAL_TABLE = """\
# cdf-poly-v2 degree=5 basis=t
C 0 1 0 0.5 0 0 0 0
S 1 2 0.5 -0.5 0 0 0 0
"""


class PolynomialCDFLookupTests(unittest.TestCase):
    def setUp(self):
        self.table = PolynomialCDF.from_lines(io.StringIO(TABLE))

    def test_lookup_uses_local_normalized_coordinate(self):
        self.assertEqual(self.table.lookup(0.25), 0.25)
        self.assertEqual(self.table.lookup(1.5), 1.0)

    def test_values_outside_support_are_clamped(self):
        self.assertEqual(self.table.lookup(-1), 0.0)
        self.assertEqual(self.table.lookup(3), 1.0)

    def test_upper_tail(self):
        self.assertEqual(self.table.p_value(0.25, upper_tail=True), 0.75)

    def test_survival_segment_is_evaluated_directly(self):
        table = PolynomialCDF.from_lines(io.StringIO(SURVIVAL_TABLE))

        self.assertEqual(table.p_value(1.5, upper_tail=True), 0.25)
        self.assertEqual(table.p_value(1.5), 0.75)

    def test_noncontiguous_segments_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "contiguous"):
            PolynomialCDF.from_lines(
                io.StringIO("0 1 0 1 0 0 0 0\n2 3 1 0 0 0 0 0\n")
            )


if __name__ == "__main__":
    unittest.main()
