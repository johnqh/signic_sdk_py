"""Type definitions for the Signic SDK.

Public types (exported via __init__.py) are defined as frozen dataclasses at
the top. Internal API response types (not exported) are defined as TypedDicts
at the bottom.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ============================================================
# Public types (exported via __init__.py)
# ============================================================


@dataclass
class SignicClientConfig:
    """Configuration for creating a :class:`SignicClient` instance.

    Example::

        config = SignicClientConfig(
            private_key="0xac09...",
            indexer_url="https://api.signic.email/idx",
            wildduck_url="https://api.signic.email/api",
        )
        client = SignicClient(config)
    """

    private_key: str
    """EVM private key (hex string starting with 0x)."""
    indexer_url: str
    """Indexer API base URL (e.g. ``https://api.signic.email/idx``)."""
    wildduck_url: str
    """WildDuck API base URL (e.g. ``https://api.signic.email/api``)."""
    email_domain: str = "signic.email"
    """Email domain (default: ``signic.email``). Also used as the SIWE domain."""
    chain_id: int = 1
    """EVM chain ID for the SIWE message (default: 1 = Ethereum mainnet)."""


@dataclass(frozen=True)
class SignicEmailAddress:
    """An email address with an optional display name."""

    address: str
    """Email address string (e.g. ``0xabc...@signic.email``)."""
    name: str
    """Display name (may be empty string)."""


@dataclass(frozen=True)
class SignicEmail:
    """Summary representation of an email, returned by
    :meth:`SignicClient.get_unread_emails`.

    Contains metadata only -- use :meth:`SignicClient.get_email` for the full body.
    """

    id: int
    """WildDuck message UID."""
    mailbox_id: str
    """Mailbox ID this message belongs to."""
    from_: SignicEmailAddress
    """Sender address (named ``from_`` because ``from`` is a Python keyword)."""
    to: list[SignicEmailAddress]
    """Recipient addresses."""
    subject: str
    """Email subject line."""
    date: str
    """ISO 8601 date from the Date header."""
    intro: str
    """Short preview of the message body (first ~128 chars)."""
    seen: bool
    """Whether the message has been read."""
    has_attachments: bool
    """Whether the message has file attachments."""


@dataclass(frozen=True)
class UnreadEmailsResult:
    """Result from :meth:`SignicClient.get_unread_emails`."""

    emails: list[SignicEmail]
    """Array of unread email summaries."""
    total: int
    """Total number of unread emails in the mailbox (may exceed array length if limited)."""


@dataclass(frozen=True)
class MarkAsReadResult:
    """Result from :meth:`SignicClient.mark_as_read`."""

    success: bool
    """Whether the update succeeded."""
    updated: int
    """Number of messages updated (typically 1)."""


@dataclass(frozen=True)
class SignicEmailAttachment:
    """Metadata for a single email attachment."""

    id: str
    """WildDuck attachment ID (use for download URLs)."""
    hash: str
    """SHA-256 hash of the attachment content (hex)."""
    filename: str
    """Original filename."""
    content_type: str
    """MIME type (e.g. ``application/pdf``)."""
    disposition: str
    """Content-Disposition value (e.g. ``attachment``, ``inline``)."""
    transfer_encoding: str
    """Transfer encoding used (content is already decoded)."""
    related: bool
    """True if this is an inline/embedded image from multipart/related."""
    size_kb: int
    """Approximate size in kilobytes."""


@dataclass(frozen=True)
class TlsInfo:
    """TLS connection information from email verification results."""

    name: str
    version: str


@dataclass(frozen=True)
class VerificationResults:
    """Email authentication verification results (TLS, SPF, DKIM)."""

    tls: TlsInfo | bool
    """TLS info or False if not available."""
    spf: dict[str, Any] | bool
    """SPF verification result or False if not available."""
    dkim: dict[str, Any] | bool
    """DKIM verification result or False if not available."""


@dataclass(frozen=True)
class SignicEmailDetail:
    """Full email detail, returned by :meth:`SignicClient.get_email`.

    Includes the complete body (HTML + text), all recipients, flags, and attachments.
    """

    id: int
    """WildDuck message UID."""
    mailbox_id: str
    """Mailbox ID this message belongs to."""
    thread: str
    """Conversation thread ID."""
    from_: SignicEmailAddress
    """Sender address."""
    to: list[SignicEmailAddress]
    """To recipients."""
    cc: list[SignicEmailAddress]
    """CC recipients."""
    bcc: list[SignicEmailAddress]
    """BCC recipients (usually only visible in drafts/sent)."""
    subject: str
    """Email subject line."""
    message_id: str
    """Message-ID header value."""
    date: str
    """ISO 8601 date from the Date header."""
    idate: str
    """ISO 8601 date when the server received the message."""
    size: int
    """Message size in bytes."""
    seen: bool
    """Whether the message has been read (\\\\Seen flag)."""
    flagged: bool
    """Whether the message is starred (\\\\Flagged flag)."""
    deleted: bool
    """Whether the message is marked for deletion (\\\\Deleted flag)."""
    draft: bool
    """Whether this is a draft (\\\\Draft flag)."""
    answered: bool
    """Whether the message has been replied to (\\\\Answered flag)."""
    forwarded: bool
    """Whether the message has been forwarded ($Forwarded flag)."""
    html: list[str]
    """HTML body parts (one string per MIME part, most messages have one)."""
    text: str
    """Plain text body."""
    attachments: list[SignicEmailAttachment]
    """File attachments with metadata."""
    reply_to: SignicEmailAddress | None = None
    """Reply-To address, if set."""
    verification_results: VerificationResults | None = None
    """Email authentication verification results (TLS, SPF, DKIM)."""


# ============================================================
# Internal types (not exported via __init__.py)
# ============================================================


@dataclass
class AuthState:
    """Stored after a successful :meth:`SignicClient.connect` call."""

    user_id: str
    access_token: str
    username: str
    inbox_mailbox_id: str


@dataclass(frozen=True)
class HttpResponse:
    """Parsed HTTP response returned by http_get/http_post/http_put."""

    status: int
    data: dict[str, Any]
    ok: bool


# Internal API response types are accessed as plain dicts with string keys
# matching the original camelCase JSON field names from the Indexer and
# WildDuck APIs. No TypedDicts needed — we access fields via bracket notation
# and map them to public dataclasses in the client.
