"""Shared fixtures and constants for Signic SDK tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from signic_sdk import SignicClient, SignicClientConfig

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock

# Hardhat account #0 — same test key as the TypeScript SDK tests
TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TEST_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def make_client(
    *,
    indexer_url: str = "https://indexer.test",
    wildduck_url: str = "https://api.test",
    email_domain: str = "signic.email",
) -> SignicClient:
    """Create a SignicClient with test credentials."""
    return SignicClient(
        SignicClientConfig(
            private_key=TEST_PRIVATE_KEY,
            indexer_url=indexer_url,
            wildduck_url=wildduck_url,
            email_domain=email_domain,
        )
    )


def add_connect_mocks(httpx_mock: HTTPXMock) -> None:
    """Add the 4 sequential HTTP responses needed for a successful connect() call.

    Order: SIWE message, wallet accounts, WildDuck auth, mailbox list.
    """
    # Step 1: Indexer returns SIWE message
    httpx_mock.add_response(
        json={
            "success": True,
            "data": {
                "walletAddress": TEST_ADDRESS,
                "chainType": "evm",
                "message": "Sign in with Ethereum",
                "chainId": 1,
            },
            "timestamp": "2026-01-01T00:00:00Z",
        },
    )
    # Step 2: Indexer returns wallet accounts
    httpx_mock.add_response(
        json={
            "success": True,
            "data": {
                "accounts": [
                    {
                        "walletAddress": TEST_ADDRESS,
                        "chainType": "evm",
                        "names": [{"name": "test", "entitled": True}],
                    }
                ],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        },
    )
    # Step 3: WildDuck authenticate
    httpx_mock.add_response(
        json={
            "success": True,
            "id": "user123",
            "username": TEST_ADDRESS,
            "token": "access-token-xyz",
        },
    )
    # Step 4: WildDuck get mailboxes
    httpx_mock.add_response(
        json={
            "success": True,
            "results": [
                {
                    "id": "inbox-id-1",
                    "name": "INBOX",
                    "path": "INBOX",
                    "specialUse": "\\Inbox",
                    "modifyIndex": 1,
                    "subscribed": True,
                    "hidden": False,
                    "total": 10,
                    "unseen": 3,
                }
            ],
        },
    )


@pytest.fixture
async def connected_client(httpx_mock: HTTPXMock) -> SignicClient:
    """Return a SignicClient that has already completed the connect() flow.

    Uses mocked HTTP responses. After this fixture runs, all connect mocks
    have been consumed and the mock is ready for additional responses.
    """
    client = make_client()
    add_connect_mocks(httpx_mock)
    await client.connect()
    return client
