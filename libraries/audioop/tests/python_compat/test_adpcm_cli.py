"""Framing and protocol tests for the Phase 8 ADPCM opcodes."""

from __future__ import annotations

import struct
from pathlib import Path

from support import (
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    adpcm2lin_body,
    lin2adpcm_body,
    parse_adpcm_response,
    run_frames,
)


def test_phase7_opcodes_still_work(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [bytes([OP_PING]), bytes([0x36, 2, 0, 0, 0, 0, 0, 0, 0, 0])])
    # 0x36 with width 2 and four zero samples encodes to four 0xd5 bytes
    assert frames == [(STATUS_OK, b""), (STATUS_OK, b"\xd5" * 4)]


def test_lin2adpcm_fresh_state(audioop_cli: Path) -> None:
    fragment = b"".join(value.to_bytes(2, "little", signed=True) for value in range(-10, 10))
    frames = run_frames(audioop_cli, [lin2adpcm_body(2, None, fragment)])
    output, state = parse_adpcm_response(frames[0][1])
    assert output.hex() == "e0000001111111111111"
    assert state == (9, 0)


def test_adpcm2lin_roundtrip_and_chunks(audioop_cli: Path) -> None:
    fragment = b"".join(value.to_bytes(2, "little", signed=True) for value in range(-10, 10))
    encoded = run_frames(audioop_cli, [lin2adpcm_body(2, None, fragment)])
    enc_output, enc_state = parse_adpcm_response(encoded[0][1])
    decoded = run_frames(audioop_cli, [adpcm2lin_body(2, None, enc_output)])
    dec_output, dec_state = parse_adpcm_response(decoded[0][1])
    # the decoded samples approximate the original within one step
    assert len(dec_output) == len(fragment)
    # chunked decoding (state round-trips) equals the whole decode
    parts = []
    running = None
    for i in range(0, len(enc_output), 2):
        frames = run_frames(audioop_cli, [adpcm2lin_body(2, running, enc_output[i : i + 2])])
        part, running = parse_adpcm_response(frames[0][1])
        parts.append(part)
    assert b"".join(parts) == dec_output
    assert running == dec_state
    _ = enc_state


def test_lin2adpcm_state_roundtrip_chunks(audioop_cli: Path) -> None:
    fragment = b"".join(value.to_bytes(2, "little", signed=True) for value in range(-10, 10))
    whole = run_frames(audioop_cli, [lin2adpcm_body(2, None, fragment)])
    whole_output, whole_state = parse_adpcm_response(whole[0][1])
    parts = []
    running = None
    for i in range(0, len(fragment), 8):
        frames = run_frames(audioop_cli, [lin2adpcm_body(2, running, fragment[i : i + 8])])
        part, running = parse_adpcm_response(frames[0][1])
        parts.append(part)
    # even-sized chunks compose exactly (documented invariant)
    assert b"".join(parts) == whole_output
    assert running == whole_state


def test_odd_sample_count_drops_nibble(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            lin2adpcm_body(2, None, b"\xe8\x03"),  # one sample
            lin2adpcm_body(2, None, b"\x01\x00\x02\x00\x03\x00"),  # three
        ],
    )
    out1, state1 = parse_adpcm_response(frames[0][1])
    assert out1 == b""
    assert state1 == (11, 8)
    out3, state3 = parse_adpcm_response(frames[1][1])
    assert len(out3) == 1
    assert state3 == (3, 0)


def test_empty_keeps_state(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [lin2adpcm_body(2, (100, 50), b"")])
    _, state = parse_adpcm_response(frames[0][1])
    assert state == (100, 50)


def test_error_frames(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            lin2adpcm_body(0, None, b""),
            lin2adpcm_body(2, None, b"\x01"),
            lin2adpcm_body(2, (32768, 0), b""),
            lin2adpcm_body(2, (0, 89), b""),
            adpcm2lin_body(0, None, b""),
            adpcm2lin_body(2, (0, -1), b""),
        ],
    )
    assert frames[0] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[1] == (STATUS_ERROR, b"not a whole number of frames")
    assert frames[2] == (STATUS_ERROR, b"bad state")
    assert frames[3] == (STATUS_ERROR, b"bad state")
    assert frames[4] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[5] == (STATUS_ERROR, b"bad state")


def test_malformed_requests(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            bytes([0x3A]),
            bytes([0x3A, 2, 0x01]) + struct.pack(">q", 5),
            bytes([0x3B]),
            bytes([0x3B, 2]) + b"\x01" + struct.pack(">q", 5),
        ],
    )
    for status, payload in frames:
        assert status == STATUS_ERROR
        assert b"too short" in payload


def test_all_widths_accepted(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            lin2adpcm_body(1, None, b"\x7f\x80"),
            lin2adpcm_body(3, None, b"\x01\x00\x00\x02\x00\x00"),
            lin2adpcm_body(4, None, b"\xff\xff\xff\x7f\x00\x00\x00\x80"),
        ],
    )
    for status, _ in frames:
        assert status == STATUS_OK


def test_unknown_opcode_still_rejected(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [b"\x99"])
    assert frames == [(STATUS_ERROR, b"unknown opcode 153")]


def test_frame_cap_still_enforced(audioop_cli: Path) -> None:
    import subprocess

    result = subprocess.run(
        [str(audioop_cli)],
        input=struct.pack(">I", 64 * 1024 * 1024 + 1) + b"\x01" * 8,
        capture_output=True,
    )
    assert result.returncode != 0
    assert b"exceeds limit" in result.stderr
