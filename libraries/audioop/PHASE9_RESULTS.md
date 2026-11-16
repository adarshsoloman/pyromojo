# Phase 9 Results — Full Audioop Compatibility Audit

Status: **audit complete; recommendation: READY FOR PHASE 10.**

## 1. Executive summary

All 26 public audioop operations were audited against CPython 3.12.3 via
the repository's own evidence (exports, CLI dispatch, oracle, vector
corpus, native and differential tests) plus fresh adversarial probes.
Every operation is **PASS**; no reference mismatches were found in any
probe this phase. Two documentation-level defects were found and fixed
(the Phase 8 test-count methodology in `PHASE8_RESULTS.md`, and the
missing third-party attribution for the transcribed codec tables). Two
known documented deviations (mul NaN policy, width-4 NaN) remain
deliberate and unchanged.

## 2. Baseline Git state

- Branch `main`; HEAD `50456ba feat(audioop): implement ADPCM encoding
  and decoding` — Phase 8 was committed between sessions, so this phase
  began from a **clean working tree** (verified with
  `git status --porcelain -uall`, 0 entries).
- After the Phase 9 fixes below, the working tree contains exactly two
  modified files (`THIRD_PARTY_NOTICES.md`,
  `libraries/audioop/docs/licensing-audit.md`) plus
  `libraries/audioop/PHASE9_RESULTS.md`.

## 3. Toolchain versions

- Mojo `1.2.0 (2016d0cd)` via `.venv/bin/mojo` (system 1.0.0 not used).
- Host Python `3.13.14` (`.venv/bin/python`).
- Reference Python `3.12.3`
  (`libraries/audioop/python_reference/.venv/bin/python`).

## 4. 26-operation compatibility matrix

Evidence sources: E1 = exported through `__init__.mojo`; E2 = CLI opcode
dispatch; E3 = oracle key; E4 = golden vectors; E5 = native tests;
E6 = Python differential tests.

