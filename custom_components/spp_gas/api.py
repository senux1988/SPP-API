"""Client for SPP - distribucia gas reading API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import DEFAULT_APP_VERSION

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://moapbe.spp-distribucia.sk/api/v1"


class SppGasError(Exception):
    """Base SPP API error."""


class SppGasAuthError(SppGasError):
    """Authentication failed."""


@dataclass(frozen=True)
class SppGasPoint:
    """SPP delivery point."""

    id: str
    name: str
    pod: str | None
    address: str | None
    meter: str | None

    @property
    def label(self) -> str:
        """Return a user-friendly point label."""
        parts = [self.name]
        if self.address:
            parts.append(self.address)
        if self.pod:
            parts.append(self.pod)
        return " - ".join(part for part in parts if part)


@dataclass(frozen=True)
class SppGasReading:
    """Latest meter reading."""

    date: str
    value: float
    meter: str | None
    consumption: float | None
    raw: dict[str, Any]


class SppGasApiClient:
    """Small async API client for SPP gas readings."""

    def __init__(
        self,
        session: ClientSession,
        *,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._access_token = access_token

    async def async_login(self) -> None:
        """Authenticate and store the bearer token.

        The captured ZAP session already contained a bearer token and did not include
        the initial OIDC login exchange. These API login candidates keep auth isolated
        so the exact flow can be adjusted without touching the HA entity layer.
        """
        if self._access_token:
            return
        if not self._username or not self._password:
            raise SppGasAuthError("Missing username or password")

        payloads = (
            {"email": self._username, "password": self._password},
            {"username": self._username, "password": self._password},
        )
        paths = ("/customer/login", "/auth/login", "/login")

        last_error: Exception | None = None
        for path in paths:
            for payload in payloads:
                try:
                    response = await self._request(
                        "POST",
                        path,
                        json=payload,
                        authenticated=False,
                    )
                except SppGasError as err:
                    last_error = err
                    continue

                token = _extract_token(response)
                if token:
                    self._access_token = token
                    return

        raise SppGasAuthError(
            "SPP authentication failed; the mobile API likely uses an OIDC login flow"
        ) from last_error

    async def async_get_points(self) -> list[SppGasPoint]:
        """Return delivery points for the current account."""
        await self.async_login()
        payload = await self._request("GET", "/point")
        data = _unwrap_data(payload)
        if not isinstance(data, list):
            raise SppGasError("Unexpected points response")
        return [_parse_point(point) for point in data if isinstance(point, dict)]

    async def async_get_latest_reading(self, point_id: str) -> SppGasReading | None:
        """Return the latest reading for a point."""
        await self.async_login()
        today = date.today().isoformat()
        payload = await self._request(
            "GET",
            f"/point/{point_id}/deduction-history",
            params={"meter": "", "filter[from]": "2017-01-01", "filter[to]": today},
        )
        data = _unwrap_data(payload)
        if not isinstance(data, dict):
            raise SppGasError("Unexpected deduction history response")
        readings = data.get("list") or []
        if not isinstance(readings, list) or not readings:
            return None

        parsed = [reading for reading in readings if isinstance(reading, dict)]
        parsed.sort(key=lambda item: str(item.get("date") or ""))
        latest = parsed[-1]
        value = _as_float(latest.get("value"))
        if value is None:
            return None
        return SppGasReading(
            date=str(latest.get("date") or ""),
            value=value,
            meter=_as_str(latest.get("meter")),
            consumption=_as_float(latest.get("consumption")),
            raw=latest,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        **kwargs: Any,
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "App-platform": "app",
            "App-Version": DEFAULT_APP_VERSION,
            "Origin": "capacitor://localhost",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
            ),
        }
        if authenticated:
            if not self._access_token:
                raise SppGasAuthError("Missing access token")
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=headers,
                timeout=30,
                **kwargs,
            ) as response:
                response.raise_for_status()
                if response.content_type == "application/json":
                    return await response.json()
                return await response.json(content_type=None)
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise SppGasAuthError("SPP API rejected credentials") from err
            raise SppGasError(f"SPP API returned HTTP {err.status}") from err
        except (ClientError, TimeoutError) as err:
            raise SppGasError("Could not connect to SPP API") from err


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _extract_token(payload: Any) -> str | None:
    candidates = [payload]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            candidates.append(data)

    for item in candidates:
        if not isinstance(item, dict):
            continue
        for key in ("token", "access_token", "auth_token", "bearer", "api_token"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value.removeprefix("Bearer ").strip()
    return None


def _parse_point(point: dict[str, Any]) -> SppGasPoint:
    address = point.get("address") if isinstance(point.get("address"), dict) else {}
    address_parts = [
        address.get("street"),
        address.get("descriptive_number"),
        address.get("city"),
    ]
    meters = point.get("meters") if isinstance(point.get("meters"), list) else []
    meter = None
    if meters and isinstance(meters[0], dict):
        meter = _as_str(meters[0].get("number"))

    return SppGasPoint(
        id=str(point["id"]),
        name=str(point.get("name") or point.get("pod") or point["id"]),
        pod=_as_str(point.get("pod")),
        address=", ".join(str(part) for part in address_parts if part),
        meter=meter,
    )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        _LOGGER.debug("Unable to parse numeric value %r", value)
        return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
