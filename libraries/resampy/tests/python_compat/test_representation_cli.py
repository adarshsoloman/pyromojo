"""Phase 3 Python compat: signal/output/coefficient CLI + framing."""

from __future__ import annotations

import hashlib
import json
import struct

from resampy_compat_support import (
    OP_ECHO,
    OP_OUTPUT_ALLOC,
    OP_OUTPUT_SET,
    OP_PING,
    OP_SIGNAL_INFO,
    STATUS_OK,
    bits,
    decode_f64le,
    error,
    f64le,
    filter_load_body,
    ok,
    parse_kv,
    run_frames,
)


def test_ping_and_echo(resampy_cli) -> None:
    assert ok(resampy_cli, bytes([OP_PING])) == b""
    assert ok(resampy_cli, bytes([OP_ECHO, 0xAA, 0x00, 0xFF])) == b"\xaa\x00\xff"


def test_clean_eof_and_multiple_frames(resampy_cli) -> None:
    frames = run_frames(
        resampy_cli,
        [
            bytes([OP_PING]),
            bytes([OP_ECHO, 7]),
            bytes([0x25, 97, 98, 99]),
        ],
    )
    assert len(frames) == 3
    assert frames[0][0] == STATUS_OK
    assert frames[1][1] == b"\x07"
    assert frames[2][1] == hashlib.sha256(b"abc").hexdigest().encode("ascii")


def test_unknown_opcode_and_empty_frame(resampy_cli) -> None:
    error(resampy_cli, bytes([0x7F]))
    error(resampy_cli, b"")


def test_signal_info_metadata(resampy_cli) -> None:
    raw = f64le([1.5, -0.0, float("inf")])
    r = parse_kv(ok(resampy_cli, bytes([OP_SIGNAL_INFO]) + raw))
    assert r["len"] == "3"
    assert r["first_bits"] == "000000000000f83f"
    assert r["last_bits"] == "000000000000f07f"
    assert r["nonfinite"] == "1"


def test_signal_info_empty(resampy_cli) -> None:
    r = parse_kv(ok(resampy_cli, bytes([OP_SIGNAL_INFO])))
    assert r["len"] == "0"
    assert r["first_bits"] == "none"


def test_output_alloc_zero_init(resampy_cli) -> None:
    payload = ok(resampy_cli, bytes([OP_OUTPUT_ALLOC]) + struct.pack(">I", 5))
    values = decode_f64le(payload)
    assert len(values) == 5
    assert all(bits(v) == bits(0.0) for v in values)


def test_output_alloc_empty(resampy_cli) -> None:
    assert ok(resampy_cli, bytes([OP_OUTPUT_ALLOC]) + struct.pack(">I", 0)) == b""


def test_output_set_indexed(resampy_cli) -> None:
    body = bytes([OP_OUTPUT_SET]) + struct.pack(">I", 4) + struct.pack(">I", 2) + f64le([-0.0])
    values = decode_f64le(ok(resampy_cli, body))
    assert len(values) == 4
    assert bits(values[2]) == bits(-0.0)
    assert bits(values[0]) == bits(0.0)


def test_output_set_out_of_range(resampy_cli) -> None:
    body = bytes([OP_OUTPUT_SET]) + struct.pack(">I", 2) + struct.pack(">I", 9) + f64le([1.0])
    error(resampy_cli, body)


def test_filter_load_valid(filter_resource, resampy_cli) -> None:
    meta, resource = filter_resource
    r = parse_kv(ok(resampy_cli, filter_load_body(meta, resource)))
    assert r["filter_id"] == "synthetic_tiny_v1"
    assert r["count"] == "8"
    assert r["byte_order"] == "little"
    assert r["sha256"] == hashlib.sha256(resource).hexdigest()


def test_filter_load_corrupt_hash(filter_resource, resampy_cli) -> None:
    meta, resource = filter_resource
    corrupt = bytearray(resource)
    corrupt[0] ^= 0xFF
    error(resampy_cli, filter_load_body(meta, bytes(corrupt)))


def test_filter_load_truncated(filter_resource, resampy_cli) -> None:
    meta, resource = filter_resource
    error(resampy_cli, filter_load_body(meta, resource[:-8]))


def test_filter_load_invalid_metadata(filter_resource, resampy_cli) -> None:
    _, resource = filter_resource
    bad = json.dumps({"schema_version": 99}).encode("utf-8")
    error(resampy_cli, filter_load_body(bad, resource))


def test_frame_size_limit_is_not_crashed(resampy_cli) -> None:
    # A declared length beyond 64 MiB must produce a framing error frame,
    # followed by a clean non-zero exit (established convention). We require an
    # actual STATUS_ERROR frame rather than accepting a bare crash.
    import subprocess

    from resampy_compat_support import parse_frames

    oversized = struct.pack(">I", 64 * 1024 * 1024 + 1) + b"\x01"
    result = subprocess.run([str(resampy_cli)], input=oversized, capture_output=True, timeout=30)
    frames = parse_frames(result.stdout)
    assert frames, "expected a framing error frame on stdout"
    assert frames[0][0] == 1, f"expected STATUS_ERROR, got {frames[0][0]}"
    assert b"exceeds limit" in frames[0][1]


def test_output_alloc_rejection_bounded(resampy_cli) -> None:
    # P2-06: the reported 20M-element request must be rejected with a status
    # frame (no OOM abort), and the session must survive.
    bodies = [
        bytes([OP_OUTPUT_ALLOC]) + struct.pack(">I", 20_000_000),
        bytes([OP_OUTPUT_ALLOC]) + struct.pack(">I", 1_000_001),
        bytes([OP_PING]),
    ]
    frames = run_frames(resampy_cli, bodies)
    assert len(frames) == 3
    assert frames[0][0] == 1 and b"exceeds limit" in frames[0][1]
    assert frames[1][0] == 1 and b"exceeds limit" in frames[1][1]
    assert frames[2][0] == STATUS_OK, "session must continue after rejected requests"


def test_output_alloc_bounds(resampy_cli) -> None:
    # Zero, one and maximum permitted allocations succeed with exact sizes.
    for n, expected_bytes in [(0, 0), (1, 8)]:
        payload = ok(resampy_cli, bytes([OP_OUTPUT_ALLOC]) + struct.pack(">I", n))
        assert len(payload) == expected_bytes
        assert all(b == 0 for b in payload)
    # Maximum permitted (1_000_000 elements = 8 MB) — verify exact length and
    # a few sampled values without materializing Python float lists.
    big = ok(resampy_cli, bytes([OP_OUTPUT_ALLOC]) + struct.pack(">I", 1_000_000))
    assert len(big) == 8_000_000
    assert big[:8] == b"\x00" * 8
    assert big[-8:] == b"\x00" * 8
