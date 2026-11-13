"""Pin bitarray==3.12.3 byte-conversion semantics the Mojo port must match.

Phase 1E oracle: ``tobytes`` packing/padding/independence, ``frombytes``
append behavior from every alignment, bytes-based construction, and
invalid-input errors. The native Mojo tests mirror these expectations.
"""

from __future__ import annotations

import random

import pytest

from bitarray import bitarray

ENDIANS = ["big", "little"]


def test_pinned_version() -> None:
    import bitarray as mod

    assert mod.__version__ == "3.12.3"


@pytest.mark.parametrize("endian", ENDIANS)
@pytest.mark.parametrize(
    ("bits", "packed"),
    [
        ("", b""),
        ("10110011", None),  # endian-specific, asserted below
        ("10110", None),
        ("1", None),
    ],
)
def test_tobytes(endian: str, bits: str, packed: bytes | None) -> None:
    a = bitarray(bits, endian=endian)
    raw = a.tobytes()
    assert type(raw) is bytes
    assert len(raw) == (len(bits) + 7) // 8
    if packed is not None:
        assert raw == packed
    if endian == "big" and bits == "10110011":
        assert raw == b"\xb3"
    if endian == "little" and bits == "10110011":
        assert raw == b"\xcd"
    if endian == "big" and bits == "10110":
        assert raw == b"\xb0"
    if endian == "little" and bits == "10110":
        assert raw == b"\r"
    if endian == "big" and bits == "1":
        assert raw == b"\x80"
    if endian == "little" and bits == "1":
        assert raw == b"\x01"


def test_tobytes_independent() -> None:
    a = bitarray("10110", endian="big")
    raw = bytearray(a.tobytes())
    raw[0] ^= 0xFF
    assert a.to01() == "10110"
    assert a.tobytes() == b"\xb0"


@pytest.mark.parametrize("endian", ENDIANS)
def test_frombytes_appends(endian: str) -> None:
    c = bitarray("1", endian=endian)
    assert c.frombytes(b"\xca") is None
    assert len(c) == 9
    assert c.endian == endian
    # Empty input is a no-op; empty target accepts whole bytes.
    d = bitarray("101", endian=endian)
    d.frombytes(b"")
    assert d.to01() == "101"
    e = bitarray("", endian=endian)
    e.frombytes(b"\xca")
    assert len(e) == 8
    # Multiple consecutive calls accumulate.
    e.frombytes(b"\x53")
    assert len(e) == 16
    assert e.to01() == bitarray(e.to01(), endian=endian).to01()


def test_frombytes_endianness() -> None:
    cases = [
        ("1", "big", "111001010"),
        ("101", "big", "10111001010"),
        ("101", "little", "10101010011"),
    ]
    for setup, endian, expected in cases:
        c = bitarray(setup, endian=endian)
        c.frombytes(b"\xca")
        assert c.to01() == expected
        assert c.endian == endian


@pytest.mark.parametrize("bad", ["hi", 5, 1.5, None, [202]])
def test_frombytes_rejects(bad: object) -> None:
    with pytest.raises(TypeError, match="bytes-like object is required"):
        bitarray("101").frombytes(bad)


def test_bytes_construction() -> None:
    assert bitarray(b"\x01\x00\x02").to01() == "000000010000000000000010"
    assert bitarray(bytearray(b"\x01")).to01() == "00000001"
    assert bitarray(b"").to01() == ""
    assert bitarray(b"\x01\x00", endian="little").to01() == "1000000000000000"
    # Construction imports packed bytes; mutating the source afterwards
    # cannot affect the bitarray (owned copy).
    src = bytearray(b"\xca")
    c = bitarray(src)
    src[0] = 0
    assert c.to01() == "11001010"


def test_bytes_roundtrip_fuzz() -> None:
    rng = random.Random(20260608)
    for _trial in range(200):
        for endian in ENDIANS:
            n = rng.choice([0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65])
            bits = "".join(rng.choice("01") for _ in range(n))
            a = bitarray(bits, endian=endian)
            raw = a.tobytes()
            assert len(raw) == (n + 7) // 8
            # frombytes appends whole bytes; trimming recovers the input.
            b = bitarray("", endian=endian)
            b.frombytes(raw)
            assert len(b) == 8 * ((n + 7) // 8)
            assert b[:n].to01() == bits
            assert b.endian == endian
