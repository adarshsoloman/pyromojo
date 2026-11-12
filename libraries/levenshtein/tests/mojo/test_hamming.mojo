"""Native tests for levenshtein_hamming (equal, padded, errors)."""

from std.testing import TestSuite, assert_equal, assert_raises

from mojo_levenshtein.hamming import levenshtein_hamming


def test_equal_lengths() raises:
    assert_equal(levenshtein_hamming("", ""), 0)
    assert_equal(levenshtein_hamming("abc", "abc"), 0)
    assert_equal(levenshtein_hamming("abc", "xyz"), 3)
    assert_equal(levenshtein_hamming("abc", "abx"), 1)


def test_padding_charges_length_difference() raises:
    assert_equal(levenshtein_hamming("abc", "ab"), 1)
    assert_equal(levenshtein_hamming("ab", "abc"), 1)
    assert_equal(levenshtein_hamming("abc", ""), 3)
    assert_equal(levenshtein_hamming("", "abc"), 3)
    assert_equal(levenshtein_hamming("abc", "xbc", False), 1)


def test_unpadded_mismatch_raises() raises:
    with assert_raises(contains="Sequences are not the same length."):
        _ = levenshtein_hamming("abc", "ab", False)
    with assert_raises(contains="Sequences are not the same length."):
        _ = levenshtein_hamming("ab", "abc", False)
    with assert_raises(contains="Sequences are not the same length."):
        _ = levenshtein_hamming("", "a", False)


def test_unicode_code_points() raises:
    assert_equal(levenshtein_hamming("é", "e"), 1)
    assert_equal(levenshtein_hamming("😀", "😃"), 1)
    assert_equal(levenshtein_hamming("😀", ""), 1)
    assert_equal(levenshtein_hamming("aé", "ae"), 1)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
