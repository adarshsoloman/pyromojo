# Phase 4 Results — Peak Analysis and Fragment Matching

Status: **complete**. Five public audioop operations implemented on the
Phase 1 sample layer; 9 public operations remain unimplemented.

## 1. Implementation summary

- `mojo/mojo_audioop/peak_analysis.mojo` (new): `avgpp`, `maxpp`,
  `findmax`, `findfactor`, `findfit`, plus `_unsigned_diff` (32-bit
  unsigned wrap), `_sum_sq`/`_sum2` (reference `_sum2` accumulation
  order), and the `FindFit` result struct. All reuse
  `validate_fragment`/`decode_fragment`; no byte logic duplicated.
- `mojo/cli.mojo` + `protocol.mojo` (modified): opcodes `0x2E`–`0x32`
  with documented payload/response formats; earlier opcodes untouched.
- `mojo/mojo_audioop/__init__.mojo` (modified): re-exports the five ops.
- `python_reference/oracle_samples.py` (modified): batch reference calls
  for all five operations (original `audioop` only).
- `python_reference/generate_audioop_vectors.py` (modified): 58 new
  `p4-` cases; prior 185 cases byte-identical.
- Native tests `tests/mojo/test_peak_analysis.mojo` (new, 15 tests);
  Python tests `test_peak_analysis_cli.py` (11), `test_peak_analysis_oracle.py`
  (3), `test_peak_analysis_vectors.py` (3).
- `scripts/run_all_tests.py` (modified): `test_peak_analysis` registered.
- Docs: `docs/peak-analysis.md` (new); `README.md` updated.

## 2. CPython source findings

Audited `Modules/audioop.c` directly and probed the reference binary:

- **avgpp/maxpp share one walk**: only differing adjacent samples are
  considered; `prevdiff` starts at a 17 sentinel so the first observed
  direction is baseline; a derivative sign change remembers the previous
  value as an extreme; the second remembered extreme produces a pair.
  `[1,2,3,2,1] → 0`; `[32767,-32768,32767] → 0`; `[1,3,1,3] → 2`.
  Plateaus are skipped. `len <= width` → 0. Differences use 32-bit
  unsigned arithmetic — `avgpp`/`maxpp` of `[MAX,MIN,MAX,MIN,MAX]` (w4)
  are **4294967295**. `avgpp` truncates the mean (`[0,3,0,1,0]` → 2);
  `maxpp` keeps the maximum.
- **findmax** is fixed 16-bit (no width argument); `length` counts
  samples; energy updates via `result = result + last² − first²`
  (left-to-right); ties keep the first window (strict `>`); `length` 0
  valid → 0; `length < 0 or len1 < length` → `Input sample should be
  longer`; odd bytes → `Strings should be even-sized`.
- **findfactor** is fixed 16-bit; equal byte lengths required
  (`Samples should be same size`); returns `sum(a·r) / sum(r²)` from two
  separate sequential loops. Zero/empty reference → `nan` (IEEE `0/0`,
  sign bit set: `0xfff8…` on this host).
- **findfit** is fixed 16-bit; `len1 < len2` → `First sample should be
  longer`. Score `(sum_ri_2·sum_aij_2 − sum_aij_ri²)/sum_aij_2` with
  incremental `sum_aij_2` and fully recomputed `sum_aij_ri` per
  candidate; strict `<` tie-breaking keeps the first window; `nan`
  candidates never beat finite bests; factor recomputed at the winner
  over `sum_ri_2`. Empty/all-zero → `(0, nan)`.

## 3. Operation compatibility table

| Operation | Reference signature | Widths | Verified semantics | Test status |
| --- | --- | --- | --- | --- |
| `avgpp` | `avgpp(fragment, width)` | 1–4 | baseline-first peak walk; unsigned diffs; truncated mean | PASS |
| `maxpp` | `maxpp(fragment, width)` | 1–4 | same walk; unsigned max (4294967295 quirk) | PASS |
| `findmax` | `findmax(fragment, length)` | fixed 16-bit | sample-index windows; strict `>` ties; length 0 valid | PASS |
| `findfactor` | `findfactor(fragment, reference)` | fixed 16-bit | least-squares ratio; `nan` on zero/empty reference | PASS |
| `findfit` | `findfit(fragment, reference)` | fixed 16-bit | exact search boundaries; strict `<` ties; `(0, nan)` edge | PASS |

## 4. Numerical edge-case results

