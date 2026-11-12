"""Pin rapidfuzz oracle behaviors the port depends on.

These tests guard the reference itself against version drift: every
semantic the Mojo implementation promises to match is asserted here
first, directly against ``rapidfuzz==3.14.6`` (MIT). The GPL
``Levenshtein`` wrapper is never imported; Phase 0 established that all
probed behaviors are identical.
"""

from __future__ import annotations

import random

import pytest
from rapidfuzz.distance import Hamming, Indel, Levenshtein


def test_ratio_is_indel_similarity_not_levenshtein() -> None:
    # Decisive: indel(abc, adc) = 2 over 6 -> 2/3; Levenshtein-based
    # normalization would give 1 - 1/6 = 5/6.
    assert Indel.normalized_similarity("abc", "adc") == 0.6666666666666667
    assert Indel.normalized_similarity("kitten", "sitting") == 0.6153846153846154
    assert Levenshtein.normalized_similarity("kitten", "sitting") == 0.5714285714285714


def test_ratio_formula_bit_exact_on_corpus() -> None:
    rng = random.Random(30303)
    alphabet = list("abcdefé😀中")
    for _ in range(300):
        left = "".join(rng.choice(alphabet) for _ in range(rng.randrange(25)))
        right = "".join(rng.choice(alphabet) for _ in range(rng.randrange(25)))
        total = len(left) + len(right)
        expected = 1.0 if total == 0 else 1.0 - Indel.distance(left, right) / total
        assert Indel.normalized_similarity(left, right) == expected


def test_empty_string_behavior() -> None:
    assert Levenshtein.distance("", "") == 0
    assert Levenshtein.distance("", "abc") == 3
    assert Levenshtein.distance("abc", "") == 3
    assert Indel.normalized_similarity("", "") == 1.0
    assert Indel.normalized_similarity("", "abc") == 0.0
    assert Hamming.distance("", "") == 0


def test_distance_cutoff_truncation() -> None:
    assert Levenshtein.distance("abc", "xyz", score_cutoff=1) == 2
    assert Levenshtein.distance("abc", "xyz", score_cutoff=2) == 3
    assert Levenshtein.distance("abc", "xyz", score_cutoff=4) == 3
    assert Levenshtein.distance("abc", "adc", score_cutoff=0) == 1
    with pytest.raises(OverflowError):
        Levenshtein.distance("abc", "adc", score_cutoff=-1)


def test_weight_validation() -> None:
    assert Levenshtein.distance("lewenstein", "levenshtein", weights=(1, 1, 2)) == 3
    assert Levenshtein.distance("abc", "adc", weights=(1, 1, 3)) == 2
    with pytest.raises(OverflowError):
        Levenshtein.distance("a", "b", weights=(-1, 1, 1))
    with pytest.raises(ValueError, match="unpack"):
        Levenshtein.distance("a", "b", weights=(1, 1))


def test_hamming_padding_and_errors() -> None:
    assert Hamming.distance("abc", "abc") == 0
    assert Hamming.distance("abc", "ab", pad=True) == 1
    assert Hamming.distance("ab", "abc", pad=True) == 1
    with pytest.raises(ValueError, match="same length"):
        Hamming.distance("abc", "ab", pad=False)


def test_no_unicode_normalization() -> None:
    assert len("é") == 1
    assert len("e\u0301") == 2
    assert Levenshtein.distance("é", "e\u0301") == 2
    assert Indel.normalized_similarity("é", "e") == 0.0


def test_code_point_not_grapheme_or_byte_semantics() -> None:
    family = "👩‍👩‍👧‍👦"
    assert len(family) == 7
    assert len(family.encode("utf-8")) == 25
    assert Levenshtein.distance(family, "") == 7
    assert Levenshtein.distance("a😀b", "ab") == 1


def test_lone_surrogate_is_one_unit() -> None:
    assert len("\ud800") == 1
    assert Levenshtein.distance("\ud800", "") == 1


def test_symmetry() -> None:
    pairs = [("kitten", "sitting"), ("abc", "adc"), ("😀ab", "ab😀"), ("", "abc")]
    for left, right in pairs:
        assert Levenshtein.distance(left, right) == Levenshtein.distance(right, left)
        assert Indel.normalized_similarity(left, right) == Indel.normalized_similarity(right, left)
