# Reference audit: `Levenshtein` 0.27.5 (+ `rapidfuzz` 3.14.6)

Pinned references: `Levenshtein==0.27.5` (import name `Levenshtein`,
distribution name lowercase `levenshtein`, Python ≥3.11,
`License-Expression: GPL-2.0-or-later`) and its dependency
`rapidfuzz==3.14.6` (`License-Expression: MIT`).
Raw probe output: `../experiments/reference_probe_output.txt`,
`../experiments/edge_cases_output.txt`.

## 1. Wrapper structure (verified)

`Levenshtein/__init__.py` is a thin wrapper. These functions delegate to
`rapidfuzz.distance` and return identical results on every probed input:

| `Levenshtein` name | delegates to |
|---|---|
| `distance` | `rapidfuzz.distance.Levenshtein.distance` |
| `ratio` | `rapidfuzz.distance.Indel.normalized_similarity` |
| `hamming` | `rapidfuzz.distance.Hamming.distance` |
| `jaro` | `rapidfuzz.distance.Jaro.similarity` |
| `jaro_winkler` | `rapidfuzz.distance.JaroWinkler.similarity` |
| `editops` | `rapidfuzz.distance.Levenshtein.editops` |
| `opcodes` | `rapidfuzz.distance.Levenshtein.opcodes` |
| `matching_blocks` | `rapidfuzz.distance.Opcodes.matching_blocks` |
| `apply_edit`, `subtract_edit`, `inverse` | same-named `rapidfuzz` helpers |

Only `median`, `median_improve`, `quickmedian`, `setmedian`, `seqratio`,
`setratio` come from the compiled `Levenshtein.levenshtein_cpp` module.
(The function objects are distinct: `Levenshtein.distance is
RFLev.distance` is `False`, but results agreed on a 403-pair deterministic
corpus including weighted, Unicode, and empty cases.)

`StringMatcher` is **not** in `__all__` and is not exported by
`__init__` — `hasattr(Levenshtein, "StringMatcher")` is `False` on a fresh
import. Importing `Levenshtein.StringMatcher` as a submodule sets the
attribute as a side effect. It warns that `isjunk`/`autojunk` are
unimplemented. Out of scope for v0.1.

## 2. `distance`

Signature: `distance(s1, s2, *, weights=(1, 1, 1), processor=None,
score_cutoff=None, score_hint=None)`.

- Unit weights `(1, 1, 1)`: classic Levenshtein (insert/delete/substitute
  each cost 1). `distance("kitten", "sitting") == 3`.
- Weighted costs `weights=(1, 1, 2)` on the doc example
  `("lewenstein", "levenshtein")` gives `3` (matches the docstring).
- `weights` accepts `None` (means default), zero costs, and floats (e.g.
  `(1.5, 1, 1)`), but these are degenerate: all-zero weights return `0`
  for any pair, negative weights raise `OverflowError` in C++ while the
  pure-Python fallback silently returns `0`. Malformed tuples raise
  `ValueError`. **Recommendation: v0.1 accepts positive-integer weights
  only and rejects everything else.**
- `score_cutoff` (int) truncates: returns `min(distance, score_cutoff +
  1)`. Verified: actual 3 with cutoff 1 → 2, cutoff 2 → 3, cutoff 4 → 3.
  Non-integer cutoffs are coerced (`0.5` behaves like `0`). Negative
  cutoff raises `OverflowError`. **Recommendation: v0.1 accepts
  non-negative `int` cutoffs only.**
- `score_hint` accepts any int and never changes the result (verified
  `score_hint=100`); it is a performance hint for implementation choice.
- Symmetry holds on all probed pairs.

## 3. `ratio` — the critical finding

`Levenshtein.ratio` is **not** derived from Levenshtein distance. It is
`Indel.normalized_similarity`, i.e. `1 - indel_distance / (len1 + len2)`
where `indel_distance = len1 + len2 - 2 * LCS`. Decisive probe:

- `ratio("abc", "adc") == 0.6666666666666667` (indel 2 over total 6),
  not `0.8333` (which a Levenshtein-distance normalization would give).
- `ratio("kitten", "sitting") == 0.6153846153846154` (indel 5 over 13).
- Empty/empty → `1.0`; one side empty → `0.0`.

`normalized_distance` / `normalized_similarity` **do not exist** on the
`Levenshtein` module (`hasattr` → `False`; direct call raises
`AttributeError`). They exist only as `rapidfuzz.distance.*` class APIs.
`ratio` is the only normalized similarity the reference package exposes,
and it is Indel-based. Do not add Levenshtein-normalized variants.

`score_cutoff` semantics for `ratio` are coarse: the C++ layer converts
the float cutoff to a distance threshold in **float32**, so the
pass/fail boundary differs from exact float comparison and from the
pure-Python fallback (probe: C++ fails at cutoff `0.66666666`,
pure-Python passes until cutoff exceeds the true score). Exact equality
(`1.0` with cutoff `1.0`) returns the score. **Recommendation: defer
`score_cutoff` for `ratio` to Phase 2; treat cutoffs as untestable
performance hints, not exact API.**

## 4. `hamming`

