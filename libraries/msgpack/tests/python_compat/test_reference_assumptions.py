"""Pins pinned-reference behaviors the compatibility harness relies on.

Every assumption is checked against both the C-backed and fallback decoders
so the harness never depends on one implementation's quirks.
"""

from __future__ import annotations

import msgpack.fallback
import pytest

import msgpack

IMPLS = (msgpack.unpackb, msgpack.fallback.unpackb)


def test_reference_version_is_pinned() -> None:
    assert msgpack.version == (1, 2, 4)


@pytest.mark.parametrize("unpackb", IMPLS)
def test_strict_map_key_rejects_non_string_keys_by_default(unpackb) -> None:
    with pytest.raises(ValueError, match="is not allowed for map key"):
        unpackb(bytes.fromhex("8100c0"))


@pytest.mark.parametrize("unpackb", IMPLS)
def test_reserved_marker_is_a_format_error(unpackb) -> None:
    with pytest.raises(msgpack.FormatError):
        unpackb(bytes.fromhex("c1"))


@pytest.mark.parametrize("unpackb", IMPLS)
def test_trailing_data_is_extra_data(unpackb) -> None:
    with pytest.raises(msgpack.ExtraData):
        unpackb(bytes.fromhex("0000"))


@pytest.mark.parametrize("unpackb", IMPLS)
def test_truncated_input_is_a_value_error(unpackb) -> None:
    with pytest.raises(ValueError, match="incomplete input"):
        unpackb(bytes.fromhex("cd01"))


def test_duplicate_keys_collapse_without_a_hook() -> None:
    raw = bytes.fromhex("82a16b01a16b02")
    assert msgpack.unpackb(raw, strict_map_key=False) == {"k": 2}
    assert msgpack.fallback.unpackb(raw, strict_map_key=False) == {"k": 2}


def test_out_of_range_integers_do_not_pack() -> None:
    with pytest.raises(OverflowError):
        msgpack.packb(2**64)
    with pytest.raises(OverflowError):
        msgpack.packb(-(2**63) - 1)


def test_floats_default_to_float64_in_both_packers() -> None:
    assert msgpack.packb(1.5) == bytes.fromhex("cb3ff8000000000000")
    assert msgpack.fallback.Packer().pack(1.5) == bytes.fromhex("cb3ff8000000000000")
    assert msgpack.packb(1.5, use_single_float=True) == bytes.fromhex("ca3fc00000")
    assert msgpack.fallback.Packer(use_single_float=True).pack(1.5) == bytes.fromhex("ca3fc00000")
