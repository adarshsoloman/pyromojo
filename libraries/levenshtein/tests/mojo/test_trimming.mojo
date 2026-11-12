"""Regression tests for common-prefix/suffix trimming in distance.

Trimming strips a shared prefix and a non-overlapping shared suffix
before dispatching to Myers/DP. These tests pin the shapes trimming
must handle: full equality, edits clustered at either end, both ends
at once, prefix-of-other pairs, repeated and Unicode content, and the
weighted/cutoff paths (which share the same trimming code).
"""

from std.collections import List
from std.testing import TestSuite, assert_equal

from mojo_levenshtein.algorithms.dynamic_programming import dp_distance
from mojo_levenshtein.distance import levenshtein_distance, levenshtein_distance_cutoff
from mojo_levenshtein.unicode import to_codepoints

from test_support import TestRng, ascii_string, random_ascii


def check_production_matches_oracle(left: String, right: String) raises:
    var a = to_codepoints(left)
    var b = to_codepoints(right)
    assert_equal(levenshtein_distance(left, right), dp_distance(a, b))


def test_identical_strings_trim_to_zero() raises:
    assert_equal(levenshtein_distance("", ""), 0)
    assert_equal(levenshtein_distance("abc", "abc"), 0)
    assert_equal(levenshtein_distance(ascii_string(97, 1000), ascii_string(97, 1000)), 0)
    var uni = String("naïve café 😀")
    assert_equal(levenshtein_distance(uni, uni), 0)


def test_difference_only_at_start() raises:
    # Shared suffix of 999 code points must trim; only the first differs.
    var left = String("X") + ascii_string(97, 999)
    var right = String("Y") + ascii_string(97, 999)
    assert_equal(levenshtein_distance(left, right), 1)
    check_production_matches_oracle(left, right)


def test_difference_only_at_end() raises:
    var left = ascii_string(97, 999) + String("X")
    var right = ascii_string(97, 999) + String("Y")
    assert_equal(levenshtein_distance(left, right), 1)
    check_production_matches_oracle(left, right)


def test_shared_prefix_and_suffix() raises:
    var left = ascii_string(97, 300) + String("XYZ") + ascii_string(98, 300)
    var right = ascii_string(97, 300) + String("PQ") + ascii_string(98, 300)
    # "XYZ" -> "PQ": substitute X->P, Y->Q, delete Z = 3.
    assert_equal(levenshtein_distance(left, right), 3)
    check_production_matches_oracle(left, right)


def test_prefix_of_other() raises:
    assert_equal(levenshtein_distance("abc", "abcdef"), 3)
    assert_equal(levenshtein_distance("abcdef", "abc"), 3)
    assert_equal(levenshtein_distance("", "abcd"), 4)
    assert_equal(levenshtein_distance("abcd", ""), 4)
    check_production_matches_oracle("abc", "abcdef")
    check_production_matches_oracle("abcdef", "abc")


def test_completely_different() raises:
    assert_equal(levenshtein_distance("abc", "xyz"), 3)
    assert_equal(levenshtein_distance(ascii_string(97, 100), ascii_string(98, 100)), 100)
    check_production_matches_oracle("abc", "xyz")


def test_repeated_characters() raises:
    # "aaa" vs "aaaa": whole short string is a shared prefix.
    assert_equal(levenshtein_distance("aaa", "aaaa"), 1)
    assert_equal(levenshtein_distance(ascii_string(97, 500), ascii_string(97, 501)), 1)
    var rep = ascii_string(97, 200)
    check_production_matches_oracle(rep, rep + String("b"))


def test_unicode_trimming() raises:
    # Shared accented prefix and emoji suffix trim at code-point level.
    var left = String("café ") + String("😀") + String(" hello")
    var right = String("café ") + String("😃") + String(" hello")
    assert_equal(levenshtein_distance(left, right), 1)
    check_production_matches_oracle(left, right)
    # Combining sequences: shared base, differing mark trims correctly.
    var nfd_a = String("é")
    var nfc_a = String("é")
    # NFD [e, U+0301] vs NFC [U+00E9]: substitute e->é, delete mark = 2.
    assert_equal(levenshtein_distance(nfd_a, nfc_a), 2)
    check_production_matches_oracle(nfd_a, nfc_a)


def test_weighted_and_cutoff_paths_trim() raises:
    var left = ascii_string(97, 200) + String("cat")
    var right = ascii_string(97, 200) + String("cut")
    assert_equal(levenshtein_distance(left, right, 1, 1, 2), 2)
    assert_equal(levenshtein_distance(left, right, 2, 2, 1), 1)
    assert_equal(levenshtein_distance_cutoff(left, right, 0), 1)
    assert_equal(levenshtein_distance_cutoff(left, right, 5), 1)
    var a = to_codepoints(left)
    var b = to_codepoints(right)
    assert_equal(dp_distance(a, b, 1, 1, 2), 2)


def test_randomized_production_matches_oracle() raises:
    var rng = TestRng(70701)
    # Random pairs share short accidental affixes; trimming must be exact.
    for _ in range(120):
        var left = random_ascii(rng, 1 + rng.next(120))
        var right = random_ascii(rng, 1 + rng.next(120))
        check_production_matches_oracle(left, right)
    # Biased alphabet forces long shared runs through the trimmer.
    for _ in range(80):
        var left = String("")
        var right = String("")
        var shared = String("")
        for _ in range(30 + rng.next(60)):
            shared += String("a")
        for _ in range(rng.next(20)):
            left += String("x")
            right += String("y")
        check_production_matches_oracle(shared + left, shared + right)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
