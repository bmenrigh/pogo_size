import io
import unittest

from pdf_tools.build_cdf_from_convo_pdf import read_pdf, write_normalized_cdf


class BuildCDFFromConvolutionPDFTests(unittest.TestCase):
    def test_left_aligned_nonuniform_buckets_are_normalized(self):
        samples = read_pdf(io.StringIO("0.0 2\n1.0 1\n3.0 0\n"))
        output = io.StringIO()

        write_normalized_cdf(samples, output)

        lines = output.getvalue().splitlines()
        self.assertEqual(lines[:2], ["# cdf-survival-v1", "# coordinate cdf survival"])
        self.assertEqual(tuple(map(float, lines[2].split()[1:])), (0.0, 1.0))
        self.assertEqual(tuple(map(float, lines[3].split()[1:])), (0.5, 0.5))
        self.assertEqual(tuple(map(float, lines[4].split()[1:])), (1.0, 0.0))

    def test_first_bucket_uses_first_rows_density(self):
        samples = read_pdf(io.StringIO("0 3\n0.25 1\n1 0\n"))
        first_area = samples[0].density * (
            samples[1].coordinate - samples[0].coordinate
        )

        self.assertEqual(first_area, 0.75)

    def test_linear_control_points_use_trapezoidal_area(self):
        samples = read_pdf(io.StringIO("0 2\n1 4\n3 0\n"))
        output = io.StringIO()

        write_normalized_cdf(samples, output, linear_control_points=True)

        lines = output.getvalue().splitlines()
        self.assertEqual(
            lines[:2], ["# linear-pdf-cdf-v1", "# coordinate normalized_pdf cdf"]
        )
        first = tuple(map(float, lines[2].split()[1:]))
        middle = tuple(map(float, lines[3].split()[1:]))
        final = tuple(map(float, lines[4].split()[1:]))
        self.assertAlmostEqual(first[0], 2 / 7)
        self.assertEqual(first[1], 0.0)
        self.assertAlmostEqual(middle[0], 4 / 7)
        self.assertAlmostEqual(middle[1], 3 / 7)
        self.assertEqual(final, (0.0, 1.0))

    def test_constant_width_does_not_make_trapezoids_equal_rectangles(self):
        samples = read_pdf(io.StringIO("0 1\n1 3\n2 0\n"))
        rectangles = io.StringIO()
        trapezoids = io.StringIO()

        write_normalized_cdf(samples, rectangles)
        write_normalized_cdf(samples, trapezoids, linear_control_points=True)

        self.assertNotEqual(rectangles.getvalue(), trapezoids.getvalue())

    def test_comments_and_blank_lines_are_ignored(self):
        samples = read_pdf(io.StringIO("# x pdf\n\n0 1\n1 0\n"))

        self.assertEqual(len(samples), 2)

    def test_unsorted_coordinates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            read_pdf(io.StringIO("0 1\n0 0\n"))

    def test_negative_density_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            read_pdf(io.StringIO("0 -1\n1 0\n"))

    def test_zero_area_is_rejected(self):
        samples = read_pdf(io.StringIO("0 0\n1 0\n"))

        with self.assertRaisesRegex(ValueError, "greater than zero"):
            write_normalized_cdf(samples, io.StringIO())


if __name__ == "__main__":
    unittest.main()
