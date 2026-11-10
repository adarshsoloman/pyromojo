from std.testing import assert_equal, TestSuite


def test_addition() raises:
    assert_equal(100 + 200, 300)


def test_multiplication() raises:
    assert_equal(20 * 5, 100)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
