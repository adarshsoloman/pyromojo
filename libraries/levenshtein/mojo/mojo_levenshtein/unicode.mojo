"""Code-point handling for the Levenshtein port.

The reference counts one Unicode code point per Python ``str`` element
(Phase 0: ``docs/unicode-semantics.md``). This module materializes that
unit: ``to_codepoints`` converts a Mojo ``String`` (always valid UTF-8)
into one ``Int`` per code point. No normalization is applied, matching
the reference. Grapheme clusters and UTF-8 bytes are the wrong unit and
are not used here.
"""

from std.collections import List


def to_codepoints(text: String) -> List[Int]:
    """Return one integer per Unicode code point in ``text``."""
    var out = List[Int](capacity=text.byte_length())
    for cp in text.codepoints():
        out.append(Int(cp))
    return out^
