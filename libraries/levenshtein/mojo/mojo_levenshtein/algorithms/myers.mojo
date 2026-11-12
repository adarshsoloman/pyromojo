"""Blocked Myers bit-parallel Levenshtein distance (unit costs).

Extends the verified single-word probes (``experiments/mojo_myers_probe.mojo``,
``experiments/mojo_myers128_probe.mojo``) to arbitrary pattern lengths with
one ``UInt64`` word per 64 code points, following Myers' block formulation:

- the ``(X & VP) + VP`` addition carries across words (multiword add with
  an explicit 0/1 carry, since Mojo wraps silently);
- the ``HP``/``HN`` shifts carry the ejected top bit into the next word,
  with ``1`` injected at bit 0 of word 0;
- the score is read from the mask bit of the last word only.

Guards (Phase 0, ``docs/mojo-probes.md``): no shift amount ever reaches
the bit width (amounts are ``i % 64`` or the constant ``1``), and ``VP``
is initialized to all-ones directly instead of via ``(1 << n) - 1``.
``mask`` uses ``(m - 1) % 64``, which is in ``0..63`` for every ``m >= 1``.

The caller passes the shorter sequence as the pattern to minimize the
word count; the result is order-independent (distance is symmetric).
"""

from std.collections import Dict, List


def myers_distance(a: List[Int], b: List[Int]) raises -> Int:
    """Unit-cost Levenshtein distance over code-point sequences.

    ``a`` is the bit-vector pattern (the shorter input); ``b`` is the
    text. Handles empty inputs, word boundaries (64, 128), and
    multiword patterns. Marked ``raises`` for the ``Dict`` lookups in
    the Peq table; every input pair has a defined distance that fits
    in ``Int``.
    """
    var m = len(a)
    var n = len(b)
    if m == 0 or n == 0:
        return m + n

    var words = (m + 63) // 64
    var last = words - 1
    var mask = UInt64(1) << UInt64((m - 1) % 64)

    var peq = Dict[Int, List[UInt64]]()
    for i in range(m):
        var code = a[i]
        if code not in peq:
            var zeros = List[UInt64](capacity=words)
            for _ in range(words):
                zeros.append(0)
            peq[code] = zeros^
        peq[code][i // 64] |= UInt64(1) << UInt64(i % 64)

    var vp = List[UInt64](capacity=words)
    var vn = List[UInt64](capacity=words)
    for _ in range(words):
        vp.append(UInt64.MAX)
        vn.append(0)

    var score = m
    for j in range(n):
        var text_code = b[j]
        var known = text_code in peq
        var add_carry = UInt64(0)
        var hp_carry = UInt64(1)
        var hn_carry = UInt64(0)
        for k in range(words):
            var pm = UInt64(0)
            if known:
                pm = peq[text_code][k]
            var x = pm & vp[k]
            var total = x + vp[k]
            var carry = UInt64(1) if total < x else UInt64(0)
            total = total + add_carry
            if total < add_carry and add_carry != 0:
                carry = UInt64(1)
            add_carry = carry
            var d0 = (total ^ vp[k]) | pm | vn[k]
            var hp = vn[k] | ~(d0 | vp[k])
            var hn = d0 & vp[k]
            if k == last:
                if hp & mask != 0:
                    score += 1
                if hn & mask != 0:
                    score -= 1
            var hp_out = hp >> 63
            var hn_out = hn >> 63
            hp = (hp << 1) | hp_carry
            hn = (hn << 1) | hn_carry
            hp_carry = hp_out
            hn_carry = hn_out
            vp[k] = hn | ~(d0 | hp)
            vn[k] = hp & d0

    return score