| Operation | Implementation | Ref behaviour | Validated cases | Exceptions | E1–E6 | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| add | arithmetic.mojo | saturating per-sample sum | widths 1–4, saturation, empty, mismatch, order, randomized | `Lengths should be the same`, size/alignment | ✓✓✓✓✓✓ | PASS | — |
| adpcm2lin | adpcm.mojo | IMA/DVI decode, high nibble first | all 256 bytes, widths 1/3/4, nibble sweep, states, chunking | `bad state`, size | ✓✓✓✓✓✓ | PASS | no alignment check (reference-exact) |
| alaw2lin | g711.mojo | 256-entry table decode | all 256 codewords, widths 1/3/4, sequences | size only | ✓✓✓✓✓✓ | PASS | alignment-free (reference-exact) |
| avg | statistics.mojo | Float64 sum + floor | widths, floor evidence, empty, extremes | size/alignment | ✓✓✓✓✓✓ | PASS | Phase 0 doc note corrected in Phase 3 |
| avgpp | peak_analysis.mojo | baseline-first peak walk, unsigned diffs, truncated mean | widths, plateaus, truncation, wrap quirk | size/alignment | ✓✓✓✓✓✓ | PASS | single peak → 0 (reference-exact) |
| bias | arithmetic.mojo | wrap via 32-bit mask | widths, wrap both ends, C-int range, empty | C-int overflow message | ✓✓✓✓✓✓ | PASS | — |
| byteswap | arithmetic.mojo | byte order swap in samples | widths, restore, negatives, order | size/alignment | ✓✓✓✓✓✓ | PASS | — |
| cross | statistics.mojo | sign-class transitions, -1 sentinel | widths, zeros, single, INT_MIN | size/alignment | ✓✓✓✓✓✓ | PASS | zero is non-negative (reference-exact) |
| findfactor | peak_analysis.mojo | `sum(a·r)/sum(r²)`, fixed 16-bit | identical/scaled/negative/zero-ref/empty/large, 16-bit interpretation | size messages, `nan` | ✓✓✓✓✓✓ | PASS | zero/empty reference → `nan` (reference-exact) |
| findfit | peak_analysis.mojo | window search, incremental `sum_aij_2`, strict `<` | shifted/tie/empty/zero-window/neg, errors | size messages, `(0, nan)` | ✓✓✓✓✓✓ | PASS | — |
| findmax | peak_analysis.mojo | fixed 16-bit energy windows, strict `>` | ties, last-window, length 0/1/==count/too long, w4-as-16bit | size messages | ✓✓✓✓✓✓ | PASS | — |
| getsample | statistics.mojo | bounded single-sample decode | all widths, negative/huge/empty indices | `Index out of range` | ✓✓✓✓✓✓ | PASS | huge Int64 indices verified |
| lin2adpcm | adpcm.mojo | IMA/DVI encode, high nibble first | widths, odd counts, states, continued, errors | size/alignment, `bad state` | ✓✓✓✓✓✓ | PASS | odd trailing nibble dropped (reference-exact) |
| lin2alaw | g711.mojo | 13-bit encode, mask 0xD5/0x55 | widths + scaling, segment boundaries, clip | size/alignment | ✓✓✓✓✓✓ | PASS | w1 ×32 upscale (reference-exact) |
| lin2lin | arithmetic.mojo | shift-based width conversion | all 16 pairs, boundaries, empty, order | size/alignment | ✓✓✓✓✓✓ | PASS | — |
| lin2ulaw | g711.mojo | 14-bit encode, bias 33, clip 32635 | widths + scaling, segment boundaries, clip | size/alignment | ✓✓✓✓✓✓ | PASS | w1 ×64 upscale (reference-exact) |
| max | statistics.mojo | unsigned absolute magnitude | widths, INT_MIN → 2³¹, negatives, empty | size/alignment | ✓✓✓✓✓✓ | PASS | — |
| maxpp | peak_analysis.mojo | unsigned peak-pair max | widths, wrap quirk 4294967295, single V | size/alignment | ✓✓✓✓✓✓ | PASS | — |
| minmax | statistics.mojo | signed pair, sentinel | widths, empty sentinel, INT_MIN-only | size/alignment | ✓✓✓✓✓✓ | PASS | — |
| mul | arithmetic.mojo | clamp→floor (`fbound`) | factors 0/±1/±0.5/tiny/large/±inf, NaN policy, widths | size/alignment | ✓✓✓✓✓✓ | PASS | NaN→0 documented deviation |
| ratecv | ratecv.mojo | stateful IIR resampler | widths, mono/2ch/4ch, ±rates, non-integer ratios, weights+gcd, chunk equivalence, errors | conversion/size/channel/weights/alignment/rate messages | ✓✓✓✓✓✓ | PASS | C-int conversion errors reproduced |
| reverse | arithmetic.mojo | sample-order reversal | widths, empty/single, mixed signs | size/alignment | ✓✓✓✓✓✓ | PASS | — |
| rms | statistics.mojo | Float64 squares + truncated sqrt | widths, all-INT_MIN → 2³¹, truncation evidence | size/alignment | ✓✓✓✓✓✓ | PASS | — |
| tomono | channels.mojo | interleaved pair mixing, `fbound` | widths, saturation, floor, odd counts, factors incl. ±inf/NaN | size/alignment | ✓✓✓✓✓✓ | PASS | NaN→0 policy at w4 (documented) |
| tostereo | channels.mojo | left-first expansion, `fbound` | widths, saturation, single, factors | size/alignment | ✓✓✓✓✓✓ | PASS | — |
| ulaw2lin | g711.mojo | 256-entry table decode | all 256 codewords, widths 1/3/4, sequences | size only | ✓✓✓✓✓✓ | PASS | alignment-free (reference-exact) |

**26/26 PASS.** All six evidence channels cover every operation
(verified programmatically: 26 CLI opcodes `0x22`–`0x3B`, 28 oracle
keys, 26 operation groups in the vector corpus, 8 native suites,
16 Python test modules).

## 5. Shared sample representation audit

