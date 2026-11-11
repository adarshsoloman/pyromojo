# MessagePack Phase 6 results: full compatibility and integration

Phase 6 integrates the completed native codec: the four-direction
compatibility matrix passes across all nine value families with both the C
and fallback reference decoders, the one remaining fundamental gap
(top-level nil/bool) is implemented, the batch CLI and every untrusted-input
path are audited, Python reference assumptions are pinned by tests, and
repository runners execute everything reproducibly. No benchmarking was done
in this phase.

## Files

Created:

- `scripts/run_all_tests.py` — repository runner: ruff lint, ruff format
  check, vector drift check, full pytest, then each native Mojo test
  executable built once and run. Fails fast with the offending command and
  output; nothing is skipped silently; requires the Mojo 1.2.x toolchain.
- `scripts/check_compatibility.py` — builds the native CLI once and runs the
  Python compatibility suite (`--library msgpack`; unknown names fail).
- `libraries/msgpack/tests/python_compat/test_reference_assumptions.py` —
  12 tests pinning reference behaviors the harness relies on (strict map
  keys, FormatError/ExtraData categories, truncation, duplicate-key
  collapse, out-of-range integers, float packing defaults).
- `libraries/msgpack/PHASE6_RESULTS.md` — this report.

Modified:

- `mojo/cli.mojo` — top-level nil/bool guards removed; the Phase 1 stub
  responses are retired. `UNIMPLEMENTED` remains only as a safety net.
- `mojo/mojo_msgpack/container.mojo` — encode depth-guard messages now name
  the exhausted limit instead of the configuration rule.
- `tests/mojo/test_regressions.mojo` — 10 tests: huge declared wire/model
  counts fail before allocation, exhausted depth names the container.
- `tests/python_compat/test_integer_compat.py`,
  `test_scalar_compat.py`, `test_container_compat.py`,
  `test_cli_protocol.py` — stub tests converted to positive nil/bool
  coverage plus a multi-request batch-mode ordering test.
- `libraries/msgpack/docs/batch_protocol.md` — nil/bool are first-class
  models; `UNIMPLEMENTED` documented as a safety net.
- `libraries/msgpack/README.md`, `README.md`, `docs/roadmap.md` — Phase 6
  status; Phase 2 runners checked off.

## Full compatibility matrix

For every integer, float32/64, string, binary, array, map, extension,
timestamp, and mixed/nested golden case:

1. Python reference control: `pack_model` reproduces the golden bytes and
   `decode_bytes` matches the tagged value (C decoder).
2. Golden bytes → Mojo `DECODE` → recursive model matches the tagged value →
   Mojo `ENCODE` reproduces the golden bytes exactly.
3. Mojo-encoded bytes decode identically under `msgpack` (C) and
   `msgpack.fallback`.
4. Mojo encode → Mojo decode roundtrips in the native generated-vector
   suite (19 array/map, 24 ext/timestamp, 80 scalar, 35 integer cases).

Exact byte equality holds everywhere except the documented reference-side
deviations: duplicate/unhashable map keys (Python `dict` cannot represent
them; asserted as ordered pairs via `object_pairs_hook`), wire-negative
extension codes (reference rejects, native accepts), and the depth-limit
asymmetry (128 native vs 1024 reference). Timestamp option decoding
(`timestamp=0/1/2/3`), datetime normalization, Float32 selection, and
fallback packer parity are each pinned by dedicated tests.

## CLI and protocol integration

- `ENCODE`/`DECODE` accept every model tag (`0x00`/`0x01`, `0x10`-`0x13`,
  `0x14`/`0x15`, `0x16`/`0x17`, `0xc0`/`0xc2`/`0xc3`); unknown tags,
  truncated frames, trailing bytes, and invalid lengths are `ERROR`.
- Recursive model framing is validated before decoding each child
  (`uint32` length, bounds check, exact consumption).
- stdout carries only length-prefixed protocol responses; diagnostics go to
  stderr; clean EOF between frames exits 0; framing errors emit one `ERROR`
  frame, a stderr diagnostic, and a non-zero exit.
- Batch mode is pinned: PING, ECHO, nil/bool DECODE/ENCODE, unknown opcode,
  empty body, and a nested-array DECODE in one process answer in order with
  no stderr output.
- No protocol change was needed: the Phase 5 wire format already covered
  every v0.1 value, so only the CLI guards were removed.

## Remaining API limitations

- Top-level nil and bool: **implemented** in this phase (valid fundamental
  values; existing model tags reused; nested behavior unchanged).
- Negative extension codes: **retained as a documented deviation**. The wire
  format allows signed int8; the reference restricts `ExtType` to 0..127.
  Pinned both ways (`error_negative_ext_code` plus native roundtrip tests).
- Depth limit 128 vs reference 1024: **retained**. The v0.1 scope requires
  bounded recursion; 128 is documented in the protocol and pinned at the
  127/128 boundary in both directions.
- Textual error responses: **retained**. Categories plus byte offsets are
  stable, asserted across all suites, and documented; no structured error
  object was added (unneeded for the CLI contract).

## Decoder safety audit findings

Reviewed every untrusted-input read in `integer.mojo`, `scalar.mojo`,
`container.mojo`, and `extension.mojo`:

- All reads are bounds-checked through `_require` before slicing; header
  bytes are validated before length fields are trusted.
