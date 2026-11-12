"""Public Hamming distance over Unicode strings.

Counts substitutions between equal-length code-point sequences. With
``pad=True`` (the default) the length difference is charged, matching
the reference; with ``pad=False`` unequal lengths raise, using the
reference message verbatim.
"""


def levenshtein_hamming(s1: String, s2: String, pad: Bool = True) raises -> Int:
    """Hamming distance between two strings.

    Raises ``Sequences are not the same length.`` when the code-point
    counts differ and ``pad`` is false. No cutoff support in v0.1.

    Compares code points in a single lockstep pass without
    materializing either string (no temporary arrays); lengths come
    from ``len(s.codepoints())`` up front.
    """
    var n1 = len(s1.codepoints())
    var n2 = len(s2.codepoints())
    if n1 != n2 and not pad:
        raise Error("Sequences are not the same length.")
    var edits = n1 - n2
    if edits < 0:
        edits = 0 - edits
    for c1, c2 in zip(s1.codepoints(), s2.codepoints()):
        if c1 != c2:
            edits += 1
    return edits
