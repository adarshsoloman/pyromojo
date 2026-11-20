# resampy (Mojo Port)

## Status: PHASE 5 COMPLETE — production `kaiser_fast` parity verified

Phase 4 adds a whole-buffer, 1-D Float64 windowed-sinc `resample` kernel and
`output_length` (native Mojo and CLI opcode `0x2A`). Phase 3's representation,
loader, comparator, and golden-vector foundations are reused; Phase 4 extends
the framed CLI with opcode `0x2A` and filter-resource validation. Phase 4
accepts **integer sampling rates only**; non-integer rate ratios from integer
rates (for example `44100 -> 48000`) are supported.

Phase 5 installed Resampy 0.4.3 with NumPy and Numba in the test environment
and verified the native kernel against upstream `kaiser_fast` output. Finite
outputs were **bit-identical** across the committed 19-case upstream parity
test and a 1,684-case finite rate/signal sweep. The test builds its coefficient
resource at runtime from the installed upstream package; no upstream
coefficient table is copied into this repository. Redistributing a standalone
production coefficient resource still requires the licensing clearance tracked
in [licensing-audit.md](docs/licensing-audit.md) §6. See
[resampling design](docs/resampling-design.md) and the audits in `docs/`.

Build and test with `--fp-mode contract=off`; run
`.venv/bin/python libraries/resampy/tests/run_phase3_tests.py` from the repo root.
The repo-wide `scripts/run_all_tests.py` independently includes the Resampy
vector drift check, contract-off CLI build, and native/Python suites.

## Library description

High-quality audio resampling: band-limited interpolation for changing the
sample rate of a signal, with selectable filter characteristics.

## Original Python package

- Package: `resampy`
- Reference target: 0.4.3, ISC. The test environment uses `resampy==0.4.3`,
  `numpy==2.5.5`, `numba==0.68.1`, and `llvmlite==0.50.0`, installed explicitly
  for Phase 5; see
  [licensing-audit.md](docs/licensing-audit.md) for differential licensing and
  unresolved coefficient-provenance questions.
- Upstream source is not vendored; the parity test uses the installed package
  and writes its filter table to a temporary directory only.

## Mojo implementation

Phase 4 provides native band-limited resampling over sample buffers, with
documented filter design, phase handling, and edge/padding treatment. Phase 4
local Mojo/reference tests use exact equality (`atol = 0.0`, `rtol = 0.0`).
The `atol = rtol = 1e-9` policy in `api-scope.md` §6 is a historical Phase 1
proposal, not the gate used in Phase 4 or Phase 5. Phase 5 measured
bit-identical finite output against upstream Resampy 0.4.3 `kaiser_fast`.

## Compatibility objectives

- Match upstream Resampy 0.4.3 `kaiser_fast` output for supported rates.
- Match output length and boundary handling for whole-buffer resampling.
- Match behaviour for supported 1-D/mono input; multi-channel remains deferred.
- Document any excluded filter modes or parameters.

## Testing requirements

- Mojo unit tests for rate ratios, signal lengths, and boundary handling.
- Python compatibility tests against the independent local reference with
  exact equality (`atol = rtol = 0`).
- Pinned-upstream parity tests using the installed Resampy 0.4.3 package;
  finite outputs use exact equality, non-finite outputs use semantic equality.
- Golden vectors for representative rates and signals, including silence and
  impulses.

## Benchmarking requirements

- Short and long signals, upsampling and downsampling, and mono input;
  multi-channel when support lands.
- Three-way comparison: Python reference, native Mojo, Mojo via Python interop.
- Cold compilation and warm execution reported separately.

## Current status

PHASE 5 COMPLETE — the Phase 4 kernel remains 1-D Float64 whole-buffer
resampling with integer sampling rates. Non-integer rates are out of scope;
non-integer ratios from integer rates are supported. Production
`kaiser_fast` parity is verified against Resampy 0.4.3. The committed synthetic
resource remains the only coefficient data in the repository; the upstream
resource is generated in a temporary directory during the upstream parity test.
Shipping a standalone production coefficient resource remains conditional on
the licensing review. Multi-channel/N-D support and benchmarks remain pending.
