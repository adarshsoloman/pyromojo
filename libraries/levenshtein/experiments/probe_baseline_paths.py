#!/usr/bin/env python3
"""Phase 0: measure the candidate benchmark paths on identical inputs.

Paths:
  1. naive Python DP (the honest pure-Python baseline)
  2. rapidfuzz pure-Python implementation (bit-parallel, algorithmically optimized)
  3. pinned C++ reference (Levenshtein package)
  4. native Mojo numbers are recorded separately by mojo_dp_probe.mojo

Run with::

    .venv/bin/python libraries/levenshtein/experiments/probe_baseline_paths.py
"""

from __future__ import annotations

import random
import string
import time

import Levenshtein
from rapidfuzz.distance import Indel_py, Levenshtein_py


def naive_distance(left: str, right: str) -> int:
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, ch_left in enumerate(left, start=1):
        current = [i] + [0] * len(right)
        for j, ch_right in enumerate(right, start=1):
            cost = 0 if ch_left == ch_right else 1
            current[j] = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + cost,
            )
        previous = current
    return previous[-1]


def naive_ratio(left: str, right: str) -> float:
    total = len(left) + len(right)
    if total == 0:
        return 1.0
    if not left or not right:
        return 0.0
    previous = [0] * (len(right) + 1)
    for ch_left in left:
        current = [0] * (len(right) + 1)
        for j, ch_right in enumerate(right, start=1):
            if ch_left == ch_right:
                current[j] = previous[j - 1] + 1
            else:
                current[j] = max(previous[j], current[j - 1])
        previous = current
    indel = total - 2 * previous[-1]
    return 1.0 - indel / total


def timed(fn, repeats: int) -> tuple[int, object]:
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


def main() -> int:
    rng = random.Random(20260101)
    print("Phase 0 baseline-path timings; min-of-repeats, ns/op")
    print(
        f"{'n':>5} {'naive_dist':>12} {'py_dist':>10} {'cpp_dist':>10}"
        f" {'naive_ratio':>12} {'py_ratio':>10} {'cpp_ratio':>10}"
    )

    for size in (8, 16, 32, 64, 128, 256, 512):
        left = "".join(rng.choice(string.ascii_letters) for _ in range(size))
        right = "".join(rng.choice(string.ascii_letters) for _ in range(size))
        repeats = 3 if size <= 128 else 2
        naive_ns, naive_value = timed(
            lambda left=left, right=right: naive_distance(left, right), repeats
        )
        py_ns, py_value = timed(
            lambda left=left, right=right: Levenshtein_py.distance(left, right), repeats
        )
        cpp_ns, cpp_value = timed(
            lambda left=left, right=right: Levenshtein.distance(left, right), repeats
        )
        nr_ns, nr_value = timed(lambda left=left, right=right: naive_ratio(left, right), repeats)
        pr_ns, pr_value = timed(
            lambda left=left, right=right: Indel_py.normalized_similarity(left, right), repeats
        )
        cr_ns, cr_value = timed(
            lambda left=left, right=right: Levenshtein.ratio(left, right), repeats
        )
        assert naive_value == py_value == cpp_value, size
        assert nr_value == pr_value == cr_value, size
        print(f"{size:5} {naive_ns:12} {py_ns:10} {cpp_ns:10} {nr_ns:12} {pr_ns:10} {cr_ns:10}")

    print("\nNotes:")
    print("- naive_* is a local two-row DP; it is the pure-Python baseline.")
    print("- py_* is rapidfuzz's bit-parallel pure-Python fallback.")
    print("- cpp_* is the pinned Levenshtein C++ reference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
