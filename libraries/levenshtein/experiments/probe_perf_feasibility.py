#!/usr/bin/env python3
"""Phase 0 benchmark-feasibility probe (not a benchmark suite).

Measures the pinned reference and its pure-Python fallback to decide which
workloads are worth carrying into Phase 1. Numbers are single-process and
preliminary; they are not published results.

Run with::

    .venv/bin/python libraries/levenshtein/experiments/probe_perf_feasibility.py
"""

from __future__ import annotations

import random
import string
import time

import Levenshtein
from rapidfuzz.distance import Indel_py, Levenshtein_py


def timed_ns(fn, repeats: int) -> tuple[int, int]:
    best = None
    result = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = fn()
        elapsed = time.perf_counter_ns() - start
        if best is None or elapsed < best:
            best = elapsed
    assert best is not None
    return best, result


def make_pair(size: int, mode: str) -> tuple[str, str]:
    rng = random.Random(1000 + size)
    if mode == "equal":
        text = "".join(rng.choice(string.ascii_letters) for _ in range(size))
        return text, text
    if mode == "one-sub":
        left = "".join(rng.choice(string.ascii_letters) for _ in range(size))
        if size == 0:
            return left, left
        index = size // 2
        replacement = "Z" if left[index] != "Z" else "Y"
        return left, left[:index] + replacement + left[index + 1 :]
    if mode == "random":
        left = "".join(rng.choice(string.ascii_letters) for _ in range(size))
        right = "".join(rng.choice(string.ascii_letters) for _ in range(size))
        return left, right
    if mode == "unrelated":
        left = "a" * size
        right = "b" * size
        return left, right
    raise ValueError(mode)


def main() -> int:
    print("Phase 0 feasibility timings; single process, min-of-repeats, ns/op")
    print(f"python: {__import__('platform').python_version()}")
    print(f"Levenshtein: {Levenshtein.__version__}")

    modes = ("equal", "one-sub", "random", "unrelated")
    sizes = (8, 16, 32, 64, 128, 256, 512, 1024, 2048)

    print("\n== distance: C++ vs pure Python ==")
    header = f"{'mode':10} {'n':>5} {'cpp_ns':>10} {'py_ns':>10} {'cpp/py':>8}"
    print(header)
    for mode in modes:
        for size in sizes:
            left, right = make_pair(size, mode)
            inner_repeats = max(1, 200_000 // max(size, 1))
            cpp_ns, cpp_value = timed_ns(
                lambda left=left, right=right: Levenshtein.distance(left, right),
                max(1, inner_repeats),
            )
            py_ns, py_value = timed_ns(
                lambda left=left, right=right: Levenshtein_py.distance(left, right),
                max(1, min(inner_repeats, 20)),
            )
            assert cpp_value == py_value, (mode, size, cpp_value, py_value)
            print(f"{mode:10} {size:5} {cpp_ns:10} {py_ns:10} {cpp_ns / py_ns:8.4f}")

    print("\n== ratio (Indel): C++ vs pure Python ==")
    print(header)
    for mode in modes:
        for size in sizes:
            left, right = make_pair(size, mode)
            inner_repeats = max(1, 200_000 // max(size, 1))
            cpp_ns, cpp_value = timed_ns(
                lambda left=left, right=right: Levenshtein.ratio(left, right),
                max(1, inner_repeats),
            )
            py_ns, py_value = timed_ns(
                lambda left=left, right=right: Indel_py.normalized_similarity(left, right),
                max(1, min(inner_repeats, 20)),
            )
            assert cpp_value == py_value, (mode, size, cpp_value, py_value)
            print(f"{mode:10} {size:5} {cpp_ns:10} {py_ns:10} {cpp_ns / py_ns:8.4f}")

    print("\n== fixed-workload sanity (n=64, random) ==")
    left, right = make_pair(64, "random")
    count = 20_000
    cpp_ns, _ = timed_ns(lambda: sum(Levenshtein.distance(left, right) for _ in range(count)), 3)
    print(f"C++ distance: {cpp_ns / count:.1f} ns/op over {count} calls")
    py_ns, _ = timed_ns(lambda: sum(Levenshtein_py.distance(left, right) for _ in range(200)), 3)
    print(f"pure-Python distance: {py_ns / 200:.1f} ns/op over 200 calls")

    print("\n== ASCII vs Unicode ==")
    ascii_left = "the quick brown fox jumps over the lazy dog"
    ascii_right = "the quick brown cat jumps over a lazy dog"
    unicode_left = "naïve café — ¿qué? 😀"
    unicode_right = "naive cafe — ¿que? 😃"
    for label, left, right in (
        ("ascii", ascii_left, ascii_right),
        ("unicode", unicode_left, unicode_right),
    ):
        cpp_ns, value = timed_ns(
            lambda left=left, right=right: Levenshtein.distance(left, right), 5
        )
        print(f"{label}: distance={value} cpp={cpp_ns} ns")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
