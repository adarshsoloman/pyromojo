"""Phase 3 / Component A: one-dimensional Float64 signal representation.

A ``Signal`` owns a ``List[Float64]``. It is a value type: copies are explicit
(``copy()``), and taking the owned buffer back out is explicit (``take()``).
No implicit dtype conversion is performed anywhere; every value is stored and
returned as the exact Float64 bit pattern provided.

Design notes
------------
- ``List[Float64]`` is chosen over ``Span`` for the owned representation: it
  has clear ownership, supports empty/single/large signals, and can be resized.
- ``Span[Float64, _]`` is used only as a *borrowed read-only view*, obtained via
  ``view()``. The view lifetime is tied to the Signal.
- No tensor or multidimensional abstraction is introduced (Phase 1 scope).
"""

from std.collections import List


struct Signal(Sized, Copyable, Movable):
    """Owned 1-D Float64 signal. Immutable by convention; no public mutators."""

    var _values: List[Float64]

    def __init__(out self):
        """Construct an empty signal."""
        self._values = List[Float64]()

    def __init__(out self, var values: List[Float64]):
        """Take ownership of ``values`` (transfer with ``^`` at call site)."""
        self._values = values^

    @staticmethod
    def from_span(values: Span[Float64, _]) -> Signal:
        """Copy a borrowed view into a new owned Signal."""
        var out = Signal()
        for i in range(len(values)):
            out._values.append(values[i])
        return out^

    @staticmethod
    def zeros(length: Int) raises -> Signal:
        """Construct a signal of exactly ``length`` zero values."""
        if length < 0:
            raise Error("signal length must be non-negative, got " + String(length))
        var out = Signal()
        for _ in range(length):
            out._values.append(0.0)
        return out^

    def __len__(self) -> Int:
        return len(self._values)

    def __getitem__(self, index: Int) raises -> Float64:
        """Bounds-checked indexed read (raises on out-of-range)."""
        if index < 0 or index >= len(self._values):
            raise Error(
                "signal index " + String(index)
                + " out of range for length " + String(len(self._values))
            )
        return self._values[index]

    def view(self) -> Span[Float64, origin_of(self._values)]:
        """Borrowed read-only view; lifetime tied to this Signal."""
        return Span(self._values)

    def copy(self) -> Signal:
        """Explicit deep copy preserving every Float64 bit pattern."""
        var out = Signal()
        for i in range(len(self._values)):
            out._values.append(self._values[i])
        return out^

    def take(self) -> List[Float64]:
        """Return a copy of the owned values (does not consume the Signal).

        An explicit, non-destructive hand-off: the Signal remains valid. Use
        ``^`` transfer at the call site when the caller wants to move values.
        """
        var out = List[Float64](capacity=len(self._values))
        for i in range(len(self._values)):
            out.append(self._values[i])
        return out^

    def is_empty(self) -> Bool:
        return len(self._values) == 0
