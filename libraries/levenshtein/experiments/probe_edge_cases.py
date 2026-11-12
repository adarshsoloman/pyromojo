#!/usr/bin/env python3
"""Phase 0 follow-up probe: edge cases, type coercion, pure-Python fallback.

Run with::

    .venv/bin/python libraries/levenshtein/experiments/probe_edge_cases.py
"""

from __future__ import annotations

import random
import string

import Levenshtein
from rapidfuzz.distance import (
    Hamming,
    Hamming_py,
    Indel,
    Indel_py,
    Jaro,
    Jaro_py,
    JaroWinkler,
    JaroWinkler_py,
    Levenshtein_py,
)
from rapidfuzz.distance import Levenshtein as RFLev


def show(label: str, value: object) -> None:
    print(f"{label}: {value!r}")


def attempt(label: str, fn) -> None:
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - deliberate exception probe
        print(f"{label}: RAISED {type(exc).__name__}: {exc}")
    else:
        print(f"{label}: {result!r}")


def section(title: str) -> None:
    print(f"\n== {title} ==")


def main() -> int:
    section("pure-python fallback availability")
    for module in (Levenshtein_py, Indel_py, Jaro_py, JaroWinkler_py, Hamming_py):
        print(f"{module.__name__}: {module.__file__}")
    print("Levenshtein_py.distance is Python:", Levenshtein_py.distance.__module__)
    attempt(
        "Levenshtein_py.distance weights negative",
        lambda: Levenshtein_py.distance("a", "b", weights=(-1, 1, 1)),
    )
    attempt(
        "Levenshtein_py.distance weights float",
        lambda: Levenshtein_py.distance("a", "b", weights=(1.5, 1, 1)),
    )

    section("cxx vs pure-python agreement (deterministic corpus)")
    rng = random.Random(20260101)
    alphabet = string.ascii_letters + string.digits + " _-éß😀"
    corpus: list[tuple[str, str]] = [("", ""), ("a", ""), ("", "a")]
    for _ in range(400):
        left = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 18)))
        right = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 18)))
        corpus.append((left, right))
    mismatches = {
        "distance": 0,
        "ratio": 0,
        "hamming_pad": 0,
        "jaro": 0,
        "jaro_winkler": 0,
    }
    for left, right in corpus:
        if Levenshtein.distance(left, right) != Levenshtein_py.distance(left, right):
            mismatches["distance"] += 1
        if Levenshtein.ratio(left, right) != Indel_py.normalized_similarity(left, right):
            mismatches["ratio"] += 1
        if Levenshtein.hamming(left, right, pad=True) != Hamming_py.distance(left, right, pad=True):
            mismatches["hamming_pad"] += 1
        if Levenshtein.jaro(left, right) != Jaro_py.similarity(left, right):
            mismatches["jaro"] += 1
        if Levenshtein.jaro_winkler(left, right) != JaroWinkler_py.similarity(left, right):
            mismatches["jaro_winkler"] += 1
    print(f"corpus size: {len(corpus)}")
    print(f"mismatches: {mismatches}")

    section("cxx vs pure-python weighted distance")
    weighted_mismatches = 0
    for left, right in corpus[:100]:
        for weights in ((1, 1, 1), (1, 1, 2), (2, 1, 1), (0, 1, 1), (1, 1, 0)):
            got = Levenshtein.distance(left, right, weights=weights)
            want = Levenshtein_py.distance(left, right, weights=weights)
            if got != want:
                weighted_mismatches += 1
                if weighted_mismatches <= 5:
                    print(f"mismatch {left!r}/{right!r} {weights}: {got} != {want}")
    print(f"weighted mismatches: {weighted_mismatches}")

    section("jaro_winkler prefix_weight bounds")
    for weight in (0.0, 0.25, 0.2501, 0.5, 0.9, 1.0, 1.0001, -0.0001, "0.1", None):
        attempt(
            f"prefix_weight={weight!r}",
            lambda weight=weight: Levenshtein.jaro_winkler(
                "MARTHA", "MARHTA", prefix_weight=weight
            ),
        )

    section("mixed and exotic input types")
    cases = [
        ("str vs bytes equal", lambda: Levenshtein.distance("abc", b"abc")),
        ("str vs bytes differ", lambda: Levenshtein.distance("abc", b"abd")),
        ("str vs bytes unicode", lambda: Levenshtein.distance("é", "é".encode())),
        ("str vs list[str]", lambda: Levenshtein.distance("abc", ["a", "b", "c"])),
        ("str vs list[int]", lambda: Levenshtein.distance("abc", [97, 98, 99])),
        ("bytes vs list[int]", lambda: Levenshtein.distance(b"abc", [97, 98, 99])),
        ("list[str] vs list[int]", lambda: Levenshtein.distance(["a"], [97])),
        ("memoryview", lambda: Levenshtein.distance(memoryview(b"abc"), memoryview(b"abd"))),
        ("range", lambda: Levenshtein.distance(range(5), range(1, 6))),
        ("generator", lambda: Levenshtein.distance((c for c in "abc"), "abc")),
        ("int", lambda: Levenshtein.distance(5, 5)),
        ("None", lambda: Levenshtein.distance(None, None)),
        ("dict", lambda: Levenshtein.distance({"a": 1}, {"a": 1})),
    ]
    for label, fn in cases:
        attempt(label, fn)

    section("weights edge cases")
    for weights in ((0, 0, 0), (0, 0, 1), (0, 1, 0), (1, 0, 0), (2, 0, 0), (1.5, 1, 1)):
        attempt(
            f"abc/adc weights={weights}",
            lambda weights=weights: Levenshtein.distance("abc", "adc", weights=weights),
        )
    for weights in ((1, 1), (1, 1, 1, 1), ()):
        attempt(
            f"bad weights={weights}",
            lambda weights=weights: Levenshtein.distance("a", "b", weights=weights),
        )

    section("score_cutoff boundaries")
    for cutoff in (0, 0.0, 1, 2, 3, 4, -1, 0.5, "1", None):
        attempt(
            f"distance('abc','xyz',score_cutoff={cutoff!r})",
            lambda cutoff=cutoff: Levenshtein.distance("abc", "xyz", score_cutoff=cutoff),
        )
    for cutoff in (0.0, 0.6666666666666666, 0.6666666666666667, 1.0, 1.5, -0.1):
        attempt(
            f"ratio('abc','adc',score_cutoff={cutoff!r})",
            lambda cutoff=cutoff: Levenshtein.ratio("abc", "adc", score_cutoff=cutoff),
        )

    section("MatchingBlock shape")
    blocks = Levenshtein.matching_blocks(Levenshtein.editops("spam", "park"), "spam", "park")
    block = blocks[0]
    print(f"type: {type(block).__module__}.{type(block).__name__}")
    print(f"is tuple: {isinstance(block, tuple)}")
    print(f"len: {len(block)} index0: {block[0]} a/b/size: {block.a}/{block.b}/{block.size}")
    print(f"tuple equality: {block == (block.a, block.b, block.size)}")
    print(f"matching_blocks of no edits: {Levenshtein.matching_blocks([], 'abc', 'abc')}")
    attempt(
        "matching_blocks wrong args",
        lambda: Levenshtein.matching_blocks([("replace", 0, 0)], "a", "b"),
    )

    section("editops tie-breaking")
    for left, right in [
        ("kitten", "sitting"),
        ("abc", "acb"),
        ("ab", "ba"),
        ("aaaa", "aa"),
        ("aa", "aaaa"),
        ("", "abc"),
        ("abc", ""),
    ]:
        print(
            f"{left!r}->{right!r}:"
            f" editops={Levenshtein.editops(left, right)}"
            f" opcodes={Levenshtein.opcodes(left, right)}"
        )
    print(
        "editops(distance-only) vs rf:",
        Levenshtein.editops("kitten", "sitting") == RFLev.editops("kitten", "sitting"),
    )

    section("median family types")
    attempt("median(['ab','ac'])", lambda: Levenshtein.median(["ab", "ac"]))
    attempt("median([b'ab',b'ac'])", lambda: Levenshtein.median([b"ab", b"ac"]))
    attempt("median(['ab',b'ac'])", lambda: Levenshtein.median(["ab", b"ac"]))
    attempt("median([1,2])", lambda: Levenshtein.median([1, 2]))
    attempt("median_improve('spam',[]) ", lambda: Levenshtein.median_improve("spam", []))
    attempt("quickmedian([])", lambda: Levenshtein.quickmedian([]))
    attempt("setmedian([])", lambda: Levenshtein.setmedian([]))
    attempt("seqratio([],[])", lambda: Levenshtein.seqratio([], []))
    attempt("setratio([],[])", lambda: Levenshtein.setratio([], []))

    section("jaro zeros and repetitions")
    for left, right in [
        ("aaaa", "aa"),
        ("abc", "bca"),
        ("ab", "ba"),
        ("aab", "aba"),
        ("😀a", "a😀"),
        ("x", "xxxxxxxx"),
    ]:
        print(
            f"{left!r}/{right!r}:"
            f" jaro={Levenshtein.jaro(left, right)!r}"
            f" py={Jaro_py.similarity(left, right)!r}"
            f" cxx={Jaro.similarity(left, right)!r}"
        )

    section("reference identity vs rapidfuzz")
    print("Levenshtein.distance is RFLev.distance:", Levenshtein.distance is RFLev.distance)
    print(
        "Levenshtein.ratio is Indel.normalized_similarity:",
        Levenshtein.ratio is Indel.normalized_similarity,
    )
    print("Levenshtein.hamming is Hamming.distance:", Levenshtein.hamming is Hamming.distance)
    print("Levenshtein.jaro is Jaro.similarity:", Levenshtein.jaro is Jaro.similarity)
    print(
        "Levenshtein.jaro_winkler is JaroWinkler.similarity:",
        Levenshtein.jaro_winkler is JaroWinkler.similarity,
    )

    section("fallback divergence: weights")
    for weights in ((1, 1, 1), (1, 1, 2), (1, 1, 1.5), (1.5, 1, 1), (0, 0, 0), (-1, 1, 1)):
        attempt(
            f"cpp weights={weights}",
            lambda weights=weights: Levenshtein.distance("ab", "ba", weights=weights),
        )
        attempt(
            f"py  weights={weights}",
            lambda weights=weights: Levenshtein_py.distance("ab", "ba", weights=weights),
        )
    for weights in ((2**63, 1, 1), (1, 2**63, 1), (1, 1, 2**63)):
        attempt(
            f"cpp huge weights={weights}",
            lambda weights=weights: Levenshtein.distance("ab", "ba", weights=weights),
        )
        attempt(
            f"py  huge weights={weights}",
            lambda weights=weights: Levenshtein_py.distance("ab", "ba", weights=weights),
        )

    section("score_cutoff strictness at equality")
    attempt(
        "ratio('abc','abc',cutoff=1.0)", lambda: Levenshtein.ratio("abc", "abc", score_cutoff=1.0)
    )
    attempt(
        "jaro('abc','abc',cutoff=1.0)", lambda: Levenshtein.jaro("abc", "abc", score_cutoff=1.0)
    )
    attempt(
        "jw('abc','abc',cutoff=1.0)",
        lambda: Levenshtein.jaro_winkler("abc", "abc", score_cutoff=1.0),
    )
    attempt(
        "hamming('abc','abc',cutoff=0)",
        lambda: Levenshtein.hamming("abc", "abc", score_cutoff=0),
    )
    attempt(
        "distance('abc','abc',cutoff=0)",
        lambda: Levenshtein.distance("abc", "abc", score_cutoff=0),
    )

    section("lone surrogates and bytes")
    attempt("distance('\\ud800','')", lambda: Levenshtein.distance("\ud800", ""))
    attempt("ratio('\\ud800','')", lambda: Levenshtein.ratio("\ud800", ""))
    attempt("distance('\\ud800','\\ud800')", lambda: Levenshtein.distance("\ud800", "\ud800"))
    attempt("distance('\\ud800','a')", lambda: Levenshtein.distance("\ud800", "a"))
    attempt("distance('a','b') bytes", lambda: Levenshtein.distance(b"a", b"b"))
    attempt("distance('a',b'a')", lambda: Levenshtein.distance("a", b"a"))
    attempt(
        "distance('\\u00e9',b'\\xc3\\xa9')", lambda: Levenshtein.distance("\u00e9", b"\xc3\xa9")
    )
    attempt("median surrogate", lambda: Levenshtein.median(["\ud800", "a"]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
