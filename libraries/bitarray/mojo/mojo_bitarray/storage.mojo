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


struct BitArray(Sized):
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

    def __len__(self) -> Int:
        """Logical length in bits (the `len()` builtin works via `Sized`)."""
        return self.length

    def nbytes(self) -> Int:
        """Physical storage in bytes: `ceil(length / 8)` (reference name)."""
        return bytes_for_bits(self.length)

    def padbits(self) -> Int:
        """Unused trailing bits in the final byte (0 when byte-aligned)."""
        return (8 - self.length % 8) % 8

    def endian(self) -> String:
        """Bit-endianness as a string, matching the reference attribute."""
        return String("big") if self.big_endian else String("little")

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
        var pad = self.padbits()
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

    # -- Phase 1B: construction from logical sequences -------------------

    def __init__(out self, s: String, big_endian: Bool) raises:
        """Build from a `'0'`/`'1'` string.

        ASCII whitespace and `'_'` are skipped, matching the reference;
        any other character raises. Endianness selects the physical
        layout; the logical sequence is identical either way.
        """
        var bits = List[Int]()
        var n = s.byte_length()
        for i in range(n):
            var ch = s[byte=i]
            if ch == "0":
                bits.append(0)
            elif ch == "1":
                bits.append(1)
            elif ch == " " or ch == "\t" or ch == "\n" or ch == "\r" or ch == "\f" or ch == "\v" or ch == "_":
                continue
            else:
                raise Error("expected '0' or '1' (or whitespace or underscore)")
        var fresh = _pack_bits(bits, big_endian)
        self.length = fresh.length
        self.big_endian = fresh.big_endian
        self.buffer = fresh.buffer.copy()

    def __init__(out self, items: List[Int], big_endian: Bool) raises:
        """Build from an iterable of bit values; only 0/1 are accepted.

        Anything else raises (reference: `ValueError`); floats, strings
        and other types cannot reach this overload in Mojo, which is the
        static equivalent of the reference `TypeError`.
        """
        var bits = List[Int](capacity=len(items))
        for i in range(len(items)):
            var v = items[i]
            if v != 0 and v != 1:
                raise Error("bit must be 0 or 1, got " + String(v))
            bits.append(v)
        var fresh = _pack_bits(bits, big_endian)
        self.length = fresh.length
        self.big_endian = fresh.big_endian
        self.buffer = fresh.buffer.copy()

    def __init__(out self, items: List[Bool], big_endian: Bool) raises:
        """Build from booleans (`True` -> 1, `False` -> 0)."""
        var bits = List[Int](capacity=len(items))
        for i in range(len(items)):
            bits.append(1 if items[i] else 0)
        var fresh = _pack_bits(bits, big_endian)
        self.length = fresh.length
        self.big_endian = fresh.big_endian
        self.buffer = fresh.buffer.copy()

    # -- Phase 1B: indexing and assignment --------------------------------

    def _resolve_index(self, i: Int, what: String) raises -> Int:
        """Translate a logical index (negatives allowed) to [0, length)."""
        var j = i + self.length if i < 0 else i
        if j < 0 or j >= self.length:
            raise Error(what)
        return j

    def __getitem__(self, i: Int) raises -> Int:
        """Logical bit value (0/1) at `i`; negatives count from the end."""
        return Int(self.read_bit(self._resolve_index(i, "bitarray index out of range")))

    def __setitem__(mut self, i: Int, v: Int) raises:
        """Set logical bit `i` to 0/1; anything else raises."""
        if v != 0 and v != 1:
            raise Error("bit must be 0 or 1, got " + String(v))
        var j = self._resolve_index(i, "bitarray assignment index out of range")
        if v == 1:
            self.set_bit(j)
        else:
            self.clear_bit(j)

    def __setitem__(mut self, i: Int, v: Bool) raises:
        """Set logical bit `i` from a boolean (`True` -> 1)."""
        self.__setitem__(i, 1 if v else 0)

    # -- Phase 1B: slicing -------------------------------------------------

    def _slice_step(self, sl: Slice) raises -> Int:
        var step = 1
        if sl.step is not None:
            step = sl.step.value()
        if step == 0:
            raise Error("slice step cannot be zero")
        return step

    def _slice_indices(self, sl: Slice) raises -> List[Int]:
        """Logical indices selected by `sl`, in iteration order.

        Python sequence semantics: omitted bounds default per step sign,
        negatives are relative to the end, out-of-range bounds clamp.
        """
        var step = self._slice_step(sl)
        var n = self.length
        var out = List[Int]()
        if step > 0:
            var lo = 0
            if sl.start is not None:
                var s = sl.start.value()
                lo = s + n if s < 0 else s
                lo = max(0, min(n, lo))
            var hi = n
            if sl.end is not None:
                var e = sl.end.value()
                hi = e + n if e < 0 else e
                hi = max(0, min(n, hi))
            var i = lo
            while i < hi:
                out.append(i)
                i += step
        else:
            var lo = n - 1
            if sl.start is not None:
                var s = sl.start.value()
                lo = s + n if s < 0 else s
                lo = max(-1, min(n - 1, lo))
            var hi = -1
            if sl.end is not None:
                var e = sl.end.value()
                hi = e + n if e < 0 else e
                hi = max(-1, min(n - 1, hi))
            var i = lo
            while i > hi:
                out.append(i)
                i += step
        return out^

    def _simple_bounds(self, sl: Slice) raises -> Tuple[Int, Int]:
        """Contiguous `[lo, hi)` span for a step-1 slice (insertion point
        when empty). Only valid when the step is 1."""
        var n = self.length
        var lo = 0
        if sl.start is not None:
            var s = sl.start.value()
            lo = s + n if s < 0 else s
            lo = max(0, min(n, lo))
        var hi = n
        if sl.end is not None:
            var e = sl.end.value()
            hi = e + n if e < 0 else e
            hi = max(0, min(n, hi))
        return (lo, hi)

    def __getitem__(self, sl: Slice) raises -> BitArray:
        """Slice with Python semantics; result keeps this endianness and
        owns independent storage."""
        var idx = self._slice_indices(sl)
        var bits = List[Int](capacity=len(idx))
        for i in range(len(idx)):
            bits.append(Int(self.read_bit(idx[i])))
        return _pack_bits(bits, self.big_endian)

    def __setitem__(mut self, sl: Slice, v: BitArray) raises:
        """Slice assignment. Step-1 slices resize (any replacement length
        is legal, like `list`); stepped slices require an exact length
        match and fail atomically.

        Note: the value parameter must be named `v` — Mojo resolves the
        `a[sl] = x` syntax against `__setitem__` overloads by that name
        (verified by probe: any other name fails to resolve).
        """
        var step = self._slice_step(sl)
        var idx = self._slice_indices(sl)
        if step == 1:
            var bounds = self._simple_bounds(sl)
            var lo = bounds[0]
            var hi = bounds[1]
            var combo = List[Int](capacity=lo + len(v) + (self.length - hi))
            for i in range(lo):
                combo.append(Int(self.read_bit(i)))
            for i in range(len(v)):
                combo.append(Int(v.read_bit(i)))
            for i in range(hi, self.length):
                combo.append(Int(self.read_bit(i)))
            var fresh = _pack_bits(combo, self.big_endian)
            self.buffer = fresh.buffer.copy()
            self.length = fresh.length
        else:
            if len(v) != len(idx):
                raise Error(
                    "attempt to assign sequence of size "
                    + String(len(v))
                    + " to extended slice of size "
                    + String(len(idx))
                )
            # Snapshot first: `v` may alias `self`.
            var rep = List[Int](capacity=len(idx))
            for k in range(len(idx)):
                rep.append(Int(v.read_bit(k)))
            for k in range(len(idx)):
                if rep[k] == 1:
                    self.set_bit(idx[k])
                else:
                    self.clear_bit(idx[k])

    def __setitem__(mut self, sl: Slice, v: Int) raises:
        """Broadcast a single 0/1 across the selected positions (never
        resizes; an empty selection is a no-op). Validated first, so a
        bad value leaves the array untouched."""
        if v != 0 and v != 1:
            raise Error("bit must be 0 or 1, got " + String(v))
        var idx = self._slice_indices(sl)
        for k in range(len(idx)):
            if v == 1:
                self.set_bit(idx[k])
            else:
                self.clear_bit(idx[k])

    def __setitem__(mut self, sl: Slice, v: Bool) raises:
        """Broadcast a boolean across the selected positions."""
        self.__setitem__(sl, 1 if v else 0)

    # -- Phase 1B: conversion and iteration --------------------------------

    def to01(self) raises -> String:
        """Logical bit sequence as a `'0'`/`'1'` string (padding ignored)."""
        var out = String("")
        for i in range(self.length):
            out += String("1") if self.read_bit(i) == UInt8(1) else String("0")
        return out^

    def tolist(self) raises -> List[Int]:
        """Logical bits as a list of ints, matching the reference."""
        var out = List[Int](capacity=self.length)
        for i in range(self.length):
            out.append(Int(self.read_bit(i)))
        return out^

    def __iter__(self) raises -> BitArrayIter:
        """Logical iteration in sequence order (snapshot semantics)."""
        return BitArrayIter(self)

    # -- Phase 1C: mutation and structural operations -----------------------

    def append(mut self, v: Int) raises:
        """Append one logical bit; only 0/1 are accepted.

        Grows the buffer by one byte exactly at byte boundaries;
        existing bits and zeroed padding are otherwise untouched.
        """
        _check_bit(v)
        if self.length % 8 == 0:
            self.buffer.append(UInt8(0))
        self.length += 1
        if v == 1:
            self.set_bit(self.length - 1)
        self.normalize_padding()

    def append(mut self, v: Bool) raises:
        """Append one logical bit from a boolean (`True` -> 1)."""
        self.append(1 if v else 0)

    def extend(mut self, other: BitArray) raises:
        """Append `other`'s logical bits; this endianness is kept.

        The source is snapshotted first, so self-extension works and
        no buffer is read while it is being grown.
        """
        var add = other.tolist()
        for i in range(len(add)):
            self.append(add[i])

    def extend(mut self, items: List[Int]) raises:
        """Append validated bits; the whole input is validated before
        anything is appended, so a bad value leaves `self` untouched."""
        for i in range(len(items)):
            _check_bit(items[i])
        for i in range(len(items)):
            self.append(items[i])

    def extend(mut self, items: List[Bool]) raises:
        """Append booleans (`True` -> 1)."""
        for i in range(len(items)):
            self.append(1 if items[i] else 0)

    def extend(mut self, s: String) raises:
        """Append bits from a `'0'`/`'1'` string (validated first, via
        the string constructor)."""
        var add = BitArray(s, self.big_endian)
        self.extend(add)

    def insert(mut self, i: Int, v: Int) raises:
        """Insert one bit; the index clamps like the reference (past-end
        appends, far-negative prepends, `-1` goes before the last bit)."""
        _check_bit(v)
        var pos = i
        if pos < 0:
            pos += self.length
        pos = max(0, min(self.length, pos))
        var bits = self.tolist()
        var combo = List[Int](capacity=len(bits) + 1)
        for k in range(pos):
            combo.append(bits[k])
        combo.append(v)
        for k in range(pos, len(bits)):
            combo.append(bits[k])
        var fresh = _pack_bits(combo, self.big_endian)
        self.buffer = fresh.buffer.copy()
        self.length = fresh.length

    def insert(mut self, i: Int, v: Bool) raises:
        """Insert one bit from a boolean (`True` -> 1)."""
        self.insert(i, 1 if v else 0)

    def delete(mut self, i: Int) raises:
        """Delete the bit at `i` (negatives allowed).

        Mojo has no `del a[i]` syntax, so this method carries the
        reference `__delitem__` semantics verbatim, including its
        `"bitarray assignment index out of range"` error.
        """
        var j = self._resolve_index(i, "bitarray assignment index out of range")
        var bits = self.tolist()
        var combo = List[Int](capacity=len(bits) - 1)
        for k in range(len(bits)):
            if k != j:
                combo.append(bits[k])
        var fresh = _pack_bits(combo, self.big_endian)
        self.buffer = fresh.buffer.copy()
        self.length = fresh.length

    def __add__(self, other: BitArray) raises -> BitArray:
        """Concatenate logical bits; the result keeps the LEFT operand's
        endianness (reference behavior, verified by probe). Both inputs
        are snapshotted, so self-concatenation is safe."""
        var combo = self.tolist()
        var right = other.tolist()
        for i in range(len(right)):
            combo.append(right[i])
        return _pack_bits(combo, self.big_endian)

    def __iadd__(mut self, other: BitArray) raises:
        """In-place concatenation; keeps this endianness."""
        self.extend(other)

    def __eq__(self, other: BitArray) raises -> Bool:
        """Logical equality; endianness-insensitive, like the reference."""
        if self.length != other.length:
            return False
        for i in range(self.length):
            if self.read_bit(i) != other.read_bit(i):
                return False
        return True

    def __ne__(self, other: BitArray) raises -> Bool:
        """Logical inequality."""
        return not self.__eq__(other)

    def _compare(self, other: BitArray) raises -> Int:
        """Lexicographic order on logical bits (`-1`/`0`/`1`); a proper
        prefix sorts first (shorter-is-smaller), per the reference."""
        var n = min(self.length, other.length)
        for i in range(n):
            var a = self.read_bit(i)
            var b = other.read_bit(i)
            if a != b:
                return -1 if a < b else 1
        if self.length == other.length:
            return 0
        return -1 if self.length < other.length else 1

    def __lt__(self, other: BitArray) raises -> Bool:
        """Lexicographic less-than on logical bits."""
        return self._compare(other) < 0

    def __le__(self, other: BitArray) raises -> Bool:
        """Lexicographic less-than-or-equal on logical bits."""
        return self._compare(other) <= 0

    def __gt__(self, other: BitArray) raises -> Bool:
        """Lexicographic greater-than on logical bits."""
        return self._compare(other) > 0

    def __ge__(self, other: BitArray) raises -> Bool:
        """Lexicographic greater-than-or-equal on logical bits."""
        return self._compare(other) >= 0