- All sample byte I/O lives in `samples.mojo`
  (`_load_sample`/`_store_sample`); every operation consumes
  `decode_fragment`/`encode_fragment`/`validate_fragment`. A grep for
  raw shift/mask math outside `samples.mojo` found only: the bias
  32-bit wrap mask (intentional, reference-exact), and the pure byte
  moves in `reverse`/`byteswap`/`find*` nibble packing (byte-level
  operations by definition, not sample decoding). **No duplicated
  byte-order or sign-extension logic exists.**
- 24-bit sign extension, all four widths' boundaries, and
  native-order detection were re-verified by the still-green
  `test_samples` suite (13 tests) and the Phase 9 extra probes.
- No defect found; no refactor needed.

## 6. `ratecv` state audit

Re-verified through the reference oracle and CLI (Phase 6 + fresh
Phase 9 probes):

- Fresh state `d = -outrate` after gcd reduction; empty input returns
  `(b"", (d, zeros))` and a continued state unchanged.
- Mono and multichannel (1/2/4 channels in vectors; randomized 1–3),
  both rate directions, non-integer ratios, custom weights with gcd
  reduction (`(5,0) → (1,0)`).
- **Chunk equivalence**: 4/4/12-frame chunks, one-sample chunks (20
  calls), and empty-chunk-between-nonempty all produce byte-identical
  output and identical final state — verified against CPython and the
  CLI (`test_chunk_equivalence_reference_and_port`).
- Invalid state: C-int conversion errors (huge nchannels/rates/
  weights) reproduced verbatim; alignment before rate checks
  reproduced.

## 7. ADPCM state audit

Re-verified (Phase 8 + fresh Phase 9 probes):

- Fresh state `(0, 0)`; empty input returns state unchanged
  (`(100, 50)` preserved).
- Predictor clamps at ±32767/-32768; index clamps [0, 88]; boundary
  states `(-32768, 0)`, `(32767, 88)`, `(-32768, 88)` accepted through
  the CLI and produce correct bytes.
- High-nibble-first packing verified by the 16-nibble sweep (exact
  outputs and states from the reference).
- Width-dependent input scaling (w1 ×256, w2 identity, w3 `>>8`,
  w4 `>>16`) and decoder output scaling verified per width.
- **Odd trailing nibble**: one sample → 0 output bytes with state
  advanced (`(11, 8)` for sample 1000; `(-10, 6)` for sample -10);
  three samples → 1 byte. **Odd-sized encoder chunks do not
  concatenate** (documented CPython behaviour); even chunks compose
  exactly; decoder chunks of any size compose exactly.

## 8. CLI/protocol audit

- Opcode registry: 26 operation opcodes `0x22`–`0x3B` plus
  `0x01`/`0x02`/`0x20`/`0x21` — all unique, all dispatched
  (`grep -c "elif opcode =="` = 29 = ping/echo + 26 operations + the
  dispatch structure). Every public operation is CLI-reachable.
- Fresh adversarial probe (14 checks, all **PASS**): empty input clean
  exit; truncated header/body rejected with non-zero exit; >64 MiB
  frame rejected (`exceeds limit`); unknown opcodes (`0x00`, `0x03`,
  `0x10`, `0x1F`, `0x3C`, `0x7F`, `0xFF`) each answered with a
  deterministic `unknown opcode N` error frame; empty frame error;
  stateful ops reject truncated state blocks with error frames;
  boundary states accepted; an 8-request mixed batch (ping, sample,
  max, alaw, adpcm, add, unknown, ping) processed end-to-end.
- One probe-expectation correction (not an implementation defect): an
  ADPCM request containing a complete state block but no fragment is
  **valid** (empty fragment) — initially mis-expectated as an error.
- Diagnostics stay on stderr; stdout carries only protocol frames;
  length cap enforced; deterministic error frames confirmed.

## 9. Oracle and golden-vector reproducibility

- Oracle: 28 operation keys (26 public + sample decode/encode), all
  calling the real `audioop` in the pinned 3.12.3 venv; state
  round-trips (lists converted back to tuples for the reference).
