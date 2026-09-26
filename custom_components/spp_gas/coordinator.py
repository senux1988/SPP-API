"""Data coordinator for SPP Gas."""

from __future__ import annotations

import logging
import re

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_conversion import VolumeConverter

from .api import SppGasApiClient, SppGasError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_POINT_ID,
    CONF_POINT_NAME,
    CONF_USERNAME,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .history import (
    SppGasHistoricalPoint,
    build_historical_points,
    build_sampled_historical_points,
)
from .models import SppGasReading

_LOGGER = logging.getLogger(__name__)


class SppGasCoordinator(DataUpdateCoordinator[SppGasReading | None]):
    """Coordinator that fetches the latest SPP reading."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        point_slug = re.sub(
            r"[^a-z0-9_]+", "_", entry.data[CONF_POINT_ID].lower()
        ).strip("_")
        self.statistic_id = f"{DOMAIN}:{point_slug}_gas_consumption"
        self.sampled_statistic_id = f"{self.statistic_id}_vzorkovana"
        self.imported_readings = 0
        self.imported_sampled_readings = 0
        self.client = SppGasApiClient(
            async_get_clientsession(hass),
            username=entry.data.get(CONF_USERNAME),
            password=entry.data.get(CONF_PASSWORD),
            access_token=entry.data.get(CONF_ACCESS_TOKEN),
        )

    async def _async_update_data(self) -> SppGasReading | None:
        try:
            readings = await self.client.async_get_readings(
                self.entry.data[CONF_POINT_ID]
            )
        except SppGasError as err:
            raise UpdateFailed(str(err)) from err

        self._async_import_history(readings)
        return readings[-1] if readings else None

    def _async_import_history(self, readings: list[SppGasReading]) -> None:
        """Import dated SPP readings into long-term statistics."""
        if "recorder" not in self.hass.config.components:
            _LOGGER.debug("Recorder is disabled; skipping SPP history import")
            return

        points = build_historical_points(readings)
        self.imported_readings = self._async_import_statistics(
            statistic_id=self.statistic_id,
            name=(
                f"{self.entry.data.get(CONF_POINT_NAME, 'SPP gas point')} "
                "gas consumption"
            ),
            points=points,
        )
        sampled_points = build_sampled_historical_points(readings)
        self.imported_sampled_readings = self._async_import_statistics(
            statistic_id=self.sampled_statistic_id,
            name=(
                f"{self.entry.data.get(CONF_POINT_NAME, 'SPP gas point')} "
                "gas consumption (daily average)"
            ),
            points=sampled_points,
        )

    def _async_import_statistics(
        self,
        *,
        statistic_id: str,
        name: str,
        points: list[SppGasHistoricalPoint],
    ) -> int:
        """Queue one set of external statistics for recorder import."""
        if not points:
            return 0

        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=name,
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=VolumeConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        statistics = [
            StatisticData(start=point.start, state=point.state, sum=point.sum)
            for point in points
        ]
        async_add_external_statistics(self.hass, metadata, statistics)
        _LOGGER.debug(
            "Queued %d SPP readings for statistic %s",
            len(statistics),
            statistic_id,
        )
        return len(statistics)
