"""Gmail-style "+" subaddressing helpers.

An address like ``john+amazon@signic.email`` is delivered to the account found
by the base local part (``john``); the ``+amazon`` tag is informational and is
preserved on the message so a reply can send from the same tagged address.

Pure, dependency-free functions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedSubaddress:
    """The parts of a parsed email address."""

    local_part: str
    """Full local part including any tag, e.g. ``john+amazon``."""
    base_local: str
    """Base local part before the first ``+``, e.g. ``john``."""
    tag: str | None
    """Tag after the first ``+`` (up to ``@``), or ``None`` if none."""
    domain: str
    """Domain part, e.g. ``signic.email``."""


def parse_subaddress(email: str) -> ParsedSubaddress | None:
    """Parse an email into base local part, tag, and domain.

    Returns ``None`` if the input is not a valid single-``@`` address.
    """
    if not email or not isinstance(email, str):
        return None
    trimmed = email.strip()
    parts = trimmed.split("@")
    if len(parts) != 2:
        return None
    local_part, domain = parts
    if not local_part or not domain:
        return None

    plus_idx = local_part.find("+")
    base_local = local_part[:plus_idx] if plus_idx >= 0 else local_part
    tag = local_part[plus_idx + 1 :] if plus_idx >= 0 else None

    # A leading "+" (empty base) is not a valid subaddress.
    if not base_local:
        return None

    return ParsedSubaddress(
        local_part=local_part, base_local=base_local, tag=tag, domain=domain
    )


def strip_subaddress_tag(email: str) -> str:
    """Return the base address with any ``+tag`` removed: ``base@domain``.

    The domain is lowercased. Returns the input stripped unchanged if it is not
    a valid address.
    """
    parsed = parse_subaddress(email)
    if parsed is None:
        return (email or "").strip()
    return f"{parsed.base_local}@{parsed.domain.lower()}"


def get_subaddress_tag(email: str) -> str | None:
    """Return the tag portion of an address, or ``None`` if there is none."""
    parsed = parse_subaddress(email)
    return parsed.tag if parsed is not None else None


def has_subaddress_tag(email: str) -> bool:
    """Return True if the address carries a ``+tag``."""
    return get_subaddress_tag(email) is not None


def build_subaddress(base_email: str, tag: str | None) -> str:
    """Build a tagged address: ``base+tag@domain``.

    If ``tag`` is empty/``None`` the base address is returned (with any existing
    tag stripped). Any existing tag on ``base_email`` is replaced.
    """
    parsed = parse_subaddress(base_email)
    if parsed is None:
        return (base_email or "").strip()
    domain = parsed.domain.lower()
    clean_tag = (tag or "").strip()
    if not clean_tag:
        return f"{parsed.base_local}@{domain}"
    return f"{parsed.base_local}+{clean_tag}@{domain}"


def same_base_address(a: str, b: str) -> bool:
    """Return True if two addresses resolve to the same mailbox.

    They must share the same base local part and domain, ignoring any ``+tag``
    and case.
    """
    pa = parse_subaddress(a)
    pb = parse_subaddress(b)
    if pa is None or pb is None:
        return False
    return (
        pa.base_local.lower() == pb.base_local.lower()
        and pa.domain.lower() == pb.domain.lower()
    )
