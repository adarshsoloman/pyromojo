"""Framing and operation tests for the audioop sample CLI."""

from __future__ import annotations

from pathlib import Path

from support import (
    OP_ECHO,
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    decode_body,
    decode_values,
    encode_body,
    request,
    run_frames,
)


def test_ping_and_echo(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [bytes([OP_PING]), bytes([OP_ECHO]) + b"hello"])
    assert frames == [(STATUS_OK, b""), (STATUS_OK, b"hello")]


def test_clean_eof_exits_zero_without_output(audioop_cli: Path) -> None:
    import subprocess

    result = subprocess.run([str(audioop_cli)], input=b"", capture_output=True)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


def test_unknown_opcode_and_empty_frame(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [b"\x99", b""])
    assert frames == [
        (STATUS_ERROR, b"unknown opcode 153"),
        (STATUS_ERROR, b"empty request frame"),
    ]


def test_decode_and_encode_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            decode_body(2, b"\x34\x12\xcc\xff"),
            encode_body(2, [4660, -52]),
        ],
    )
    assert frames == [
        (STATUS_OK, b"4660 -52"),
        (STATUS_OK, b"\x34\x12\xcc\xff"),
    ]


def test_empty_fragment_roundtrip(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [decode_body(3, b""), encode_body(3, [])])
    assert frames == [(STATUS_OK, b""), (STATUS_OK, b"")]


def test_error_frames(audioop_cli: Path) -> None:
    frames = run_frames(
        audioop_cli,
        [
            decode_body(0, b""),
            decode_body(2, b"\x01\x02\x03"),
            encode_body(1, [128]),
        ],
    )
    assert frames[0] == (STATUS_ERROR, b"Size should be 1, 2, 3 or 4")
    assert frames[1] == (STATUS_ERROR, b"not a whole number of frames")
    assert frames[2] == (STATUS_ERROR, b"sample value 128 out of range for width 1")


def test_truncated_frame_is_fatal(audioop_cli: Path) -> None:
    import subprocess

    result = subprocess.run(
        [str(audioop_cli)],
        input=request(b"\x01")[:-2],
        capture_output=True,
    )
    assert result.returncode != 0
    assert b"truncated frame header" in result.stderr


def test_decode_rejects_short_payload(audioop_cli: Path) -> None:
    frames = run_frames(audioop_cli, [bytes([0x20]), bytes([0x21])])
    assert frames[0] == (STATUS_ERROR, b"decode request too short: need a width byte")
    assert frames[1] == (STATUS_ERROR, b"encode request too short: need a width byte")
    assert decode_values(b"") == []
