"""Config flow for SPP Gas."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SppGasApiClient,
    SppGasAuthError,
    SppGasConnectionError,
    SppGasError,
)
from .const import (
    CONF_POINT_ID,
    CONF_POINT_NAME,
    CONF_POINT_POD,
    DOMAIN,
)
from .models import SppGasPoint

_LOGGER = logging.getLogger(__name__)


class SppGasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the SPP Gas config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._auth_data: dict[str, Any] = {}
        self._points: list[SppGasPoint] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for credentials and fetch delivery points."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._auth_data = {
                key: value
                for key, value in user_input.items()
                if value not in (None, "")
            }
            client = SppGasApiClient(
                async_get_clientsession(self.hass),
                username=self._auth_data.get(CONF_USERNAME),
                password=self._auth_data.get(CONF_PASSWORD),
            )
            try:
                self._points = await client.async_get_points()
            except SppGasAuthError as err:
                _LOGGER.warning("SPP authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except SppGasConnectionError as err:
                _LOGGER.warning("SPP connection failed: %s", err)
                errors["base"] = "cannot_connect"
            except SppGasError as err:
                _LOGGER.warning("SPP setup request failed: %s", err)
                errors["base"] = "api_error"
            except Exception:
                _LOGGER.exception("Unexpected error while configuring SPP Gas")
                errors["base"] = "unknown"
            else:
                if not self._points:
                    errors["base"] = "no_points"
                elif len(self._points) == 1:
                    return await self._create_entry(self._points[0])
                else:
                    return await self.async_step_point()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_point(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user choose a delivery point."""
        if user_input is not None:
            point = next(
                point
                for point in self._points
                if point.id == user_input[CONF_POINT_ID]
            )
            return await self._create_entry(point)

        return self.async_show_form(
            step_id="point",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POINT_ID): vol.In(
                        {point.id: point.label for point in self._points}
                    )
                }
            ),
        )

    async def _create_entry(
        self, point: SppGasPoint
    ) -> config_entries.ConfigFlowResult:
        await self.async_set_unique_id(point.id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=point.label,
            data={
                **self._auth_data,
                CONF_POINT_ID: point.id,
                CONF_POINT_NAME: point.name,
                CONF_POINT_POD: point.pod,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return SppGasOptionsFlow()


class SppGasOptionsFlow(config_entries.OptionsFlow):
    """Options flow placeholder."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.OptionsFlowResult:
        return self.async_create_entry(title="", data={})
