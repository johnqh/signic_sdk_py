"""Main client for the Signic decentralized email platform.

Authenticates via SIWE (Sign-In with Ethereum) through a two-service flow:

1. **Indexer API** -- generates and verifies the SIWE message
2. **WildDuck API** -- issues an access token and serves email data

Call :meth:`SignicClient.connect` before using any email methods. Methods that
require authentication will raise :class:`~signic_sdk.errors.SignicAuthError`
if called before connect.

Example::

    from signic_sdk import SignicClient, SignicClientConfig

    config = SignicClientConfig(
        private_key="0xac09...",
        indexer_url="https://api.signic.email/idx",
        wildduck_url="https://api.signic.email/api",
    )

    async with SignicClient(config) as client:
        print(client.get_address())       # "0xf39F..."
        print(client.get_email_address()) # "0xf39F...@signic.email"

        await client.connect()

        result = await client.get_unread_emails(10)
        full = await client.get_email(result.emails[0].id)
        await client.mark_as_read(result.emails[0].id)
"""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct

from signic_sdk._network.http import http_get, http_post, http_put
from signic_sdk.errors import SignicAuthError, SignicError
from signic_sdk.types import (
    AuthState,
    MarkAsReadResult,
    SignicClientConfig,
    SignicEmail,
    SignicEmailAddress,
    SignicEmailAttachment,
    SignicEmailDetail,
    TlsInfo,
    UnreadEmailsResult,
    VerificationResults,
)

_DEFAULT_EMAIL_DOMAIN = "signic.email"
_DEFAULT_CHAIN_ID = 1


