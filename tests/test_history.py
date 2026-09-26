"""Tests for converting SPP readings to historical statistics."""

from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path
from types import ModuleType
import unittest


INTEGRATION_DIR = Path(__file__).parents[1] / "custom_components" / "spp_gas"
package = ModuleType("custom_components.spp_gas")
package.__path__ = [str(INTEGRATION_DIR)]
sys.modules.setdefault("custom_components.spp_gas", package)

from custom_components.spp_gas.history import (  # noqa: E402
    build_historical_points,
    build_sampled_historical_points,
)
from custom_components.spp_gas.models import SppGasReading  # noqa: E402


def reading(
    reading_date: str,
    value: float,
    consumption: float | None,
    meter: str = "meter-1",
) -> SppGasReading:
    return SppGasReading(
        date=reading_date,
        value=value,
        consumption=consumption,
        meter=meter,
        raw={},
    )


class HistoricalPointsTest(unittest.TestCase):
    def test_builds_monotonic_sum_and_uses_meter_difference_as_fallback(self) -> None:
        points = build_historical_points(
            [
                reading("2024-01-01", 100, 12),
                reading("2024-02-01", 110, 10),
                reading("2024-03-01", 125, None),
                reading("2024-04-01", 5, 5, meter="meter-2"),
            ]
        )

        self.assertEqual([point.state for point in points], [100, 110, 125, 5])
        self.assertEqual([point.sum for point in points], [0, 10, 25, 30])
        self.assertEqual(
            points[0].start,
            datetime(2023, 12, 31, 23, tzinfo=timezone.utc),
        )

    def test_deduplicates_dates_and_skips_invalid_dates(self) -> None:
        points = build_historical_points(
            [
                reading("invalid", 50, 5),
                reading("2024-07-01", 100, 0),
                reading("2024-07-01", 101, 0),
            ]
        )

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].state, 101)
        self.assertEqual(
            points[0].start,
            datetime(2024, 6, 30, 22, tzinfo=timezone.utc),
        )

    def test_distributes_interval_evenly_across_calendar_days(self) -> None:
        points = build_sampled_historical_points(
            [
                reading("2024-01-01", 100, 0),
                reading("2024-01-04", 130, 30),
            ]
        )

        self.assertEqual([point.sum for point in points], [0, 10, 20, 30])
        self.assertEqual([point.state for point in points], [0, 10, 20, 30])
        self.assertEqual(
            [point.start for point in points],
            [
                datetime(2023, 12, 31, 23, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 23, tzinfo=timezone.utc),
                datetime(2024, 1, 2, 23, tzinfo=timezone.utc),
                datetime(2024, 1, 3, 23, tzinfo=timezone.utc),
            ],
        )

    def test_distributes_multiple_intervals_without_rounding(self) -> None:
        points = build_sampled_historical_points(
            [
                reading("2024-01-01", 100, 0),
                reading("2024-01-03", 105, 5),
                reading("2024-01-06", 112, 7),
            ]
        )

        self.assertEqual(len(points), 6)
        self.assertAlmostEqual(points[1].sum, 2.5)
        self.assertAlmostEqual(points[2].sum, 5)
        self.assertAlmostEqual(points[3].sum, 5 + 7 / 3)
        self.assertAlmostEqual(points[4].sum, 5 + 14 / 3)
        self.assertAlmostEqual(points[5].sum, 12)

    def test_sampled_points_use_fallback_and_handle_meter_replacement(self) -> None:
        points = build_sampled_historical_points(
            [
                reading("2024-01-01", 100, 0),
                reading("2024-01-03", 106, None),
                reading("2024-01-05", 2, None, meter="meter-2"),
                reading("2024-01-07", 8, 6, meter="meter-2"),
            ]
        )

        self.assertEqual([point.sum for point in points], [0, 3, 6, 6, 6, 9, 12])

    def test_sampled_points_deduplicate_and_stop_at_last_reading(self) -> None:
        points = build_sampled_historical_points(
            [
                reading("invalid", 50, 5),
                reading("2024-07-01", 100, 0),
                reading("2024-07-01", 101, 0),
                reading("2024-07-03", 105, 4),
            ]
        )

        self.assertEqual(len(points), 3)
        self.assertEqual(points[-1].sum, 4)
        self.assertEqual(
            points[-1].start,
            datetime(2024, 7, 2, 22, tzinfo=timezone.utc),
        )

    def test_sampled_points_follow_local_midnight_across_dst(self) -> None:
        points = build_sampled_historical_points(
            [
                reading("2024-03-30", 100, 0),
                reading("2024-04-01", 102, 2),
            ]
        )

        self.assertEqual(
            [point.start for point in points],
            [
                datetime(2024, 3, 29, 23, tzinfo=timezone.utc),
                datetime(2024, 3, 30, 23, tzinfo=timezone.utc),
                datetime(2024, 3, 31, 22, tzinfo=timezone.utc),
            ],
        )


if __name__ == "__main__":
    unittest.main()
