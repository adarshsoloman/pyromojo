"""Packed-bit storage foundation for the native bitarray port (Phase 1A).

A `BitArray` owns a `List[UInt8]` buffer holding exactly
`ceil(length / 8)` bytes, plus an endianness flag. Bit `i` lives in
byte `i // 8`; within the byte at position `7 - (i % 8)` (big-endian)
or `i % 8` (little-endian) — the reference `BITMASK` rule.

Invariants (enforced at construction, preserved by every mutator):
- `length` is the exact logical bit count.
- `buffer` holds exactly `ceil(length / 8)` bytes.
- Padding bits in the final byte are always zero.
- Invalid indexes raise; arithmetic never relies on wraparound and no
  shift amount ever reaches the bit width (all shifts are by values
  in 0..7, guarded by construction).
"""

from std.collections import List

comptime ENDIAN_BIG: Bool = True
comptime ENDIAN_LITTLE: Bool = False


def bytes_for_bits(n: Int) -> Int:
    """Whole bytes needed to store `n` bits: ceil(n / 8), overflow-free.

    Division happens before any addition, and `n >= 0` is a precondition
    of every caller, so no wraparound is possible.
    """
    var full = n // 8
    if n % 8 != 0:
        return full + 1
    return full


struct BitArray:
    var buffer: List[UInt8]
    var length: Int
    var big_endian: Bool

    def __init__(out self, var buffer: List[UInt8], length: Int, big_endian: Bool) raises:
        """Take ownership of a packed buffer.

        The buffer must hold exactly `ceil(length / 8)` bytes; anything
        else raises. Padding bits are normalized to zero on entry.
        """
        if length < 0:
            raise Error("negative bit length")
        if len(buffer) != bytes_for_bits(length):
            raise Error("buffer size does not match bit length")
        self.buffer = buffer^
        self.length = length
        self.big_endian = big_endian
        self.normalize_padding()

    def byte_count(self) -> Int:
        """Physical storage in bytes, derived from the logical length."""
        return bytes_for_bits(self.length)

    def pad_count(self) -> Int:
        """Unused trailing bits in the final byte (0 when byte-aligned)."""
        return (8 - self.length % 8) % 8

    def _check_index(self, i: Int) raises:
        if i < 0 or i >= self.length:
            raise Error("bit index out of range")

    def byte_index(self, i: Int) raises -> Int:
        """Byte holding logical bit `i` (bounds-checked)."""
        self._check_index(i)
        return i // 8

    def bit_mask(self, i: Int) raises -> UInt8:
        """Single-bit mask for logical bit `i` (bounds-checked)."""
        self._check_index(i)
        if self.big_endian:
            return UInt8(1) << UInt8(7 - (i % 8))
        return UInt8(1) << UInt8(i % 8)

    def read_bit(self, i: Int) raises -> UInt8:
        """Logical bit value (0 or 1) at index `i`."""
        var b = self.byte_index(i)
        if self.buffer[b] & self.bit_mask(i) != UInt8(0):
            return UInt8(1)
        return UInt8(0)

    def set_bit(mut self, i: Int) raises:
        """Set logical bit `i` to 1, leaving neighbours untouched."""
        var b = self.byte_index(i)
        self.buffer[b] = self.buffer[b] | self.bit_mask(i)

    def clear_bit(mut self, i: Int) raises:
        """Set logical bit `i` to 0, leaving neighbours untouched."""
        var b = self.byte_index(i)
        self.buffer[b] = self.buffer[b] & ~self.bit_mask(i)

    def normalize_padding(mut self):
        """Zero out any padding bits in the final byte (idempotent)."""
        var pad = self.pad_count()
        if pad == 0 or len(self.buffer) == 0:
            return
        var last = len(self.buffer) - 1
        if self.big_endian:
            # Valid bits are the top (8 - pad) bits; zero the low `pad`.
            self.buffer[last] = self.buffer[last] & (UInt8(0xFF) << UInt8(pad))
        else:
            # Valid bits are the low (8 - pad) bits; zero the top `pad`.
            var keep = UInt8(8 - pad)
            self.buffer[last] = self.buffer[last] & (UInt8(1) << keep) - UInt8(1)