- Length arithmetic cannot overflow: wire/model lengths are at most u32
  added to in-buffer offsets (64-bit `Int`); the single u64 shift
  (`nanoseconds << 34`) happens only after the 999999999 validation.
- Allocation follows validation in every path: declared counts are checked
  against `max_container_items` and remaining input before any `List`
  capacity is reserved (new regression tests pin 4-billion wire and model
  counts on both paths).
- Depth and item limits apply uniformly to wire decode, model decode,
  wire encode, and model append, including empty containers at the boundary.
- UTF-8 validation stays strict (`String(from_utf8)` only); timestamp
  nanoseconds are validated on decode, encode, and model paths; code `-1`
  with a bad length or bad nanoseconds is `invalid-timestamp`, never a
  generic extension.
- `0xc1` stays `invalid-marker`; every other byte value maps to exactly one
  documented outcome; trailing data is rejected at the exact offset.
- Two encode depth-guard messages named the configuration rule instead of
  the exhausted limit; fixed and pinned. No other audit gaps found.

## Python reference compatibility findings

Probed `msgpack==1.2.4` directly and pinned the results:

- `strict_map_key=True` is the default and rejects non-string keys in both
  implementations (messages differ; tests match the shared wording).
- `c1` raises `FormatError`, trailing bytes raise `ExtraData`, truncation
  raises `ValueError("incomplete input")` — identical categories in C and
  fallback.
- Without `object_pairs_hook`, duplicate keys collapse to the last value
  in both implementations (why the harness always uses the hook).
- Out-of-range integers raise `OverflowError` on pack in both packers;
  floats default to float64 and honor `use_single_float` in both packers.
- No hidden assumptions remain: the harness uses only `packb`/`unpackb`,
  `Packer`, `ExtType`, `Timestamp`, `object_pairs_hook`, `strict_map_key`,
  `use_bin_type`, `use_single_float`, `datetime`, and `timestamp=` — all
  pinned above.

## Repository test-runner integration

- `scripts/run_all_tests.py` resolves tools from `.venv/bin` (falling back
  to `uv run`), verifies `Mojo 1.2.x`, then runs lint, format check, drift
  check, full pytest, and all seven native executables. Verified end to end
  from the repository root: `run_all_tests: all suites passed`.
- `scripts/check_compatibility.py` builds `build/msgpack_cli` once and runs
  `libraries/msgpack/tests/python_compat`: `129 passed`.
- Reproducible from a clean checkout: `uv sync --extra dev` resolves 20
  packages; every command below was re-run after the sync.

## Test results

Toolchain: Mojo 1.2.0 (2016d0cd), Python 3.13.14, pytest 9.2.0,
ruff 0.17.4, msgpack 1.2.4, uv 0.12.5.

```text
$ uv sync --extra dev
Resolved 20 packages in 0.91ms
Checked 19 packages in 55ms

$ .venv/bin/pytest -q
129 passed in 11.02s

$ ./build/test_depth
Summary [ 0.040 ] 8 tests run: 8 passed , 0 failed , 0 skipped

$ ./build/test_integer_codec
Summary [ 0.039 ] 12 tests run: 12 passed , 0 failed , 0 skipped

$ ./build/test_generated_vectors
Summary [ 45.764 ] 12 tests run: 12 passed , 0 failed , 0 skipped

$ ./build/test_scalar_codec
Summary [ 0.451 ] 13 tests run: 13 passed , 0 failed , 0 skipped

$ ./build/test_container_codec
Summary [ 14.173 ] 13 tests run: 13 passed , 0 failed , 0 skipped

$ ./build/test_extension_codec
Summary [ 0.265 ] 11 tests run: 11 passed , 0 failed , 0 skipped

$ ./build/test_regressions
Summary [ 0.045 ] 10 tests run: 10 passed , 0 failed , 0 skipped

$ .venv/bin/ruff check libraries shared scripts
All checks passed!

$ .venv/bin/ruff format --check libraries shared scripts
26 files already formatted

$ .venv/bin/python libraries/msgpack/python_reference/generate_vectors.py --check
vectors: 162 cases, committed artifacts are current

$ .venv/bin/python scripts/run_all_tests.py
run_all_tests: all suites passed

$ .venv/bin/python scripts/check_compatibility.py
check_compatibility: all compatibility suites passed
```

The bundle and schema validate under the stdlib validator
(`test_bundle_is_structurally_valid`, part of the 129 pytest). The JSON
Schema Draft 2020-12 one-off check was not run: the optional `jsonschema`
package is not installed, and Phase 6 adds no new dependencies.

## Tests not run

- Benchmarks: out of scope for Phase 6 (no benchmark code was executed;
  `scripts/run_all_benchmarks.py` remains a placeholder).
- CI workflows: unchanged placeholders; local toolchain runs above are the
  verification record.
- `jsonschema` Draft 2020-12 validation: dependency unavailable; stdlib
  validation covers the same bundle in-suite.

## Remaining limitations

- Negative extension codes decode natively but are rejected by the
  reference (documented, pinned both ways).
- Native default depth limit is 128 vs the reference 1024 (documented,
  pinned at the boundary).
- Reference container/ext size caps are input-relative while native caps
  are absolute (1,000,000 items); both reject, with different messages.
- Decode errors are textual (category plus offset), not structured objects.
- Payloads are copied on encode and decode; no performance optimization or
  zero-copy path is claimed in this phase.
