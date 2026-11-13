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

    def _find_bounds(self, start: Int, stop: Int) -> Tuple[Int, Int]:
        """`[lo, hi)` window for `find`/`index`/sub-`count`.

        Unlike slice bounds, the start is NOT clamped above: negatives
        are relative to the end and both ends floor at zero, but an
        over-length start stays over-length so the window is genuinely
        empty (`start > stop` after this normalization means no match).
        This reproduces the reference exactly, including its quirk that
        an empty pattern with `start > n` finds nothing while `search`
        (which uses slice bounds) still yields the boundary position.
        """
        var n = self.length
        var lo = start + n if start < 0 else start
        lo = max(0, lo)
        var hi = stop + n if stop < 0 else stop
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

    # -- Phase 1D1: bitwise operations and shifts ---------------------------

    def _check_compat(self, other: BitArray) raises:
        """Validate binary operands: equal length first (the reference
        reports length mismatches before endianness mismatches), then
        equal endianness."""
        if self.length != other.length:
            raise Error("bitarrays of equal length expected")
        if self.big_endian != other.big_endian:
            raise Error("bitarrays of equal bit-endianness expected")

    def __and__(self, other: BitArray) raises -> BitArray:
        """Logical AND. Pad bits are zero in both inputs by invariant;
        the result is normalized anyway for defense in depth."""
        self._check_compat(other)
        var out = List[UInt8](capacity=len(self.buffer))
        for i in range(len(self.buffer)):
            out.append(self.buffer[i] & other.buffer[i])
        var result = BitArray(out^, self.length, self.big_endian)
        result.normalize_padding()
        return result^

    def __or__(self, other: BitArray) raises -> BitArray:
        """Logical OR (same padding argument as `__and__`)."""
        self._check_compat(other)
        var out = List[UInt8](capacity=len(self.buffer))
        for i in range(len(self.buffer)):
            out.append(self.buffer[i] | other.buffer[i])
        var result = BitArray(out^, self.length, self.big_endian)
        result.normalize_padding()
        return result^

    def __xor__(self, other: BitArray) raises -> BitArray:
        """Logical XOR (same padding argument as `__and__`)."""
        self._check_compat(other)
        var out = List[UInt8](capacity=len(self.buffer))
        for i in range(len(self.buffer)):
            out.append(self.buffer[i] ^ other.buffer[i])
        var result = BitArray(out^, self.length, self.big_endian)
        result.normalize_padding()
        return result^

    def __invert__(self) raises -> BitArray:
        """Logical NOT. `~` flips pad bits too, so the result must be
        re-normalized (not optional here, unlike AND/OR/XOR)."""
        var out = List[UInt8](capacity=len(self.buffer))
        for i in range(len(self.buffer)):
            out.append(~self.buffer[i])
        var result = BitArray(out^, self.length, self.big_endian)
        result.normalize_padding()
        return result^

    def __iand__(mut self, other: BitArray) raises:
        """In-place AND; validated before any mutation (atomic)."""
        self._check_compat(other)
        for i in range(len(self.buffer)):
            self.buffer[i] = self.buffer[i] & other.buffer[i]
        self.normalize_padding()

    def __ior__(mut self, other: BitArray) raises:
        """In-place OR; validated before any mutation (atomic)."""
        self._check_compat(other)
        for i in range(len(self.buffer)):
            self.buffer[i] = self.buffer[i] | other.buffer[i]
        self.normalize_padding()

    def __ixor__(mut self, other: BitArray) raises:
        """In-place XOR; validated before any mutation (atomic)."""
        self._check_compat(other)
        for i in range(len(self.buffer)):
            self.buffer[i] = self.buffer[i] ^ other.buffer[i]
        self.normalize_padding()

    def _shifted(self, k: Int, left: Bool) raises -> BitArray:
        """Length-preserving shift with zero fill, packed byte-at-a-time.

        Left: `new[i] = old[i + k]`; right: `new[i] = old[i - k]`;
        out-of-range reads are zero. Whole bytes shift by `k // 8` with
        an intra-byte carry of `k % 8`; the carry direction follows the
        endianness (big-endian logical order is MSB-first, little-endian
        is LSB-first). All shift amounts are in 0..7 by construction
        (`bi == 0` takes a branch, so no shift ever reaches the width),
        and padding is re-normalized afterwards.
        """
        if k < 0:
            raise Error("negative shift count")
        var nb = len(self.buffer)
        var out = List[UInt8](capacity=nb)
        for _ in range(nb):
            out.append(UInt8(0))
        var bo = k // 8
        var bi = k % 8
        for j in range(nb):
            var acc: UInt8 = UInt8(0)
            if left:
                var s = j + bo
                if s < nb:
                    if self.big_endian:
                        acc = self.buffer[s] << UInt8(bi)
                        if bi != 0 and s + 1 < nb:
                            acc = acc | (self.buffer[s + 1] >> UInt8(8 - bi))
                    else:
                        acc = self.buffer[s] >> UInt8(bi)
                        if bi != 0 and s + 1 < nb:
                            acc = acc | (self.buffer[s + 1] << UInt8(8 - bi))
            else:
                var s = j - bo
                if s >= 0:
                    if self.big_endian:
                        acc = self.buffer[s] >> UInt8(bi)
                        if bi != 0 and s - 1 >= 0:
                            acc = acc | (self.buffer[s - 1] << UInt8(8 - bi))
                    else:
                        acc = self.buffer[s] << UInt8(bi)
                        if bi != 0 and s - 1 >= 0:
                            acc = acc | (self.buffer[s - 1] >> UInt8(8 - bi))
            out[j] = acc
        var result = BitArray(out^, self.length, self.big_endian)
        result.normalize_padding()
        return result^

    def __lshift__(self, k: Int) raises -> BitArray:
        """Length-preserving left shift with zero fill."""
        return self._shifted(k, True)

    def __rshift__(self, k: Int) raises -> BitArray:
        """Length-preserving right shift with zero fill."""
        return self._shifted(k, False)

    def __ilshift__(mut self, k: Int) raises:
        """In-place left shift (length unchanged)."""
        var fresh = self._shifted(k, True)
        self.buffer = fresh.buffer.copy()
        self.length = fresh.length

    def __irshift__(mut self, k: Int) raises:
        """In-place right shift (length unchanged)."""
        var fresh = self._shifted(k, False)
        self.buffer = fresh.buffer.copy()
        self.length = fresh.length

    # -- Phase 1D2: population count and search ------------------------------

    def _popcount(self) -> Int:
        """Number of set bits among LOGICAL bits (padding masked out).

        Byte-wise SWAR popcount (the Phase 0 validated formulation);
        the final partial byte is masked to its valid bits first, so
        padding — always zero by invariant — can never leak into the
        total even if an invariant were violated upstream.
        """
        var total = 0
        var nb = len(self.buffer)
        if nb == 0:
            return 0
        for i in range(nb - 1):
            total += Int(_popcount_byte(self.buffer[i]))
        var last = self.buffer[nb - 1]
        var pad = self.padbits()
        if pad != 0:
            if self.big_endian:
                last = last & (UInt8(0xFF) << UInt8(pad))
            else:
                last = last & (((UInt8(1) << UInt8(8 - pad)) - UInt8(1)))
        total += Int(_popcount_byte(last))
        return total

    def count(self) raises -> Int:
        """Count of set bits (reference default `value=1`)."""
        return self._popcount()

    def count(self, v: Int) raises -> Int:
        """Count of `v` bits; only 0/1 accepted (zeros via complement)."""
        _check_bit(v)
        if v == 1:
            return self._popcount()
        return self.length - self._popcount()

    def count(self, v: Bool) raises -> Int:
        """Count of `True` (1) or `False` (0) bits."""
        return self.count(1 if v else 0)

    def count(self, v: Int, start: Int) raises -> Int:
        """Count of `v` from `start` to the end (reference default stop)."""
        return self.count(v, start, self.length, 1)

    def count(self, v: Bool, start: Int) raises -> Int:
        """Count of a boolean bit from `start` to the end."""
        return self.count(1 if v else 0, start)

    def count(self, v: Int, start: Int, stop: Int) raises -> Int:
        """Count of `v` over `[start:stop)` (reference default step 1)."""
        return self.count(v, start, stop, 1)

    def count(self, v: Bool, start: Int, stop: Int) raises -> Int:
        """Count of a boolean bit over `[start:stop)`."""
        return self.count(1 if v else 0, start, stop)

    def count(self, v: Bool, start: Int, stop: Int, step: Int) raises -> Int:
        """Count of a boolean bit over `self[start:stop:step]`."""
        return self.count(1 if v else 0, start, stop, step)

    def count(self, v: Int, start: Int, stop: Int, step: Int) raises -> Int:
        """Count of `v` over `self[start:stop:step]` — exactly the slice
        semantics (reference: `a.count(v, s, e, st) == a[s:e:st].count(v)`),
        including the step-zero error from slice normalization."""
        _check_bit(v)
        var idx = self._slice_indices(slice(start, stop, step))
        var total = 0
        for i in range(len(idx)):
            if Int(self.read_bit(idx[i])) == v:
                total += 1
        return total

    def count(self, sub: BitArray) raises -> Int:
        """Non-overlapping occurrences of `sub` over the whole array."""
        return self.count(sub, 0, self.length)

    def count(self, sub: BitArray, start: Int, stop: Int) raises -> Int:
        """Non-overlapping occurrences of `sub` with matches contained in
        `[start:stop)`. An empty pattern matches at every position
        `lo..=hi` of a non-empty window (reference: `n+1` over the full
        array; an over-length start yields an empty window and 0)."""
        var bounds = self._find_bounds(start, stop)
        var lo = bounds[0]
        var hi = bounds[1]
        var m = len(sub)
        if m == 0:
            return (hi - lo) + 1
        var total = 0
        var p = lo
        while p + m <= hi:
            if self._match_at(sub, p):
                total += 1
                p += m
            else:
                p += 1
        return total

    def _match_at(self, pat: BitArray, at: Int) raises -> Bool:
        """Whether `pat` matches `self` starting at logical index `at`."""
        for k in range(len(pat)):
            if self.read_bit(at + k) != pat.read_bit(k):
                return False
        return True

    def _search_from(
        self, pat: BitArray, lo: Int, hi: Int, right: Bool
    ) raises -> List[Int]:
        """Match start positions with `pat` contained in `[lo:hi)`.

        Overlapping matches are reported (like the reference); an empty
        pattern matches every position `lo..=hi`. Ascending unless
        `right` is set, which yields descending order.
        """
        var out = List[Int]()
        var m = len(pat)
        if m == 0:
            var positions = List[Int](capacity=(hi - lo) + 1)
            var q = lo
            while q <= hi:
                positions.append(q)
                q += 1
            if right:
                var rev = List[Int](capacity=len(positions))
                var r = len(positions) - 1
                while r >= 0:
                    rev.append(positions[r])
                    r -= 1
                return rev^
            return positions^
        if right:
            var p = hi - m
            while p >= lo:
                if self._match_at(pat, p):
                    out.append(p)
                p -= 1
        else:
            var p = lo
            while p + m <= hi:
                if self._match_at(pat, p):
                    out.append(p)
                p += 1
        return out^

    def search(self, sub: BitArray) raises -> List[Int]:
        """Start positions where `sub` occurs (ascending).

        Returns a materialized `List[Int]`: the reference yields a lazy
        iterator, which Mojo cannot express; the positions and order are
        otherwise identical.
        """
        return self.search(sub, 0, self.length, False)

    def search(self, sub: BitArray, start: Int, stop: Int) raises -> List[Int]:
        """Start positions with matches contained in `[start:stop)`."""
        return self.search(sub, start, stop, False)

    def search(
        self, sub: BitArray, start: Int, stop: Int, right: Bool
    ) raises -> List[Int]:
        """Start positions, descending when `right` is set (reference
        `right=True`). Bounds clamp like slices; `start > stop` matches
        nothing."""
        var bounds = self._simple_bounds(slice(start, stop))
        return self._search_from(sub, bounds[0], bounds[1], right)

    def search(self, v: Int) raises -> List[Int]:
        """Positions of the single bit `v` (reference accepts ints)."""
        _check_bit(v)
        return self.search(_one_bit(v, self.big_endian))

    def search(self, v: Int, start: Int, stop: Int) raises -> List[Int]:
        """Positions of `v` within `[start:stop)`."""
        _check_bit(v)
        return self.search(_one_bit(v, self.big_endian), start, stop)

    def search(
        self, v: Int, start: Int, stop: Int, right: Bool
    ) raises -> List[Int]:
        """Positions of `v` within `[start:stop)`, descending if `right`."""
        _check_bit(v)
        return self.search(_one_bit(v, self.big_endian), start, stop, right)

    def search(self, v: Bool) raises -> List[Int]:
        """Positions of `True` (1) or `False` (0) bits."""
        return self.search(1 if v else 0)

    def search(self, v: Bool, start: Int, stop: Int) raises -> List[Int]:
        """Positions of a boolean bit within `[start:stop)`."""
        return self.search(1 if v else 0, start, stop)

    def search(
        self, v: Bool, start: Int, stop: Int, right: Bool
    ) raises -> List[Int]:
        """Positions of a boolean bit within `[start:stop)`, descending
        if `right`."""
        return self.search(1 if v else 0, start, stop, right)

    # -- Phase 1D3: remaining sequence operations ----------------------------

    def reverse(mut self) raises:
        """Reverse the logical bit sequence in place.

        Pairwise swap of symmetric logical bits; no temporary buffer is
        allocated. Length, endianness, and padding are unaffected (empty
        and single-bit arrays are natural no-ops).
        """
        var i = 0
        var j = self.length - 1
        while i < j:
            var a = self.read_bit(i)
            var b = self.read_bit(j)
            if a == UInt8(1):
                self.set_bit(j)
            else:
                self.clear_bit(j)
            if b == UInt8(1):
                self.set_bit(i)
            else:
                self.clear_bit(i)
            i += 1
            j -= 1

    def fill(mut self) raises -> Int:
        """Pad with zeros to a byte boundary; return bits added."""
        return self.fill(8)

    def fill(mut self, m: Int) raises -> Int:
        """Append zeros until the length is a multiple of `m`; return the
        number of bits added (in `range(m)`).

        `m` must be a positive int (reference: `ValueError` otherwise).
        """
        if m <= 0:
            raise Error("m must be a positive integer")
        var add = (m - self.length % m) % m
        for _ in range(add):
            self.append(0)
        return add

    def copy(self) raises -> BitArray:
        """Independent copy with the same logical bits and endianness."""
        return BitArray(self.buffer.copy(), self.length, self.big_endian)

    def rotate(mut self) raises:
        """Rotate right by one position (reference default `k=1`)."""
        self.rotate(1)

    def rotate(mut self, k: Int) raises:
        """Rotate right by `k mod n` in place (negative `k` rotates left).

        Mojo `%` truncates toward zero, so negative counts use floored
        modulo explicitly. Empty arrays are a no-op (avoids div-by-zero);
        multiples of the length are identity.
        """
        var n = self.length
        if n == 0:
            return
        var r = ((k % n) + n) % n
        if r == 0:
            return
        var bits = self.tolist()
        var combo = List[Int](capacity=n)
        for i in range(n):
            combo.append(bits[(i - r + n) % n])
        var fresh = _pack_bits(combo, self.big_endian)
        self.buffer = fresh.buffer.copy()
        self.length = fresh.length

    def _find_first(
        self, pat: BitArray, lo: Int, hi: Int, right: Bool
    ) raises -> Int:
        """Lowest (or rightmost, if `right`) match start with `pat`
        contained in `[lo:hi)`; -1 when absent. An empty pattern matches
        `lo` (or `hi` when `right`); an empty window matches nothing."""
        var m = len(pat)
        if m == 0:
            if hi < lo:
                return -1
            return hi if right else lo
        if right:
            var p = hi - m
            while p >= lo:
                if self._match_at(pat, p):
                    return p
                p -= 1
            return -1
        var p = lo
        while p + m <= hi:
            if self._match_at(pat, p):
                return p
            p += 1
        return -1

    def find(self, sub: BitArray) raises -> Int:
        """Lowest index where `sub` occurs, or -1 when absent."""
        return self.find(sub, 0, self.length, False)

    def find(self, sub: BitArray, start: Int, stop: Int) raises -> Int:
        """Lowest match start with `sub` contained in `[start:stop)`."""
        return self.find(sub, start, stop, False)

    def find(
        self, sub: BitArray, start: Int, stop: Int, right: Bool
    ) raises -> Int:
        """Lowest (or rightmost, if `right`) match start, or -1."""
        var bounds = self._find_bounds(start, stop)
        return self._find_first(sub, bounds[0], bounds[1], right)

    def find(self, v: Int) raises -> Int:
        """Lowest index of the single bit `v`, or -1 when absent."""
        _check_bit(v)
        return self.find(_one_bit(v, self.big_endian))

    def find(self, v: Int, start: Int, stop: Int) raises -> Int:
        """Lowest index of `v` with the match in `[start:stop)`."""
        _check_bit(v)
        return self.find(_one_bit(v, self.big_endian), start, stop)

    def find(
        self, v: Int, start: Int, stop: Int, right: Bool
    ) raises -> Int:
        """Lowest (or rightmost) index of `v`, or -1 when absent."""
        _check_bit(v)
        return self.find(_one_bit(v, self.big_endian), start, stop, right)

    def find(self, v: Bool) raises -> Int:
        """Lowest index of a boolean bit, or -1 when absent."""
        return self.find(1 if v else 0)

    def find(self, v: Bool, start: Int, stop: Int) raises -> Int:
        """Lowest boolean-bit index with the match in `[start:stop)`."""
        return self.find(1 if v else 0, start, stop)

    def find(
        self, v: Bool, start: Int, stop: Int, right: Bool
    ) raises -> Int:
        """Lowest (or rightmost) boolean-bit index, or -1."""
        return self.find(1 if v else 0, start, stop, right)

    def index(self, sub: BitArray) raises -> Int:
        """Lowest index where `sub` occurs; `ValueError` when absent."""
        return self.index(sub, 0, self.length, False)

    def index(self, sub: BitArray, start: Int, stop: Int) raises -> Int:
        """Lowest match start in `[start:stop)`; `ValueError` if absent."""
        return self.index(sub, start, stop, False)

    def index(
        self, sub: BitArray, start: Int, stop: Int, right: Bool
    ) raises -> Int:
        """Lowest (or rightmost) match start; `ValueError` when absent,
        with the reference message `bitarray('<bits>') not in bitarray`."""
        var at = self.find(sub, start, stop, right)
        if at == -1:
            raise Error("bitarray('" + sub.to01() + "') not in bitarray")
        return at

    def _index_int(
        self, v: Int, start: Int, stop: Int, right: Bool
    ) raises -> Int:
        """Shared int-index core with the reference `<v> not in bitarray`
        message (distinct from the sub-bitarray message)."""
        _check_bit(v)
        var at = self.find(_one_bit(v, self.big_endian), start, stop, right)
        if at == -1:
            raise Error(String(v) + " not in bitarray")
        return at

    def index(self, v: Int) raises -> Int:
        """Lowest index of the single bit `v`; `ValueError` if absent."""
        return self._index_int(v, 0, self.length, False)

    def index(self, v: Int, start: Int, stop: Int) raises -> Int:
        """Lowest index of `v` in `[start:stop)`; `ValueError` if absent."""
        return self._index_int(v, start, stop, False)

    def index(
        self, v: Int, start: Int, stop: Int, right: Bool
    ) raises -> Int:
        """Lowest (or rightmost) index of `v`; `ValueError` when absent."""
        return self._index_int(v, start, stop, right)

    def _index_bool(
        self, v: Bool, start: Int, stop: Int, right: Bool
    ) raises -> Int:
        """Shared boolean-index core with the reference `True`/`False`
        spelling in the missing message."""
        var at = self.find(1 if v else 0, start, stop, right)
        if at == -1:
            raise Error(String(v) + " not in bitarray")
        return at

    def index(self, v: Bool) raises -> Int:
        """Lowest index of a boolean bit; `ValueError` if absent."""
        return self._index_bool(v, 0, self.length, False)

    def index(self, v: Bool, start: Int, stop: Int) raises -> Int:
        """Lowest boolean-bit index in `[start:stop)`; `ValueError` if absent."""
        return self._index_bool(v, start, stop, False)

    def index(
        self, v: Bool, start: Int, stop: Int, right: Bool
    ) raises -> Int:
        """Lowest (or rightmost) boolean-bit index; `ValueError` if absent."""
        return self._index_bool(v, start, stop, right)


def _check_bit(v: Int) raises:
    """Reject anything but 0/1 (reference: `ValueError`)."""
    if v != 0 and v != 1:
        raise Error("bit must be 0 or 1, got " + String(v))


def _popcount_byte(b: UInt8) -> UInt8:
    """SWAR population count of one byte (formulation validated against
    a nibble table on adversarial inputs in Phase 0). All intermediate
    values stay far below 255, so silent wraparound cannot occur."""
    var x = b - ((b >> UInt8(1)) & UInt8(0x55))
    x = (x & UInt8(0x33)) + ((x >> UInt8(2)) & UInt8(0x33))
    return (x + (x >> UInt8(4))) & UInt8(0x0F)


def _one_bit(v: Int, big_endian: Bool) raises -> BitArray:
    """Single-bit pattern array (endianness is irrelevant to logical
    matching, but the constructor requires a flag)."""
    var bits = List[Int](capacity=1)
    bits.append(v)
    return _pack_bits(bits, big_endian)


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
