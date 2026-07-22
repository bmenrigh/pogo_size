import io
import unittest

from pdf_tools.compress_pdf_linear import (
    CompressionStats,
    PDFPoint,
    compress_points,
    read_pdf_points,
    write_compressed_pdf,
)


def points(values):
    return [PDFPoint(str(x), str(y), float(x), float(y)) for x, y in values]


class CompressPDFLinearTests(unittest.TestCase):
    def test_perfect_line_keeps_only_endpoints(self):
        result = list(compress_points(points([(0, 1), (1, 3), (2, 5), (3, 7)])))

        self.assertEqual([(p.coordinate, p.density) for p in result], [(0, 1), (3, 7)])

    def test_search_continues_after_an_invalid_endpoint(self):
        # At 10% tolerance, x=2 cannot connect directly to x=0 because it
        # misses x=1 by 15%.  The later x=3 endpoint recovers both by <10%.
        result = list(
            compress_points(
                points([(0, 0), (1, 1), (2, 2.3), (3, 3.24)]),
                relative_error=0.1,
            )
        )

        self.assertEqual([p.coordinate for p in result], [0, 3])

    def test_point_outside_tolerance_is_retained(self):
        result = list(
            compress_points(points([(0, 1), (1, 1), (2, 1.01), (3, 1)]))
        )

        self.assertIn(2, [p.coordinate for p in result])

    def test_zero_density_must_be_recovered_exactly(self):
        result = list(
            compress_points(points([(0, 0), (1, 0), (2, 0), (3, 1)]))
        )

        self.assertEqual([p.coordinate for p in result], [0, 2, 3])

    def test_variable_coordinate_widths_are_supported(self):
        result = list(
            compress_points(points([(0, 1), (0.25, 1.5), (2, 5), (10, 21)]))
        )

        self.assertEqual([p.coordinate for p in result], [0, 10])

    def test_original_text_and_stats_are_preserved(self):
        parsed = read_pdf_points(
            io.StringIO("0.000000 1.000000000000000\n1.000000 2.0\n"),
            "test",
        )
        output = io.StringIO()
        stats = write_compressed_pdf(parsed, output)

        self.assertEqual(
            output.getvalue(),
            "0.000000\t1.000000000000000\n1.000000\t2.0\n",
        )
        self.assertEqual(stats, CompressionStats(input_points=2, output_points=2))

    def test_bad_input_is_rejected(self):
        parsed = read_pdf_points(io.StringIO("0 1\n0 -1\n"), "test")

        with self.assertRaisesRegex(ValueError, "nonnegative"):
            list(parsed)


if __name__ == "__main__":
    unittest.main()
