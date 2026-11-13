"""Deterministic bitarray benchmark workloads.

Every workload is a fixed logical bit sequence built from
``random.Random`` with the configured seed, in a fixed build order,
plus the shift distances exercised for it. All three implementations
process logically identical sequences (the same bit strings; each
implementation packs them according to the workload endianness).

Sizes sweep 64 bits to 1 MiB. Distributions cover all-zero, all-one,
alternating, sparse random, dense random, and uniform random inputs.
For binary operations the second operand is drawn independently from
the same distribution (fixed patterns repeat identically on both
sides by construction).
"""

from __future__ import annotations

import random


def shift_distances(n: int) -> list[int]:
    """Shift counts benchmarked at size n (deduplicated, ascending)."""
    if n <= 0:
        return [0]
    return sorted({d for d in (1, 8, 64, n // 4, n) if d <= n})


def _pattern_bits(rng: random.Random, dist: str, n: int, dense_p: float, sparse_p: float) -> str:
    if dist == "zeros":
        return "0" * n
    if dist == "ones":
        return "1" * n
    if dist == "alternating":
        return "".join("1" if i % 2 == 0 else "0" for i in range(n))
    if dist == "sparse":
        return "".join("1" if rng.random() < sparse_p else "0" for _ in range(n))
    if dist == "dense":
        return "".join("0" if rng.random() < (1.0 - dense_p) else "1" for _ in range(n))
    return "".join(rng.choice("01") for _ in range(n))


def build_workloads(seed: int, config: dict) -> list[dict]:
    """Return workload dicts in a stable order.

    Each workload holds two independent logical operands (``bits_a``,
    ``bits_b``), the endianness, and the shift distances for that size.
    """
    rng = random.Random(seed)
    workloads: list[dict] = []
    for n in config["sizes"]:
        for dist in config["distributions"]:
            for endian in config["endianness"]:
                bits_a = _pattern_bits(
                    rng, dist, n, config["dense_density"], config["sparse_density"]
                )
                bits_b = _pattern_bits(
                    rng, dist, n, config["dense_density"], config["sparse_density"]
                )
                workloads.append(
                    {
                        "id": f"n{n:07d}-{dist}-{endian}",
                        "nbits": n,
                        "dist": dist,
                        "endian": endian,
                        "bits_a": bits_a,
                        "bits_b": bits_b,
                        "shifts": shift_distances(n),
                    }
                )
    return workloads


def workload_bytes(bits: str, endian: str) -> bytes:
    """Pack a logical bit string the way the C reference does."""
    from bitarray import bitarray

    return bitarray(bits, endian=endian).tobytes()


def fnv1a_checksum(nbits: int, endian_id: int, packed: bytes) -> int:
    """FNV-1a 64-bit checksum over nbits, endian id, and packed bytes.

    Identical inputs to the Mojo ``bench.mojo`` checksum, used to
    verify large benchmark results without shipping full hex dumps.
    """
    import struct

    data = struct.pack(">I", nbits) + bytes([endian_id]) + packed
    h = 14695981039346656037
    for byte in data:
        h = ((h ^ byte) * 1099511628217961) & 0xFFFFFFFFFFFFFFFF
    return h
