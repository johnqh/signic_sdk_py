# signic-sdk

Python SDK for the [Signic](https://signic.email) decentralized email platform. Authenticate with an Ethereum wallet via SIWE (Sign-In with Ethereum) and read emails from a WildDuck mail server.

## Installation

```bash
pip install signic-sdk
```

**Requirements:** Python >= 3.11

## Quick Start

```python
import asyncio
from signic_sdk import SignicClient, SignicClientConfig

async def main():
    config = SignicClientConfig(
        private_key="0xac09...",
        indexer_url="https://api.signic.email/idx",
        wildduck_url="https://api.signic.email/api",
    )

    async with SignicClient(config) as client:
        # Derive addresses (no auth needed)
        print(client.get_address())       # "0xf39F..."
        print(client.get_email_address()) # "0xf39F...@signic.email"

        # Authenticate via SIWE
        await client.connect()

        # Fetch unread emails
        result = await client.get_unread_emails(10)
        print(f"{result.total} unread emails")

        # Get full email content
        full = await client.get_email(result.emails[0].id)
        print(full.subject, full.text)

        # Mark as read
        await client.mark_as_read(result.emails[0].id)

asyncio.run(main())
```

## API Reference

### `SignicClient(config)`

Create a new client instance.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `private_key` | `str` | Yes | EVM private key (hex with 0x prefix) |
| `indexer_url` | `str` | Yes | Indexer API base URL |
| `wildduck_url` | `str` | Yes | WildDuck API base URL |
| `email_domain` | `str` | No | Email domain (default: `signic.email`) |
| `chain_id` | `int` | No | EVM chain ID for SIWE (default: `1`) |

Supports `async with` for automatic resource cleanup:

```python
async with SignicClient(config) as client:
    await client.connect()
    ...
# httpx client is automatically closed
```

Or close manually:

```python
client = SignicClient(config)
try:
    await client.connect()
    ...
finally:
    await client.aclose()
```

### Methods

#### `get_address() -> str`

Returns the EVM wallet address derived from the private key. Does not require authentication.

#### `get_email_address() -> str`

Returns the Signic email address (e.g. `0xabc...@signic.email`). Does not require authentication.

#### `is_connected() -> bool`

Returns `True` if `connect()` has completed successfully.

#### `async connect() -> None`

Authenticate with the Signic platform via SIWE. Must be called before any email methods.

Performs a 6-step flow:
1. Fetch a SIWE message from the Indexer
2. Sign the message with the wallet's private key
3. Convert the signature to base64
4. Verify the signature with the Indexer
5. Authenticate with WildDuck to get an access token
6. Locate the INBOX mailbox

**Raises:** `SignicAuthError` on auth failure, `SignicNetworkError` on network failure.

#### `async get_unread_emails(limit: int = 50) -> UnreadEmailsResult`

Fetch unread emails from the inbox. Returns summary objects (use `get_email()` for full content).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | `int` | `50` | Maximum number of emails to return |

**Returns:** `UnreadEmailsResult` with `.emails: list[SignicEmail]` and `.total: int`

#### `async get_email(email_id: int, mailbox_id: str | None = None) -> SignicEmailDetail`

Fetch the complete email by ID, including HTML/text body, all recipients, attachments, and flags.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `email_id` | `int` | - | Message UID from `SignicEmail.id` |
| `mailbox_id` | `str \| None` | INBOX | Mailbox to fetch from |

**Returns:** `SignicEmailDetail` with `html`, `text`, `cc`, `bcc`, `reply_to`, `attachments`, `verification_results`, and all message flags.

#### `async mark_as_read(message_id: int, mailbox_id: str | None = None) -> MarkAsReadResult`

Mark a message as read (sets the `\Seen` flag).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `message_id` | `int` | - | Message UID |
| `mailbox_id` | `str \| None` | INBOX | Mailbox containing the message |

**Returns:** `MarkAsReadResult` with `.success: bool` and `.updated: int`

#### `async aclose() -> None`

Close the underlying HTTP client. Called automatically when using `async with`.

### Types

All types are frozen dataclasses.

#### `SignicEmail`

Summary email object returned by `get_unread_emails()`.

```python
@dataclass(frozen=True)
class SignicEmail:
    id: int                           # Message UID
    mailbox_id: str                   # Mailbox ID
    from_: SignicEmailAddress         # Sender (from_ because from is reserved)
    to: list[SignicEmailAddress]      # Recipients
    subject: str                      # Subject line
    date: str                         # ISO 8601 date
    intro: str                        # Preview (~128 chars)
    seen: bool                        # Read status
    has_attachments: bool             # Has file attachments
```

#### `SignicEmailDetail`

Full email object returned by `get_email()`.

```python
@dataclass(frozen=True)
class SignicEmailDetail:
    id: int
    mailbox_id: str
    thread: str                                     # Conversation thread ID
    from_: SignicEmailAddress
    to: list[SignicEmailAddress]
    cc: list[SignicEmailAddress]
    bcc: list[SignicEmailAddress]
    subject: str
    message_id: str                                 # Message-ID header
    date: str                                       # Date header (ISO 8601)
    idate: str                                      # Server receive date (ISO 8601)
    size: int                                       # Size in bytes
    seen: bool
    flagged: bool
    deleted: bool
    draft: bool
    answered: bool
    forwarded: bool
    html: list[str]                                 # HTML body parts
    text: str                                       # Plain text body
    attachments: list[SignicEmailAttachment]         # File attachments
    reply_to: SignicEmailAddress | None = None
    verification_results: VerificationResults | None = None
```

#### `SignicEmailAttachment`

```python
@dataclass(frozen=True)
class SignicEmailAttachment:
    id: str                # Attachment ID
    hash: str              # SHA-256 hash (hex)
    filename: str          # Original filename
    content_type: str      # MIME type
    disposition: str       # "attachment" or "inline"
    transfer_encoding: str # Transfer encoding
    related: bool          # Inline/embedded image
    size_kb: int           # Approximate size in KB
```

### Error Classes

All errors extend `SignicError` which carries `operation` and `status_code` attributes.

| Error | When |
|-------|------|
| `SignicError` | Base class for all SDK errors |
| `SignicAuthError` | Authentication failure (401/403) or calling methods before `connect()` |
| `SignicNetworkError` | Network failure (DNS, timeout, no response) |
| `SignicValidationError` | Input validation failure (400/422) |

```python
from signic_sdk import SignicError, SignicAuthError

try:
    await client.get_unread_emails()
except SignicAuthError as err:
    print(f"Auth failed: {err.operation} {err.status_code}")
except SignicError as err:
    print(f"SDK error: {err}")
```

## License

BUSL-1.1
