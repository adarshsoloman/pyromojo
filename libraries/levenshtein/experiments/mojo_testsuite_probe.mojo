"""Phase 0 probe: raises, assert_raises, and TestSuite discovery."""

from std.testing import TestSuite, assert_equal, assert_raises


def validate_non_negative(value: Int) raises:
    if value < 0:
        raise Error("negative value: " + String(value))


def test_raises_carries_message() raises:
    with assert_raises(contains="negative value"):
        validate_non_negative(-1)


def test_raises_on_boundary() raises:
    validate_non_negative(0)
    assert_equal(1 + 1, 2)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
