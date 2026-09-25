"""Tests for the SPP API authentication flow."""

from __future__ import annotations

import sys
from pathlib import Path
import ssl
from types import ModuleType
import unittest


aiohttp = ModuleType("aiohttp")


class ClientError(Exception):
    """Local stand-in for aiohttp.ClientError."""


class ClientResponseError(ClientError):
    """Local stand-in carrying the HTTP status used by the client."""

    def __init__(self, request_info: object, history: object, *, status: int) -> None:
        super().__init__(status)
        self.status = status


class ClientSession:
    """Type placeholder for aiohttp.ClientSession."""


aiohttp.ClientError = ClientError
aiohttp.ClientResponseError = ClientResponseError
aiohttp.ClientSession = ClientSession
sys.modules.setdefault("aiohttp", aiohttp)


INTEGRATION_DIR = Path(__file__).parents[1] / "custom_components" / "spp_gas"
package = ModuleType("custom_components.spp_gas")
package.__path__ = [str(INTEGRATION_DIR)]
sys.modules.setdefault("custom_components.spp_gas", package)

from custom_components.spp_gas.api import (  # noqa: E402
    API_BASE_URL,
    AUTH_TOKEN_URL,
    SppGasApiClient,
    SppGasAuthError,
    SppGasConnectionError,
)


class FakeResponse:
    """Minimal aiohttp response context manager."""

    content_type = "application/json"

    def __init__(self, payload: object, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise ClientResponseError(None, (), status=self.status)

    async def json(self, **kwargs: object) -> object:
        return self.payload


class FakeSession:
    """Return queued responses and record request arguments."""

    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append((method, url, kwargs))
        return self.responses.pop(0)


class SppGasApiClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_login_exchanges_oauth_token_and_fetches_points(self) -> None:
        session = FakeSession(
            FakeResponse({"access_token": "oauth-token"}),
            FakeResponse({"access_token": "api-token"}),
            FakeResponse(
                {
                    "data": [
                        {
                            "id": "point-id",
                            "name": "Home",
                            "pod": "POD-1",
                            "address": {"city": "Bratislava"},
                            "meters": [{"number": "123"}],
                        }
                    ]
                }
            ),
        )
        client = SppGasApiClient(
            session, username="USER@example.com", password="secret"
        )

        points = await client.async_get_points()

        self.assertEqual([point.id for point in points], ["point-id"])
        self.assertEqual(session.requests[0][1], AUTH_TOKEN_URL)
        self.assertEqual(session.requests[0][2]["data"]["grant_type"], "password")
        ssl_context = session.requests[0][2]["ssl"]
        self.assertIsInstance(ssl_context, ssl.SSLContext)
        self.assertTrue(ssl_context.check_hostname)
        self.assertEqual(ssl_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(session.requests[1][1], f"{API_BASE_URL}/login-web")
        self.assertEqual(
            session.requests[1][2]["json"]["access_token"], "oauth-token"
        )
        self.assertTrue(
            session.requests[1][2]["json"]["fcm_token"].startswith(
                "home-assistant:"
            )
        )
        self.assertEqual(
            session.requests[2][2]["headers"]["Authorization"],
            "Bearer api-token",
        )

    async def test_oauth_validation_error_is_an_auth_error(self) -> None:
        session = FakeSession(FakeResponse({}, status=400))
        client = SppGasApiClient(
            session, username="user@example.com", password="wrong"
        )

        with self.assertRaises(SppGasAuthError):
            await client.async_login()

    async def test_expired_api_token_triggers_one_new_login(self) -> None:
        session = FakeSession(
            FakeResponse({"access_token": "oauth-token-1"}),
            FakeResponse({"access_token": "api-token-1"}),
            FakeResponse({}, status=401),
            FakeResponse({"access_token": "oauth-token-2"}),
            FakeResponse({"access_token": "api-token-2"}),
            FakeResponse({"data": []}),
        )
        client = SppGasApiClient(
            session, username="user@example.com", password="secret"
        )

        self.assertEqual(await client.async_get_points(), [])
        self.assertEqual(
            session.requests[-1][2]["headers"]["Authorization"],
            "Bearer api-token-2",
        )

    async def test_connection_failure_has_specific_error_type(self) -> None:
        class FailingSession:
            def request(self, method: str, url: str, **kwargs: object) -> None:
                raise ClientError("DNS lookup failed")

        client = SppGasApiClient(
            FailingSession(), username="user@example.com", password="secret"
        )

        with self.assertRaisesRegex(SppGasConnectionError, AUTH_TOKEN_URL):
            await client.async_login()


if __name__ == "__main__":
    unittest.main()
