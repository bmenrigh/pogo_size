import io
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pdf_tools.compress_cdf_poly import (
    compress_cdf,
    evaluate_polynomial,
    read_cdf,
    write_segments,
)
from pdf_tools.cdf_poly_lookup import PolynomialCDF


class CompressCDFPolynomialTests(unittest.TestCase):
    def test_fifth_order_cdf_compresses_to_one_segment(self):
        t = np.linspace(0.0, 1.0, 101)
        cumulatives = t**5

        segments = compress_cdf(cumulatives, 1e-6, preserve_both_tails=False)

        self.assertEqual(len(segments), 1)
        predicted = evaluate_polynomial(segments[0].coefficients, t)
        np.testing.assert_allclose(predicted, cumulatives, rtol=1e-6, atol=1e-15)

    def test_fifth_order_upper_tail_is_also_preserved(self):
        t = np.linspace(0.0, 1.0, 101)
        cumulatives = 1.0 - (1.0 - t) ** 5

        segments = compress_cdf(cumulatives, 1e-6)

        survivals = 1.0 - cumulatives
        for segment in segments:
            local_t = np.linspace(
                0.0, 1.0, segment.end_index - segment.start_index + 1
            )
            predicted = evaluate_polynomial(segment.coefficients, local_t)
            expected = (
                cumulatives[segment.start_index : segment.end_index + 1]
                if segment.kind == "C"
                else survivals[segment.start_index : segment.end_index + 1]
            )
            np.testing.assert_allclose(
                predicted, expected, rtol=1e-6, atol=1e-15
            )

    def test_output_round_trips_through_lookup(self):
        coordinates = np.linspace(0.0, 1.0, 101)
        cumulatives = coordinates**3
        segments = compress_cdf(cumulatives, 1e-6)
        output = io.StringIO()
        write_segments(coordinates, segments, output)

        table = PolynomialCDF.from_lines(io.StringIO(output.getvalue()))

        self.assertAlmostEqual(table.lookup(0.25), 0.25**3)
        self.assertAlmostEqual(table.lookup(0.75), 0.75**3)

    def test_reader_requires_equal_spacing_and_monotone_cdf(self):
        with tempfile.TemporaryDirectory() as directory:
            uneven = Path(directory, "uneven.txt")
            uneven.write_text("0 0\n1 0.5\n3 1\n", encoding="utf-8")
            falling = Path(directory, "falling.txt")
            falling.write_text("0 0\n1 0.6\n2 0.5\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "equally spaced"):
                read_cdf(uneven)
            with self.assertRaisesRegex(ValueError, "nondecreasing"):
                read_cdf(falling)

    def test_reader_preserves_explicit_small_survival_values(self):
        with tempfile.TemporaryDirectory() as directory:
            table = Path(directory, "tails.txt")
            table.write_text(
                "0 0.0e+00 1.0e+00\n"
                "1 9.99999999994721e-01 5.279e-12\n"
                "2 1.0e+00 0.0e+00\n",
                encoding="utf-8",
            )

            _, _, survivals = read_cdf(table)

            self.assertEqual(survivals[1], 5.279e-12)

    def test_zero_plateau_is_preserved(self):
        cumulatives = np.array([0.0, 0.0, 0.0, 0.1, 0.2])

        segments = compress_cdf(cumulatives, 1e-6)
        coordinates = np.arange(len(cumulatives), dtype=float)
        output = io.StringIO()
        write_segments(coordinates, segments, output)
        table = PolynomialCDF.from_lines(io.StringIO(output.getvalue()))

        self.assertEqual(table.lookup(0.5), 0.0)

    def test_survival_zero_plateau_is_exact(self):
        cumulatives = np.array([0.0, 0.5, 1.0, 1.0, 1.0])
        survivals = np.array([1.0, 0.5, 1e-20, 0.0, 0.0])
        coordinates = np.arange(len(cumulatives), dtype=float)

        segments = compress_cdf(
            cumulatives, 1e-9, survivals, coordinates=coordinates
        )
        output = io.StringIO()
        write_segments(coordinates, segments, output)
        table = PolynomialCDF.from_lines(io.StringIO(output.getvalue()))

        self.assertEqual(table.p_value(3.5, upper_tail=True), 0.0)


if __name__ == "__main__":
    unittest.main()
