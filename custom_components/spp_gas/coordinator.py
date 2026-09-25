"""Data coordinator for SPP Gas."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SppGasApiClient, SppGasError, SppGasReading
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_POINT_ID,
    CONF_USERNAME,
    DOMAIN,
    UPDATE_INTERVAL,
)

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
        self.client = SppGasApiClient(
            async_get_clientsession(hass),
            username=entry.data.get(CONF_USERNAME),
            password=entry.data.get(CONF_PASSWORD),
            access_token=entry.data.get(CONF_ACCESS_TOKEN),
        )

    async def _async_update_data(self) -> SppGasReading | None:
        try:
            return await self.client.async_get_latest_reading(
                self.entry.data[CONF_POINT_ID]
            )
        except SppGasError as err:
            raise UpdateFailed(str(err)) from err
