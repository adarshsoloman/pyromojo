# Phase 8 Results — ADPCM Encoding and Decoding

Status: **complete**. `lin2adpcm` and `adpcm2lin` implemented natively.
This completes the 26-operation audioop v0.1.0 API.

## 1. Implementation summary

- `mojo/mojo_audioop/adpcm.mojo` (new): `lin2adpcm`, `adpcm2lin`, the
  `AdpcmState`/`AdpcmResult` structs, and the verbatim
  `indexTable`/`stepsizeTable` tables. Reuses
  `validate_fragment`/`validate_width`/`decode_fragment`/
  `encode_fragment`; no byte logic duplicated; no Phase 1–7 code
  modified.
- `mojo/cli.mojo` + `protocol.mojo` (modified): opcodes `0x3A`/`0x3B`
  with a serializable state block; earlier opcodes untouched.
- `mojo/mojo_audioop/__init__.mojo` (modified): re-exports.
- `python_reference/oracle_samples.py` (modified): oracle calls for
  both operations (original `audioop` only).
- `python_reference/generate_audioop_vectors.py` (modified): 325 new
  `p8-` cases; prior 952 cases byte-identical.
- Native tests `tests/mojo/test_adpcm.mojo` (new, 11 tests); Python
  tests `test_adpcm_cli.py` (11), `test_adpcm_oracle.py` (3),
  `test_adpcm_vectors.py` (3).
- `scripts/run_all_tests.py` (modified): `test_adpcm` registered.
- Docs: `docs/adpcm.md` (new); `README.md` updated.

## 2. CPython source audit findings

- Tables: `indexTable[16] = {-1,-1,-1,-1,2,4,6,8,-1,-1,-1,-1,2,4,6,8}`;
  `stepsizeTable[89] = {7, 8, …, 32767}` (classic IMA/DVI).
- Encoder: `check_parameters` (width + alignment) first, then state
  (`None` → (0,0); range check → `ValueError bad state`; reference-only
  tuple errors). Input `GETSAMPLE32 >> 16` (w1 ×256, w2 unchanged,
  w3 `>>8`, w4 `>>16`); predictor updated with the **reconstructed
  vpdiff**, clamped [-32768, 32767]; index clamped [0, 88]; nibbles
  packed high-first; odd trailing sample's nibble dropped
  (`len/(width*2)` output bytes) while the state still advances.
- Decoder: `check_size` only (any byte length); high nibble first;
  identical reconstruction/clamping; output `valpred << 16` stored
  through the top-aligned shift; two samples per input byte.
- Probed: all validation messages and orders, per-width scaling, the
  16-nibble sweep from a fresh state (exact outputs and states), odd
  sample counts, empty inputs, and chunk composition.

## 3. Exact accepted widths

Both operations: widths 1–4. Encoder requires whole samples; decoder
accepts any byte count.

## 4. Validation and exception behavior

Verbatim: `Size should be 1, 2, 3 or 4`, `not a whole number of frames`
(encoder only), `bad state` (predictor/index out of range, both ops).
Reference-only `TypeError state must be a tuple or None` /
`lin2adpcm()/adpcm2lin(): illegal state argument` are unreachable
through the CLI's structural state block and are documented.

## 5. State representation and serialization

`AdpcmState` holds `valpred: Int64` (16-bit predictor, [-32768, 32767])
and `index: Int64` ([0, 88]) — exactly the reference tuple semantics,
preserved across calls without simplification. CLI `0x3A`/`0x3B`
requests carry `uint8 has_state | int64_be valpred | int64_be index`;
responses append the updated state after `uint32_be out_len | bytes`.

## 6. Encoder and decoder differential results

*(Counts corrected in Phase 9 to match the actual emissions in
`test_adpcm_oracle.py`; the test results themselves were valid and
unchanged.)*

- Curated oracle cases: **317** — 29 encoder (16 per-width + 13
  edge/error: boundary, alternating, abrupt, repeated, zero,
  small-diff fragments; empty, one/three-sample odd cases; continued
  and boundary states; all error paths) + 288 decoder (the exhaustive
  **256 byte values** at width 2 + 24 sampled width-1/3/4 cases + 8
  sequence/state/error cases).
- Randomized cases: **115** — 80 encoder (4 widths × 20) + 35 decoder
  (20 width-2 + 15 width-1/3/4 sequences; seed **20260610**).
- **Methodology**: the 256 decoder bytes are tested as **256
  independent CLI requests** (one emission per byte, each compared 1:1
  against the oracle), not one combined input; the same 256 bytes also
  appear as 256 independent golden-vector cases replayed individually.
- Mismatches: **0**; exception mismatches: **0** (exact messages).
- Comparison: exact output bytes and exact `(valpred, index)` state.

## 7. Golden vector counts and SHA-256

- Before: **952**. After: **1277** (… + **325** `p8-` cases:
  lin2adpcm 21, adpcm2lin 304).
- Existing vectors untouched; generator deterministic; `--check`
  passes.
- Bundle sha256:
  `1ccaeeb01921ac27343a5f8406c442a9843773be02e4b17a10c84353886b7a39`.

## 8. Chunk-boundary and odd-sample findings

- **Encoder, even chunks**: concatenated output equals the whole
  encoding; final state equal (verified against the reference and
  through the CLI with state round-trips).
