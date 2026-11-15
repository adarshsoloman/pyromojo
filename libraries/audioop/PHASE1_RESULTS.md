# Phase 1 Results — Sample Representation Layer

Status: **complete**. Scope was the internal signed-sample representation only.
No public audioop operation is implemented.

## 1. Deliverables

| Path | Purpose |
| --- | --- |
| `mojo/mojo_audioop/samples.mojo` | Width/fragment validation, sample bounds, single-sample and fragment decode/encode, native byte-order detection |
| `mojo/mojo_audioop/protocol.mojo` | Length-prefixed frame I/O shared by the CLI and tests |
| `mojo/mojo_audioop/__init__.mojo` | Re-exports the sample and protocol symbols |
| `mojo/cli.mojo` | Batch test harness: `0x20` decode, `0x21` encode, errors as frames |
| `tests/mojo/test_samples.mojo` | 13 native tests |
| `tests/python_compat/{conftest,support}.py` | CLI build fixture, framing helpers, reference oracle fixture |
| `tests/python_compat/test_samples_{cli,oracle,vectors}.py` | 20 Python compatibility tests |
| `python_reference/oracle_samples.py` | CPython 3.12 batch oracle (`getsample`, `int.to_bytes` + `getsample` round-trip) |
| `tests/vectors/audioop_vectors.json` | 66 cases (42 preserved + 24 sample-layer) |
| `docs/sample-representation.md` | Layer contract and limits |

## 2. Representation

- Widths 1–4 bytes, signed two's complement.
- Decoded samples are `Int32`; all four ranges fit.
- Encoding accepts `Int64` so values just outside the 32-bit range
  (`±2147483649`) are representable and rejected rather than wrapped by a
  narrower type.
- Byte order is host-native, matching the reference's direct word loads.
  No endianness parameter exists in the frozen API.
- Native order is detected with `bitcast[DType.uint8, 2](UInt16(1))` from
  `std.memory`; no pointer casts and no hard-coded endianness.
- 24-bit samples are sign-extended via bit 23: `raw - 2^24` when the sign
  bit is set. Encoding masks to 24 bits.
- One `_load_sample`/`_store_sample` pair handles all widths and both
  byte orders; there is no per-width duplicated byte logic.

## 3. Validation and errors

Validation order matches the reference: width (`audioop_check_size`) then
frame alignment (`audioop_check_parameters`).

| Condition | Result |
| --- | --- |
| Width not in 1–4 | `Size should be 1, 2, 3 or 4` |
| Length not a multiple of width | `not a whole number of frames` |
| Sample index outside `0..count-1` | `Index out of range` |
| Empty fragment | valid, zero samples |
| Encode value outside width range | `sample value <v> out of range for width <w>` |

The encoder has no reference counterpart; refusing out-of-range values is
the documented Phase 0 decision. Fragment encoding validates every value
before writing, so failures never produce partial output.

## 4. CLI harness

Standard PyroMojo framing: `uint32_be length | body`, response body
`uint8 status | payload`. Opcodes `0x20`/`0x21`; empty frames and unknown
opcodes return error frames. Truncated headers/bodies and frames over
64 MiB are fatal. Request-level errors do not stop processing of following
frames, which lets one process answer a whole batch.

## 5. Verification

| Check | Command | Result |
| --- | --- | --- |
| Native suite | `mojo build libraries/audioop/tests/mojo/test_samples.mojo -I libraries/audioop/mojo -I libraries/audioop/tests/mojo` then run | **13 passed, 0 failed** |
| Python compat | `.venv/bin/python -m pytest libraries/audioop/tests/python_compat -q` | **20 passed** |
| Full repository | `.venv/bin/python scripts/run_all_tests.py` | **all suites passed**; pytest **565 passed** |
| Vector drift | `libraries/audioop/python_reference/.venv/bin/python .../generate_audioop_vectors.py --check` | **66 cases match**, sha256 `7764993554df87001dc2aa2a59920e99c10c16551217531eda3da2c516ee5f5d` |
| Lint | `.venv/bin/ruff check .` | clean |
| Format | `.venv/bin/ruff format --check .` | clean |
| Whitespace | `git diff --check` | clean |

Differential coverage details:

- Decode oracle: `audioop.getsample` over every whole sample; validation
  side effect via `audioop.max` to obtain the reference error messages.
- Encode oracle: `int.to_bytes(width, sys.byteorder, signed=True)`, then
  decoded back with `getsample` to prove the bytes mean what was intended.
- Curated cases per width: both endpoints, `0`, `-1`, `1`, empty fragment,
  error cases.
- Randomized: seed `20260610` (decode) and `20260611` (encode), 50
  fragments/vectors per width, lengths `0, 1, 2, 3, 8, 17` samples.
- Golden vectors: all 24 sample cases replayed through the CLI, including
  slice boundaries and both error families.

## 6. Deliberate scope limits

- Only the internal sample layer; all 26 public functions remain
  unimplemented.
- No buffer-protocol/generic input support; fragments are byte spans.
- Native order only; the frozen API has no endianness option.
- No benchmarks or performance tuning in this phase.
- Python compatibility tests build the CLI on demand; the repository's CI
  still runs only ruff and Python tests, so Mojo execution is not yet a CI
  gate.

## 7. Phase 0 decisions honoured

- Frozen 26-function surface untouched; no other library modified.
- Exact reference error messages and sentinels preserved.
- Sample widths, empty-fragment validity, and alignment rules match the
  reference audit.
- No commit, push, tag, or release performed.
- Licensing posture unchanged: independent implementation, no vendored
  upstream source.

## 8. Conclusion

The sample representation layer is complete, native-tested, differentially
tested against CPython 3.12, covered by regenerable golden vectors, and
documented. It provides a stable base for Phase 2 without expanding the
public API or changing any Phase 0 decision.
