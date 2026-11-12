"""Native tests for levenshtein_distance (unit, weighted, cutoff)."""

from std.testing import TestSuite, assert_equal, assert_raises

from mojo_levenshtein.distance import (
    levenshtein_distance,
    levenshtein_distance_cutoff,
)

from test_support import TestRng, ascii_string, random_ascii


def test_reference_pairs() raises:
    assert_equal(levenshtein_distance("", ""), 0)
    assert_equal(levenshtein_distance("", "abc"), 3)
    assert_equal(levenshtein_distance("abc", ""), 3)
    assert_equal(levenshtein_distance("abc", "abc"), 0)
    assert_equal(levenshtein_distance("kitten", "sitting"), 3)
    assert_equal(levenshtein_distance("abc", "adc"), 1)
    assert_equal(levenshtein_distance("lewenstein", "levenshtein"), 2)
    assert_equal(levenshtein_distance("spam", "park"), 3)
    assert_equal(levenshtein_distance("ab", "ba"), 2)


def test_weighted_reference_values() raises:
    assert_equal(levenshtein_distance("lewenstein", "levenshtein", 1, 1, 2), 3)
    assert_equal(levenshtein_distance("lewenstein", "levenshtein", 2, 2, 1), 3)
    assert_equal(levenshtein_distance("abc", "adc", 1, 1, 2), 2)
    assert_equal(levenshtein_distance("", "abc", 2, 1, 1), 6)
    assert_equal(levenshtein_distance("abc", "", 2, 1, 1), 3)
    assert_equal(levenshtein_distance("", "", 2, 1, 1), 0)


def test_order_independent() raises:
    assert_equal(
        levenshtein_distance("kitten", "sitting"),
        levenshtein_distance("sitting", "kitten"),
    )
    var many_a = ascii_string(97, 70)
    assert_equal(
        levenshtein_distance(many_a, "b"),
        levenshtein_distance("b", many_a),
    )


def test_cutoff_truncation() raises:
    assert_equal(levenshtein_distance_cutoff("abc", "xyz", 1), 2)
    assert_equal(levenshtein_distance_cutoff("abc", "xyz", 2), 3)
    assert_equal(levenshtein_distance_cutoff("abc", "xyz", 4), 3)
    assert_equal(levenshtein_distance_cutoff("abc", "adc", 0), 1)
    assert_equal(levenshtein_distance_cutoff("abc", "abc", 0), 0)
    assert_equal(levenshtein_distance_cutoff("kitten", "sitting", 2), 3)
    assert_equal(levenshtein_distance_cutoff("kitten", "sitting", 3), 3)


def test_invalid_inputs_raise() raises:
    with assert_raises(contains="positive integers"):
        _ = levenshtein_distance("a", "b", 0, 1, 1)
    with assert_raises(contains="positive integers"):
        _ = levenshtein_distance("a", "b", -1, 1, 1)
    with assert_raises(contains="positive integers"):
        _ = levenshtein_distance("a", "b", 1, 1, 0)
    with assert_raises(contains="non-negative integer"):
        _ = levenshtein_distance_cutoff("a", "b", -1)


def test_unicode_code_points() raises:
    assert_equal(levenshtein_distance("é", "e"), 1)
    # NFD "e" + combining acute (two code points) is not normalized.
    assert_equal(levenshtein_distance("é", "e\u0301"), 2)
    assert_equal(levenshtein_distance("😀", ""), 1)
    assert_equal(levenshtein_distance("a😀b", "ab"), 1)
    assert_equal(levenshtein_distance("naïve", "naive"), 1)
    assert_equal(levenshtein_distance("straße", "strasse"), 2)


def test_word_boundaries() raises:
    var short = ascii_string(97, 63)
    var exact = ascii_string(97, 64)
    var over = ascii_string(97, 65)
    var other = ascii_string(98, 65)
    assert_equal(levenshtein_distance(exact, exact), 0)
    assert_equal(levenshtein_distance(short, exact), 1)
    assert_equal(levenshtein_distance(over, exact), 1)
    assert_equal(levenshtein_distance(over, other), 65)
    var long_a = ascii_string(97, 200)
    var long_b = ascii_string(98, 200)
    assert_equal(levenshtein_distance(long_a, long_b), 200)
    assert_equal(levenshtein_distance(long_a, long_a), 0)


def test_random_strings_are_symmetric() raises:
    var rng = TestRng(20260101)
    for _ in range(50):
        var left = random_ascii(rng, rng.next(70))
        var right = random_ascii(rng, rng.next(70))
        assert_equal(
            levenshtein_distance(left, right),
            levenshtein_distance(right, left),
        )


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
