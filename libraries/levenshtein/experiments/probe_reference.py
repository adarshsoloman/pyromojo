#!/usr/bin/env python3
"""Phase 0 black-box audit of the pinned Levenshtein reference.

This script only observes behaviour. It does not import private internals and
does not copy upstream code. Run with::

    .venv/bin/python libraries/levenshtein/experiments/probe_reference.py

Findings are printed as ``key: value`` lines and captured verbatim into
``reference_probe_output.txt``.
"""

from __future__ import annotations

import importlib.metadata
import platform
import sys
import unicodedata

import Levenshtein
import rapidfuzz
from rapidfuzz.distance import Hamming, Indel, Jaro, JaroWinkler
from rapidfuzz.distance import Levenshtein as RFLev

try:
    from Levenshtein.StringMatcher import StringMatcher
except Exception as exc:  # noqa: BLE001 - reporting an import probe
    StringMatcher = None
    STRING_MATCHER_ERROR = f"{type(exc).__name__}: {exc}"
else:
    STRING_MATCHER_ERROR = ""


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
    section("environment")
    print(f"python: {platform.python_version()} ({sys.implementation.name})")
    print(f"platform: {platform.platform()}")
    print(f"Levenshtein.__version__: {Levenshtein.__version__}")
    print(f"Levenshtein.__license__: {Levenshtein.__license__}")
    print(f"Levenshtein.__author__: {Levenshtein.__author__}")
    print(f"distribution version: {importlib.metadata.version('Levenshtein')}")
    print(f"rapidfuzz.__version__: {rapidfuzz.__version__}")
    print(f"rapidfuzz distribution: {importlib.metadata.version('rapidfuzz')}")
    print(f"Levenshtein module file: {Levenshtein.__file__}")

    section("public API surface")
    public = [name for name in dir(Levenshtein) if not name.startswith("_")]
    show("public names", public)
    for name in (
        "distance",
        "ratio",
        "normalized_distance",
        "normalized_similarity",
        "hamming",
        "jaro",
        "jaro_winkler",
        "editops",
        "opcodes",
        "matching_blocks",
        "median",
        "median_improve",
        "quickmedian",
        "setmedian",
        "seqratio",
        "setratio",
        "inverse",
        "apply_edit",
        "subtract_edit",
        "StringMatcher",
    ):
        print(f"has {name}: {hasattr(Levenshtein, name)}")
    print(f"Levenshtein.StringMatcher module imports: {StringMatcher is not None}")
    if STRING_MATCHER_ERROR:
        print(f"StringMatcher import error: {STRING_MATCHER_ERROR}")
    show(
        "rapidfuzz.distance modules",
        [name for name in dir(rapidfuzz.distance) if not name.startswith("_")],
    )

    section("distance: baseline cases")
    pairs = [
        ("", ""),
        ("", "abc"),
        ("abc", ""),
        ("abc", "abc"),
        ("kitten", "sitting"),
        ("abc", "adc"),
        ("abc", "xyz"),
        ("ab", "ba"),
        ("a", "b"),
        ("spam", "park"),
        ("lewenstein", "levenshtein"),
    ]
    for left, right in pairs:
        print(
            f"distance({left!r}, {right!r}) = {Levenshtein.distance(left, right)}"
            f" | rf={RFLev.distance(left, right)}"
            f" | indel={Indel.distance(left, right)}"
            f" | ratio={Levenshtein.ratio(left, right)!r}"
            f" | rf_norm_sim={Indel.normalized_similarity(left, right)!r}"
            f" | norm_dist={Indel.normalized_distance(left, right)!r}"
        )

    section("ratio formula: indel vs Levenshtein distance")
    for left, right in [("abc", "adc"), ("kitten", "sitting"), ("a", "bbbb")]:
        lev = Levenshtein.distance(left, right)
        indel = Indel.distance(left, right)
        total = len(left) + len(right)
        print(
            f"{left!r} vs {right!r}: lev={lev} indel={indel} total={total}"
            f" lev_ratio={1 - lev / total if total else 1.0!r}"
            f" indel_ratio={1 - indel / total if total else 1.0!r}"
            f" actual={Levenshtein.ratio(left, right)!r}"
        )

    section("normalized_* availability")
    attempt("Levenshtein.normalized_distance", lambda: Levenshtein.normalized_distance("a", "b"))
    attempt(
        "Levenshtein.normalized_similarity", lambda: Levenshtein.normalized_similarity("a", "b")
    )
    show("rf Levenshtein.normalized_distance", RFLev.normalized_distance("abc", "adc"))
    show("rf Levenshtein.normalized_similarity", RFLev.normalized_similarity("abc", "adc"))
    show("rf Indel.normalized_distance", Indel.normalized_distance("abc", "adc"))
    show("rf Indel.normalized_similarity", Indel.normalized_similarity("abc", "adc"))

    section("distance weights")
    weight_cases = [
        (1, 1, 1),
        (1, 1, 2),
        (2, 2, 1),
        (1, 2, 1),
        (2, 1, 1),
        (0, 1, 1),
        (1, 1, 0),
        (-1, 1, 1),
        (1, 1, 100),
        (1, 1, 1.5),
        None,
    ]
    for weights in weight_cases:
        attempt(
            f"distance('lewenstein','levenshtein',weights={weights})",
            lambda weights=weights: Levenshtein.distance(
                "lewenstein", "levenshtein", weights=weights
            ),
        )
    show("weighted abc/adc (1,1,2)", Levenshtein.distance("abc", "adc", weights=(1, 1, 2)))
    show("weighted abc/adc (1,1,3)", Levenshtein.distance("abc", "adc", weights=(1, 1, 3)))

    section("score_cutoff semantics")
    attempt("distance('abc','xyz')", lambda: Levenshtein.distance("abc", "xyz"))
    attempt(
        "distance('abc','xyz',score_cutoff=1)",
        lambda: Levenshtein.distance("abc", "xyz", score_cutoff=1),
    )
    attempt(
        "distance('abc','adc',score_cutoff=0)",
        lambda: Levenshtein.distance("abc", "adc", score_cutoff=0),
    )
    attempt(
        "distance('abc','adc',score_hint=100)",
        lambda: Levenshtein.distance("abc", "adc", score_hint=100),
    )
    attempt(
        "ratio('abc','adc',score_cutoff=0.9)",
        lambda: Levenshtein.ratio("abc", "adc", score_cutoff=0.9),
    )
    attempt(
        "ratio('abc','adc',score_cutoff=0.6)",
        lambda: Levenshtein.ratio("abc", "adc", score_cutoff=0.6),
    )
    attempt(
        "hamming('abc','abx',score_cutoff=0)",
        lambda: Levenshtein.hamming("abc", "abx", score_cutoff=0),
    )

    section("hamming")
    for left, right, pad in [
        ("abc", "abc", True),
        ("abc", "ab", True),
        ("abc", "ab", False),
        ("abc", "xyz", True),
        ("", "", True),
        ("é", "e", True),
        ("😀", "", True),
    ]:
        attempt(
            f"hamming({left!r},{right!r},pad={pad})",
            lambda left=left, right=right, pad=pad: Levenshtein.hamming(left, right, pad=pad),
        )
    print("rf Hamming.distance('abc','ab',pad=True) =", Hamming.distance("abc", "ab", pad=True))
    attempt(
        "rf Hamming.distance('abc','ab',pad=False)",
        lambda: Hamming.distance("abc", "ab", pad=False),
    )

    section("jaro and jaro_winkler")
    jaro_pairs = [
        ("", ""),
        ("", "a"),
        ("a", ""),
        ("a", "a"),
        ("MARTHA", "MARHTA"),
        ("DIXON", "DICKSONX"),
        ("abc", "abc"),
        ("abc", "xyz"),
    ]
    for left, right in jaro_pairs:
        print(
            f"jaro({left!r},{right!r}) = {Levenshtein.jaro(left, right)!r}"
            f" | rf={Jaro.similarity(left, right)!r}"
            f" | jw={Levenshtein.jaro_winkler(left, right)!r}"
            f" | rf_jw={JaroWinkler.similarity(left, right)!r}"
        )
    for weight in (0.0, 0.1, 0.25, 0.2501, -0.1):
        attempt(
            f"jaro_winkler('MARTHA','MARHTA',prefix_weight={weight})",
            lambda weight=weight: Levenshtein.jaro_winkler(
                "MARTHA", "MARHTA", prefix_weight=weight
            ),
        )
    attempt(
        "jaro('MARTHA','MARHTA',score_cutoff=0.99)",
        lambda: Levenshtein.jaro("MARTHA", "MARHTA", score_cutoff=0.99),
    )
    attempt(
        "jaro_winkler('MARTHA','MARHTA',score_cutoff=0.99)",
        lambda: Levenshtein.jaro_winkler("MARTHA", "MARHTA", score_cutoff=0.99),
    )

    section("unicode semantics")
    unicode_cases = [
        ("é", "e"),
        ("é", "e\u0301"),
        (unicodedata.normalize("NFC", "é"), unicodedata.normalize("NFD", "é")),
        ("😀", ""),
        ("😀", "😃"),
        ("👩‍👩‍👧‍👦", ""),
        ("a😀b", "ab"),
        ("naïve", "naive"),
        ("straße", "strasse"),
        ("æ", "ae"),
    ]
    for left, right in unicode_cases:
        print(
            f"{left!r} vs {right!r}:"
            f" len={len(left)}/{len(right)}"
            f" bytes={len(left.encode('utf-8'))}/{len(right.encode('utf-8'))}"
            f" distance={Levenshtein.distance(left, right)}"
            f" ratio={Levenshtein.ratio(left, right)!r}"
            f" jaro={Levenshtein.jaro(left, right)!r}"
        )
    print(
        "NFC == NFD (codepoint equality):",
        unicodedata.normalize("NFC", "é") == unicodedata.normalize("NFD", "é"),
    )
    print(
        "NFC == NFD (byte equality):",
        unicodedata.normalize("NFC", "é").encode() == unicodedata.normalize("NFD", "é").encode(),
    )

    section("input types and mixing")
    attempt("distance(b'abc', b'adc')", lambda: Levenshtein.distance(b"abc", b"adc"))
    attempt(
        "distance(bytearray(b'abc'), bytearray(b'adc'))",
        lambda: Levenshtein.distance(bytearray(b"abc"), bytearray(b"adc")),
    )
    attempt("distance(['a','b'], ['a','c'])", lambda: Levenshtein.distance(["a", "b"], ["a", "c"]))
    attempt("distance([1,2,3],[1,2,4])", lambda: Levenshtein.distance([1, 2, 3], [1, 2, 4]))
    attempt("distance(('a','b'), ('a','c'))", lambda: Levenshtein.distance(("a", "b"), ("a", "c")))
    attempt("distance('abc', b'abc')", lambda: Levenshtein.distance("abc", b"abc"))
    attempt("distance('abc', ['a','b','c'])", lambda: Levenshtein.distance("abc", ["a", "b", "c"]))
    attempt("ratio(['ab'],['ac'])", lambda: Levenshtein.ratio(["ab"], ["ac"]))
    attempt(
        "ratio(['ab'],['ac'],processor=lambda s: s[0])",
        lambda: Levenshtein.ratio(["ab"], ["ac"], processor=lambda s: s[0]),
    )
    attempt(
        "distance('ABC','abd',processor=str.lower)",
        lambda: Levenshtein.distance("ABC", "abd", processor=str.lower),
    )

    section("edit operations")
    for left, right in [("spam", "park"), ("kitten", "sitting"), ("man", "scotsman")]:
        print(f"editops({left!r},{right!r}) = {Levenshtein.editops(left, right)}")
        print(f"opcodes({left!r},{right!r}) = {Levenshtein.opcodes(left, right)}")
        print(
            f"matching_blocks({left!r},{right!r}) = "
            f"{Levenshtein.matching_blocks(Levenshtein.editops(left, right), left, right)}"
        )
    e = Levenshtein.editops("man", "scotsman")
    print("inverse(editops) =", Levenshtein.inverse(e))
    print("apply_edit(full) =", Levenshtein.apply_edit(e, "man", "scotsman"))
    print("apply_edit(partial) =", Levenshtein.apply_edit(e[:3], "man", "scotsman"))
    print(
        "subtract_edit demo =",
        Levenshtein.apply_edit(Levenshtein.subtract_edit(e, e[:3]), "scoman", "scotsman"),
    )

    section("median family")
    fixme = [
        "Levnhtein",
        "Leveshein",
        "Leenshten",
        "Leveshtei",
        "Lenshtein",
        "Lvenstein",
        "Levenhtin",
        "evenshtei",
    ]
    show("median(fixme)", Levenshtein.median(fixme))
    show("quickmedian(fixme)", Levenshtein.quickmedian(fixme))
    show("setmedian(fixme)", Levenshtein.setmedian(fixme))
    show("median_improve('spam', fixme)", Levenshtein.median_improve("spam", fixme))
    show("median weighted", Levenshtein.median(["ab", "ac", "ad"], [1, 1, 1]))
    show(
        "seqratio",
        Levenshtein.seqratio(
            ["newspaper", "litter bin", "tinny", "antelope"],
            ["caribou", "sausage", "gorn", "woody"],
        ),
    )
    show(
        "setratio",
        Levenshtein.setratio(
            ["newspaper", "litter bin", "tinny", "antelope"],
            ["caribou", "sausage", "gorn", "woody"],
        ),
    )
    attempt("median([])", lambda: Levenshtein.median([]))
    attempt("median([b'ab', b'ac'])", lambda: Levenshtein.median([b"ab", b"ac"]))
    attempt("median(['ab', b'ac'])", lambda: Levenshtein.median(["ab", b"ac"]))

    section("symmetry and reference identity")
    corpus = [
        ("", ""),
        ("a", "b"),
        ("kitten", "sitting"),
        ("abc", "adc"),
        ("😀ab", "ab😀"),
        ("aaaaaaaa", "aaa"),
    ]
    for left, right in corpus:
        print(
            f"{left!r}/{right!r}:"
            f" dist_sym={Levenshtein.distance(left, right) == Levenshtein.distance(right, left)}"
            f" ratio_sym={Levenshtein.ratio(left, right) == Levenshtein.ratio(right, left)}"
            f" jaro_sym={Levenshtein.jaro(left, right) == Levenshtein.jaro(right, left)}"
            " jw_sym="
            f"{Levenshtein.jaro_winkler(left, right) == Levenshtein.jaro_winkler(right, left)}"
            " dist==rf="
            f"{Levenshtein.distance(left, right) == RFLev.distance(left, right)}"
            " ratio==indel_ns="
            f"{Levenshtein.ratio(left, right) == Indel.normalized_similarity(left, right)}"
        )

    section("StringMatcher")
    if StringMatcher is not None:
        matcher = StringMatcher(seq1="spam", seq2="park")
        print("StringMatcher.ratio() =", matcher.ratio())
        print("StringMatcher.quick_ratio() =", matcher.quick_ratio())
        print("StringMatcher.get_editops() =", matcher.get_editops())
        print("StringMatcher.get_opcodes() =", matcher.get_opcodes())
        print("StringMatcher.get_matching_blocks() =", matcher.get_matching_blocks())
        attempt("StringMatcher(isjunk=True)", lambda: StringMatcher(isjunk=True))
        attempt("StringMatcher(autojunk=True)", lambda: StringMatcher(autojunk=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
