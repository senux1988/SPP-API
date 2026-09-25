"""Client for SPP - distribucia gas reading API."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
import hashlib
import logging
from pathlib import Path
import ssl
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import DEFAULT_APP_VERSION
from .models import SppGasPoint, SppGasReading

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://moapbe.spp-distribucia.sk/api/v1"
AUTH_TOKEN_URL = "https://login.spp-distribucia.sk/oxauth/restv1/token"
AUTH_CLIENT_ID = "40ec5358-e8d3-4ec4-8c40-eb0cfdf8208d"
AUTH_CA_BUNDLE = (
    Path(__file__).parent / "certs" / "spp_login_ca_bundle.pem"
)


class SppGasError(Exception):
    """Base SPP API error."""


class SppGasAuthError(SppGasError):
    """Authentication failed."""


class SppGasConnectionError(SppGasError):
    """Connection to an SPP service failed."""


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
        """Authenticate with SPP and store the mobile API bearer token."""
        if self._access_token:
            return
        if not self._username or not self._password:
            raise SppGasAuthError("Missing username or password")

        oauth_response = await self._request_url(
            "POST",
            AUTH_TOKEN_URL,
            headers=self._base_headers(include_app_headers=False),
            ssl=_auth_ssl_context(),
            data={
                "grant_type": "password",
                "client_id": AUTH_CLIENT_ID,
                "client_secret": "",
                "scope": "openid",
                "username": self._username,
                "password": self._password,
            },
        )
        oauth_token = _extract_token(oauth_response)
        if not oauth_token:
            raise SppGasAuthError("SPP identity service did not return an access token")

        login_response = await self._request(
            "POST",
            "/login-web",
            authenticated=False,
            json={
                "access_token": oauth_token,
                "version": DEFAULT_APP_VERSION,
                "fcm_token": self._installation_id(),
            },
        )
        api_token = _extract_token(login_response)
        if not api_token:
            raise SppGasAuthError("SPP mobile API did not return an access token")
        self._access_token = api_token

    def _installation_id(self) -> str:
        """Return a stable, account-specific identifier required by login-web."""
        username = (self._username or "").strip().lower().encode()
        digest = hashlib.sha256(username).hexdigest()
        return f"home-assistant:{digest}"

    async def async_get_points(self) -> list[SppGasPoint]:
        """Return delivery points for the current account."""
        await self.async_login()
        payload = await self._request("GET", "/point")
        data = _unwrap_data(payload)
        if not isinstance(data, list):
            raise SppGasError("Unexpected points response")
        return [_parse_point(point) for point in data if isinstance(point, dict)]

    async def async_get_readings(self, point_id: str) -> list[SppGasReading]:
        """Return all available readings for a point, oldest first."""
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
        if not isinstance(readings, list):
            raise SppGasError("Unexpected deduction history list")

        parsed: list[SppGasReading] = []
        for raw_reading in readings:
            if not isinstance(raw_reading, dict):
                continue
            reading_date = _as_str(raw_reading.get("date"))
            value = _as_float(raw_reading.get("value"))
            if not reading_date or value is None:
                continue
            try:
                date.fromisoformat(reading_date[:10])
            except ValueError:
                _LOGGER.warning(
                    "Skipping SPP reading with invalid date %r", reading_date
                )
                continue
            parsed.append(
                SppGasReading(
                    date=reading_date,
                    value=value,
                    meter=_as_str(raw_reading.get("meter")),
                    consumption=_as_float(raw_reading.get("consumption")),
                    raw=raw_reading,
                )
            )
        parsed.sort(key=lambda reading: reading.date)
        return parsed

    async def async_get_latest_reading(self, point_id: str) -> SppGasReading | None:
        """Return the latest reading for a point."""
        readings = await self.async_get_readings(point_id)
        return readings[-1] if readings else None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        **kwargs: Any,
    ) -> Any:
        headers = self._base_headers()
        if authenticated:
            if not self._access_token:
                raise SppGasAuthError("Missing access token")
            headers["Authorization"] = f"Bearer {self._access_token}"

        url = f"{API_BASE_URL}{path}"
        try:
            return await self._request_url(
                method,
                url,
                headers=headers,
                **kwargs,
            )
        except SppGasAuthError:
            if not authenticated or not self._username or not self._password:
                raise

        self._access_token = None
        await self.async_login()
        headers["Authorization"] = f"Bearer {self._access_token}"
        return await self._request_url(method, url, headers=headers, **kwargs)

    def _base_headers(self, *, include_app_headers: bool = True) -> dict[str, str]:
        """Return headers shared with the captured mobile application."""
        headers = {
            "Accept": "application/json",
            "Origin": "capacitor://localhost",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
            ),
        }
        if include_app_headers:
            headers["App-platform"] = "app"
            headers["App-Version"] = DEFAULT_APP_VERSION
        return headers

    async def _request_url(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        **kwargs: Any,
    ) -> Any:
        """Send a request and normalize SPP API failures."""
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                timeout=30,
                **kwargs,
            ) as response:
                response.raise_for_status()
                if response.content_type == "application/json":
                    return await response.json()
                return await response.json(content_type=None)
        except ClientResponseError as err:
            is_login_request = url == AUTH_TOKEN_URL or url.endswith("/login-web")
            if err.status in (401, 403) or (
                is_login_request and err.status in (400, 422)
            ):
                raise SppGasAuthError("SPP API rejected credentials") from err
            raise SppGasError(
                f"SPP API returned HTTP {err.status} for {url}"
            ) from err
        except (ClientError, TimeoutError) as err:
            raise SppGasConnectionError(
                f"Could not connect to {url}: {err}"
            ) from err


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


@lru_cache(maxsize=1)
def _auth_ssl_context() -> ssl.SSLContext:
    """Build a verified context with the CA chain omitted by SPP's server."""
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=str(AUTH_CA_BUNDLE))
    return context


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
