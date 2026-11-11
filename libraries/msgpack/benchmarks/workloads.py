"""Deterministic benchmark workloads and the shared value fingerprint.

Every workload is built from ``random.Random`` with the configured fixed
seed, so all three implementations process equivalent logical values. The
fingerprint fold mirrors ``bench.mojo`` exactly (FNV-1a over kind tags and
big-endian payloads); equal fingerprints mean equivalent decoded values.
"""

from __future__ import annotations

import random
import struct

from generate_vectors import MapPairs

import msgpack

FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211
MASK64 = (1 << 64) - 1

KIND_NIL = 0
KIND_BOOL = 1
KIND_INT = 2
KIND_FLOAT32 = 3
KIND_FLOAT64 = 4
KIND_STR = 5
KIND_BIN = 6
KIND_ARRAY = 7
KIND_MAP = 8
KIND_EXT = 9
KIND_TIMESTAMP = 10
KIND_UINT = 11


def _update(h: int, byte: int) -> int:
    return ((h ^ byte) * FNV_PRIME) & MASK64


def _bytes(h: int, data: bytes) -> int:
    for byte in data:
        h = _update(h, byte)
    return h


def fingerprint(value) -> int:
    """Fold any unpacked value exactly like the Mojo benchmark does."""
    h = FNV_OFFSET
    h = _fold(h, value)
    return h


def _fold(h: int, value) -> int:
    if value is None:
        return _update(h, KIND_NIL)
    if isinstance(value, bool):
        h = _update(h, KIND_BOOL)
        return _update(h, 1 if value else 0)
    if isinstance(value, int):
        if value < 0:
            h = _update(h, KIND_INT)
            return _bytes(h, struct.pack(">q", value))
        h = _update(h, KIND_UINT)
        return _bytes(h, struct.pack(">Q", value))
    if isinstance(value, float):
        h = _update(h, KIND_FLOAT64)
        return _bytes(h, struct.pack(">d", value))
    if isinstance(value, str):
        h = _update(h, KIND_STR)
        return _bytes(h, value.encode("utf-8"))
    if isinstance(value, (bytes, bytearray)):
        h = _update(h, KIND_BIN)
        return _bytes(h, bytes(value))
    if isinstance(value, msgpack.Timestamp):
        h = _update(h, KIND_TIMESTAMP)
        h = _bytes(h, struct.pack(">q", value.seconds))
        return _bytes(h, struct.pack(">I", value.nanoseconds))
    if isinstance(value, msgpack.ExtType):
        h = _update(h, KIND_EXT)
        h = _update(h, value.code & 0xFF)
        return _bytes(h, bytes(value.data))
    if isinstance(value, MapPairs):
        h = _update(h, KIND_MAP)
        for key, item in value:
            h = _fold(h, key)
            h = _fold(h, item)
        return h
    if isinstance(value, dict):
        h = _update(h, KIND_MAP)
        for key, item in value.items():
            h = _fold(h, key)
            h = _fold(h, item)
        return h
    if isinstance(value, (list, tuple)):
        h = _update(h, KIND_ARRAY)
        for item in value:
            h = _fold(h, item)
        return h
    raise AssertionError(f"unfoldable value {type(value).__name__}")


def fnv_single(data: bytes) -> int:
    """Single-pass FNV-1a over encoded bytes (encode checksum comparison)."""
    return _bytes(FNV_OFFSET, data)


def build_workloads(seed: int) -> list[tuple[str, str, object]]:
    """Return (name, description, value) triples in a stable order."""
    rng = random.Random(seed)

    def mixed_int(index: int) -> int:
        pools = [
            rng.randint(-100, 100),
            rng.randint(0, 255),
            rng.randint(0, 65535),
            rng.randint(0, 2**32 - 1),
            rng.randint(0, 2**64 - 1),
            rng.randint(-(2**63), -129),
            rng.randint(-128, 127),
        ]
        return pools[index % len(pools)]

    primitives = [
        1,
        -2,
        300,
        70000,
        2**40,
        2**63 - 1,
        -(2**63),
        1.5,
        -0.0,
        3.14159,
        1e300,
        "hello",
        "héllo € 😀",
        "",
        "x" * 100,
        b"\x00\xff\x80",
        b"y" * 64,
        True,
        False,
        None,
    ]
    ints_small = [mixed_int(index) for index in range(1000)]
    ints_large = [mixed_int(index) for index in range(100000)]
    floats = [rng.uniform(-1e6, 1e6) for _ in range(10000)]
    floats += [1e300, 1e-300, float("inf"), float("-inf"), -0.0]
    strings = []
    for index in range(1000):
        length = [0, 1, 5, 31, 32, 100, 1000][index % 7]
        if index % 11 == 0:
            strings.append(("héllo € 😀" * ((length // 8) + 1))[: max(length, 8)])
        else:
            strings.append("s" * length)
    binary = [rng.randbytes(size) for size in (0, 1, 255, 256, 1000, 10000, 65535, 100000)]
    maps_small = {f"k{index:03d}": mixed_int(index) for index in range(100)}
    maps_large = {f"k{index:05d}": mixed_int(index) for index in range(20000)}

    nested: object = [1, "two", None]
    for level in range(12):
        if level % 2 == 0:
            nested = {"level": level, "child": nested, "flag": level % 2 == 0}
        else:
            nested = [level, nested, level * 1.5]

    telemetry = []
    for index in range(500):
        telemetry.append(
            {
                "sensor": f"s-{index % 8}",
                "ts": msgpack.Timestamp(1700000000 + index, (index * 7919) % 10**9),
                "values": [rng.uniform(-100.0, 100.0) for _ in range(8)],
                "ok": index % 2 == 0,
                "code": index % 256,
            }
        )

    payload_large = {
        "name": "z" * 500000,
        "blob": rng.randbytes(300000),
        "series": [mixed_int(index) for index in range(50000)],
        "meta": {"k": "v" * 1000, "n": -123456789},
    }

    extensions = [
        msgpack.ExtType(0, b""),
        msgpack.ExtType(3, b"\x01" * 17),
        msgpack.ExtType(42, b"q" * 300),
        msgpack.ExtType(127, b"\xff" * 16),
        msgpack.Timestamp(2**32 - 1, 0),
        msgpack.Timestamp(-5, 123),
        msgpack.Timestamp(2**34, 999999999),
        [msgpack.ExtType(7, b"\x00"), msgpack.Timestamp(0, 999999999)],
    ]

    return [
        ("primitives", "19-item mixed array of scalars (int/float/str/bin/bool/nil)", primitives),
        ("ints_small", "array of 1,000 mixed-width integers", ints_small),
        ("ints_large", "array of 100,000 mixed-width integers", ints_large),
        ("floats", "array of 10,005 float64 values incl. extremes", floats),
        ("strings", "array of 1,000 strings, 0..1000 bytes, some unicode", strings),
        ("binary", "array of 8 blobs, 0..100,000 bytes", binary),
        ("maps_small", "map of 100 str->int pairs", maps_small),
        ("maps_large", "map of 20,000 str->int pairs", maps_large),
        ("nested", "12-deep alternating array/map nesting", nested),
        ("telemetry", "500 sensor readings with timestamps", telemetry),
        ("payload_large", "~1 MB mixed document", payload_large),
        ("extensions", "ext and timestamp values incl. nesting", extensions),
    ]
