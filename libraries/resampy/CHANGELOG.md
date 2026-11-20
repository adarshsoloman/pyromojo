# Changelog

All notable changes to the `resampy` native Mojo port will be documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
[Semantic Versioning](https://semver.org/).

## resampy-v0.1.0 — unreleased (BLOCKED — LICENSING)

Initial native Mojo implementation of the supported `resampy` 0.4.3
`resample` contract for 1-D Float64 signals with integer sampling rates.
Implementation, numerical verification, and benchmarks are complete. Public
release is **blocked** because written clearance to redistribute the production
`kaiser_fast` coefficient table has not been obtained; the repository ships
only a synthetic coefficient resource.

### Added

- **Signal and output layers** (`signal.mojo`, `output.mojo`) — owned
  `List[Float64]` signals, borrowed views, explicit copies, zero-initialized
  outputs, bounds-checked access, and a 1,000,000-sample output cap. Validated
  by 23 native tests.
- **Strict filter-resource loader** (`coefficients.mojo`) — two-file JSON +
  raw little-endian Float64 format, ordered schema/dtype/endianness/metadata
  validation, SHA-256 integrity checking, and bounded reads. The loader accepts
  an externally supplied licensed resource; no upstream coefficient table is
  committed. Validated by 19 native tests.
- **Float, JSON, SHA-256, and comparison utilities** (`float_codec.mojo`,
  `json_codec.mojo`, `sha256.mojo`, `numerical_compare.mojo`,
  `golden_vector.mojo`) — exact IEEE-754 round-tripping, strict flat-JSON
  parsing, SHA-256, semantic NaN/Inf comparison, and validated golden-vector
  parsing/serialization. Validated by 76 native tests.
- **Windowed-sinc kernel** (`resample.mojo`) — `resample` and
  `output_length` with upstream truncating length, `scale = min(1, ratio)`,
  first-order half-window interpolation, forward-difference table, sequential
  Float64 accumulation, zero-extension boundaries, downsampling gain
  compensation, equal-rate exact copy, and `--fp-mode contract=off`. Validated
  by 23 native tests.
- **Framed CLI and protocol** (`cli.mojo`, `protocol.mojo`) — `0x01`/`0x02`
  infrastructure opcodes, representation/verification opcodes `0x20`–`0x29`,
  and `OP_RESAMPLE = 0x2A`. Requests are length-framed; malformed requests
  return a `STATUS_ERROR` frame without crashing the session.
- **Golden vectors** — 17 deterministic resampling cases from the independent
  stdlib reference plus 12 representation cases, with a `--check` drift gate.
  Expected resampling outputs are **not** upstream Resampy output and use
  synthetic coefficients only.
- **Verification suites** — 144 native Mojo test functions and 90 Python
  compatibility tests, including 19 pinned upstream `kaiser_fast` parity tests.
  The upstream tests read the installed package's coefficient table into a
  temporary directory at runtime and never commit it.
- **Four-path benchmark suite** (`benchmarks/`) — upstream warm, upstream cold
  (fresh-process JIT), native in-process, and native CLI over 275 measured
  cells, 5 documented exclusions, 2 independent runs, 5 warmups, and 25
  samples per path. Every cell passed an exact SHA-256 output gate.

### Compatibility

- Verified against **resampy 0.4.3** (commit
  `7c484f8eec54b87e8f566578dc3e48a2be81cc80`, ISC) with NumPy 2.5.5,
  Numba 0.68.1, and llvmlite 0.50.0.
- Finite outputs were bit-identical to upstream across the 19 committed
  parity tests and a 1,684-case finite rate/signal sweep. Non-finite outputs
  matched position-wise (NaN and infinity sign).
- **Documented deviations:** empty or truncating-to-zero output returns an
  empty buffer where upstream raises `ValueError`; rates are integer-only;
  output is capped at 1,000,000 samples; filter precision and finite
  coefficients are validated; Mojo raises `Error` and the CLI returns
  `STATUS_ERROR` instead of Python exception types.
- **Deferred:** `kaiser_best`, `resample_nu`, N-D/arbitrary `axis`, float32,
  complex, integer-to-float conversion, `parallel`, runtime `sinc_window` and
  callable filters, non-integer sampling rates, and Python-to-Mojo interop.

### Performance

- Native in-process medians were **0.13x–0.25x** upstream warm medians across
  rate-pair aggregates, i.e. upstream is faster on this host. The 1:1 case is
  dominated by native per-call allocation.
- Native CLI medians were **15x–33x** native in-process medians, except 1:1,
  which is dominated by the ~16.7 ms process floor.
- No optimization work was performed and no universal-speedup claim is made.
  See [`benchmarks/reports/BENCHMARK_REPORT.md`](benchmarks/reports/BENCHMARK_REPORT.md).

### Toolchain

- Mojo **1.2.0** (`2016d0cd`) via `uv` (`.venv/bin/mojo`).
- Host Python **3.13.14**; pinned upstream reference **resampy 0.4.3**.
- Numerical builds use `--fp-mode contract=off`.

### Release blocker

- `kaiser_fast` coefficient redistribution has not been cleared. The
  unresolved requirement is recorded in
  [`docs/licensing-audit.md`](docs/licensing-audit.md) §6,
  [`RELEASE_READINESS.md`](RELEASE_READINESS.md) §8, and
  [`RELEASE_HANDOFF.md`](RELEASE_HANDOFF.md) §5. No legal conclusion is made
  by this project.
