"""Deterministic Levenshtein benchmark workloads.

Every workload is a fixed string pair built from ``random.Random`` with
the configured seed, in a fixed build order, plus hand-written edge
cases. All implementations process the same pairs. Sizes sweep the
Myers word boundaries (1, 7, 31, 63, 64, 65, 127, 128, 129, 192, 256,
512, 1024, 2048) and include reversed-argument variants so both pattern
assignments are measured.
"""

from __future__ import annotations

import random

ASCII = "abcdefghijklmnopqrstuvwxyz0123456789"
ACCENTS = "café naïve straße æ ø ü ñ ¿¡"
CJK = "中文日本語한국어漢字ひらがな"
EMOJI = ["😀", "😃", "🎉", "🚀", "👩\u200d👩\u200d👧\u200d👦", "é", "ü"]
COMBINING_BASE = "eao"
COMBINING_MARK = "\u0301\u0302\u0327"


def _rand_text(rng: random.Random, alphabet: str, length: int) -> str:
    return "".join(rng.choice(alphabet) for _ in range(length))


def _rand_emoji(rng: random.Random, length: int) -> str:
    return "".join(rng.choice(EMOJI) for _ in range(length))


def _rand_combining(rng: random.Random, length: int) -> str:
    return "".join(rng.choice(COMBINING_BASE) + rng.choice(COMBINING_MARK) for _ in range(length))


def _one_substitution(rng: random.Random, text: str, alphabet: str = ASCII) -> str:
    if not text:
        return "a"
    index = rng.randrange(len(text))
    replacement = rng.choice(alphabet)
    if replacement == text[index]:
        replacement = "Z" if replacement != "Z" else "Y"
    return text[:index] + replacement + text[index + 1 :]


def build_workloads(seed: int) -> list[tuple[str, str, str, str]]:
    """Return (name, description, s1, s2) tuples in a stable order."""
    rng = random.Random(seed)
    workloads: list[tuple[str, str, str, str]] = []

    def add(name: str, description: str, s1: str, s2: str) -> None:
        workloads.append((name, description, s1, s2))

    # Hand-written small cases (also covered by golden vectors).
    add("empty_vs_empty", "both inputs empty (edge case)", "", "")
    add("empty_vs_short", "one empty input, one 3-char input", "", "abc")
    add("short_ascii_equal", "identical 12-char ASCII strings", "abcdefghijkl", "abcdefghijkl")
    add(
        "short_ascii_onesub",
        "12-char ASCII, single substitution",
        "abcdefghijkl",
        "abcXefghijkl",
    )
    left = _rand_text(rng, ASCII, 12)
    right = _rand_text(rng, ASCII, 12)
    add("short_ascii_random", "random 12-char ASCII pair", left, right)
    add("short_ascii_unrelated", "all-different 12-char ASCII", "a" * 12, "b" * 12)

    # Medium (Myers single-word and two-word shapes).
    left = _rand_text(rng, ASCII, 64)
    add("medium_ascii_equal", "identical 64-char ASCII strings", left, left)
    add(
        "medium_ascii_onesub",
        "64-char ASCII, single substitution",
        left,
        _one_substitution(rng, left),
    )
    right = _rand_text(rng, ASCII, 64)
    add("medium_ascii_random", "random 64-char ASCII pair", left, right)
    add("medium_ascii_unrelated", "all-different 64-char ASCII", "a" * 64, "b" * 64)

    # Long (multiword Myers).
    left = _rand_text(rng, ASCII, 256)
    add(
        "long_ascii_onesub",
        "256-char ASCII, single substitution",
        left,
        _one_substitution(rng, left),
    )
    right = _rand_text(rng, ASCII, 256)
    add("long_ascii_random", "random 256-char ASCII pair", left, right)
    add("long_ascii_unrelated", "all-different 256-char ASCII", "a" * 256, "b" * 256)

    # Extra-long (naive Python DP excluded by the driver).
    left = _rand_text(rng, ASCII, 1024)
    right = _rand_text(rng, ASCII, 1024)
    add("xlong_ascii_random", "random 1024-char ASCII pair", left, right)
    add("xlong_ascii_unrelated", "all-different 1024-char ASCII", "a" * 1024, "b" * 1024)
    left = _rand_text(rng, ASCII, 2048)
    right = _rand_text(rng, ASCII, 2048)
    add("huge_ascii_random", "random 2048-char ASCII pair", left, right)
    add("huge_ascii_equal", "identical 2048-char ASCII strings", left, left)
    add(
        "huge_ascii_onesub",
        "2048-char ASCII, single substitution",
        left,
        _one_substitution(rng, left),
    )

    # Unequal lengths, both argument orders.
    short = _rand_text(rng, ASCII, 48)
    long = _rand_text(rng, ASCII, 160)
    add("unequal_lengths", "48-char vs 160-char ASCII", short, long)
    add("unequal_lengths_rev", "160-char vs 48-char ASCII (reversed)", long, short)
    short = _rand_text(rng, ASCII, 256)
    long = _rand_text(rng, ASCII, 1024)
    add("unequal_large", "256-char vs 1024-char ASCII", short, long)

    # Repeated-character stress.
    add(
        "repeated_chars", "'a'*128 vs random 128-char ASCII", "a" * 128, _rand_text(rng, ASCII, 128)
    )
    add("repeated_uniform", "all-different 128-char ('a' vs 'b')", "a" * 128, "b" * 128)

    # Unicode: accents, CJK, astral emoji, combining sequences.
    accents = (_rand_text(rng, ACCENTS, 40) + " café naïve straße")[:48]
    add("unicode_accents", "48-char accented Latin mix", accents, _rand_text(rng, ACCENTS, 48))
    cjk = _rand_text(rng, CJK, 48)
    add("unicode_cjk", "48-char CJK pair", cjk, _rand_text(rng, CJK, 48))
    emoji_left = _rand_emoji(rng, 24)
    add("emoji_astral", "24-code-point astral emoji pair", emoji_left, _rand_emoji(rng, 24))
    combining = _rand_combining(rng, 20)
    add("combining", "20-grapheme NFD-style combining pair", combining, _rand_combining(rng, 20))

    # Myers word-boundary sweep: exact sizes around 64-bit words.
    for size in (1, 7, 31, 63, 64, 65, 127, 128, 129, 192, 256, 512, 1024, 2048):
        left = _rand_text(rng, ASCII, size)
        right = _rand_text(rng, ASCII, size)
        add(
            f"size_{size:04d}_random",
            f"random {size}-char ASCII pair (Myers boundary)",
            left,
            right,
        )

    return workloads


def workload_meta(s1: str, s2: str) -> dict[str, int]:
    """Code-point and byte lengths for reporting."""
    return {
        "cp_len1": len(s1),
        "cp_len2": len(s2),
        "byte_len1": len(s1.encode("utf-8")),
        "byte_len2": len(s2.encode("utf-8")),
    }
