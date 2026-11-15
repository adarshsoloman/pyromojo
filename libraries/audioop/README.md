# audioop (Mojo Port)

## Status: PHASE 2 COMPLETE (6 of 26 operations)

## Library description

Legacy operations on raw audio samples: sample-width conversion, channel
conversion, gain, bias, clipping, RMS, peak, and related transforms. The module
was part of the Python standard library and was removed in Python 3.13 under
PEP 594, so a native implementation is useful for code maintaining that
behaviour.

## Original Python package

- Reference: CPython **3.12.3** `audioop` (C extension). The module was
  deprecated in 3.11 and removed in 3.13, so the reference is used through an
  isolated 3.12 interpreter in `python_reference/.venv`.
- Provenance, hashes, build-equivalence proof, and license chain:
  [`docs/reference-audit.md`](docs/reference-audit.md) and
  [`docs/licensing-audit.md`](docs/licensing-audit.md).
- Upstream source is not vendored; the port is independent and no code was
  copied.

## Planned Mojo implementation

Native sample-buffer transforms over 8-, 16-, 24-, and 32-bit integer
samples. Phase 0 froze the v0.1 scope to all 26 reference functions, native
byte order (no endianness parameter exists upstream), bytes fragments, and
reference-compatible sentinels and error messages. See
[`docs/api-scope.md`](docs/api-scope.md) and
[`PHASE0_RESULTS.md`](PHASE0_RESULTS.md).

Phase 1 implements the internal signed-sample layer used by every
operation: width/fragment validation, single-sample and fragment
decode/encode, native byte order, and 24-bit sign extension. See
[`docs/sample-representation.md`](docs/sample-representation.md) and
[`PHASE1_RESULTS.md`](PHASE1_RESULTS.md).

Phase 2 implements the first six public operations on that layer:
`add` (saturating), `bias` (wrapping), `mul` (clamp-then-floor), `reverse`,
`byteswap`, and `lin2lin`. The remaining 20 public functions are **not
implemented yet**. See [`docs/arithmetic-operations.md`](docs/arithmetic-operations.md)
and [`PHASE2_RESULTS.md`](PHASE2_RESULTS.md).

## Compatibility objectives

- Match reference results for supported sample widths and operations.
- Preserve saturating and wrapping behaviour exactly where the reference
  distinguishes them.
- Handle empty buffers, odd buffer lengths, and fragment counts as the
  reference does.
- Document any operation intentionally excluded from the port.

## Testing requirements

- Mojo unit tests for each supported operation and sample width.
- Python compatibility tests against the reference implementation.
- Golden vectors including boundary amplitudes, silence, and malformed buffer
  lengths. The corpus now has 116 cases: the original 42 function cases,
  24 sample-representation cases, and 50 Phase 2 arithmetic cases, generated
  by the pinned reference and guarded by `--check` drift detection.

## Benchmarking requirements

- Short and long buffers, mono and multi-channel, from 0 frames through
  1 Mi-frame workloads.
- Three-way comparison: naive Python, reference C, native Mojo (no Python
  interop path in v0.1).
- Cold compilation and warm execution reported separately. The methodology is
  fixed in [`docs/benchmark-design.md`](docs/benchmark-design.md); no
  benchmarks have been run yet.

## Current status

Phase 2 complete: six arithmetic/fragment operations with native tests,
CPython 3.12 differential tests, golden vectors, and documentation.
20 public operations remain unimplemented. Results:
[`PHASE2_RESULTS.md`](PHASE2_RESULTS.md); earlier evidence remains in
[`PHASE1_RESULTS.md`](PHASE1_RESULTS.md) and
[`PHASE0_RESULTS.md`](PHASE0_RESULTS.md).
