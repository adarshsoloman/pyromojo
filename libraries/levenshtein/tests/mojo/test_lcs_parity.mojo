"""DP-versus-blocked-LCS parity over deterministic randomized pairs.

The DP oracle (``dp_lcs_length``) and the blocked bit-parallel LCS
(``lcs_bitparallel``) must agree exactly on every input shape: empty,
single-word, word boundaries (63/64/65, 127/128/129), multiword,
repeated characters, all-identical/all-different strings, asymmetric
lengths, and non-ASCII code points.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal

from mojo_levenshtein.algorithms.dynamic_programming import dp_lcs_length
from mojo_levenshtein.algorithms.lcs import lcs_bitparallel
from mojo_levenshtein.unicode import to_codepoints

from test_support import TestRng, random_ascii, random_codepoints


def check_pair(left: String, right: String) raises:
    var a = to_codepoints(left)
    var b = to_codepoints(right)
    assert_equal(lcs_bitparallel(a, b), dp_lcs_length(a, b))
    assert_equal(lcs_bitparallel(b, a), dp_lcs_length(a, b))


def test_fixed_cases() raises:
    check_pair("", "")
    check_pair("", "abc")
    check_pair("a", "")
    check_pair("abc", "abc")
    check_pair("abc", "adc")
    check_pair("kitten", "sitting")
    check_pair("abcdef", "azced")
    check_pair("aaaa", "aa")
    check_pair("aa", "aaaa")
    check_pair("ab", "ba")
    check_pair("abc", "xyz")


def test_word_boundaries() raises:
    var rng = TestRng(80801)
    for size in range(60, 70):
        check_pair(random_ascii(rng, size), random_ascii(rng, size))
    for size in range(124, 133):
        check_pair(random_ascii(rng, size), random_ascii(rng, size))
    for size in range(188, 197):
        check_pair(random_ascii(rng, size), random_ascii(rng, size))


def test_repeated_and_uniform() raises:
    var rng = TestRng(80802)
    var sizes = List[Int](capacity=8)
    sizes.append(1)
    sizes.append(2)
    sizes.append(63)
    sizes.append(64)
    sizes.append(65)
    sizes.append(128)
    sizes.append(200)
    sizes.append(300)
    for size in sizes:
        var repeated = String("")
        for _ in range(size):
            repeated += "a"
        check_pair(repeated, random_ascii(rng, size))
        var other = String("")
        for _ in range(size):
            other += "b"
        check_pair(repeated, other)
        # Identical long strings: LCS must equal the full length.
        var a = to_codepoints(repeated)
        assert_equal(lcs_bitparallel(a, a), size)


def test_random_ascii_parity() raises:
    var rng = TestRng(80803)
    for _ in range(300):
        var left = random_ascii(rng, rng.next(301))
        var right = random_ascii(rng, rng.next(301))
        check_pair(left, right)


def test_random_code_point_parity() raises:
    var rng = TestRng(80804)
    for _ in range(150):
        var left = random_codepoints(rng, rng.next(200))
        var right = random_codepoints(rng, rng.next(200))
        assert_equal(lcs_bitparallel(left, right), dp_lcs_length(left, right))
        assert_equal(lcs_bitparallel(right, left), dp_lcs_length(left, right))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
