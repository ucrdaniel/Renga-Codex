"""Own GUID fixtures only; vendor headers/type libraries are not required."""

import pytest

from renga_codex_bridge.sdk import SDK, parse_guids


def test_synthetic_guid_components_preserve_byte_order():
    source = """
const GUID TestObject = {0x12345678, 0x9ABC, 0x4DEF,
    {0x81, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF}};
"""
    assert parse_guids(source) == {"TestObject": "{12345678-9ABC-4DEF-8123-456789ABCDEF}"}


def test_multiple_independent_guid_declarations_are_parsed():
    source = """
const GUID First = {0x12345678, 0x1234, 0x4321, {0x98, 0x76, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC}};
const GUID Second = {0x87654321, 0x4321, 0x1234, {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00, 0x11}};
"""
    actual = parse_guids(source)
    assert actual["First"] == "{12345678-1234-4321-9876-123456789ABC}"
    assert actual["Second"] == "{87654321-4321-1234-AABB-CCDDEEFF0011}"


def test_malformed_guid_is_not_silently_published():
    with pytest.raises(ValueError, match="GUID"):
        parse_guids("const GUID Broken = {0x12345678, 0x1234, 0x4321};")


def test_unconfigured_sdk_has_an_actionable_error(monkeypatch):
    monkeypatch.delenv("RENGA_SDK_PATH", raising=False)
    with pytest.raises(FileNotFoundError, match="RENGA_SDK_PATH"):
        SDK()
