# Phase 6 Results — Stateful Sample-Rate Conversion (`ratecv`)

Status: **complete**. `ratecv` implemented on the Phase 1 sample layer;
6 public operations remain unimplemented.

## 1. Implementation summary

- `mojo/mojo_audioop/ratecv.mojo` (new): `ratecv` (fresh state,
  reference `state=None`), `ratecv_continue` (resumed state), the
  `RatecvState`/`RatecvResult` structs, `_gcd`, and the C-int
  argument-range check. Reuses `validate_width`, `decode_fragment`,
  `encode_fragment`; no byte logic duplicated. No Phase 1–5 code
  modified.
- `mojo/cli.mojo` + `protocol.mojo` (modified): opcode `0x35` with a
  state block that round-trips through separate CLI calls.
- `mojo/mojo_audioop/__init__.mojo` (modified): re-exports.
- `python_reference/oracle_samples.py` (modified): `ratecv` oracle
  calling the original module; state round-trips through JSON
  (lists converted back to tuples because the reference requires
  tuples).
- `python_reference/generate_audioop_vectors.py` (modified): 31 new
  `p6-` cases; prior 276 cases byte-identical.
- Native tests `tests/mojo/test_ratecv.mojo` (new, 11 tests); Python
  tests `test_ratecv_cli.py` (10), `test_ratecv_oracle.py` (3),
  `test_ratecv_vectors.py` (3).
- `scripts/run_all_tests.py` (modified): `test_ratecv` registered.
- Docs: `docs/ratecv.md` (new); `README.md` updated.

## 2. CPython source findings

Audited `audioop_ratecv_impl` and probed the reference binary:

- Validation order: C `int` argument conversion first (huge args →
  `Python int too large to convert to C int`, precedence over all body
  checks — probed with `nchannels=0` + huge rate), then width, then
  `# of channels should be >= 1`, then
  `width * nchannels too big for a C int`, then the weight check, then
  fragment alignment (`not a whole number of frames`) — **before** the
  rate check (`sampling rate not > 0`).
- `inrate`/`outrate` and `weightA`/`weightB` are gcd-reduced; `(5, 0)`
  reduces to `(1, 0)`.
- Samples are scaled to the 32-bit position (`GETSAMPLE32`/`SETSAMPLE32`,
  ×2^(32−8·width)); filtering and interpolation happen at that scale.
- Filter: `cur_i = (int)((wA·cur + wB·prev)/(wA+wB))` in double,
  truncated toward zero (C `(int)` cast — not floor).
- Phase loop: fresh `d = -outrate` (reduced); input consumed only while
  `d < 0`; output produced only while `d >= 0`
  (`(int)((prev·d + cur·(outrate−d))/outrate)`, truncation toward
  zero); finalize when the input runs out during the `d < 0` phase.
- State: `(d, ((prev_i, cur_i) per channel))`; empty input returns
  `(b"", (-outrate, zeros))`; the returned state feeds the next call
  directly.

## 3. State representation and protocol changes

- `RatecvState` holds `d: Int64` plus per-channel `prev_i`/`cur_i`
  (`List[Int64]`); `RatecvResult` holds the output bytes and the state.
  Values are the 32-bit-scaled samples, exactly as the reference
  stores them — no simplification of phase or filter history.
- CLI `0x35` request:
  `uint8 width | int64_be nchannels | int64_be inrate | int64_be
  outrate | int64_be weightA | int64_be weightB | uint8 has_state |
  [int64_be d | nchannels × (int64_be prev | int64_be cur)] | fragment`
  (the channel count is 8 bytes so argument-conversion errors are
  reachable through the CLI).
- CLI response: `uint32_be out_len | output bytes | int64_be d |
  nchannels × (int64_be prev | int64_be cur)`; the state block can be
  pasted into the next request. Verified by state round-trip tests.

## 4. Validation and exception behavior

All messages verbatim and in the reference order:

`Size should be 1, 2, 3 or 4`, `# of channels should be >= 1`,
`width * nchannels too big for a C int`,
`weightA should be >= 1, weightB should be >= 0`,
`not a whole number of frames`, `sampling rate not > 0`,
`Python int too large to convert to C int`.

Reference-only state errors (non-tuple state → `TypeError state must be
a tuple or None`; wrong channel count → `ratecv(): illegal state
argument`) are not reachable through the CLI's own state block; the
oracle reproduces them by calling the reference directly.

## 5. Numerical compatibility findings

- Double-precision accumulation and C `(int)` truncation toward zero
  reproduced exactly (verified by curated cases, e.g. weights `(2, 1)`
  filter value `43690666`, then `58254222`).
- 32-bit sample scaling verified per width: w2 sample 1000 →
  `65536000`; w1 sample 100 → `1677721600`; w4 unshifted.
- Saturation is implicit: outputs are interpolations between filtered
  samples, and storage truncates through the top-aligned shift; byte
  outputs match the reference at all widths including `INT_MIN`/`MAX`.
- No undefined behaviour is reachable for valid arguments; no port
  policy deviations were needed.

## 6. Golden vector count and SHA-256

