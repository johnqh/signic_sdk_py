"""Tests for SignicClient — mirrors client.test.ts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from signic_sdk import SignicClient, SignicClientConfig
from signic_sdk.errors import SignicAuthError
from tests.conftest import TEST_ADDRESS, TEST_PRIVATE_KEY, add_connect_mocks, make_client

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


class TestConstructor:
    def test_derives_correct_address_from_private_key(self) -> None:
        client = make_client()
        assert client.get_address() == TEST_ADDRESS

    def test_uses_default_email_domain(self) -> None:
        client = make_client()
        assert client.get_email_address() == f"{TEST_ADDRESS}@signic.email"

    def test_respects_custom_email_domain(self) -> None:
        client = SignicClient(
            SignicClientConfig(
                private_key=TEST_PRIVATE_KEY,
                indexer_url="https://indexer.test",
                wildduck_url="https://api.test",
                email_domain="custom.email",
            )
        )
        assert client.get_email_address() == f"{TEST_ADDRESS}@custom.email"

    def test_strips_trailing_slashes_from_urls(self) -> None:
        client = SignicClient(
            SignicClientConfig(
                private_key=TEST_PRIVATE_KEY,
                indexer_url="https://indexer.test///",
                wildduck_url="https://api.test/",
            )
        )
        assert client.get_address() == TEST_ADDRESS


class TestIsConnected:
    def test_returns_false_before_connect(self) -> None:
        client = make_client()
        assert client.is_connected() is False


class TestGetUnreadEmailsBeforeConnect:
    async def test_raises_auth_error(self) -> None:
        client = make_client()
        with pytest.raises(SignicAuthError):
            await client.get_unread_emails()


class TestGetEmailBeforeConnect:
    async def test_raises_auth_error(self) -> None:
        client = make_client()
        with pytest.raises(SignicAuthError):
            await client.get_email(1)


class TestMarkAsReadBeforeConnect:
    async def test_raises_auth_error(self) -> None:
        client = make_client()
        with pytest.raises(SignicAuthError):
            await client.mark_as_read(1)


class TestConnect:
    async def test_authenticates_through_full_siwe_flow(self, httpx_mock: HTTPXMock) -> None:
        client = make_client()
        add_connect_mocks(httpx_mock)
        await client.connect()

        assert client.is_connected() is True

        requests = httpx_mock.get_requests()
        assert len(requests) == 4

        # Step 1: SIWE message request
        siwe_req = requests[0]
        assert "/wallets/" in str(siwe_req.url)
        assert "/message?" in str(siwe_req.url)

        # Step 2: wallet accounts request has auth headers
        accounts_req = requests[1]
        assert "/accounts" in str(accounts_req.url)
        assert accounts_req.headers.get("x-signature") is not None
        assert accounts_req.headers.get("x-message") is not None
        assert accounts_req.headers.get("x-signer") == TEST_ADDRESS

        # Step 3: WildDuck authenticate is POST
        auth_req = requests[2]
        assert "/authenticate" in str(auth_req.url)
        assert auth_req.method == "POST"

        # Step 4: mailboxes request has Bearer token
        mailbox_req = requests[3]
        assert "/mailboxes" in str(mailbox_req.url)
        assert mailbox_req.headers.get("authorization") == "Bearer access-token-xyz"


class TestGetUnreadEmailsAfterConnect:
    async def test_fetches_unread_emails_and_maps_them(
        self, connected_client: SignicClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            json={
                "success": True,
                "total": 1,
                "page": 1,
                "previousCursor": False,
                "nextCursor": False,
                "results": [
                    {
                        "id": 42,
                        "mailbox": "inbox-id-1",
                        "thread": "t1",
                        "from": {"address": "sender@test.com", "name": "Sender"},
                        "to": [{"address": TEST_ADDRESS, "name": ""}],
                        "subject": "Hello",
                        "date": "2026-03-31T00:00:00Z",
                        "intro": "Preview text",
                        "attachments": False,
                        "seen": False,
                        "flagged": False,
                        "size": 1024,
                    }
                ],
            },
        )

        result = await connected_client.get_unread_emails()

        assert result.total == 1
        assert len(result.emails) == 1

        email = result.emails[0]
        assert email.id == 42
        assert email.mailbox_id == "inbox-id-1"
        assert email.from_.address == "sender@test.com"
        assert email.from_.name == "Sender"
        assert email.to[0].address == TEST_ADDRESS
        assert email.subject == "Hello"
        assert email.date == "2026-03-31T00:00:00Z"
        assert email.intro == "Preview text"
        assert email.seen is False
        assert email.has_attachments is False

        # Verify unseen=true is in the URL (the 5th request, after 4 connect mocks)
        request = httpx_mock.get_requests()[-1]
        assert "unseen=true" in str(request.url)
        assert "limit=50" in str(request.url)

    async def test_respects_custom_limit(
        self, connected_client: SignicClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            json={
                "success": True,
                "total": 0,
                "page": 1,
                "previousCursor": False,
                "nextCursor": False,
                "results": [],
            },
        )

        await connected_client.get_unread_emails(10)

        request = httpx_mock.get_requests()[-1]
        assert "limit=10" in str(request.url)


class TestGetEmailAfterConnect:
    async def test_fetches_full_email_detail(
        self, connected_client: SignicClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            json={
                "success": True,
                "id": 42,
                "mailbox": "inbox-id-1",
                "user": "user123",
                "thread": "t1",
                "from": {"address": "sender@test.com", "name": "Sender"},
                "to": [{"address": TEST_ADDRESS, "name": ""}],
                "cc": [],
                "bcc": [],
                "subject": "Hello",
                "messageId": "<msg-1@test.com>",
                "date": "2026-03-31T00:00:00Z",
                "idate": "2026-03-31T00:00:01Z",
                "size": 2048,
                "seen": False,
                "flagged": True,
                "deleted": False,
                "draft": False,
                "answered": False,
                "forwarded": False,
                "html": ["<p>Hello</p>"],
                "text": "Hello",
                "attachments": [],
            },
        )

        detail = await connected_client.get_email(42)

        assert detail.id == 42
        assert detail.mailbox_id == "inbox-id-1"
        assert detail.thread == "t1"
        assert detail.from_.address == "sender@test.com"
        assert detail.subject == "Hello"
        assert detail.message_id == "<msg-1@test.com>"
        assert detail.html == ["<p>Hello</p>"]
        assert detail.text == "Hello"
        assert detail.flagged is True
        assert detail.seen is False

    async def test_uses_custom_mailbox_id(
        self, connected_client: SignicClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            json={
                "success": True,
                "id": 99,
                "mailbox": "custom-mailbox",
                "user": "user123",
                "thread": "t2",
                "from": {"address": "a@b.com", "name": ""},
                "to": [],
                "cc": [],
                "bcc": [],
                "subject": "Test",
                "messageId": "<msg-2@test.com>",
                "date": "2026-04-01T00:00:00Z",
                "idate": "2026-04-01T00:00:01Z",
                "size": 512,
                "seen": True,
                "flagged": False,
                "deleted": False,
                "draft": False,
                "answered": False,
                "forwarded": False,
                "html": [],
                "text": "",
                "attachments": [],
            },
        )

        await connected_client.get_email(99, "custom-mailbox")

        request = httpx_mock.get_requests()[-1]
        assert "/mailboxes/custom-mailbox/messages/99" in str(request.url)


class TestMarkAsReadAfterConnect:
    async def test_sends_put_with_seen_true(
        self, connected_client: SignicClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(json={"success": True, "updated": 1})

        result = await connected_client.mark_as_read(42)

        assert result.success is True
        assert result.updated == 1

        request = httpx_mock.get_requests()[-1]
        assert "/messages/42" in str(request.url)
        assert request.method == "PUT"
        assert json.loads(request.content) == {"seen": True}

    async def test_uses_custom_mailbox_id(
        self, connected_client: SignicClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(json={"success": True, "updated": 1})

        await connected_client.mark_as_read(99, "custom-mailbox")

        request = httpx_mock.get_requests()[-1]
        assert "/mailboxes/custom-mailbox/messages/99" in str(request.url)
