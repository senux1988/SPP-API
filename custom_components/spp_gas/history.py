"""Convert SPP readings to Home Assistant historical statistic points."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import logging
from zoneinfo import ZoneInfo

from .models import SppGasReading

_LOGGER = logging.getLogger(__name__)

SPP_TIME_ZONE = ZoneInfo("Europe/Bratislava")


@dataclass(frozen=True)
class SppGasHistoricalPoint:
    """One hourly long-term statistic generated from an SPP reading."""

    start: datetime
    state: float
    sum: float


def build_historical_points(
    readings: list[SppGasReading],
) -> list[SppGasHistoricalPoint]:
    """Build ordered, monotonic statistics from dated meter readings."""
    readings_by_date: dict[date, SppGasReading] = {}
    for reading in readings:
        try:
            reading_date = date.fromisoformat(reading.date[:10])
        except ValueError:
            _LOGGER.warning("Skipping SPP reading with invalid date %r", reading.date)
            continue
        readings_by_date[reading_date] = reading

    ordered = sorted(readings_by_date.items())
    if not ordered:
        return []

    points: list[SppGasHistoricalPoint] = []
    cumulative_sum = 0.0
    previous: SppGasReading | None = None

    for reading_date, reading in ordered:
        if previous is not None:
            interval_consumption = reading.consumption
            if interval_consumption is None or interval_consumption < 0:
                if (
                    reading.meter == previous.meter
                    and reading.value >= previous.value
                ):
                    interval_consumption = reading.value - previous.value
                else:
                    interval_consumption = 0.0
            cumulative_sum += interval_consumption

        local_start = datetime.combine(reading_date, time.min, SPP_TIME_ZONE)
        points.append(
            SppGasHistoricalPoint(
                start=local_start.astimezone(timezone.utc),
                state=reading.value,
                sum=cumulative_sum,
            )
        )
        previous = reading

    return points
