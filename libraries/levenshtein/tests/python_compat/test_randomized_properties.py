"""Deterministic randomized comparison: CLI vs rapidfuzz oracle.

Fresh pairs (not in the golden bundle) across lengths, alphabets, and
parameter shapes, sent through the native CLI in batches. Complements
the golden vectors with property-style coverage: symmetry, truncation
bounds, and exact agreement on every sampled input.
"""

from __future__ import annotations

import random
import struct
from pathlib import Path

from rapidfuzz.distance import Hamming, Indel, Levenshtein

STATUS_OK = 0
STATUS_ERROR = 1
SEED = 40404
PAIRS = 200


def request(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def field(text: str) -> bytes:
    encoded = text.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def run_cli(binary: Path, data: bytes) -> bytes:
    import subprocess

    result = subprocess.run([str(binary)], input=data, capture_output=True, timeout=300)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert result.stderr == b""
    return result.stdout


def parse_all(payload: bytes) -> list[tuple[int, bytes]]:
    frames: list[tuple[int, bytes]] = []
    offset = 0
    while offset < len(payload):
        (length,) = struct.unpack(">I", payload[offset : offset + 4])
        offset += 4
        body = payload[offset : offset + length]
        offset += length
        frames.append((body[0], body[1:]))
    assert offset == len(payload)
    return frames


def sample_pairs() -> list[tuple[str, str]]:
    rng = random.Random(SEED)
    alphabet = list("abcdefABCDEF0123456789 _-éèêëßæñøü中あ😀😃")
    pairs = [("", ""), ("", "abc"), ("x", ""), ("é", "e\u0301"), ("😀a", "a😀")]
    for _ in range(PAIRS):
        left = "".join(rng.choice(alphabet) for _ in range(rng.randrange(70)))
        right = "".join(rng.choice(alphabet) for _ in range(rng.randrange(70)))
        pairs.append((left, right))
    return pairs


def test_randomized_cli_agreement(levenshtein_cli: Path) -> None:
    pairs = sample_pairs()
    requests: list[bytes] = []
    expectations: list[tuple[str, object]] = []
    for left, right in pairs:
        requests.append(
            request(b"\x20" + struct.pack(">Q", 1) * 3 + b"\x00" + field(left) + field(right))
        )
        expectations.append(("int", Levenshtein.distance(left, right)))
        requests.append(request(b"\x21" + field(left) + field(right)))
        expectations.append(("float", Indel.normalized_similarity(left, right)))
        requests.append(request(b"\x22\x01" + field(left) + field(right)))
        expectations.append(("int", Hamming.distance(left, right, pad=True)))
        if len(left) != len(right):
            requests.append(request(b"\x22\x00" + field(left) + field(right)))
            expectations.append(("error", "Sequences are not the same length."))
        weights = (2, 1, 1) if len(left) % 2 == 0 else (1, 1, 2)
        requests.append(
            request(b"\x20" + struct.pack(">QQQ", *weights) + b"\x00" + field(left) + field(right))
        )
        expectations.append(("int", Levenshtein.distance(left, right, weights=weights)))

    stdout = run_cli(levenshtein_cli, b"".join(requests))
    frames = parse_all(stdout)
    assert len(frames) == len(expectations)
    for (status, payload), (kind, expected) in zip(frames, expectations, strict=True):
        if kind == "error":
            assert status == STATUS_ERROR
            assert expected.encode("utf-8") in payload
        else:
            assert status == STATUS_OK
            if kind == "int":
                (value,) = struct.unpack(">Q", payload)
            else:
                (value,) = struct.unpack(">d", payload)
            assert value == expected


def test_symmetry_and_truncation_bounds(levenshtein_cli: Path) -> None:
    pairs = sample_pairs()[:40]
    requests: list[bytes] = []
    for left, right in pairs:
        requests.append(
            request(b"\x20" + struct.pack(">Q", 1) * 3 + b"\x00" + field(left) + field(right))
        )
        requests.append(
            request(b"\x20" + struct.pack(">Q", 1) * 3 + b"\x00" + field(right) + field(left))
        )
        distance = Levenshtein.distance(left, right)
        cutoff = max(distance - 1, 0)
        requests.append(
            request(
                b"\x20"
                + struct.pack(">Q", 1) * 3
                + b"\x01"
                + struct.pack(">Q", cutoff)
                + field(left)
                + field(right)
            )
        )
    stdout = run_cli(levenshtein_cli, b"".join(requests))
    frames = parse_all(stdout)
    assert len(frames) == 3 * len(pairs)
    for index, (left, right) in enumerate(pairs):
        forward = struct.unpack(">Q", frames[3 * index][1])[0]
        backward = struct.unpack(">Q", frames[3 * index + 1][1])[0]
        assert forward == backward == Levenshtein.distance(left, right)
        assert frames[3 * index + 2][0] == STATUS_OK
        truncated = struct.unpack(">Q", frames[3 * index + 2][1])[0]
        distance = Levenshtein.distance(left, right)
        assert truncated == min(distance, max(distance - 1, 0) + 1)
