# Phase 7 Results — G.711 A-law and μ-law Codecs

Status: **complete**. `lin2alaw`, `alaw2lin`, `lin2ulaw`, `ulaw2lin`
implemented natively; `lin2adpcm`/`adpcm2lin` remain.

## 1. Implementation summary

- `mojo/mojo_audioop/g711.mojo` (new): the four operations plus
  `_linear2alaw`/`_linear2ulaw` (reference `st_linear2alaw` /
  `st_14linear2ulaw`), `_search`, and the two 256-entry decoder tables
  embedded verbatim from the reference source
  (`comptime StaticTuple[Int16, 256]`). Reuses
  `validate_fragment`/`validate_width`/`decode_fragment`/
  `encode_fragment`; no byte logic duplicated; no Phase 1–6 code
  modified.
- `mojo/cli.mojo` + `protocol.mojo` (modified): opcodes `0x36`–`0x39`;
  earlier opcodes untouched.
- `mojo/mojo_audioop/__init__.mojo` (modified): re-exports the four ops.
- `python_reference/oracle_samples.py` (modified): oracle calls for all
  four operations (original `audioop` only).
- `python_reference/generate_audioop_vectors.py` (modified): 645 new
  `p7-` cases; prior 307 cases byte-identical.
- Native tests `tests/mojo/test_g711.mojo` (new, 12 tests); Python
  tests `test_g711_cli.py` (10), `test_g711_oracle.py` (3),
  `test_g711_vectors.py` (3).
- `scripts/run_all_tests.py` (modified): `test_g711` registered.
- Docs: `docs/g711.md` (new); `README.md` updated.

## 2. CPython source audit findings

- **Encoders** (`audioop_check_parameters` first): every sample is
  scaled to the 32-bit position (`GETSAMPLE32`), then shifted
  arithmetically to the codec range — total shifts
  `<<6/>>2/>>10/>>18` (mu-law) and `<<5/>>3/>>11/>>19` (A-law) for
  widths 1/2/3/4. Width-1 samples are scaled **up** (×64 / ×32), not
  truncated.
- **mu-law** (`st_14linear2ulaw`): magnitude, clip at 32635, add bias
  33, segment via `search(value, seg_uend, 8)`, pack
  `seg<<4 | (value >> (seg+1)) & 0xF`, XOR `0xFF` (non-negative) or
  `0x7F` (negative).
- **A-law** (`st_linear2alaw`): non-negative → mask `0xD5`; negative →
  mask `0x55` with `value = -value - 1`; segment via
  `search(value, seg_aend, 8)`; quantization bits
  `(value >> 1) & 0xF` (segments 0–1) or `(value >> seg) & 0xF`;
  output `aval ^ mask`.
- **Decoders** (`audioop_check_size` only — alignment NOT checked,
  probed with 1/3-byte inputs): each byte indexes the reference's
  256-entry `int16` table; `decoded16 * 2^16` is stored through
  `SETSAMPLE32` (top-aligned truncating shift: w1 `>>24`, w2 `>>16`,
  w3 `>>8`, w4 unchanged).

## 3. Supported widths per operation

All four operations support widths 1–4. Encoders require whole
samples; decoders accept any byte length.

## 4. Validation and exception behavior

Verbatim: `Size should be 1, 2, 3 or 4` (all four operations);
`not a whole number of frames` (encoders only). Empty input is valid
for all four (empty output).

## 5. Golden vector counts and hash

- Before: **307**. After: **952** (… + **645** `p7-` cases: lin2alaw 37,
  lin2ulaw 40, alaw2lin 284, ulaw2lin 284).
- Existing vectors untouched; generator deterministic; `--check`
  passes.
- Bundle sha256:
  `87fe4c8f9e45b471f69054540aae057d2e074b317f40645325ca39212b272930`.

## 6. Exhaustive decoder verification

- All **256 A-law codewords** at width 2: compared byte-for-byte
  against the reference (oracle differential + golden vectors) —
  0 mismatches.
- All **256 mu-law codewords** at width 2: same — 0 mismatches.
- Sampled codewords `{0x00, 0x55, 0x2A, 0x7F, 0x80, 0xD5, 0xAA, 0xFF}`
  at widths 1, 3 and 4 for both codecs — 0 mismatches (truncation
  behaviour per width verified).
- The embedded tables were additionally cross-checked against the
  reference at extraction time.

## 7. Differential test counts and seed

- Curated oracle cases: **578** (encoder basics/scaling/errors +
  512 exhaustive decoder codewords + sampled widths + sequences).
- Randomized encoder cases: **240** (4 widths × 30 × 2 encoders;
  seed **20260610**).
- Roundtrip chains: 48 full encode→decode comparisons against the
  reference (both codecs, all widths; seed **20260611** for the
  property inputs).
- Mismatches: **0**; exception mismatches: **0** (exact messages).

## 8. Native Mojo test count

`test_g711.mojo`: **12 tests run: 12 passed, 0 failed**.

## 9. Python test count

Audioop compatibility suite: **119 passed** (was 103; +16: CLI 10,
oracle 3, vectors 3).

## 10. Full repository test results

| Check | Command | Result |
| --- | --- | --- |
| Native suites (samples/arithmetic/statistics/peak/channels/ratecv) | build + run each | exit 0; 13/19/13/15/11/11 passed |
| Native g711 | build + run via runner | exit 0; **12 passed** |
| Full runner | `.venv/bin/python scripts/run_all_tests.py` | exit 0; **all suites passed**; **29 native suites / 287 native tests**; **664 pytest passed** |
| Vector drift | `python_reference/.venv/bin/python .../generate_audioop_vectors.py --check` | exit 0; **952 cases match** |

## 11. Ruff and formatting results

- `.venv/bin/ruff check .` → exit 0, `All checks passed!`
- `.venv/bin/ruff format --check .` → exit 0.
- `git diff --check` → exit 0.

## 12. Files created and modified

Created: `mojo/mojo_audioop/g711.mojo`, `tests/mojo/test_g711.mojo`,
`tests/python_compat/test_g711_cli.py`,
`tests/python_compat/test_g711_oracle.py`,
`tests/python_compat/test_g711_vectors.py`, `docs/g711.md`,
`PHASE7_RESULTS.md`.

Modified: `libraries/audioop/README.md`, `mojo/cli.mojo`,
`mojo/mojo_audioop/protocol.mojo`, `mojo/mojo_audioop/__init__.mojo`,
`python_reference/oracle_samples.py`,
`python_reference/generate_audioop_vectors.py`,
`tests/vectors/audioop_vectors.json`, `tests/python_compat/support.py`,
six vector-count test files, `scripts/run_all_tests.py`.

Deleted: none.

## 13. Known deviations and limitations

- None: all defined behaviour reproduced exactly; no port policy
  deviations were required (no NaN/UB paths in these codecs).
- `lin2adpcm`/`adpcm2lin` remain unimplemented (out of scope this
  phase).
- No benchmarks (deferred per instructions).

## 14. Git branch, HEAD, and working-tree status

- Branch: `main`. HEAD: `3d5337d feat(audioop): implement stateful
  sample rate conversion` — the Phase 6 work committed between
  sessions, outside this phase.
- Working tree: 14 modified + 7 created files, 0 deleted;
  `git diff --check` clean.

## 15. Confirmation

**No commit, push, tag, or release was performed during this phase.**

## 16. Phase verdict

**PHASE 7 COMPLETE — READY FOR REVIEW.**