- Vector corpus: **1277 cases** covering all 26 operations + the
  sample layer; `--check` re-run this phase: `1277 cases match`, exit
  0 — generation is deterministic and drift-detecting.
- Vector metadata: every case records `id`, `op`, `width` where
  applicable, `args`, and `expected` (result/exception) — sufficient
  to reproduce each call.
- All prior phase vectors remain byte-identical (count assertions in
  the seven vector test files: 42/24/50/69/58/33/31/645/325 preserved).

## 10. Phase 8 test-count clarification

`PHASE8_RESULTS.md` section 5 previously reported "54 curated + 120
randomized" oracle-backed cases. Counting the actual emissions in
`test_adpcm_oracle.py`:

- **Curated: 317 oracle-backed cases** — 29 encoder (16 per-width +
  13 edge/error) + 288 decoder (256 exhaustive byte values at width 2
  + 24 sampled width-1/3/4 cases + 8 sequences/state/error cases).
- **Randomized: 115 cases** — 80 encoder (4 widths × 20) + 35 decoder
  (20 width-2 + 15 width-1/3/4).
- **Methodology confirmation**: the 256 decoder bytes are tested as
  **256 independent CLI requests** (one `batch.emit` per byte, each
  compared 1:1 against the oracle), *not* one combined input. The same
  256 bytes additionally appear as 256 independent golden-vector
  cases, replayed individually.
- `PHASE8_RESULTS.md` section 5 has been corrected in place (with a
  dated note) to record these counts; test results themselves were
  valid and unchanged.

## 11. Malformed-input and boundary test results

Beyond the existing suites (which already cover invalid widths,
misalignment, invalid states, empty fragments, and boundary values for
every operation), this phase added fresh probes:

- 14 CLI adversarial checks — all PASS (section 8).
- 14 extra reference-differential edge cases — all PASS, **0
  mismatches**: `getsample` with `2^62`/`2^31`/`-2^31` indices;
  `findfit` with a single candidate beyond index 0; `mul` with a
  subnormal factor (`5e-324`); `tomono` with `±1e-300` factors;
  `ratecv` 1:1 at all four widths with boundary samples; `lin2lin`
  identity with `INT_MIN`/`INT_MAX` at every width.
- No crashes, hangs, or inconsistent errors observed.

## 12. Licensing and provenance findings

- `docs/licensing-audit.md` (Phase 0) documents the CPython
  `audioop.c` → SoX 12.17.7 `g777.c`/`g771.c` chain and the embedded
  Sun Microsystems unrestricted-use notice.
- **Finding 1 (fixed)**: `THIRD_PARTY_NOTICES.md` had no audioop
  entry, although the Phase 0 audit prepared the attribution paragraph
  for insertion "when implementation begins". The entry has now been
  added (reference pin, retained Sun notice quoted in full for the
  transcribed G.711 tables, IMA/DVI constants note, derived-vectors
  statement).
- **Finding 2 (documented)**: the Phase 0 plan said codec tables would
  be "regenerated, not transcribed". Phase 7 initially used
  algorithmic decoder formulas, which did not reproduce CPython's
  table ordering, so the tables were transcribed verbatim from the
  reference `audioop.c` — exactly the contingency the plan's revisit
  clause anticipated. `docs/licensing-audit.md` §3.2 now records this
  decision and its coverage rationale (Sun notice for the G.711
  tables; standard IMA/DVI constants for ADPCM, cross-checked against
  the published specification). No SoX file was vendored; the tables
  are data within a PSF-2.0 file whose codec section carries the Sun
  notice.
- No other third-party material was copied.

## 13. Documentation consistency findings

