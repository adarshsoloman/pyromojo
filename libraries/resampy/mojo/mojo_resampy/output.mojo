"""Phase 3 / Component B: owned Float64 output buffer.

An ``OutputBuffer`` owns a zero-initialized ``List[Float64]``. It is independent
of any interpolation algorithm: it only knows its length and its elements.

Design notes
------------
- Allocation is exact-size with ``resize(length, 0.0)``; every element is zero.
- Indexed reads/writes are bounds-checked (no unchecked buffer access).
- ``take()`` copies the values out for hand-off; ``release()`` returns an owned
  ``List[Float64]`` constructed element-by-element to keep ownership explicit.
- Zero-length and single-element buffers are valid.
"""

from std.collections import List


# Allocation limit for a single output buffer. Guards the semantic length
# supplied by a CLI request before any allocation or byte-size multiplication.
comptime MAX_OUTPUT_ELEMENTS: Int = 1_000_000
comptime MAX_OUTPUT_BYTES: Int = MAX_OUTPUT_ELEMENTS * 8


struct OutputBuffer(Sized, Copyable, Movable):
    """Owned, zero-initialized 1-D Float64 output buffer."""

    var _values: List[Float64]

    def __init__(out self, length: Int) raises:
        if length < 0:
            raise Error("output length must be non-negative, got " + String(length))
        if length > MAX_OUTPUT_ELEMENTS:
            raise Error(
                "output length " + String(length) + " exceeds limit "
                + String(MAX_OUTPUT_ELEMENTS)
            )
        self._values = List[Float64](capacity=length)
        self._values.resize(length, 0.0)

    def __len__(self) -> Int:
        return len(self._values)

    def __getitem__(self, index: Int) raises -> Float64:
        if index < 0 or index >= len(self._values):
            raise Error(
                "output index " + String(index)
                + " out of range for length " + String(len(self._values))
            )
        return self._values[index]

    def set(mut self, index: Int, value: Float64) raises:
        """Bounds-checked indexed write of an exact Float64 value."""
        if index < 0 or index >= len(self._values):
            raise Error(
                "output index " + String(index)
                + " out of range for length " + String(len(self._values))
            )
        self._values[index] = value

    def add(mut self, index: Int, value: Float64) raises:
        """Bounds-checked accumulation (for a future interpolation kernel)."""
        if index < 0 or index >= len(self._values):
            raise Error(
                "output index " + String(index)
                + " out of range for length " + String(len(self._values))
            )
        self._values[index] += value

    def view(self) -> Span[Float64, origin_of(self._values)]:
        return Span(self._values)

    def take(self) -> List[Float64]:
        """Return an owned copy of the values (buffer remains valid)."""
        var out = List[Float64](capacity=len(self._values))
        for i in range(len(self._values)):
            out.append(self._values[i])
        return out^

    def is_empty(self) -> Bool:
        return len(self._values) == 0
