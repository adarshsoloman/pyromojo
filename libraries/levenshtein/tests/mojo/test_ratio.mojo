"""Native tests for levenshtein_ratio (Indel normalized similarity)."""

from std.testing import TestSuite, assert_equal

from mojo_levenshtein.ratio import levenshtein_ratio


def test_reference_values() raises:
    assert_equal(levenshtein_ratio("", ""), 1.0)
    assert_equal(levenshtein_ratio("", "abc"), 0.0)
    assert_equal(levenshtein_ratio("abc", ""), 0.0)
    assert_equal(levenshtein_ratio("abc", "abc"), 1.0)
    # Indel-based: 1 - 2/6, NOT Levenshtein-based 1 - 1/6.
    assert_equal(levenshtein_ratio("abc", "adc"), 0.6666666666666667)
    assert_equal(levenshtein_ratio("kitten", "sitting"), 0.6153846153846154)
    assert_equal(levenshtein_ratio("lewenstein", "levenshtein"), 0.8571428571428572)
    assert_equal(levenshtein_ratio("ab", "ba"), 0.5)
    assert_equal(levenshtein_ratio("a", "b"), 0.0)
    assert_equal(levenshtein_ratio("abc", "xyz"), 0.0)


def test_unicode_code_points() raises:
    assert_equal(levenshtein_ratio("é", "e"), 0.0)
    assert_equal(levenshtein_ratio("😀", "😃"), 0.0)
    assert_equal(levenshtein_ratio("a😀b", "ab"), 0.8)
    assert_equal(levenshtein_ratio("naïve", "naive"), 0.8)


def test_order_independent() raises:
    assert_equal(
        levenshtein_ratio("kitten", "sitting"),
        levenshtein_ratio("sitting", "kitten"),
    )
    assert_equal(
        levenshtein_ratio("abc", "adc"),
        levenshtein_ratio("adc", "abc"),
    )


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
