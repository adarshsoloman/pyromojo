"""Blocked bit-parallel longest-common-subsequence length.

Bit-vector LCS (Hunt–Szymanski formulation): with ``S[c]`` the bitmask
of pattern positions holding code point ``c``,

    U = S[c] | D;  D = (D << 1) | 1;  D = U & ~(U - D)

applied per text character, the final ``popcount(D)`` is the LCS
length. Extended here to arbitrary pattern lengths with one ``UInt64``
word per 64 code points:

- the ``U - D`` subtraction borrows across words (multiword subtract
  with an explicit 0/1 borrow, since Mojo wraps silently);
- the ``D << 1`` shift carries the ejected top bit into the next word,
  with ``1`` injected at bit 0 of word 0;
- bits past the pattern end stay zero (``S[c]`` has zeros there and
  the update preserves that), so a plain popcount over all words is
  exact — no mask needed.

Guards (same discipline as ``myers.mojo``): no shift amount ever
reaches the bit width (amounts are ``i % 64``, ``1``, or ``63``),
and ``VP``-style initialization is all-ones-free by construction
(``D`` starts at zero).

The caller passes the shorter sequence as the pattern to minimize the
word count; the result is order-independent.
"""

from std.collections import Dict, List


def _popcount64(x: UInt64) -> Int:
    """Population count via SWAR; branchless, no width-edge shifts."""
    var v = x - ((x >> 1) & UInt64(0x5555555555555555))
    v = (v & UInt64(0x3333333333333333)) + ((v >> 2) & UInt64(0x3333333333333333))
    v = (v + (v >> 4)) & UInt64(0x0F0F0F0F0F0F0F0F)
    return Int((v * UInt64(0x0101010101010101)) >> 56)


def lcs_bitparallel(a: List[Int], b: List[Int]) raises -> Int:
    """LCS length over code-point sequences via blocked bit-parallelism.

    ``a`` is the bit-vector pattern (the shorter input); ``b`` is the
    text. Handles empty inputs, word boundaries (64, 128), and
    multiword patterns. Marked ``raises`` for the ``Dict`` lookups in
    the Peq table; every input pair has a defined result that fits in
    ``Int``.
    """
    var m = len(a)
    var n = len(b)
    if m == 0 or n == 0:
        return 0

    var words = (m + 63) // 64
    var peq = Dict[Int, List[UInt64]]()
    for i in range(m):
        var code = a[i]
        if code not in peq:
            var zeros = List[UInt64](capacity=words)
            for _ in range(words):
                zeros.append(0)
            peq[code] = zeros^
        peq[code][i // 64] |= UInt64(1) << UInt64(i % 64)

    var d = List[UInt64](capacity=words)
    for _ in range(words):
        d.append(0)

    for j in range(n):
        var known = b[j] in peq
        var borrow = UInt64(0)
        var shift_carry = UInt64(1)
        for k in range(words):
            var pm = UInt64(0)
            if known:
                pm = peq[b[j]][k]
            var u = pm | d[k]
            var shifted = (d[k] << 1) | shift_carry
            shift_carry = d[k] >> 63
            var t = shifted + borrow
            var b1 = UInt64(1) if t < shifted else UInt64(0)
            var sub = u - t
            var b2 = UInt64(1) if sub > u else UInt64(0)
            borrow = b1 | b2
            d[k] = u & ~sub

    var total = 0
    for k in range(words):
        total += _popcount64(d[k])
    return total
