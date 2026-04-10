"""Signic SDK -- Python client for the Signic decentralized email platform.

Authenticate via SIWE (Sign-In with Ethereum) and read emails from a WildDuck
mail server.

Example::

    from signic_sdk import SignicClient, SignicClientConfig

    config = SignicClientConfig(
        private_key="0xac09...",
        indexer_url="https://api.signic.email/idx",
        wildduck_url="https://api.signic.email/api",
    )

    async with SignicClient(config) as client:
        await client.connect()
        result = await client.get_unread_emails()
        for email in result.emails:
            print(email.subject)
"""

from signic_sdk.client import SignicClient
from signic_sdk.errors import (
    SignicAuthError,
    SignicError,
    SignicNetworkError,
    SignicValidationError,
)
from signic_sdk.types import (
    MarkAsReadResult,
    SignicClientConfig,
    SignicEmail,
    SignicEmailAddress,
    SignicEmailAttachment,
    SignicEmailDetail,
    UnreadEmailsResult,
)

__all__ = [
    "MarkAsReadResult",
    "SignicAuthError",
    "SignicClient",
    "SignicClientConfig",
    "SignicEmail",
    "SignicEmailAddress",
    "SignicEmailAttachment",
    "SignicEmailDetail",
    "SignicError",
    "SignicNetworkError",
    "SignicValidationError",
    "UnreadEmailsResult",
]
