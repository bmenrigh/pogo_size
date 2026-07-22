import contextlib
import io
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from pdf_tools.weighted_average_pdfs import (
    parse_weight,
    prepare_inputs,
    print_summary,
    write_weighted_average,
)


class WeightedAveragePDFTests(unittest.TestCase):
    def test_fraction_weight_is_parsed_exactly(self):
        self.assertEqual(parse_weight("471/500"), Fraction(471, 500))

    def test_non_fraction_weight_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "n/m form"):
            parse_weight("0.5")

    def test_weights_must_sum_to_one_before_files_are_opened(self):
        with self.assertRaisesRegex(ValueError, "not 1"):
            prepare_inputs(["1/4", "missing-a", "1/4", "missing-b"])

    def test_pdfs_are_individually_normalized_to_their_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory, "first.txt")
            second = Path(directory, "second.txt")
            first.write_text("0 2\n1 0\n2 0\n", encoding="utf-8")
            second.write_text("0 0\n1 2\n2 0\n", encoding="utf-8")
            inputs = prepare_inputs(["1/4", str(first), "3/4", str(second)])
            output = io.StringIO()

            area = write_weighted_average(inputs, output)

            self.assertEqual(
                output.getvalue(),
                "0\t0.250000000000000\n"
                "1\t0.750000000000000\n"
                "2\t0.000000000000000\n",
            )
            self.assertEqual(area, 1)

    def test_summary_goes_to_selected_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory, "pdf.txt")
            pdf.write_text("0 1\n1 0\n", encoding="utf-8")
            inputs = prepare_inputs(["1/1", str(pdf)])
            summary = io.StringIO()

            with contextlib.redirect_stdout(io.StringIO()):
                print_summary(inputs, summary)

            self.assertIn("1/1", summary.getvalue())
            self.assertIn("Total weight: 1", summary.getvalue())

    def test_mismatched_coordinate_grids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory, "first.txt")
            second = Path(directory, "second.txt")
            first.write_text("0 1\n1 0\n", encoding="utf-8")
            second.write_text("0 1\n2 0\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "grid does not match"):
                prepare_inputs(["1/2", str(first), "1/2", str(second)])


if __name__ == "__main__":
    unittest.main()
