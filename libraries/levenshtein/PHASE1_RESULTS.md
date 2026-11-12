# Levenshtein — Phase 1 results

Status: core v0.1 implementation complete. All verification below was
executed; nothing is reported as passed without a run. No production
benchmarks were built and no performance claims are made.

Toolchain: Mojo 1.2.0 (2016d0cd), Python 3.13.14, oracle
`rapidfuzz==3.14.6` (MIT). The GPL `Levenshtein` package was never
imported or depended on.

## 1. Files created and modified

Created under `libraries/levenshtein/`:

- `mojo/mojo_levenshtein/__init__.mojo` — public re-exports.
- `mojo/mojo_levenshtein/unicode.mojo` — `to_codepoints`.
- `mojo/mojo_levenshtein/distance.mojo` — public distance + cutoff.
- `mojo/mojo_levenshtein/ratio.mojo` — public ratio.
- `mojo/mojo_levenshtein/hamming.mojo` — public hamming.
- `mojo/mojo_levenshtein/protocol.mojo` — framed protocol (framing
  design copied from MessagePack, decoupled from it; extended with u64
  and float64-bit helpers and Levenshtein opcodes).
- `mojo/mojo_levenshtein/algorithms/__init__.mojo` — oracle re-exports.
- `mojo/mojo_levenshtein/algorithms/dynamic_programming.mojo` — DP.
- `mojo/mojo_levenshtein/algorithms/myers.mojo` — blocked Myers.
- `mojo/cli.mojo` — batch CLI over stdin/stdout.
- `tests/mojo/test_support.mojo` — seeded LCG + string builders.
- `tests/mojo/test_distance.mojo`, `test_ratio.mojo`,
  `test_hamming.mojo`, `test_myers_parity.mojo`, `test_guards.mojo`,
  `test_generated_vectors.mojo` — native suites.
- `tests/mojo/generated_vectors.mojo` — generated typed goldens.
- `tests/vectors/levenshtein_vectors.json` — 434 golden cases.
- `tests/python_compat/conftest.py`, `test_cli.py`,
  `test_golden_vectors.py`, `test_oracle_assumptions.py`,
  `test_randomized_properties.py` — Python compat suite.
- `python_reference/generate_vectors.py` — deterministic generator
  with `--check` drift gate.
- `python_reference/requirements.txt` — `rapidfuzz==3.14.6`.

Modified: `scripts/run_all_tests.py` (suite table now covers both
libraries; msgpack entries byte-identical in behavior),
`scripts/check_compatibility.py` (`levenshtein` library added),
`pyproject.toml` (`rapidfuzz==3.14.6` in dev dependency-group,
mirroring the `msgpack==1.2.4` precedent),
`libraries/levenshtein/README.md` (status + scope + results).

`build/` scratch files were removed; `build/` is gitignored.
Test files use unique basenames (`test_cli.py`, …) because pytest
collects both libraries' `tests/python_compat/` dirs into one run and
duplicate basenames collide without `__init__.py` packages — a
deliberate deviation from the msgpack filenames, not a behavior change.

## 2. Public APIs implemented

Exactly the three approved operations, `str`-in, code-point semantics:

- `levenshtein_distance(s1, s2, insertion=1, deletion=1,
  substitution=1) -> Int` — unit weights dispatch to blocked Myers
  (shorter input as pattern); other positive-integer weights use DP.
  Zero/negative weights raise; the `(len1+len2) * max_weight` product
  is validated against `Int.MAX` before any accumulation.
- `levenshtein_distance_cutoff(s1, s2, score_cutoff, ...) -> Int` —
  exact `min(distance, cutoff + 1)`; negative cutoffs raise. The `+ 1`
  provably cannot overflow (computed only when the true distance, which
  fits in `Int`, exceeds the cutoff).
- `levenshtein_ratio(s1, s2) -> Float64` — Indel normalized similarity,
  `1 - (len1 + len2 - 2·LCS) / (len1 + len2)`; empty/empty → 1.0.
- `levenshtein_hamming(s1, s2, pad=True) -> Int` — substitution count
  plus length difference when padding; unequal lengths with
  `pad=False` raise `"Sequences are not the same length."`
  (reference message verbatim).

Core entry points kept independent of transport:
`to_codepoints`, `dp_distance`, `dp_lcs_length`, `myers_distance`.

## 3. DP implementation details

Two-row rolling DP over `List[Int]` code points, `Int` accumulators.
`dp_distance` validates each weight (`> 0`) and the overflow bound
up front, so no cell can wrap; empty inputs short-circuit to
`m * insertion` / `n * deletion` (verified against the oracle:
6, 3, 0 for `(2,1,1)` on `""`/`"abc"`). `dp_lcs_length` needs no
bounds (result ≤ min length). The DP stays a first-class tested
oracle: `test_myers_parity` (450 randomized + boundary pairs) and
`test_generated_vectors` (all 434 goldens) assert it on every input
the optimized path takes.

## 4. Myers implementation details

Blocked bit-parallel Myers over `UInt64` words, one word per 64 code
points, `Dict[Int, List[UInt64]]` Peq table:

- multiword add carry (`x + VP + carry_in` with explicit 0/1 carry),
  since Mojo wraps silently and offers no carry flag;
- HP/HN shifts carry the ejected top bit into the next word, with `1`
  injected at bit 0 of word 0;
- score read from the mask bit of the last word only, where
  `mask = 1 << ((m - 1) % 64)`;
