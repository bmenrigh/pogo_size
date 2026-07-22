#!/usr/bin/env python3
"""Look up p-values from CDF or piecewise-linear PDF/CDF tables.

Each data row contains:

    bucket_start  cumulative_at_bucket_start

For two-column input, the CDF is linearly interpolated between rows. For
three-column ``coordinate PDF CDF`` input, the PDF is linearly interpolated and
integrated, producing the corresponding quadratic CDF within each segment.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Lookup:
    """Interpolated values at one point in a distribution."""

    density: float
    cumulative: float


class CDFTable:
    """An immutable, searchable CDF table."""

    def __init__(
        self,
        starts: Sequence[float],
        cumulatives: Sequence[float],
        densities: Sequence[float] | None = None,
        survivals: Sequence[float] | None = None,
    ) -> None:
        if len(starts) != len(cumulatives):
            raise ValueError("table columns have different lengths")
        if len(starts) < 2:
            raise ValueError("table must contain at least two data rows")
        if densities is not None and len(densities) != len(starts):
            raise ValueError("table columns have different lengths")
        if survivals is not None and len(survivals) != len(starts):
            raise ValueError("table columns have different lengths")

        for row, (left, right) in enumerate(zip(starts, starts[1:]), start=2):
            if right <= left:
                raise ValueError(
                    f"bucket starts must be strictly increasing (row {row})"
                )
        for row, start in enumerate(starts, start=1):
            if not isfinite(start):
                raise ValueError(f"bucket start must be finite (row {row})")
        if densities is not None:
            for row, density in enumerate(densities, start=1):
                if not isfinite(density) or density < 0.0:
                    raise ValueError(
                        f"density must be finite and nonnegative (row {row})"
                    )
        for row, cumulative in enumerate(cumulatives, start=1):
            if not isfinite(cumulative) or cumulative < 0.0:
                raise ValueError(
                    f"cumulative value must be finite and nonnegative (row {row})"
                )
        for row, (left, right) in enumerate(
            zip(cumulatives, cumulatives[1:]), start=2
        ):
            if right < left:
                raise ValueError(
                    f"cumulative values must be nondecreasing (row {row})"
                )
        if survivals is not None:
            for row, survival in enumerate(survivals, start=1):
                if not isfinite(survival) or survival < 0.0:
                    raise ValueError(
                        f"survival value must be finite and nonnegative (row {row})"
                    )
            for row, (left, right) in enumerate(
                zip(survivals, survivals[1:]), start=2
            ):
                if right > left:
                    raise ValueError(
                        f"survival values must be nonincreasing (row {row})"
                    )

        self.starts = tuple(starts)
        self.cumulatives = tuple(cumulatives)
        self.densities = tuple(densities) if densities is not None else None
        self.survivals = tuple(survivals) if survivals is not None else None

    @classmethod
    def from_lines(cls, lines: Iterable[str]) -> "CDFTable":
        starts: list[float] = []
        cumulatives: list[float] = []
        densities: list[float] | None = None
        survivals: list[float] | None = None
        column_count: int | None = None
        survival_format = False

        for line_number, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if line == "# cdf-survival-v1":
                    survival_format = True
                continue

            columns = line.split()
            if len(columns) not in (2, 3):
                raise ValueError(
                    f"line {line_number}: expected 2 or 3 columns, "
                    f"found {len(columns)}"
                )
            if column_count is None:
                column_count = len(columns)
                if column_count == 3:
                    if survival_format:
                        survivals = []
                    else:
                        densities = []
            elif len(columns) != column_count:
                raise ValueError(
                    f"line {line_number}: cannot mix 2- and 3-column rows"
                )
            try:
                start = float(columns[0])
                if len(columns) == 3 and survival_format:
                    cumulative = float(columns[1])
                    survival = float(columns[2])
                    density = None
                else:
                    cumulative = float(columns[-1])
                    density = float(columns[1]) if len(columns) == 3 else None
                    survival = None
            except ValueError as error:
                raise ValueError(
                    f"line {line_number}: table columns must be numbers"
                ) from error

            starts.append(start)
            cumulatives.append(cumulative)
            if densities is not None and density is not None:
                densities.append(density)
            if survivals is not None and survival is not None:
                survivals.append(survival)

        return cls(starts, cumulatives, densities, survivals)

    @classmethod
    def from_path(cls, path: str | Path) -> "CDFTable":
        with Path(path).open(encoding="utf-8") as table_file:
            return cls.from_lines(table_file)

    @property
    def total_probability(self) -> float:
        return self.cumulatives[-1]

    def lookup(self, value: float) -> Lookup:
        """Interpolate the CDF and derive its constant slope in the bucket."""
        if not isfinite(value):
            raise ValueError("lookup value must be finite")
        if value < self.starts[0]:
            return Lookup(density=0.0, cumulative=0.0)
        if value >= self.starts[-1]:
            density = (
                self.densities[-1]
                if value == self.starts[-1] and self.densities is not None
                else 0.0
            )
            return Lookup(density=density, cumulative=self.total_probability)

        bucket = bisect_right(self.starts, value) - 1
        left = self.starts[bucket]
        right = self.starts[bucket + 1]
        width = right - left
        offset = value - left
        fraction = offset / width

        bucket_probability = self.cumulatives[bucket + 1] - self.cumulatives[bucket]
        if self.densities is None:
            density = bucket_probability / width
            cumulative = self.cumulatives[bucket] + fraction * bucket_probability
        else:
            left_density = self.densities[bucket]
            right_density = self.densities[bucket + 1]
            density = left_density + fraction * (right_density - left_density)
            partial_area = offset * (left_density + density) / 2.0
            full_area = width * (left_density + right_density) / 2.0
            if full_area > 0.0:
                cumulative = self.cumulatives[bucket] + bucket_probability * (
                    partial_area / full_area
                )
            else:
                cumulative = self.cumulatives[bucket] + fraction * bucket_probability
        return Lookup(density=density, cumulative=cumulative)

    def p_value(self, value: float, *, upper_tail: bool = False) -> float:
        if not isfinite(value):
            raise ValueError("lookup value must be finite")
        if upper_tail and self.survivals is not None:
            if value < self.starts[0]:
                return self.survivals[0]
            if value >= self.starts[-1]:
                return self.survivals[-1]
            bucket = bisect_right(self.starts, value) - 1
            fraction = (value - self.starts[bucket]) / (
                self.starts[bucket + 1] - self.starts[bucket]
            )
            return self.survivals[bucket] + fraction * (
                self.survivals[bucket + 1] - self.survivals[bucket]
            )
        cumulative = self.lookup(value).cumulative
        if upper_tail:
            return max(0.0, self.total_probability - cumulative)
        return cumulative


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Look up p-values in a two-column bucket/CDF table using linear "
            "CDF interpolation, or a three-column PDF/CDF control-point table "
            "using integrated linear-PDF interpolation."
        )
    )
    parser.add_argument("table", type=Path, help="path to the PDF/CDF table")
    parser.add_argument("values", metavar="VALUE", type=float, nargs="+")
    parser.add_argument(
        "--upper-tail",
        action="store_true",
        help="print total probability minus the lower-tail CDF",
    )
    parser.add_argument(
        "--show-density",
        action="store_true",
        help="also print the bucket density derived from the CDF slope",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        table = CDFTable.from_path(args.table)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    for value in args.values:
        result = table.lookup(value)
        p_value = table.p_value(value, upper_tail=args.upper_tail)
        if args.show_density:
            print(f"{value:.15g}\t{p_value:.15g}\t{result.density:.15g}")
        else:
            print(f"{value:.15g}\t{p_value:.15g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
