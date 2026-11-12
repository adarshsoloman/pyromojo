# Unicode semantics

Unit of comparison: one **Unicode code point** (= one Python `str`
element). Verified by probe (`../experiments/reference_probe_output.txt`).

## Verified behaviors

| case | `len` | `distance` | `ratio` | reading |
|---|---|---|---|---|
| `"é"` vs `"e"` | 1 / 1 | 1 | 0.0 | precomposed é ≠ e |
| `"é"` vs `"e\u0301"` | 1 / 2 | 2 | 0.0 | **no normalization**; NFC ≠ NFD |
| `"😀"` vs `""` | 1 / 0 | 1 | 0.0 | astral char is one unit |
| `"😀"` vs `"😃"` | 1 / 1 | 1 | 0.0 | one substitution |
| `"👩‍👩‍👧‍👦"` vs `""` | 7 / 0 | 7 | 0.0 | ZWJ family = 7 code points, not 1 grapheme |
| `"a😀b"` vs `"ab"` | 3 / 2 | 1 | 0.8 | one insertion |
| `"naïve"` vs `"naive"` | 5 / 5 | 1 | 0.8 | ï ≠ i, one substitution |
| `"straße"` vs `"strasse"` | 6 / 7 | 2 | 0.769… | ß→ss is delete+insert through code points |
| `"æ"` vs `"ae"` | 1 / 2 | 2 | 0.0 | no compatibility decomposition |

`ratio("é", "e") == 0.0` proves lengths and distances are counted in code
points, not UTF-8 bytes (byte lengths are 2 and 1, which would give a
nonzero score under byte semantics).

## Consequences for the Mojo port

- Mojo `String` is UTF-8 with explicit iteration views: `s.codepoints()`
  (matches the reference unit), `s.graphemes()` (does **not** match —
  family emoji is 1 grapheme vs 7 code points), `s.as_bytes()` (does not
  match). The port must materialize `List[Int]` code points (probe:
  `../experiments/mojo_dp_probe.mojo`).
- Mojo has no normalization API in scope and must not add one: the
  reference does not normalize, so NFC/NFD pairs stay unequal.
- Slicing must use `s[codepoint=a:b]`; byte slicing and bare `s[a:b]`
  (rejected by the compiler) have different units. Indexing
  `CodepointsIter` is unsupported — materialize first.

## Documented deviations (v0.1)

1. **Lone surrogates**: Python `"\ud800"` is a one-element `str` and
   `distance("\ud800", "") == 1`. Mojo `String` requires valid UTF-8 and
   rejects surrogate byte sequences (`String(from_utf8=...)` raises
   `Cannot construct a String from invalid UTF-8 data`), so lone
   surrogates are unrepresentable. v0.1 rejects them; surfaced as a
   validation error, not silent coercion.
2. **Non-UTF-8 bytes**: the reference accepts `bytes`/`bytearray` and
   compares byte values (with the code-point/byte mixing hazard documented
   in `reference-audit.md` §8). v0.1 accepts `str` only.
3. **Grapheme clusters**: no grapheme API is ported; callers needing
   user-perceived characters must segment before calling. The reference
   itself is code-point based, so this is parity, not a gap.