def _check_bit(v: Int) raises:
    """Reject anything but 0/1 (reference: `ValueError`)."""
    if v != 0 and v != 1:
        raise Error("bit must be 0 or 1, got " + String(v))


def _pack_bits(bits: List[Int], big_endian: Bool) raises -> BitArray:
    """Pack caller-validated 0/1 values into an owned `BitArray`."""
    var n = len(bits)
    var buf = List[UInt8](capacity=bytes_for_bits(n))
    for _ in range(bytes_for_bits(n)):
        buf.append(UInt8(0))
    var out = BitArray(buf^, n, big_endian)
    for i in range(n):
        if bits[i] == 1:
            out.set_bit(i)
    return out^


struct BitArrayIter(Sized):
    """Snapshot iterator over logical bits (yields `Int` 0/1)."""

    var snap: BitArray
    var pos: Int

    def __init__(out self, src: BitArray) raises:
        self.snap = BitArray(src.buffer.copy(), src.length, src.big_endian)
        self.pos = 0

    def __next__(mut self) raises -> Int:
        if self.pos >= len(self.snap):
            raise Error("iterator exhausted")
        var v = Int(self.snap.read_bit(self.pos))
        self.pos += 1
        return v

    def __len__(self) -> Int:
        return len(self.snap) - self.pos
