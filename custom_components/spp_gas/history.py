"""Convert SPP readings to Home Assistant historical statistic points."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
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
    ordered = _ordered_readings(readings)
    if not ordered:
        return []

    points: list[SppGasHistoricalPoint] = []
    cumulative_sum = 0.0
    previous: SppGasReading | None = None

    for reading_date, reading in ordered:
        if previous is not None:
            cumulative_sum += _interval_consumption(previous, reading)

        points.append(
            SppGasHistoricalPoint(
                start=_local_midnight_utc(reading_date),
                state=reading.value,
                sum=cumulative_sum,
            )
        )
        previous = reading

    return points


def build_sampled_historical_points(
    readings: list[SppGasReading],
) -> list[SppGasHistoricalPoint]:
    """Distribute each reading interval evenly across its calendar days."""
    ordered = _ordered_readings(readings)
    if not ordered:
        return []

    first_date, first_reading = ordered[0]
    points = [
        SppGasHistoricalPoint(
            start=_local_midnight_utc(first_date),
            state=0.0,
            sum=0.0,
        )
    ]
    cumulative_sum = 0.0
    previous_date = first_date
    previous_reading = first_reading

    for reading_date, reading in ordered[1:]:
        day_count = (reading_date - previous_date).days
        interval_consumption = _interval_consumption(previous_reading, reading)
        interval_start_sum = cumulative_sum

        for day_offset in range(1, day_count + 1):
            point_date = previous_date + timedelta(days=day_offset)
            cumulative_sum = (
                interval_start_sum
                + interval_consumption * day_offset / day_count
            )
            points.append(
                SppGasHistoricalPoint(
                    start=_local_midnight_utc(point_date),
                    state=cumulative_sum,
                    sum=cumulative_sum,
                )
            )

        previous_date = reading_date
        previous_reading = reading

    return points


def _ordered_readings(
    readings: list[SppGasReading],
) -> list[tuple[date, SppGasReading]]:
    """Return readings sorted by date, keeping the last duplicate."""
    readings_by_date: dict[date, SppGasReading] = {}
    for reading in readings:
        try:
            reading_date = date.fromisoformat(reading.date[:10])
        except ValueError:
            _LOGGER.warning("Skipping SPP reading with invalid date %r", reading.date)
            continue
        readings_by_date[reading_date] = reading

    return sorted(readings_by_date.items())


def _interval_consumption(
    previous: SppGasReading, current: SppGasReading
) -> float:
    """Return consumption between two readings using the SPP fallback rules."""
    if current.consumption is not None and current.consumption >= 0:
        return current.consumption
    if current.meter == previous.meter and current.value >= previous.value:
        return current.value - previous.value
    return 0.0


def _local_midnight_utc(reading_date: date) -> datetime:
    """Convert midnight in the SPP timezone to UTC."""
    local_start = datetime.combine(reading_date, time.min, SPP_TIME_ZONE)
    return local_start.astimezone(timezone.utc)
