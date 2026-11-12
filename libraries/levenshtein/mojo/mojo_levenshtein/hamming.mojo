"""Public Hamming distance over Unicode strings.

Counts substitutions between equal-length code-point sequences. With
``pad=True`` (the default) the length difference is charged, matching
the reference; with ``pad=False`` unequal lengths raise, using the
reference message verbatim.
"""

from mojo_levenshtein.unicode import to_codepoints


def levenshtein_hamming(s1: String, s2: String, pad: Bool = True) raises -> Int:
    """Hamming distance between two strings.

    Raises ``Sequences are not the same length.`` when the code-point
    counts differ and ``pad`` is false. No cutoff support in v0.1.
    """
    var a = to_codepoints(s1)
    var b = to_codepoints(s2)
    var short_count = len(a)
    var long_count = len(b)
    if short_count > long_count:
        short_count = len(b)
        long_count = len(a)
    if len(a) != len(b) and not pad:
        raise Error("Sequences are not the same length.")
    var edits = long_count - short_count
    for i in range(short_count):
        if a[i] != b[i]:
            edits += 1
    return edits
