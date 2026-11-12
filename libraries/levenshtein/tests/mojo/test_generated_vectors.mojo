"""Every golden vector through the public API and both algorithm paths."""

from std.testing import TestSuite, assert_equal, assert_raises

from mojo_levenshtein.algorithms.dynamic_programming import dp_distance
from mojo_levenshtein.distance import (
    levenshtein_distance,
    levenshtein_distance_cutoff,
)
from mojo_levenshtein.hamming import levenshtein_hamming
from mojo_levenshtein.ratio import levenshtein_ratio
from mojo_levenshtein.unicode import to_codepoints

from generated_vectors import LevVector, levenshtein_vectors


def check_vector(vector: LevVector) raises:
    var left = String(vector.s1)
    var right = String(vector.s2)
    if vector.op == "distance":
        if vector.has_error:
            with assert_raises(contains=String(vector.error_contains)):
                if vector.has_cutoff:
                    _ = levenshtein_distance_cutoff(
                        left,
                        right,
                        vector.cutoff,
                        vector.insertion,
                        vector.deletion,
                        vector.substitution,
                    )
                else:
                    _ = levenshtein_distance(
                        left,
                        right,
                        vector.insertion,
                        vector.deletion,
                        vector.substitution,
                    )
            return
        var actual: Int
        if vector.has_cutoff:
            actual = levenshtein_distance_cutoff(
                left,
                right,
                vector.cutoff,
                vector.insertion,
                vector.deletion,
                vector.substitution,
            )
        else:
            actual = levenshtein_distance(
                left, right, vector.insertion, vector.deletion, vector.substitution
            )
        assert_equal(actual, vector.expected_int)
        # The DP oracle must agree on the same inputs; truncation for
        # cutoff cases mirrors the public wrapper exactly.
        var a = to_codepoints(left)
        var b = to_codepoints(right)
        var oracle = dp_distance(a, b, vector.insertion, vector.deletion, vector.substitution)
        if vector.has_cutoff and oracle > vector.cutoff:
            oracle = vector.cutoff + 1
        assert_equal(oracle, vector.expected_int)
    elif vector.op == "ratio":
        assert_equal(levenshtein_ratio(left, right), vector.expected_float)
    else:
        if vector.has_error:
            with assert_raises(contains=String(vector.error_contains)):
                _ = levenshtein_hamming(left, right, vector.pad)
            return
        assert_equal(levenshtein_hamming(left, right, vector.pad), vector.expected_int)


def test_all_golden_vectors() raises:
    var cases = levenshtein_vectors()
    var count = 0
    for i in range(len(cases)):
        check_vector(cases[i])
        count += 1
    assert_equal(count, len(cases))
    assert_equal(count > 400, True)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
