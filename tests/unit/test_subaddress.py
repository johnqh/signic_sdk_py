"""Tests for the plus-addressing (subaddress) helpers."""

from __future__ import annotations

from signic_sdk import (
    build_subaddress,
    get_subaddress_tag,
    has_subaddress_tag,
    parse_subaddress,
    same_base_address,
    strip_subaddress_tag,
)


def test_parse_base_and_tag() -> None:
    parsed = parse_subaddress("john+amazon@signic.email")
    assert parsed is not None
    assert parsed.base_local == "john"
    assert parsed.tag == "amazon"
    assert parsed.domain == "signic.email"

    untagged = parse_subaddress("john@signic.email")
    assert untagged is not None
    assert untagged.tag is None


def test_parse_keeps_only_first_plus() -> None:
    parsed = parse_subaddress("a+b+c@signic.email")
    assert parsed is not None
    assert parsed.base_local == "a"
    assert parsed.tag == "b+c"


def test_parse_invalid() -> None:
    assert parse_subaddress("nope") is None
    assert parse_subaddress("+tag@signic.email") is None
    assert parse_subaddress("a@b@c") is None
    assert parse_subaddress("") is None


def test_strip_tag_lowercases_domain() -> None:
    assert strip_subaddress_tag("john+amazon@Signic.Email") == "john@signic.email"
    assert strip_subaddress_tag("john@signic.email") == "john@signic.email"


def test_get_and_has_tag() -> None:
    assert get_subaddress_tag("john+ebay@signic.email") == "ebay"
    assert get_subaddress_tag("john@signic.email") is None
    assert has_subaddress_tag("john+ebay@signic.email") is True
    assert has_subaddress_tag("john@signic.email") is False


def test_build_and_replace_tag() -> None:
    assert build_subaddress("john@signic.email", "amazon") == "john+amazon@signic.email"
    assert build_subaddress("john+old@signic.email", "new") == "john+new@signic.email"
    assert build_subaddress("john+old@signic.email", "") == "john@signic.email"
    assert build_subaddress("john+old@signic.email", None) == "john@signic.email"


def test_same_base_address() -> None:
    assert same_base_address("john+amazon@signic.email", "JOHN@Signic.Email") is True
    assert same_base_address("john+a@signic.email", "john+b@signic.email") is True
    assert same_base_address("john@signic.email", "jane@signic.email") is False
    assert same_base_address("john@signic.email", "john@other.email") is False
