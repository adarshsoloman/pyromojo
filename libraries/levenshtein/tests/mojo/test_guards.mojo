"""Regression tests for the Phase 0 hazard findings.

- Shifts must never reach the full bit width (the n == 64 / n == 128
  Myers failure mode): exact-boundary patterns are exercised through
  the public API.
- Integer arithmetic wraps silently: oversized weight/length products
  raise instead of wrapping.
- The Mojo constant folder mis-rounds multi-op float expressions
  (``1.0 - 2.0 / 6.0`` folds to ``...666``); runtime computation is
  exact, and this test pins the runtime result through ``ratio``.
"""

from std.testing import TestSuite, assert_equal, assert_raises

from mojo_levenshtein.distance import (
    levenshtein_distance,
    levenshtein_distance_cutoff,
)
from mojo_levenshtein.ratio import levenshtein_ratio

from test_support import ascii_string


def test_full_word_patterns() raises:
    var pattern_64 = ascii_string(97, 64)
    var pattern_128 = ascii_string(97, 128)
    assert_equal(levenshtein_distance(pattern_64, pattern_64), 0)
    assert_equal(levenshtein_distance(pattern_128, pattern_128), 0)
    assert_equal(levenshtein_distance(pattern_64, ascii_string(98, 64)), 64)
    assert_equal(levenshtein_distance(pattern_128, ascii_string(98, 128)), 128)
    # The exact Phase 0 failure shape: 128-against-128 random content
    # must equal the DP oracle (covered by parity tests; spot-checked).
    assert_equal(levenshtein_distance(pattern_128, pattern_64), 64)


def test_weight_product_overflow_raises() raises:
    var long = ascii_string(97, 1000)
    with assert_raises(contains="exceed the Int range"):
        _ = levenshtein_distance(long, long, Int.MAX, 1, 1)
    with assert_raises(contains="exceed the Int range"):
        _ = levenshtein_distance(long, long, 1, Int.MAX, 1)


def test_runtime_float_arithmetic_is_exact() raises:
    # Pins the runtime computation against the literal; a constant-fold
    # regression in the toolchain would show up here, not in goldens.
    assert_equal(levenshtein_ratio("abc", "adc"), 0.6666666666666667)
    var two = 2.0
    var six = 6.0
    assert_equal(1.0 - two / six, 0.6666666666666667)


def test_cutoff_plus_one_cannot_overflow() raises:
    assert_equal(
        levenshtein_distance_cutoff("abc", "xyz", Int.MAX - 1), 3
    )
    assert_equal(levenshtein_distance_cutoff("abc", "abc", Int.MAX), 0)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
