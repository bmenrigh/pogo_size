#!/usr/bin/env python3
"""Look up p-values in a marked-tail cdf-poly piecewise-polynomial table."""

from __future__ import annotations

import argparse
import math
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Segment:
    kind: str
    basis: str
    start: float
    end: float
    coefficients: tuple[float, ...]

    def evaluate(self, value: float) -> float:
        t = (value - self.start) / (self.end - self.start)
        if self.basis == "endpoint-q":
            correction = self.coefficients[-1]
            for coefficient in self.coefficients[-2:1:-1]:
                correction = correction * t + coefficient
            return (
                (1.0 - t) * self.coefficients[0]
                + t * self.coefficients[1]
                + t * (1.0 - t) * correction
            )
        result = self.coefficients[-1]
        for coefficient in self.coefficients[-2::-1]:
            result = result * t + coefficient
        return result


class PolynomialCDF:
    def __init__(self, segments: Sequence[Segment]) -> None:
        if not segments:
            raise ValueError("polynomial CDF must contain at least one segment")
        previous: Segment | None = None
        for row, segment in enumerate(segments, start=1):
            if segment.kind not in ("C", "S"):
                raise ValueError(f"segment kind must be C or S (row {row})")
            if segment.basis not in ("power", "endpoint-q"):
                raise ValueError(f"unknown polynomial basis (row {row})")
            if not (
                math.isfinite(segment.start)
                and math.isfinite(segment.end)
                and segment.end > segment.start
                and all(math.isfinite(value) for value in segment.coefficients)
            ):
                raise ValueError(f"invalid polynomial segment (row {row})")
            if len(segment.coefficients) != 6:
                raise ValueError(f"expected 6 coefficients (row {row})")
            if previous is not None and segment.start != previous.end:
                raise ValueError(f"segments must be contiguous (row {row})")
            previous = segment

        self.segments = tuple(segments)
        self.starts = tuple(segment.start for segment in segments)

    @classmethod
    def from_lines(cls, lines: Iterable[str]) -> "PolynomialCDF":
        segments: list[Segment] = []
        basis = "power"
        for line_number, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if line.startswith("# cdf-poly-v3"):
                    basis = "endpoint-q"
                continue
            columns = line.split()
            if len(columns) not in (8, 9):
                raise ValueError(
                    f"line {line_number}: expected 8 or 9 columns, "
                    f"found {len(columns)}"
                )
            try:
                if len(columns) == 9:
                    kind = columns[0]
                    numbers = tuple(map(float, columns[1:]))
                else:
                    kind = "C"  # Backward-compatible cdf-poly-v1 row.
                    numbers = tuple(map(float, columns))
            except ValueError as error:
                raise ValueError(
                    f"line {line_number}: all columns must be numbers"
                ) from error
            segments.append(
                Segment(kind, basis, numbers[0], numbers[1], numbers[2:])
            )
        return cls(segments)

    @classmethod
    def from_path(cls, path: str | Path) -> "PolynomialCDF":
        with Path(path).open(encoding="utf-8") as input_file:
            return cls.from_lines(input_file)

    def lookup_tails(self, value: float) -> tuple[float, float]:
        if not math.isfinite(value):
            raise ValueError("lookup value must be finite")
        if value < self.segments[0].start:
            return 0.0, 1.0
        if value >= self.segments[-1].end:
            return 1.0, 0.0

        index = bisect_right(self.starts, value) - 1
        segment = self.segments[index]
        stored_tail = min(1.0, max(0.0, segment.evaluate(value)))
        if segment.kind == "C":
            return stored_tail, max(0.0, 1.0 - stored_tail)
        return max(0.0, 1.0 - stored_tail), stored_tail

    def lookup(self, value: float) -> float:
        return self.lookup_tails(value)[0]

    def p_value(self, value: float, *, upper_tail: bool = False) -> float:
        lower, upper = self.lookup_tails(value)
        return upper if upper_tail else lower


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Look up p-values in a cdf-poly compressed tail table."
    )
    parser.add_argument("table", type=Path, help="polynomial CDF path")
    parser.add_argument("values", metavar="VALUE", type=float, nargs="+")
    parser.add_argument(
        "--upper-tail",
        action="store_true",
        help="print the upper-tail survival probability",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        table = PolynomialCDF.from_path(args.table)
        for value in args.values:
            print(f"{value:.15g}\t{table.p_value(value, upper_tail=args.upper_tail):.15g}")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
