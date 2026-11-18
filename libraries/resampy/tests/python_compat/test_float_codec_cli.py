"""Phase 3 Python compat: exact Float64 codec + SHA-256 via the native CLI."""

from __future__ import annotations

import hashlib
import struct

from resampy_compat_support import (
    OP_F64_DECODE,
    OP_F64_ENCODE,
    OP_SHA256,
    SPECIAL_VALUES,
    b64decode,
    bits,
    decode_f64le,
    error,
    f64le,
    ok,
    sha256_hex,
)


def test_f64_encode_matches_python_base64(resampy_cli) -> None:
    raw = f64le(SPECIAL_VALUES)
    payload = ok(resampy_cli, bytes([OP_F64_ENCODE]) + raw)
    assert payload.decode("ascii") == __import__("base64").b64encode(raw).decode("ascii")


def test_f64_decode_reconstructs_exact_bits(resampy_cli) -> None:
    raw = f64le(SPECIAL_VALUES)
    import base64

    b64 = base64.b64encode(raw).decode("ascii")
    payload = ok(resampy_cli, bytes([OP_F64_DECODE]) + b64.encode("ascii"))
    back = decode_f64le(payload)
    assert len(back) == len(SPECIAL_VALUES)
    for got, want in zip(back, SPECIAL_VALUES, strict=True):
        assert bits(got) == bits(want), f"bit mismatch {bits(got):#x} vs {bits(want):#x}"


def test_roundtrip_all_special_values(resampy_cli) -> None:
    raw = f64le(SPECIAL_VALUES)
    b64 = ok(resampy_cli, bytes([OP_F64_ENCODE]) + raw)
    back = decode_f64le(ok(resampy_cli, bytes([OP_F64_DECODE]) + b64))
    for got, want in zip(back, SPECIAL_VALUES, strict=True):
        assert bits(got) == bits(want)


def test_nan_payload_bits(resampy_cli) -> None:
    custom_nan = struct.unpack("<d", struct.pack("<Q", 0x7FF8123456789ABC))[0]
    raw = f64le([custom_nan])
    b64 = ok(resampy_cli, bytes([OP_F64_ENCODE]) + raw)
    assert b64decode(b64.decode("ascii")) == raw


def test_empty_vector(resampy_cli) -> None:
    b64 = ok(resampy_cli, bytes([OP_F64_ENCODE]))
    assert b64 == b""
    assert ok(resampy_cli, bytes([OP_F64_DECODE])) == b""


def test_misaligned_decode_returns_error(resampy_cli) -> None:
    import base64

    bad = base64.b64encode(b"\x01\x02\x03").decode("ascii")
    error(resampy_cli, bytes([OP_F64_DECODE]) + bad.encode("ascii"))


def test_invalid_base64_returns_error(resampy_cli) -> None:
    error(resampy_cli, bytes([OP_F64_DECODE]) + b"YQ")


def test_sha256_matches_hashlib(resampy_cli) -> None:
    for data in (b"", b"abc", b"hello", bytes(range(256)), b"\x00" * 100):
        got = ok(resampy_cli, bytes([OP_SHA256]) + data).decode("ascii")
        assert got == hashlib.sha256(data).hexdigest()


def test_sha256_hex_helper() -> None:
    assert sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
