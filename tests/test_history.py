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

from custom_components.spp_gas.history import build_historical_points  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
