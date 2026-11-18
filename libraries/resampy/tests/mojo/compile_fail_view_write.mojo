"""Compile-failure fixture: writing through Signal.view() must be rejected.

This file is intentionally invalid Mojo. tests/python_compat/test_signal_view_immutability.py
compiles it and asserts a non-zero exit, proving the read-only view is
enforced by the type system rather than by convention.
"""

from std.collections import List
from mojo_resampy.signal import Signal


def main() raises:
    var values = List[Float64]()
    values.append(1.0)
    var signal = Signal(values^)
    signal.view()[0] = 99.0
