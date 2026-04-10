# Signic SDK (Python)

Python SDK for the Signic decentralized email platform. Authenticates users via SIWE (Sign-In with Ethereum) and provides read access to emails stored in a WildDuck mail server.

## Architecture

```
SignicClient
├── Indexer API (mail_box_indexer) — SIWE auth, wallet verification
└── WildDuck API (wildduck) — email storage and retrieval
```

**Auth flow** (`connect()`): get SIWE message from Indexer -> sign with eth_account -> verify signature with Indexer -> authenticate with WildDuck -> find INBOX mailbox ID.

**Email addresses** are derived from EVM wallet addresses: `{walletAddress}@{emailDomain}`.

## Project structure

```
src/signic_sdk/
├── __init__.py        — Public exports (SignicClient, types, errors)
├── py.typed           — PEP 561 typed package marker
├── client.py          — SignicClient class (all public methods)
├── types.py           — Public dataclasses (top) + internal types (bottom)
├── errors.py          — Error hierarchy: SignicError > Auth | Network | Validation
└── _network/
    ├── __init__.py
    └── http.py        — Async HTTP utilities (http_get/http_post/http_put)

tests/
├── conftest.py        — Shared fixtures, test constants, connect mock helper
├── unit/
│   ├── test_errors.py — Error hierarchy tests
│   ├── test_http.py   — HTTP utility tests (pytest-httpx)
│   └── test_client.py — Client tests with mocked HTTP
└── integration/
    └── test_connect.py — Real endpoint tests (skipped without env vars)
```

## Commands

```bash
# Activate venv first
source .venv/bin/activate

# Individual checks
ruff check src tests                     # lint
ruff format --check src tests            # format check
mypy src                                 # type check (strict)
pytest -m "not integration"              # unit tests only
pytest                                   # all tests (integration skipped without env vars)
pytest -m integration                    # integration tests only

# Full verify (CI equivalent)
ruff check src tests && ruff format --check src tests && mypy src && pytest -m "not integration"
```

## Code conventions

- Async-first: all HTTP methods are async, `SignicClient` uses `httpx.AsyncClient`
- Python 3.11+, ESM equivalent: src layout with hatchling
- Only runtime deps: `httpx` (HTTP) and `eth-account` (Ethereum signing)
- Public types are frozen dataclasses; internal API response types are plain dicts
- `from_` field name (trailing underscore) because `from` is a Python keyword
- Tests use `pytest-httpx` with `add_response()` for FIFO mock queuing
- `ruff` for linting + formatting, `mypy --strict` for type checking
- Error hierarchy: `SignicError` is the base; subclasses for auth (401/403), validation (400/422), network (connection failures)
- Every public method that hits an API requires auth — calls `self._require_auth()` first
- API response mapping: WildDuck camelCase dict keys -> public snake_case dataclasses

## Adding a new public method

1. Add any new public return dataclasses to the top section of `types.py`
2. Implement the method on `SignicClient` in `client.py` — call `self._require_auth()`, use `http_get`/`http_post`/`http_put` with `self._http_client`, check `response.data.get("success")`, map to public dataclasses
3. Export new public types from `__init__.py` and add to `__all__`
4. Add tests in `tests/unit/test_client.py` using the `connected_client` fixture + `httpx_mock`
5. Run full verify to confirm everything passes

## Related projects (same machine)

- `/Users/johnhuang/projects/signic_sdk` — TypeScript version of this SDK (the reference implementation)
- `/Users/johnhuang/projects/mail_box_indexer` — Blockchain indexer backend (Ponder + Hono)
- `/Users/johnhuang/projects/wildduck` — WildDuck mail server (Node.js + MongoDB)
- `/Users/johnhuang/projects/signic_sdk_demo` — React demo app consuming the TypeScript SDK

## WildDuck API reference (commonly used)

These are the WildDuck REST endpoints this SDK calls:

- `GET /wallets/{address}/message?chainId&domain&url` — (Indexer) Get SIWE message
- `GET /wallets/{address}/accounts` — (Indexer) Verify signature, get wallet accounts. Headers: `x-signature`, `x-message`, `x-signer`
- `POST /authenticate` — (WildDuck) Get access token. Body: `{ username, signature, message, signer, scope, token, protocol }`
- `GET /users/{id}/mailboxes?counters=true` — (WildDuck) List mailboxes
- `GET /users/{id}/mailboxes/{mailbox}/messages?unseen&limit` — (WildDuck) List messages
- `GET /users/{id}/mailboxes/{mailbox}/messages/{message}` — (WildDuck) Get full message detail
- `PUT /users/{id}/mailboxes/{mailbox}/messages/{message}` — (WildDuck) Update message flags