- `README.md` status line ("PHASE 8 COMPLETE — all 26 operations
  implemented") matches the verified inventory; no drop-in
  compatibility or performance claims are made that the evidence does
  not support.
- Each phase document documents its opcodes, payload formats, widths,
  error messages, and deviations; the frozen `api-scope.md` decisions
  (NaN policy, native byte order, fixed-16-bit `find*`) are honoured
  and cross-referenced.
- Known documented deviations remain exactly two, both deliberate:
  `mul`/`tomono`/`tostereo` NaN→0 policy (reference UB), and
  reference-only state-type errors not reachable through the CLI's
  structural state blocks.
- One minor gap noted (not fixed this phase): there is no single
  consolidated CLI opcode-registry document; the registry is
  documented per phase (`0x20`–`0x39` in the phase docs, `0x3A`/`0x3B`
  in `docs/adpcm.md`, the registry itself in `protocol.mojo`).
  Recommended for the release-preparation phase.

## 14. Exact validation commands and results

| Command | Result |
| --- | --- |
| `.venv/bin/ruff check .` | exit 0, `All checks passed!` |
| `.venv/bin/ruff format --check .` | exit 0 |
| `.venv/bin/python scripts/run_all_tests.py` | exit 0; **all suites passed**; **30 native suites / 298 native tests** (8 audioop suites = 105 tests); **681 pytest passed** (136 audioop compatibility tests) |
| `libraries/audioop/python_reference/.venv/bin/python libraries/audioop/python_reference/generate_audioop_vectors.py --check` | exit 0; **1277 cases match** |
| `git diff --check` | exit 0 |
| Phase 9 CLI adversarial probe (14 checks) | **14 PASS** |
| Phase 9 extra differential probe (14 cases) | **0 mismatches** |

## 15. Bugs found and fixes applied

1. **Phase 8 report counts** (`PHASE8_RESULTS.md` §5): corrected from
   "54 curated + 120 randomized" to the actual **317 curated (incl.
   256 exhaustive decoder emissions) + 115 randomized**, with the
   256-independent-requests methodology stated explicitly. No test
   results were altered.
2. **Missing third-party attribution** (`THIRD_PARTY_NOTICES.md`):
   added the audioop entry with the retained Sun Microsystems notice
   (quoted in full) covering the transcribed G.711 tables, the
   IMA/DVI constants note, and the derived-data statement.
3. **Licensing-audit plan deviation undocumented**
   (`docs/licensing-audit.md` §3.2): added a Phase 9 update recording
   the transcription decision, its trigger (algorithmic decoder did
   not reproduce table ordering), and its coverage rationale.

No implementation (Mojo) code changes were required — no behavioral
defect was found.

## 16. Outstanding limitations and known deviations

- `mul`/`tomono`/`tostereo` NaN results → 0 (documented port policy;
  the reference's `(int)NaN` is UB).
- Reference-only state-type errors (`TypeError state must be a tuple
  or None`, function-prefixed illegal-state messages) are not
  reachable through the CLI's structural state blocks.
- Encoder odd-chunk concatenation is not byte-equal to whole encoding
  (CPython behaviour, documented).
- Encoder input scaling for `lin2adpcm`/`mul`-family follows the
  reference exactly, including the width-1 upscale — not a deviation,
  listed because it surprises readers.
- No consolidated CLI opcode-registry document (recommended for the
  release-preparation phase).
- Benchmarks: none exist yet (Phase 10 scope).

## 17. Files changed

- `THIRD_PARTY_NOTICES.md` — audioop attribution entry added.
- `libraries/audioop/docs/licensing-audit.md` — §3.2 Phase 9 update.
- `libraries/audioop/PHASE8_RESULTS.md` — §6 counts corrected to the
  actual methodology (317 curated incl. 256 exhaustive decoder
  emissions, 115 randomized; 256 independent requests), with a dated
  note; results unchanged.
- No implementation, test, oracle, or vector files changed.

## 18. Final Git status

- Branch `main`; HEAD `50456ba` (unchanged — no commits made).
- Working tree: 3 modified files + this report; `git diff --check`
  clean.

## 19. Recommendation

**READY FOR PHASE 10** (integrated benchmarking and release
preparation). All 26 operations are reference-verified, the CLI and
protocol are robust under adversarial input, golden vectors are
deterministic and drift-checked, provenance and attribution are now
complete and honest, and the documentation matches the implementation.