- **Encoder, odd chunks**: NOT byte-equal to the whole encoding — each
  call drops its own odd trailing nibble and starts a fresh buffer
  (e.g. `[1,2,3,4]` whole = `1111`; 3+1 chunks give `11` + ``). State
  still advances per sample. Documented, not forced into a false
  invariant.
- **Decoder**: chunks of any size compose exactly (verified through the
  CLI with 2-byte and 1-byte chunks).

## 9. Native Mojo test count

`test_adpcm.mojo`: **11 tests run: 11 passed, 0 failed**.

## 10. Python test count

Audioop compatibility suite: **136 passed** (was 119; +17: CLI 11,
oracle 3, vectors 3).

## 11. Full repository test results

| Check | Command | Result |
| --- | --- | --- |
| Native suites (samples/arithmetic/statistics/peak/channels/ratecv/g711) | build + run each | exit 0; 13/19/13/15/11/11/12 passed |
| Native adpcm | build + run via runner | exit 0; **11 passed** |
| Full runner | `.venv/bin/python scripts/run_all_tests.py` | exit 0; **all suites passed**; **30 native suites / 298 native tests**; **681 pytest passed** |
| Vector drift | `python_reference/.venv/bin/python .../generate_audioop_vectors.py --check` | exit 0; **1277 cases match** |

## 12. Ruff and formatting results

- `.venv/bin/ruff check .` → exit 0, `All checks passed!`
- `.venv/bin/ruff format --check .` → exit 0.
- `git diff --check` → exit 0.

## 13. Final 26-operation API inventory

| # | Operation | Module | CLI opcode | Oracle | Vectors | Native tests |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | add | arithmetic | 0x22 | ✓ | ✓ | ✓ |
| 2 | bias | arithmetic | 0x23 | ✓ | ✓ | ✓ |
| 3 | mul | arithmetic | 0x24 | ✓ | ✓ | ✓ |
| 4 | reverse | arithmetic | 0x25 | ✓ | ✓ | ✓ |
| 5 | byteswap | arithmetic | 0x26 | ✓ | ✓ | ✓ |
| 6 | lin2lin | arithmetic | 0x27 | ✓ | ✓ | ✓ |
| 7 | getsample | statistics | 0x28 | ✓ | ✓ | ✓ |
| 8 | max | statistics | 0x29 | ✓ | ✓ | ✓ |
| 9 | minmax | statistics | 0x2A | ✓ | ✓ | ✓ |
| 10 | avg | statistics | 0x2B | ✓ | ✓ | ✓ |
| 11 | rms | statistics | 0x2C | ✓ | ✓ | ✓ |
| 12 | cross | statistics | 0x2D | ✓ | ✓ | ✓ |
| 13 | avgpp | peak_analysis | 0x2E | ✓ | ✓ | ✓ |
| 14 | maxpp | peak_analysis | 0x2F | ✓ | ✓ | ✓ |
| 15 | findmax | peak_analysis | 0x30 | ✓ | ✓ | ✓ |
| 16 | findfactor | peak_analysis | 0x31 | ✓ | ✓ | ✓ |
| 17 | findfit | peak_analysis | 0x32 | ✓ | ✓ | ✓ |
| 18 | tomono | channels | 0x33 | ✓ | ✓ | ✓ |
| 19 | tostereo | channels | 0x34 | ✓ | ✓ | ✓ |
| 20 | ratecv | ratecv | 0x35 | ✓ | ✓ | ✓ |
| 21 | lin2alaw | g711 | 0x36 | ✓ | ✓ | ✓ |
| 22 | alaw2lin | g711 | 0x37 | ✓ | ✓ | ✓ |
| 23 | lin2ulaw | g711 | 0x38 | ✓ | ✓ | ✓ |
| 24 | ulaw2lin | g711 | 0x39 | ✓ | ✓ | ✓ |
| 25 | lin2adpcm | adpcm | 0x3A | ✓ | ✓ | ✓ |
| 26 | adpcm2lin | adpcm | 0x3B | ✓ | ✓ | ✓ |

**26/26 implemented** — verified against the actual repository
inventory (exports, 26 operation opcodes `0x22`–`0x3B`, 28 oracle
operations including the Phase 1 sample layer, 26 operation groups in
the vector corpus, 8 native test suites with 105 audioop test
functions, Python compatibility suites, and per-phase documentation).

## 14. Known deviations and limitations

- Reference-only state type errors (`TypeError state must be a tuple
  or None`, function-prefixed illegal-state errors) are unreachable
  through the CLI's structural state block; documented.
- Encoder odd-chunk concatenation is not byte-equal to whole encoding
  (CPython behaviour, documented and tested, not forced).
- No benchmarks (deferred per instructions).

## 15. Git branch, HEAD, and working-tree status

- Branch: `main`. HEAD: `9118860 feat(audioop): implement G.711 A-law
  and mu-law codecs` — the Phase 7 work committed between sessions,
  outside this phase.
- Working tree: 15 modified + 7 created files, 0 deleted;
  `git diff --check` clean.

## 16. Confirmation

**No commit, push, tag, or release was performed during this phase.**

## 17. Phase verdict

**PHASE 8 COMPLETE — READY FOR REVIEW.**
