# signic-sdk

Python SDK for the [Signic](https://signic.email) decentralized email platform. Authenticate with an Ethereum wallet via SIWE (Sign-In with Ethereum) and read emails from a WildDuck mail server.

Also provides methods to claim a custom (human-readable) email address and pure helper functions for Gmail-style `+tag` subaddressing.

License: BUSL-1.1 (Business Source License). Async-first (`httpx.AsyncClient`); all network methods are coroutines.

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

#### `async check_custom_address_availability(name: str) -> CustomAddressAvailability`

Check whether a desired custom address local part is available. Does **not** require `connect()`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Desired local part (e.g. `john`); lowercased server-side |

**Returns:** `CustomAddressAvailability` with `.name`, `.available: bool`, and (when unavailable) `.reason` / `.service`.

#### `async get_custom_address() -> CustomAddressState`

Get the connected wallet's current custom-address state. Requires `connect()`.

**Returns:** `CustomAddressState`.
**Raises:** `SignicAuthError` if not connected.

#### `async set_custom_address(name: str) -> CustomAddressState`

Claim a custom (human-readable) address for the connected wallet. A custom address can be set only while credits remain, and is rejected if already taken, reserved, a wallet-address string, or ending in an ENS/SNS postfix. Call `check_custom_address_availability()` first to validate. Requires `connect()`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Desired local part; lowercased server-side |

**Returns:** `CustomAddressState`.
**Raises:** `SignicAuthError` if not connected; `SignicValidationError` if the name is rejected (400); `SignicError` on conflict (409) or other errors.

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

#### `CustomAddressAvailability`

Returned by `check_custom_address_availability()`.

```python
@dataclass(frozen=True)
class CustomAddressAvailability:
    name: str                 # Normalized (lowercased) local part checked
    available: bool           # Whether it can be claimed
    reason: str | None = None # e.g. "taken", "reserved", "wallet_address",
                              #      "name_service_postfix", "invalid_format"
    service: str | None = None # For name_service_postfix: "ENS" or "SNS"
```

#### `CustomAddressState`

Returned by `get_custom_address()` and `set_custom_address()`.

```python
@dataclass(frozen=True)
class CustomAddressState:
    wallet_address: str        # Owning wallet address
    chain_type: str            # "EVM" or "SOLANA"
    custom_address: str | None # Active custom local part, or None
    credits_remaining: int     # Remaining (re)set allowance
```

## Subaddressing

Pure, dependency-free helpers for Gmail-style `+tag` addresses (`john+amazon@signic.email` delivers to `john`). All are importable from `signic_sdk`.

```python
from signic_sdk import (
    parse_subaddress, strip_subaddress_tag, get_subaddress_tag,
    has_subaddress_tag, build_subaddress, same_base_address,
)

parse_subaddress("john+amazon@signic.email")  # ParsedSubaddress(local_part, base_local, tag, domain) or None
strip_subaddress_tag("john+amazon@signic.email")  # "john@signic.email"
get_subaddress_tag("john+amazon@signic.email")    # "amazon"
has_subaddress_tag("john@signic.email")           # False
build_subaddress("john@signic.email", "shopping") # "john+shopping@signic.email"
same_base_address("John+a@signic.email", "john+b@signic.email")  # True
```

`ParsedSubaddress` is a frozen dataclass with fields `local_part`, `base_local`, `tag: str | None`, and `domain`.

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

## Development

Requires Python >= 3.11. The package uses a `src/` layout and is built with [hatchling](https://hatch.pypa.io/).

```bash
# Set up a virtual environment and install with dev dependencies (editable)
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Lint, format check, and type check
ruff check src tests
ruff format --check src tests
mypy src                       # strict mode

# Tests (pytest with asyncio_mode=auto)
pytest -m "not integration"    # unit tests only (no network)
pytest -m integration          # integration tests (require env vars below)
pytest                         # all; integration auto-skipped without env vars

# Build a wheel/sdist
pip install build && python -m build
```

Integration tests hit real Signic endpoints and are skipped unless these environment variables are all set: `SIGNIC_PRIVATE_KEY`, `SIGNIC_INDEXER_URL`, `SIGNIC_WILDDUCK_URL`.

CI/CD runs via GitHub Actions (`.github/workflows/ci-cd.yml`), which calls a shared reusable workflow and publishes to PyPI when `PYPI_TOKEN` is configured.

## License

BUSL-1.1 (Business Source License 1.1)
