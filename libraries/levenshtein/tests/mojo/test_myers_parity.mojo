"""DP-versus-Myers parity over deterministic randomized pairs.

The DP oracle and the blocked Myers implementation must agree exactly on
every input shape: empty, single-word, word boundaries (63/64/65,
127/128/129), multiword, repeated characters, all-different strings,
asymmetric lengths, and non-ASCII code points.
"""

from std.collections import List
from std.testing import TestSuite, assert_equal

from mojo_levenshtein.algorithms.dynamic_programming import dp_distance
from mojo_levenshtein.algorithms.myers import myers_distance
from mojo_levenshtein.unicode import to_codepoints

from test_support import TestRng, random_ascii, random_codepoints


def check_pair(left: String, right: String) raises:
    var a = to_codepoints(left)
    var b = to_codepoints(right)
    assert_equal(myers_distance(a, b), dp_distance(a, b))
    assert_equal(myers_distance(b, a), dp_distance(a, b))


def test_fixed_boundaries() raises:
    check_pair("", "")
    check_pair("", "abc")
    check_pair("a", "")
    check_pair("kitten", "sitting")
    check_pair("abc", "adc")
    check_pair("ab", "ba")
    check_pair("aaaa", "aa")
    check_pair("aa", "aaaa")


def test_word_boundaries() raises:
    var rng = TestRng(60601)
    for size in range(60, 70):
        check_pair(random_ascii(rng, size), random_ascii(rng, size))
    for size in range(124, 133):
        check_pair(random_ascii(rng, size), random_ascii(rng, size))
    for size in range(188, 197):
        check_pair(random_ascii(rng, size), random_ascii(rng, size))


def test_repeated_and_uniform() raises:
    var rng = TestRng(60602)
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


def test_random_ascii_parity() raises:
    var rng = TestRng(60603)
    for _ in range(300):
        var left = random_ascii(rng, rng.next(301))
        var right = random_ascii(rng, rng.next(301))
        check_pair(left, right)


def test_random_code_point_parity() raises:
    var rng = TestRng(60604)
    for _ in range(150):
        var left = random_codepoints(rng, rng.next(200))
        var right = random_codepoints(rng, rng.next(200))
        assert_equal(myers_distance(left, right), dp_distance(left, right))
        assert_equal(myers_distance(right, left), dp_distance(left, right))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
