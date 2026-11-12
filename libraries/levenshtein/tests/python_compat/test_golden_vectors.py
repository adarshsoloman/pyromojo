"""Golden vectors through the native CLI, one batched session.

Every ``via_cli`` case in the committed bundle is encoded, sent in a
single CLI invocation, and compared exactly (integers) or bit-exactly
(float64 payload). Cases that cannot cross the CLI (negative weights
and cutoffs are not u64-encodable) are skipped here and covered by the
native ``test_generated_vectors`` suite instead; the skipped id set is
asserted to stay exactly the documented two.
"""

from __future__ import annotations

import struct
from pathlib import Path

STATUS_OK = 0
STATUS_ERROR = 1

DOCUMENTED_CLI_SKIPS = {"weights_negative", "cutoff_negative"}


def request(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def field(text: str) -> bytes:
    encoded = text.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def encode(case: dict) -> bytes:
    op = case["op"]
    if op == "distance":
        body = b"\x20"
        for weight in case["weights"]:
            body += struct.pack(">Q", weight)
        if case["cutoff"] is None:
            body += b"\x00"
        else:
            body += b"\x01" + struct.pack(">Q", case["cutoff"])
        body += field(case["s1"]) + field(case["s2"])
        return request(body)
    if op == "ratio":
        return request(b"\x21" + field(case["s1"]) + field(case["s2"]))
    if op == "hamming":
        return request(
            b"\x22"
            + (b"\x01" if case.get("pad", True) else b"\x00")
            + field(case["s1"])
            + field(case["s2"])
        )
    raise AssertionError(f"unknown op {op!r}")


def decode(case: dict, payload: bytes):
    op = case["op"]
    if op == "ratio":
        (value,) = struct.unpack(">d", payload)
        return value
    (value,) = struct.unpack(">Q", payload)
    return value


def run_cli(binary: Path, data: bytes) -> tuple[int, bytes, bytes]:
    import subprocess

    result = subprocess.run([str(binary)], input=data, capture_output=True, timeout=300)
    return result.returncode, result.stdout, result.stderr


def test_all_cli_covered_vectors(vectors_bundle: dict, levenshtein_cli: Path) -> None:
    cases = [c for c in vectors_bundle["cases"] if c.get("via_cli", True)]
    skipped = {c["id"] for c in vectors_bundle["cases"] if not c.get("via_cli", True)}
    assert skipped == DOCUMENTED_CLI_SKIPS

    data = b"".join(encode(case) for case in cases)
    returncode, stdout, stderr = run_cli(levenshtein_cli, data)
    assert returncode == 0, stderr.decode("utf-8", "replace")
    assert stderr == b""

    offset = 0
    for case in cases:
        assert len(stdout) - offset >= 4, f"truncated header at {case['id']}"
        (length,) = struct.unpack(">I", stdout[offset : offset + 4])
        offset += 4
        assert len(stdout) - offset >= length, f"truncated body at {case['id']}"
        body = stdout[offset : offset + length]
        offset += length
        assert body, f"empty body at {case['id']}"
        status, payload = body[0], body[1:]
        if "error_contains" in case:
            assert status == STATUS_ERROR, case["id"]
            assert case["error_contains"].encode("utf-8") in payload, case["id"]
        else:
            assert status == STATUS_OK, (case["id"], payload)
            assert decode(case, payload) == case["expected"], case["id"]
    assert offset == len(stdout), "trailing bytes in CLI output"
