"""Phase 0 probe: std.testing discovery and assert_raises."""

from std.testing import TestSuite, assert_equal, assert_raises


def test_arithmetic() raises:
    assert_equal(2 + 2, 4)


def test_assert_raises() raises:
    with assert_raises(contains="boom"):
        raise Error("boom happened")


def test_failure_is_attributed() raises:
    assert_equal(String("abc").byte_length(), 3)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
