"""Phase 0 Mojo 1.2.0 probe: 64-bit word operations for packed bits.

Verifies: UInt64 and/or/xor/not, guarded shifts (never shifting by
>= width — full-width shifts are target-dependent, see below),
SWAR population count vs a nibble table, partial-word masking
(equivalent of the reference `zlc`/`zlw` zeroed-tail helpers), and
multi-word carry-free composition.

Run with::

    .venv/bin/mojo run experiments/toolchain_validation/bitarray/words.mojo
"""

from std.collections import List
from std.testing import assert_equal


def shl_guarded(x: UInt64, amount: Int) -> UInt64:
    """Left shift valid only for 0 <= amount < 64 (guarded by contract)."""
    if amount < 0 or amount >= 64:
        # Mirrors the reference discipline: shifts at/above the width
        # are undefined behaviour, so callers must branch instead.
        return 0
    return x << UInt64(amount)


def shr_guarded(x: UInt64, amount: Int) -> UInt64:
    """Right shift valid only for 0 <= amount < 64 (guarded by contract)."""
    if amount < 0 or amount >= 64:
        return 0
    return x >> UInt64(amount)


def popcount_swar(x: UInt64) -> Int:
    """Population count via SWAR (no builtin in Mojo 1.2.0's std)."""
    var v = x - ((x >> 1) & UInt64(0x5555555555555555))
    v = (v & UInt64(0x3333333333333333)) + ((v >> 2) & UInt64(0x3333333333333333))
    v = (v + (v >> 4)) & UInt64(0x0F0F0F0F0F0F0F0F)
    return Int((v * UInt64(0x0101010101010101)) >> 56)


def nibble_table() -> List[Int]:
    var table = List[Int](capacity=16)
    for i in range(16):
        var count = 0
        var v = i
        while v != 0:
            count += v & 1
            v >>= 1
        table.append(count)
    return table^


def popcount_table(x: UInt64, table: List[Int]) -> Int:
    var total = 0
    var v = x
    for _ in range(16):
        total += table[Int(v & UInt64(0xF))]
        v >>= 4
    return total


def mask_low_bits(n: Int) -> UInt64:
    """Mask with the low n bits set (0 <= n <= 64), no width-edge shift."""
    if n <= 0:
        return UInt64(0)
    if n >= 64:
        return UInt64.MAX
    return (UInt64(1) << UInt64(n)) - UInt64(1)


def main() raises:
    # Bitwise primitives on full words.
    assert_equal(UInt64(0xF0F0) & UInt64(0x0FF0), UInt64(0x00F0))
    assert_equal(UInt64(0xF0F0) | UInt64(0x0FF0), UInt64(0xFFF0))
    assert_equal(UInt64(0xF0F0) ^ UInt64(0xFFFF), UInt64(0x0F0F))
    assert_equal(~UInt64(0), UInt64.MAX)
    assert_equal(UInt64(0xFF) & UInt64(0x0F), UInt64(0x0F))
    print("PASS and/or/xor/not match C truth tables")

    # Guarded shifts at and around the word boundary.
    assert_equal(shl_guarded(UInt64(1), 0), UInt64(1))
    assert_equal(shl_guarded(UInt64(1), 63), UInt64(1) << UInt64(63))
    assert_equal(shl_guarded(UInt64(1), 64), UInt64(0))
    assert_equal(shl_guarded(UInt64(1), 100), UInt64(0))
    assert_equal(shr_guarded(UInt64.MAX, 63), UInt64(1))
    assert_equal(shr_guarded(UInt64.MAX, 64), UInt64(0))
    assert_equal(shr_guarded(UInt64(0xFF), 4), UInt64(0x0F))
    print("PASS guarded shifts: sub-width exact, width+ saturates to 0")

    # Runtime (non-constant) full-width shifts are target-defined, so
    # the guard above is load-bearing, not stylistic.
    var runtime_amount = 64
    var probe = List[UInt64]()
    probe.append(UInt64(runtime_amount))
    var folded = UInt64(1) << probe[0]
    print("INFO runtime 1<<64 folds to:", folded, "(target-defined; must never be relied on)")

    # SWAR popcount agrees with a nibble table on adversarial inputs.
    var table = nibble_table()
    var patterns = List[UInt64]()
    patterns.append(UInt64(0))
    patterns.append(UInt64.MAX)
    patterns.append(UInt64(0xAAAAAAAAAAAAAAAA))
    patterns.append(UInt64(0x5555555555555555))
    patterns.append(UInt64(0x8000000000000001))
    patterns.append(UInt64(0x0F0F0F0F0F0F0F0F))
    for i in range(len(patterns)):
        assert_equal(popcount_swar(patterns[i]), popcount_table(patterns[i], table))
    assert_equal(popcount_swar(UInt64.MAX), 64)
    assert_equal(popcount_swar(UInt64(0)), 0)
    print("PASS SWAR popcount matches nibble-table popcount")

    # Partial-word masks (reference zlc/zlw equivalents).
    assert_equal(mask_low_bits(0), UInt64(0))
    assert_equal(mask_low_bits(1), UInt64(1))
    assert_equal(mask_low_bits(7), UInt64(0x7F))
    assert_equal(mask_low_bits(8), UInt64(0xFF))
    assert_equal(mask_low_bits(63), UInt64(0x7FFFFFFFFFFFFFFF))
    assert_equal(mask_low_bits(64), UInt64.MAX)
    assert_equal(mask_low_bits(100), UInt64.MAX)
    assert_equal(mask_low_bits(-3), UInt64(0))
    # Zeroed-tail load: partial final word OR masked tail.
    var tail = UInt64(0xFF) | ~mask_low_bits(5)
    assert_equal(tail & mask_low_bits(5), UInt64(0x1F))
    print("PASS masks cover 0..64+ without width-edge shifts")

    # Multi-word composition: 65-bit all-ones has popcount 65.
    var words = List[UInt64]()
    words.append(UInt64.MAX)
    words.append(UInt64(1))
    var total = 0
    for i in range(len(words)):
        total += popcount_swar(words[i])
    assert_equal(total, 65)
    # And with the last word masked to 1 valid bit.
    words[1] = words[1] & mask_low_bits(1)
    total = 0
    for i in range(len(words)):
        total += popcount_swar(words[i])
    assert_equal(total, 64 + 1)
    print("PASS multi-word popcount composes across words")

    print("words: all checks passed")