- **no shift ever reaches the bit width** (amounts are `i % 64` or the
  constant `1`); `VP` initializes to all-ones directly — the Phase 0
  `n == 128` failure mode is structurally impossible, and
  `test_guards` pins the exact-boundary shapes through the public API;
- the public layer passes the shorter string as pattern (order-free
  result; symmetry is tested).

`myers_distance` is marked `raises` for the `Dict` lookups the type
system cannot prove safe; every input pair has a defined result.

## 5. Unicode handling

`to_codepoints` materializes one `Int` per code point
(`~3.6 µs` for 2048 code points, negligible). No normalization anywhere:
NFC é vs NFD `e`+U+0301 is distance 2 (pinned in goldens and native
tests). `graphemes()` and byte views are never used. Rejections are
explicit errors, never coercion: invalid UTF-8 frames fail at the CLI
(`String(from_utf8=...)` raises), lone surrogates and raw bytes are
unrepresentable by construction (documented in
`docs/unicode-semantics.md`).

## 6. Reference compatibility results

- 434/434 golden vectors pass natively (exact `Int`, bit-exact
  `Float64`), covering ASCII, accents, emoji, astral, NFD, ZWJ, CJK,
  word boundaries 63–256, multiword, uniform/repeated/all-diff,
  lengths to 2048, weights, cutoffs, and error cases.
- 432/434 pass through the CLI; the 2 skips (`weights_negative`,
  `cutoff_negative`) are u64-inencodable and covered natively, with
  the skip set asserted exact.
- 205 fresh randomized CLI pairs (unit/weighted distance, ratio,
  hamming, pad errors, symmetry, truncation bounds) agree exactly.
- Oracle assumptions pinned directly against rapidfuzz (10 tests),
  including the decisive `ratio("abc","adc") == 0.6666666666666667`
  and the bit-exact `1 - dist/total` formula on a 300-pair corpus.

## 7. Golden vector count

434 cases: 241 distance (fixed, unicode, 5 pairs × 6 weight sets,
cutoffs, 3 error cases), 163 ratio, 30 hamming (incl. 2 pad errors).
Deterministic (`SEED = 20260202`); `--check` drift-gated in
`run_all_tests.py`; committed JSON + generated Mojo module verified
current.

## 8. Native Mojo test results

6 suites, 25 tests, all pass (`build/levenshtein_*`, wall-clock):

- `test_distance` 8, `test_ratio` 3, `test_hamming` 4,
  `test_myers_parity` 5 (450 DP-vs-Myers pairs),
  `test_guards` 4, `test_generated_vectors` 1 (434 goldens).

Note: this Mojo version's `TestSuite` prints per-test timings that are
not wall-clock seconds (a 0.14 s wall run reports ~122 s); timings are
therefore never quoted as performance data. Wall-clock for all six
suites is under one second.

## 9. Python compatibility test results

24 tests, all pass: `test_cli` 11 (framing, batching, malformed
payloads, EOF, binary safety), `test_golden_vectors` 1 (432 batched
CLI frames), `test_oracle_assumptions` 10, `test_randomized_properties`
2 (205 pairs × up to 5 checks). Verified via
`check_compatibility.py --library levenshtein`.

## 10. Repository-wide regression results

`run_all_tests.py` exits 0: ruff check + format clean, both drift gates
current, **153 pytest passed** (129 msgpack + 24 levenshtein), all 13
native suites pass (79 msgpack + 25 levenshtein tests). MessagePack
sources, tests, and vectors untouched; both runners are
library-aware without behavior change to the msgpack paths.

## 11. Performance observations (exploratory only)

No benchmark suite was built and no claim is made. For orientation:

- Phase 0 probes: Mojo Myers-64 ≈ 611 ns at n=64 (~1.3× the C++
  reference); Mojo DP trails C++ ~250× at n=2048 — the documented
  reason the blocked implementation exists.
- CLI smoke: 20 mixed requests (n ≤ 2048) answered correctly in
  ~21 ms wall including process spawn — transport works, nothing more.
- A Mojo toolchain quirk found during testing: multi-op Float64
  constant expressions mis-fold (`1.0 - 2.0 / 6.0` folds to
  `...666`), while runtime arithmetic and single-literal parsing are
  exact. Ratio computes at runtime, so results are exact; the quirk is
  pinned by `test_guards` and generator output uses plain literals only.

## 12. Known limitations

- Jaro/Jaro-Winkler, editops/opcodes/matching-blocks, median family,
  `StringMatcher`: not implemented (Phase 0 §2 reasons stand).
- No similarity `score_cutoff`, no `processor`/`score_hint`, weights
  restricted to positive integers fitting the documented `Int` bound;
  u64 CLI fields above `Int.MAX` are rejected.
- `str`-only: bytes and lone surrogates are rejected, never coerced.
- Ratio uses DP LCS (no bit-parallel LCS yet); Peq tables rebuild per
  call (no caching).
- Golden Mojo source escapes all non-ASCII (`\u`/`\U`); NFD cases are
  escape-explicit so no invisible characters hide in tests.

## 13. Recommended next phase

Phase 2 (benchmarks, per `docs/benchmark-design.md`): adopt the
proposed gates (≥5× over naive Python at n≤512; within 3× of C++ at
n≤128), add cold-compile/RSS reporting, and evaluate a blocked
bit-parallel LCS for `ratio` before any large-n performance statement.
Algorithm additions (Jaro, editops) remain separate scoped proposals,
not part of the benchmark phase. No other library starts until this
report is reviewed.
