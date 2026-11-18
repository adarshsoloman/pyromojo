"""Phase 3 native tests: Component B (OutputBuffer)."""

from std.collections import List
from std.testing import TestSuite, assert_equal, assert_true, assert_raises

from mojo_resampy.output import OutputBuffer
from test_support import assert_bits_equal


def test_alloc_zero_length() raises:
    var b = OutputBuffer(0)
    assert_equal(len(b), 0)
    assert_true(b.is_empty())


def test_alloc_single_element() raises:
    var b = OutputBuffer(1)
    assert_equal(len(b), 1)
    assert_bits_equal(b[0], 0.0)


def test_alloc_initializes_all_zero() raises:
    var b = OutputBuffer(1000)
    assert_equal(len(b), 1000)
    for i in range(len(b)):
        assert_bits_equal(b[i], 0.0)


def test_indexed_write_read() raises:
    var b = OutputBuffer(4)
    b.set(0, 1.5)
    b.set(2, -0.0)
    b.set(3, 5e-324)
    assert_bits_equal(b[0], 1.5)
    assert_bits_equal(b[1], 0.0)
    assert_bits_equal(b[2], -0.0)
    assert_bits_equal(b[3], 5e-324)


def test_accumulation() raises:
    var b = OutputBuffer(2)
    b.add(0, 1.25)
    b.add(0, 2.5)
    assert_bits_equal(b[0], 3.75)
    assert_bits_equal(b[1], 0.0)


def test_take_returns_copy() raises:
    var b = OutputBuffer(3)
    b.set(1, 7.0)
    var taken = b.take()
    assert_equal(len(taken), 3)
    assert_bits_equal(taken[1], 7.0)
    taken[1] = -1.0
    assert_bits_equal(b[1], 7.0)


def test_view_read() raises:
    var b = OutputBuffer(3)
    b.set(1, 2.0)
    var v = b.view()
    assert_equal(len(v), 3)
    assert_bits_equal(v[1], 2.0)


def test_reject_negative_length() raises:
    with assert_raises():
        _ = OutputBuffer(-1)


def test_index_out_of_range_read() raises:
    var b = OutputBuffer(2)
    with assert_raises():
        _ = b[2]
    with assert_raises():
        _ = b[-1]


def test_index_out_of_range_write() raises:
    var b = OutputBuffer(2)
    with assert_raises():
        b.set(2, 1.0)
    with assert_raises():
        b.add(-1, 1.0)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
