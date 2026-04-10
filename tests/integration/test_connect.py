"""Integration tests that hit real Signic endpoints.

These tests are skipped unless all required environment variables are set:
- SIGNIC_PRIVATE_KEY: EVM private key (hex, 0x-prefixed)
- SIGNIC_INDEXER_URL: Indexer API base URL
- SIGNIC_WILDDUCK_URL: WildDuck API base URL

Run with: pytest -m integration
"""

from __future__ import annotations

import os

import pytest

from signic_sdk import SignicClient, SignicClientConfig

_PRIVATE_KEY = os.environ.get("SIGNIC_PRIVATE_KEY", "")
_INDEXER_URL = os.environ.get("SIGNIC_INDEXER_URL", "")
_WILDDUCK_URL = os.environ.get("SIGNIC_WILDDUCK_URL", "")

_SKIP_REASON = "Set SIGNIC_PRIVATE_KEY, SIGNIC_INDEXER_URL, and SIGNIC_WILDDUCK_URL to run"
_HAS_ENV = bool(_PRIVATE_KEY and _INDEXER_URL and _WILDDUCK_URL)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _HAS_ENV, reason=_SKIP_REASON),
]


@pytest.fixture
def client() -> SignicClient:
    return SignicClient(
        SignicClientConfig(
            private_key=_PRIVATE_KEY,
            indexer_url=_INDEXER_URL,
            wildduck_url=_WILDDUCK_URL,
        )
    )


class TestRealConnect:
    async def test_connect_and_fetch_emails(self, client: SignicClient) -> None:
        """End-to-end: connect via SIWE and fetch unread emails."""
        async with client:
            assert client.is_connected() is False

            await client.connect()

            assert client.is_connected() is True
            assert client.get_address().startswith("0x")
            assert "@" in client.get_email_address()

            result = await client.get_unread_emails(5)
            assert result.total >= 0
            assert isinstance(result.emails, list)