Signature: `hamming(s1, s2, *, pad=True, processor=None,
score_cutoff=None)`. Counts substitutions; `pad=True` charges the length
difference (so `hamming("abc", "ab", pad=True) == 1`); `pad=False` with
unequal lengths raises `ValueError: Sequences are not the same length.`
`score_cutoff` truncates like `distance` (cutoff 0 with distance 1 → 1).

## 5. `jaro` and `jaro_winkler`

Standard Jaro similarity on code points; window
`max(0, max(len1, len2)//2 - 1)` confirmed by `jaro("abc", "bca") == 0.0`
and `jaro("ab", "ba") == 0.0`. Known values hold:
`jaro("MARTHA", "MARHTA") == 0.9444444444444445`,
`jaro("DIXON", "DICKSONX") == 0.7666666666666666`,
`jaro("", "") == 1.0`, `jaro("", "a") == 0.0`.

Jaro-Winkler: `jw = jaro + prefix_len * prefix_weight * (1 - jaro)` with
common-prefix length capped at 4 — confirmed:
`0.9444444444444445 + 3*0.1*(1-0.9444444444444445) ==
0.9611111111111111`. But `prefix_weight` is validated against **0.0–1.0**,
not the documented 0.0–0.25: `0.2501` is accepted, `0.5` returns `1.0` for
the MARTHA pair, `1.0001`/`-0.0001` raise `ValueError`. **Recommendation:
defer Jaro-Winkler (and Jaro) to Phase 2; the weight-range documentation
bug must be resolved first.**

## 6. Edit operations (deferred, audited for risk)

`editops` returns opcodes as plain 3-tuples
`('replace'|'insert'|'delete', src_pos, dest_pos)`; `opcodes` returns
5-tuples with `equal` spans. Tie-breaking is implementation-specific:
`'ab' -> 'ba'` yields `insert(0,0), delete(1,2)` (not delete+insert).
`matching_blocks` returns `MatchingBlock` objects (a C++ type that is
tuple-equal and indexable but **not** a tuple: `isinstance(block, tuple)`
is `False`), always terminated by a zero-size sentinel block (e.g.
`matching_blocks([], "abc", "abc")` → full block + sentinel). Wrong-arity
calls are **silently accepted** (`matching_blocks` on a single replace op
returns a zero block, no error). Byte-for-byte parity with this family
requires matching the exact C++ tie-breaking — defer to Phase 2+.

`inverse` / `apply_edit` / `subtract_edit` round-trip correctly
(`apply_edit(editops, s1, s2) == s2`); they are mechanically derivable
once `editops` is pinned, so they inherit its deferral.

## 7. Median family (deferred, audited for risk)

`median([...8 variants...]) == "Levenshtein"`,
`quickmedian` gives `"Levnshein"`, `setmedian` gives `"Levnhtein"`,
`median_improve("spam", fixme) == "enhtein"`. Notes: `median([]) == ""`
(no error); accepts and mixes `bytes` (returns `str`); non-string items
raise `TypeError`; `seqratio([], []) == setratio([], []) == 1.0`. These
solve the generalized-median problem (NP-hard, heuristic), a different
problem from pairwise distance — defer.

## 8. Input types (verified coercion hazards)

The reference accepts `str`, `bytes`, `bytearray`, `memoryview`, lists,
tuples, and ranges of hashables — but coerces per element in ways that
are **not** principled:

- `distance("abc", b"abc") == 0` but `distance("é", "é".encode()) == 2`:
  `str` is compared by code point, `bytes` by byte value.
- `distance(["a"], [97]) == 0`: single-char strings are coerced to their
  code points, so element types silently mix.
- Generators raise `TypeError` (no `len`); dicts raise `KeyError: 0`;
  `None`/ints raise `TypeError`.

**Recommendation: v0.1 accepts Unicode `str` only and rejects everything
else. The coercion behavior is unspecified, version-sensitive, and
unsafe to promise parity with.**

## 9. Pure-Python fallback (benchmark path)

`rapidfuzz.distance.{Levenshtein,Indel,Jaro,JaroWinkler,Hamming}_py` are
pure-Python implementations that agree with C++ on the full 403-pair
corpus (unit and integer-weighted distance, ratio, hamming-pad, Jaro,
Jaro-Winkler). Internally, unit-cost `Levenshtein_py.distance` is Myers
bit-parallel over Python big ints (`_uniform_distance`), weighted costs
fall back to O(n²) DP (`_uniform_generic`); `Indel_py` goes through
`LCSseq_py`. Two known divergences: negative weights return `0` instead
of raising, and `ratio` cutoffs use exact float comparison instead of
the C++ float32 conversion. Neither affects cutoff-free exact values.
These modules are the honest "optimized native Python" benchmark path.

## 10. License decision (recorded)

- Oracle choice: use **`rapidfuzz==3.14.6` (MIT)** as the compatibility
  oracle and benchmark reference. Do **not** depend on the
  `Levenshtein==0.27.5` package (GPL-2.0-or-later); its behavior is
  covered because every probed `Levenshtein.*` result equals the
  corresponding `rapidfuzz.distance.*` result.
- Per `THIRD_PARTY_NOTICES.md`, no GPL code is distributed, linked, or
  incorporated; the GPL package was installed ephemerally in `.venv`
  for black-box observation only and must not enter
  `pyproject.toml` / `requirements` / committed code or vectors.