class SignicClient:
    """Client for the Signic decentralized email platform.

    Supports ``async with`` for automatic resource cleanup::

        async with SignicClient(config) as client:
            await client.connect()
            emails = await client.get_unread_emails()
    """

    def __init__(self, config: SignicClientConfig) -> None:
        self._account = Account.from_key(config.private_key)
        self._indexer_url = config.indexer_url.rstrip("/")
        self._wildduck_url = config.wildduck_url.rstrip("/")
        self._email_domain = config.email_domain or _DEFAULT_EMAIL_DOMAIN
        self._chain_id = config.chain_id or _DEFAULT_CHAIN_ID
        self._auth_state: AuthState | None = None
        self._http_client = httpx.AsyncClient()

    async def __aenter__(self) -> SignicClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client. Call this when done, or use ``async with``."""
        await self._http_client.aclose()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_address(self) -> str:
        """Return the EVM wallet address derived from the private key. Does not require auth."""
        return self._account.address  # type: ignore[no-any-return]

    def get_email_address(self) -> str:
        """Return the Signic email address for this wallet (e.g. ``0xabc...@signic.email``).

        Does not require auth.
        """
        return f"{self._account.address}@{self._email_domain}"

    def is_connected(self) -> bool:
        """Return True if :meth:`connect` has completed successfully."""
        return self._auth_state is not None

    async def connect(self) -> None:
        """Authenticate with the Signic platform via SIWE.

        Performs a 6-step flow:

        1. Fetch a SIWE message from the Indexer
        2. Sign the message with the wallet's private key (via eth_account)
        3. Convert the signature from hex to base64
        4. Verify the signature with the Indexer (also fetches wallet accounts)
        5. Authenticate with WildDuck using the verified signature
        6. Locate the INBOX mailbox ID for subsequent email operations

        Raises:
            SignicAuthError: If signature verification or WildDuck authentication fails.
            SignicNetworkError: If any API request fails at the network level.
        """
        address: str = self._account.address
        domain = self._email_domain
        url = f"https://{domain}"

        # Step 1: Get SIWE message from Indexer
        siwe_message = await self._get_siwe_message(address, domain, url)

        # Step 2: Sign the message with eth_account
        signable = encode_defunct(text=siwe_message)
        signed = self._account.sign_message(signable)
        raw_signature = signed.signature.hex()

        # Step 3: Format signature hex -> base64
        base64_signature = self._format_signature_to_base64(raw_signature)

        # Step 4: Verify with Indexer (get wallet accounts)
        await self._get_wallet_accounts(address, siwe_message, base64_signature)

        # Step 5: Authenticate with WildDuck
        auth_response = await self._authenticate_with_wildduck(
            address, base64_signature, siwe_message
        )

        # Step 6: Find INBOX mailbox
        user_id: str = auth_response["id"]
        access_token: str = auth_response["token"]
        inbox_id = await self._find_inbox_mailbox_id(user_id, access_token)

        self._auth_state = AuthState(
            user_id=user_id,
            access_token=access_token,
            username=address,
            inbox_mailbox_id=inbox_id,
        )

    async def get_unread_emails(self, limit: int = 50) -> UnreadEmailsResult:
        """Fetch unread emails from the inbox.

        Returns summary objects -- use :meth:`get_email` for the full message body.

        Args:
            limit: Maximum number of emails to return (default: 50).

        Raises:
            SignicAuthError: If not connected.
        """
        self._require_auth()
        auth = self._auth_state
        assert auth is not None

        params = urlencode({"unseen": "true", "limit": str(limit)})
        url = (
            f"{self._wildduck_url}/users/{auth.user_id}"
            f"/mailboxes/{auth.inbox_mailbox_id}/messages?{params}"
        )

        response = await http_get(self._http_client, url, self._wildduck_headers())

        if not response.data.get("success"):
            raise SignicError(
                response.data.get("error", "Failed to get messages"),
                "get_unread_emails",
                response.status,
            )

        emails = [self._map_message_to_email(msg) for msg in response.data["results"]]
        return UnreadEmailsResult(emails=emails, total=response.data["total"])

    async def get_email(self, email_id: int, mailbox_id: str | None = None) -> SignicEmailDetail:
        """Fetch the complete email by its ID, including HTML/text body, all
        recipients, attachments, flags, and verification results.

        Args:
            email_id: WildDuck message UID (from :attr:`SignicEmail.id`).
            mailbox_id: Mailbox to fetch from (defaults to INBOX).

        Raises:
            SignicAuthError: If not connected.
        """
        self._require_auth()
        auth = self._auth_state
        assert auth is not None
        mbox_id = mailbox_id or auth.inbox_mailbox_id

        url = f"{self._wildduck_url}/users/{auth.user_id}/mailboxes/{mbox_id}/messages/{email_id}"
        response = await http_get(self._http_client, url, self._wildduck_headers())

        if not response.data.get("success"):
            raise SignicError(
                response.data.get("error", "Failed to get message"),
                "get_email",
                response.status,
            )

        return self._map_message_detail(response.data)

    async def mark_as_read(
        self, message_id: int, mailbox_id: str | None = None
    ) -> MarkAsReadResult:
        """Mark a message as read (sets the ``\\Seen`` flag).

        Args:
            message_id: WildDuck message UID.
            mailbox_id: Mailbox containing the message (defaults to INBOX).

        Raises:
            SignicAuthError: If not connected.
        """
        self._require_auth()
        auth = self._auth_state
        assert auth is not None
        mbox_id = mailbox_id or auth.inbox_mailbox_id

        url = f"{self._wildduck_url}/users/{auth.user_id}/mailboxes/{mbox_id}/messages/{message_id}"
        response = await http_put(self._http_client, url, {"seen": True}, self._wildduck_headers())

        if not response.data.get("success"):
            raise SignicError(
                response.data.get("error", "Failed to mark as read"),
                "mark_as_read",
                response.status,
            )

        return MarkAsReadResult(
            success=True,
            updated=response.data.get("updated", 1),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_auth(self) -> None:
        """Guard that raises SignicAuthError if connect() hasn't been called."""
        if self._auth_state is None:
            raise SignicAuthError(
                "Not connected. Call connect() first.",
                "require_auth",
            )

    async def _get_siwe_message(self, address: str, domain: str, url: str) -> str:
        """Fetch the SIWE message to sign from the Indexer API."""
        params = urlencode({"chainId": str(self._chain_id), "domain": domain, "url": url})
        endpoint = f"{self._indexer_url}/wallets/{quote(address)}/message?{params}"

        response = await http_get(
            self._http_client,
            endpoint,
            {"Content-Type": "application/json", "Accept": "application/json"},
        )

        data = response.data
        if not data.get("success") or not data.get("data", {}).get("message"):
            raise SignicError(
                data.get("error", "Failed to get SIWE message"),
                "get_siwe_message",
                response.status,
            )

        return data["data"]["message"]  # type: ignore[no-any-return]

    @staticmethod
    def _format_signature_to_base64(hex_signature: str) -> str:
        """Convert a hex-encoded signature (0x...) to a base64 string for API headers."""
        clean_hex = hex_signature.removeprefix("0x")
        raw_bytes = bytes.fromhex(clean_hex)
        return base64.b64encode(raw_bytes).decode("ascii")

    async def _get_wallet_accounts(self, address: str, message: str, base64_signature: str) -> None:
        """Verify the SIWE signature with the Indexer and retrieve wallet accounts.

        Sends the signature + message in custom headers (x-signature, x-message, x-signer).
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-signature": base64_signature,
            "x-message": quote(message, safe=""),
            "x-signer": address,
        }
        endpoint = f"{self._indexer_url}/wallets/{quote(address)}/accounts"

        response = await http_get(self._http_client, endpoint, headers)

        if not response.data.get("success"):
            raise SignicAuthError(
                response.data.get("error", "Failed to get wallet accounts"),
                "get_wallet_accounts",
                response.status,
            )

    async def _authenticate_with_wildduck(
        self, address: str, base64_signature: str, message: str
    ) -> dict[str, Any]:
        """Exchange the verified SIWE signature for a WildDuck access token."""
        body = {
            "username": address,
            "signature": base64_signature,
            "message": message,
            "signer": address,
            "scope": "master",
            "token": True,
            "protocol": "API",
        }

        response = await http_post(
            self._http_client,
            f"{self._wildduck_url}/authenticate",
            body,
            {"Content-Type": "application/json", "Accept": "application/json"},
        )

        data = response.data
        if not data.get("success") or not data.get("id") or not data.get("token"):
            raise SignicAuthError(
                data.get("error", "WildDuck authentication failed"),
                "authenticate_with_wildduck",
                response.status,
            )

        return data

    async def _find_inbox_mailbox_id(self, user_id: str, access_token: str) -> str:
        """Find the INBOX mailbox ID by querying the user's mailbox list."""
        url = f"{self._wildduck_url}/users/{user_id}/mailboxes?counters=true"

        response = await http_get(
            self._http_client,
            url,
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
        )

        if not response.data.get("success"):
            raise SignicError(
                response.data.get("error", "Failed to get mailboxes"),
                "find_inbox_mailbox_id",
                response.status,
            )

        for mb in response.data["results"]:
            if mb.get("specialUse") == "\\Inbox" or mb.get("path") == "INBOX":
                return mb["id"]  # type: ignore[no-any-return]

        raise SignicError("INBOX mailbox not found", "find_inbox_mailbox_id")

    def _wildduck_headers(self) -> dict[str, str]:
        """Build the standard Authorization + JSON headers for WildDuck API calls."""
        assert self._auth_state is not None
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self._auth_state.access_token}",
        }

    @staticmethod
    def _map_message_to_email(msg: dict[str, Any]) -> SignicEmail:
        """Map a WildDuck message list item to the public SignicEmail shape."""
        from_data = msg.get("from") or {"address": "", "name": ""}
        return SignicEmail(
            id=msg["id"],
            mailbox_id=msg["mailbox"],
            from_=SignicEmailAddress(address=from_data["address"], name=from_data["name"]),
            to=[SignicEmailAddress(address=a["address"], name=a["name"]) for a in msg["to"]],
            subject=msg["subject"],
            date=msg["date"],
            intro=msg["intro"],
            seen=msg["seen"],
            has_attachments=msg["attachments"],
        )

    @staticmethod
    def _map_message_detail(msg: dict[str, Any]) -> SignicEmailDetail:
        """Map a WildDuck message detail response to the public SignicEmailDetail shape."""
        from_data = msg.get("from") or {"address": "", "name": ""}

        def _addr(a: dict[str, Any]) -> SignicEmailAddress:
            return SignicEmailAddress(address=a["address"], name=a["name"])

        reply_to = None
        if msg.get("replyTo"):
            reply_to = _addr(msg["replyTo"])

        verification_results = None
        vr = msg.get("verificationResults")
        if vr is not None:
            tls_raw = vr.get("tls")
            tls: TlsInfo | bool
            if isinstance(tls_raw, dict):
                tls = TlsInfo(name=tls_raw["name"], version=tls_raw["version"])
            else:
                tls = False
            verification_results = VerificationResults(
                tls=tls,
                spf=vr.get("spf", False),
                dkim=vr.get("dkim", False),
            )

        attachments_raw: list[dict[str, Any]] = msg.get("attachments") or []
        attachments = [
            SignicEmailAttachment(
                id=a["id"],
                hash=a["hash"],
                filename=a["filename"],
                content_type=a["contentType"],
                disposition=a["disposition"],
                transfer_encoding=a["transferEncoding"],
                related=a["related"],
                size_kb=a["sizeKb"],
            )
            for a in attachments_raw
        ]

        return SignicEmailDetail(
            id=msg["id"],
            mailbox_id=msg["mailbox"],
            thread=msg["thread"],
            from_=_addr(from_data),
            reply_to=reply_to,
            to=[_addr(a) for a in msg["to"]],
            cc=[_addr(a) for a in (msg.get("cc") or [])],
            bcc=[_addr(a) for a in (msg.get("bcc") or [])],
            subject=msg["subject"],
            message_id=msg["messageId"],
            date=msg["date"],
            idate=msg["idate"],
            size=msg["size"],
            seen=msg["seen"],
            flagged=msg["flagged"],
            deleted=msg["deleted"],
            draft=msg["draft"],
            answered=msg["answered"],
            forwarded=msg["forwarded"],
            html=msg.get("html") or [],
            text=msg.get("text") or "",
            attachments=attachments,
            verification_results=verification_results,
        )
