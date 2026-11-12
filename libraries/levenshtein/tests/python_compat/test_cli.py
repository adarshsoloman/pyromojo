"""Byte-level tests for the Levenshtein batch CLI framing protocol."""

from __future__ import annotations

import struct
from pathlib import Path

STATUS_OK = 0
STATUS_ERROR = 1
MAX_FRAME_BYTES = 64 * 1024 * 1024


def request(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def run_cli(binary: Path, data: bytes, timeout: float = 60) -> tuple[int, bytes, bytes]:
    import subprocess

    result = subprocess.run(
        [str(binary)],
        input=data,
        capture_output=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def parse_frames(payload: bytes) -> list[tuple[int, bytes]]:
    frames: list[tuple[int, bytes]] = []
    offset = 0
    while offset < len(payload):
        assert len(payload) - offset >= 4, "truncated response header"
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        offset += 4
        assert len(payload) - offset >= length, "truncated response body"
        body = payload[offset : offset + length]
        offset += length
        assert body, "response body must contain a status byte"
        frames.append((body[0], body[1:]))
    return frames


def field(text: str) -> bytes:
    encoded = text.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def distance_request(
    s1: str,
    s2: str,
    weights: tuple[int, int, int] = (1, 1, 1),
    cutoff: int | None = None,
) -> bytes:
    body = b"\x20"
    for weight in weights:
        body += struct.pack(">Q", weight)
    if cutoff is None:
        body += b"\x00"
    else:
        body += b"\x01" + struct.pack(">Q", cutoff)
    return request(body + field(s1) + field(s2))


def test_ping_and_echo(levenshtein_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(
        levenshtein_cli, request(b"\x01") + request(b"\x02\x00\xffhello")
    )
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [(STATUS_OK, b""), (STATUS_OK, b"\x00\xffhello")]


def test_clean_eof_exits_zero_without_output(levenshtein_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(levenshtein_cli, b"")
    assert returncode == 0
    assert stdout == b""
    assert stderr == b""


def test_clean_eof_after_frames(levenshtein_cli: Path) -> None:
    returncode, stdout, _ = run_cli(levenshtein_cli, request(b"\x01"))
    assert returncode == 0
    assert parse_frames(stdout) == [(STATUS_OK, b"")]


def test_unknown_opcode_is_an_error_frame(levenshtein_cli: Path) -> None:
    returncode, stdout, stderr = run_cli(levenshtein_cli, request(b"\x99"))
    assert returncode == 0
    assert stderr == b""
    frames = parse_frames(stdout)
    assert frames[0][0] == STATUS_ERROR
    assert b"unknown opcode 153" in frames[0][1]


def test_empty_request_body_is_an_error_frame(levenshtein_cli: Path) -> None:
    returncode, stdout, _ = run_cli(levenshtein_cli, request(b""))
    assert returncode == 0
    frames = parse_frames(stdout)
    assert frames == [(STATUS_ERROR, b"empty request frame")]


def test_batch_mode_answers_mixed_requests_in_order(levenshtein_cli: Path) -> None:
    data = (
        request(b"\x01")
        + distance_request("kitten", "sitting")
        + request(b"\x99")
        + request(b"")
        + distance_request("abc", "adc")
    )
    returncode, stdout, stderr = run_cli(levenshtein_cli, data)
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [
        (STATUS_OK, b""),
        (STATUS_OK, struct.pack(">Q", 3)),
        (STATUS_ERROR, b"unknown opcode 153"),
        (STATUS_ERROR, b"empty request frame"),
        (STATUS_OK, struct.pack(">Q", 1)),
    ]


def test_echo_is_binary_safe_and_handles_pipe_chunks(levenshtein_cli: Path) -> None:
    payload = bytes(range(256)) * 4096
    returncode, stdout, stderr = run_cli(levenshtein_cli, request(b"\x02" + payload))
    assert returncode == 0
    assert stderr == b""
    assert parse_frames(stdout) == [(STATUS_OK, payload)]


def test_malformed_distance_payloads_are_error_frames(
    levenshtein_cli: Path,
) -> None:
    bodies = [
        b"\x20\x00\x00\x00",  # truncated weights
        b"\x20" + struct.pack(">Q", 1) * 3 + b"\x02",  # bad cutoff flag
        b"\x20" + struct.pack(">Q", 1) * 3 + b"\x00" + struct.pack(">I", 10),  # short s1
        b"\x20"
        + struct.pack(">Q", 1) * 3
        + b"\x00"
        + field("ab")
        + field("cd")
        + b"extra",  # trailing bytes
        b"\x20"
        + struct.pack(">Q", 1) * 3
        + b"\x00"
        + struct.pack(">I", 1)
        + b"\xff"
        + field(""),  # invalid UTF-8
        b"\x22\x02" + field("a") + field("b"),  # bad hamming pad flag
        b"\x22\x01" + struct.pack(">I", 2) + b"ab",  # truncated second string
    ]
    data = b"".join(request(body) for body in bodies)
    returncode, stdout, stderr = run_cli(levenshtein_cli, data)
    assert returncode == 0
    assert stderr == b""
    frames = parse_frames(stdout)
    assert len(frames) == len(bodies)
    for status, _ in frames:
        assert status == STATUS_ERROR


def test_u64_weights_beyond_int_range_are_rejected(
    levenshtein_cli: Path,
) -> None:
    huge = struct.pack(">Q", 2**63)
    body = b"\x20" + huge + struct.pack(">Q", 1) * 2 + b"\x00" + field("a") + field("b")
    returncode, stdout, stderr = run_cli(levenshtein_cli, request(body))
    assert returncode == 0
    assert stderr == b""
    frames = parse_frames(stdout)
    assert frames[0][0] == STATUS_ERROR
    assert b"Int range" in frames[0][1]


def test_u64_cutoff_beyond_int_range_is_no_truncation(
    levenshtein_cli: Path,
) -> None:
    # A cutoff above Int range can never truncate (every distance fits in
    # Int), so it must behave exactly like no cutoff — not an error.
    huge = struct.pack(">Q", 2**64 - 1)
    body = b"\x20" + struct.pack(">Q", 1) * 3 + b"\x01" + huge + field("abc") + field("xyz")
    returncode, stdout, stderr = run_cli(levenshtein_cli, request(body))
    assert returncode == 0
    assert stderr == b""
    frames = parse_frames(stdout)
    assert frames == [(STATUS_OK, struct.pack(">Q", 3))]


def test_framing_errors_emit_one_error_frame_and_fail(
    levenshtein_cli: Path,
) -> None:
    cases = [
        (b"\x00\x00", b"truncated frame header"),
        (struct.pack(">I", 3) + b"\x01", b"truncated frame body"),
        (struct.pack(">I", MAX_FRAME_BYTES + 1), b"exceeds limit"),
    ]
    for data, message in cases:
        returncode, stdout, stderr = run_cli(levenshtein_cli, data)
        assert returncode != 0
        assert stderr != b""
        frames = parse_frames(stdout)
        assert len(frames) == 1
        assert frames[0][0] == STATUS_ERROR
        assert message in frames[0][1]


def test_valid_frame_before_framing_error_is_answered(
    levenshtein_cli: Path,
) -> None:
    data = request(b"\x01") + struct.pack(">I", 5) + b"\x02ab"
    returncode, stdout, stderr = run_cli(levenshtein_cli, data)
    assert returncode != 0
    assert stderr != b""
    frames = parse_frames(stdout)
    assert frames[0] == (STATUS_OK, b"")
    assert frames[1][0] == STATUS_ERROR
    assert len(frames) == 2
