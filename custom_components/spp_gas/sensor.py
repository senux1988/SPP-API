"""Sensor platform for SPP Gas."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_POINT_ID, CONF_POINT_NAME, CONF_POINT_POD, DOMAIN
from .coordinator import SppGasCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SPP Gas sensors."""
    coordinator: SppGasCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SppGasTotalReadingSensor(coordinator)])


class SppGasTotalReadingSensor(CoordinatorEntity[SppGasCoordinator], SensorEntity):
    """Latest total gas meter reading."""

    _attr_device_class = SensorDeviceClass.GAS
    _attr_has_entity_name = True
    _attr_name = "Gas meter reading"
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: SppGasCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        point_id = entry.data[CONF_POINT_ID]
        self._attr_unique_id = f"{DOMAIN}_{point_id}_total_reading"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, point_id)},
            "manufacturer": "SPP - distribucia",
            "name": entry.data.get(CONF_POINT_NAME, "SPP gas point"),
            "model": entry.data.get(CONF_POINT_POD),
        }

    @property
    def native_value(self) -> float | None:
        """Return the latest meter value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return reading metadata."""
        reading = self.coordinator.data
        if reading is None:
            return {}
        return {
            "reading_date": reading.date,
            "meter": reading.meter,
            "last_period_consumption_m3": reading.consumption,
            "historical_statistics_id": self.coordinator.statistic_id,
            "imported_readings": self.coordinator.imported_readings,
        }