- Before: **276**. After: **307** (… + **31** `p6-` cases).
- Existing vectors untouched; generator deterministic; `--check` passes.
- Bundle sha256:
  `bb30e5a7cf0ed6c7b725f966b778df1f0d730c672a232f651eb5bac4f89a0b69`.
- Coverage: all widths; mono/2ch/4ch; equal rates, up- and downsampling,
  non-integer ratio; custom and gcd-reduced weights; empty/one-sample
  fragments; extrema; alternating; continued state (mono and 2ch);
  every error path including argument-conversion and the
  width·nchannels C-int overflow.

## 7. Differential test counts and seeds

- Curated differential cases: **41** (basics, all widths ×3 rate
  directions, multichannel, weights, continued states, 10 error cases).
- Randomized differential cases: **80** (4 widths × 20; random
  channels 1–3, frame counts 0–9, rate pool incl. equal/upsample/
  downsample/non-integer ratios, random weights; seed **20260610**).
- Mismatches: **0**; exception mismatches: **0** (exact messages).
- Comparison policy: exact output bytes and exact returned state
  (`d` and every per-channel pair); no tolerances.

## 8. Chunk-equivalence results

Dedicated group `test_chunk_equivalence_reference_and_port` plus native
`test_ratecv_chunk_equivalence*`:

- 20-frame fragment (8k→16k) vs chunks of 4/4/12 frames: equal output
  bytes and equal final state — on the reference **and** the port, and
  the port's whole output/state equal the reference's.
- One-sample chunks (20 calls): equal, both implementations.
- Empty chunk between non-empty chunks: equal, both implementations.
- Multichannel (2ch, 8000→44100, chunks of 1/2/1 frames): equal.
- Native multichunk test with per-byte and per-state asserts: pass.

## 9. Exact native and Python test counts

- Native `test_ratecv.mojo`: **11 tests run: 11 passed, 0 failed**.
- Python: **103 passed** (was 87; +16: CLI 10, oracle 3, vectors 3).

## 10. Commands executed and their results

| Check | Command | Result |
| --- | --- | --- |
| Native samples | build + run `/tmp/audioop_phase6_samples` | exit 0; 13 passed |
| Native arithmetic | build + run `/tmp/audioop_phase6_arithmetic` | exit 0; 19 passed |
| Native statistics | build + run `/tmp/audioop_phase6_statistics` | exit 0; 13 passed |
| Native peak | build + run `/tmp/audioop_phase6_peak` | exit 0; 15 passed |
| Native channels | build + run `/tmp/audioop_phase6_channels` | exit 0; 11 passed |
| Native ratecv | build + run via runner | exit 0; 11 passed |
| Full runner | `.venv/bin/python scripts/run_all_tests.py` | exit 0; **all suites passed**; **28 native suites / 275 native tests**; **648 pytest passed** |
| Vector drift | `python_reference/.venv/bin/python .../generate_audioop_vectors.py --check` | exit 0; **307 cases match** |

## 11. Ruff and formatting results

- `.venv/bin/ruff check .` → exit 0, `All checks passed!`
- `.venv/bin/ruff format --check .` → exit 0.
- `git diff --check` → exit 0.

## 12. Files changed

Created: `mojo/mojo_audioop/ratecv.mojo`, `tests/mojo/test_ratecv.mojo`,
`tests/python_compat/test_ratecv_cli.py`,
`tests/python_compat/test_ratecv_oracle.py`,
`tests/python_compat/test_ratecv_vectors.py`,
`docs/ratecv.md`, `PHASE6_RESULTS.md`.

Modified: `libraries/audioop/README.md`, `mojo/cli.mojo`,
`mojo/mojo_audioop/protocol.mojo`, `mojo/mojo_audioop/__init__.mojo`,
`python_reference/oracle_samples.py`,
`python_reference/generate_audioop_vectors.py`,
`tests/vectors/audioop_vectors.json`, `tests/python_compat/support.py`,
`test_samples_vectors.py`, `test_arithmetic_vectors.py`,
`test_statistics_vectors.py`, `test_peak_analysis_vectors.py`,
`test_channels_vectors.py`, `scripts/run_all_tests.py`.

Deleted: none.

## 13. Known deviations and limitations

- 6 public operations remain unimplemented (`lin2alaw`, `alaw2lin`,
  `lin2ulaw`, `ulaw2lin`, `lin2adpcm`, `adpcm2lin`).
- Reference `state` object errors (`TypeError state must be a tuple or
  None`, `ratecv(): illegal state argument`) are not reproducible
  through the CLI's own state block; the CLI reports structural errors
  instead. The port API separates fresh/continued state explicitly.
- The CLI channel count is transmitted as 8 bytes (new opcode, no
  back-compat constraint) so argument-conversion errors remain
  testable end-to-end.
- No benchmarks (deferred per phase instructions).

## 14. Git branch, HEAD, and working-tree status

- Branch: `main`. HEAD: `ea6ae5d feat(audioop): implement channel
  conversion operations` — the Phase 5 work committed between sessions,
  outside this phase.
- Working tree: 13 modified + 7 created files (listed above), 0
  deleted; `git diff --check` clean.

## 15. Confirmation

**No commit, push, tag, or release was performed during this phase.**

## 16. Phase verdict

**PHASE 6 COMPLETE — READY FOR REVIEW.**