- `avgpp`/`maxpp` w4 `[MAX,MIN,MAX,MIN,MAX]` = **4294967295** (unsigned
  wrap; port reproduces via `UInt32` wrap on two's-complement patterns).
- `avgpp` truncation: diffs 3,3,1 → 7/3 → **2**.
- `findmax` tie `[1,2,1,2] len2` → **0** (first window);
  `[0,0,5,5] len2` → **2** (last window wins when strictly better);
  `[1,2,3] len1` → **2**; length 0 on empty → **0**.
- `findfactor` zero/empty reference → **nan** (`0xfff8…` bit-exact);
  `findfactor(zero fragment, nonzero ref)` → **0.0**; scaled → **2.0**;
  negative → **-1.0**; `[30000,30000]` vs `[1,1]` → **30000.0**.
- `findfit`: exact at 0 → `(0, 1.0)`; shifted → `(1, 1.0)`; scaled →
  `(0, 2.0)`; tie → `(0, 1.0)`; empty both → `(0, nan)`; zero window →
  `(0, nan)`; `[5,6,0,0,0,0]` vs `[1,2]` → `(0, 3.4)` (nan candidates
  lose to finite bests).

## 5. Differential testing

- Reference version: CPython **3.12.3** (isolated venv).
- Curated differential cases: **47 oracle-backed cases** (peak walk ×
  widths × signal shapes; unsigned wrap; all find* error paths; nan and
  scaled/shifted/tie matching cases).
- Randomized differential cases: **480** (4 widths × 24 iterations × 5
  ops; styles mixed/positive/negative/constant/plateau/alternating;
  random `findmax` lengths 0..samples+1; equal-length findfactor pairs;
  both orderings for findfit).
- Random seed: **20260610**.
- Mismatches: **0**. Exception mismatches: **0** (verbatim messages).
- Floating-point comparison policy: **bit-exact** via IEEE-754 bytes for
  finite values; nan compared as nan-ness only (JSON cannot carry the
  nan sign; the port's `0xfff8…` matches the reference's actual bits,
  verified in `test_nan_bit_policy` and the CLI tests).

## 6. Golden vectors

- Before: **185** (42 + 24 + 50 + 69). After: **243** (… + **58**
  `p4-` cases).
- Existing vectors untouched; generator deterministic; `--check` passes.
- Bundle sha256:
  `61945fc9f12abe934b7903a4b971135c0ad90f4b1672d10dfb7f15b90a4f6bd7`.
- Coverage: every operation; all widths for avgpp/maxpp; error cases
  for all five ops; constant/monotonic/alternating/plateau signals;
  unsigned wrap; length 0/1/==count/too-long/negative; odd bytes;
  identical/scaled/shifted/negative/zero-reference fragments; ties;
  nan results; the fixed-16-bit interpretation of width-4 bytes.

## 7. Native Mojo test counts

`test_peak_analysis.mojo`: **15 tests run: 15 passed, 0 failed**.
Prior native audioop suites still pass: samples 13/13, arithmetic 19/19,
statistics 13/13.

## 8. Python test counts

Audioop compatibility suite: **71 passed** (was 54; +17: CLI 11,
oracle 3, vectors 3).

## 9. Repository-wide validation results

| Check | Command | Result |
| --- | --- | --- |
| Native samples | build + run `/tmp/audioop_phase4_samples` | exit 0; **13 passed** |
| Native arithmetic | build + run `/tmp/audioop_phase4_arithmetic` | exit 0; **19 passed** |
| Native statistics | build + run `/tmp/audioop_phase4_statistics` | exit 0; **13 passed** |
| Native peak analysis | build + run via runner | exit 0; **15 passed** |
| Full runner | `.venv/bin/python scripts/run_all_tests.py` | exit 0; **all suites passed**; **26 native suites / 253 native tests**; **616 pytest passed** |
| Vector drift | `python_reference/.venv/bin/python .../generate_audioop_vectors.py --check` | exit 0; **243 cases match** |
| Ruff | `.venv/bin/ruff check .` | exit 0, `All checks passed!` |
| Format | `.venv/bin/ruff format --check .` | exit 0 |
| Whitespace | `git diff --check` | exit 0 |

## 10. Known limitations and deviations

- 9 public operations remain unimplemented: `tomono`, `tostereo`,
  `ratecv`, `lin2alaw`, `alaw2lin`, `lin2ulaw`, `ulaw2lin`,
  `lin2adpcm`, `adpcm2lin`.
- `find*` operations are fixed 16-bit by reference design; the CLI
  `findmax` payload carries no width byte (documented deviation from
  the phase sketch's "width, length, fragment" format).
- The 4294967295 `avgpp`/`maxpp` result and the `0xfff8…` nan are
  reference-exact quirks, reproduced deliberately (not deviations).
- The Phase 0 `avg()` floor correction (established in Phase 3) is
  documented in `docs/statistics-operations.md`; Phase 0 historical
  documents remain unedited, as required.
- No benchmarks or performance work (per scope).
- CI still runs ruff + pytest only; Mojo suites are not a CI gate.

## 11. Git state

Created this phase: `mojo/mojo_audioop/peak_analysis.mojo`,
`tests/mojo/test_peak_analysis.mojo`,
`tests/python_compat/test_peak_analysis_cli.py`,
`tests/python_compat/test_peak_analysis_oracle.py`,
`tests/python_compat/test_peak_analysis_vectors.py`,
`docs/peak-analysis.md`, `PHASE4_RESULTS.md`.

Modified this phase: `libraries/audioop/README.md`,
`mojo/cli.mojo`, `mojo/mojo_audioop/protocol.mojo`,
`mojo/mojo_audioop/__init__.mojo`, `python_reference/oracle_samples.py`,
`python_reference/generate_audioop_vectors.py`,
`tests/vectors/audioop_vectors.json`,
`tests/python_compat/support.py`,
`tests/python_compat/test_arithmetic_vectors.py`,
`tests/python_compat/test_samples_vectors.py`,
`tests/python_compat/test_statistics_vectors.py`,
`scripts/run_all_tests.py`.

Deleted: none. No commits, pushes, tags, or releases were made during
this phase. HEAD is `815d562 feat(audioop): implement sample statistics
operations` — the Phase 3 work committed between sessions, outside this
phase.

## 12. Final phase verdict

**PHASE 4 COMPLETE — READY FOR REVIEW.**
