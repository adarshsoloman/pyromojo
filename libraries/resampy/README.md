# resampy (Mojo Port)

## Status: v0.1.0 release candidate — BLOCKED on coefficient licensing

The native implementation, upstream parity, and benchmarks are complete for
the supported contract: **1-D Float64, integer sampling rates, `kaiser_fast`
supplied as a validated external resource, sequential execution**. The
repository ships only a synthetic coefficient resource. Public release is
blocked because written clearance to redistribute the production
`kaiser_fast` table has not been obtained. See
[Release readiness](RELEASE_READINESS.md) §8 and
[licensing audit](docs/licensing-audit.md) §6.

## What is implemented

- `resample` and `output_length` in `mojo/mojo_resampy/resample.mojo`.
- Windowed-sinc interpolation with upstream length truncation,
  `scale = min(1, ratio)`, first-order half-window interpolation, a
  forward-difference table, zero-extension boundaries, downsampling gain
  compensation, and equal-rate exact copy.
- Integer rates with integer or non-integer rate ratios (for example
  `44100 -> 48000`). Non-integer sampling rates are out of scope.
- A strict two-file filter loader (JSON metadata + little-endian Float64
  payload, SHA-256 checked, bounded reads). Any licensed production resource
  can be supplied without changing the kernel.
- A framed CLI with representation/verification opcodes `0x20`–`0x29` and
  `OP_RESAMPLE = 0x2A`.
- 17 resampling golden vectors from the independent stdlib reference and 12
  representation vectors, plus a `--check` drift gate.
- 144 native Mojo test functions and 90 Python compatibility tests.

## Reference compatibility

Reference: **resampy 0.4.3**, commit
`7c484f8eec54b87e8f566578dc3e48a2be81cc80`, ISC. Test runtime: NumPy 2.5.5,
Numba 0.68.1, llvmlite 0.50.0.

- 19 committed upstream parity tests pass (15 finite signal/rate cases plus
  4 non-finite/subnormal cases).
- Finite outputs are **bit-identical** (`atol = rtol = 0`) across the parity
  tests and a 1,684-case finite sweep.
- Non-finite outputs match position-wise (NaN and infinity sign).
- Upstream source is not vendored. The parity test reads the installed
  package's coefficient table into a temporary directory and deletes it.

Local tests use exact equality against the independent stdlib reference. The
historical `atol = rtol = 1e-9` proposal in `docs/api-scope.md` §6 is not the
adopted gate.

## Documented deviations

| Behaviour | Upstream 0.4.3 | This port |
|---|---|---|
| Empty / truncating-to-zero output | `ValueError` | Empty buffer; CLI success with empty payload |
| Non-integer sampling rates | Supported | Out of scope; integer rates only |
| Output length cap | No explicit cap observed | Rejected above 1,000,000 samples |
| Filter validation | Not matched | Precision, count, and finite-coefficient checks |
| Error type | Python exceptions | Mojo `Error`; CLI `STATUS_ERROR` |
| N-D / axis / float32 / complex / parallel | Supported | Deferred or out of scope |

Other deferred features: `kaiser_best`, `resample_nu`, integer-to-float
conversion, `sinc_window`, callable filters, and Python-to-Mojo interop.

## Benchmarks

Four paths: upstream warm, upstream cold (fresh-process JIT), native
in-process, and native CLI. 275 measured cells, 5 documented exclusions,
2 independent runs, 5 warmups, 25 samples per path, median-of-medians, seed
`20260610`.

- Correctness gate: **275/275 PASS** by exact SHA-256 of the little-endian
  Float64 output; output lengths match exactly.
- Native in-process vs upstream warm: `0.13x–0.25x` across rate-pair
  aggregates. Upstream warm is faster on this host; 1:1 is native
  allocation-floor dominated.
- CLI overhead: `15x–33x` native in-process; 1:1 is dominated by the
  `~16.7 ms` process floor.
- Cold costs: upstream first call `~455 ms`; native bench build `~1.63 s`;
  native CLI build `~1.98 s`.
- Python-to-Mojo interop is unavailable and reported as a gap.

No optimization work was performed and no universal-speedup claim is made.
Full tables and raw data:
[`benchmarks/reports/BENCHMARK_REPORT.md`](benchmarks/reports/BENCHMARK_REPORT.md).

## Build and test

Run from the repository root:

```bash
uv sync --extra dev
.venv/bin/mojo build libraries/resampy/mojo/cli.mojo \
  -I libraries/resampy/mojo --fp-mode contract=off -o build/resampy_cli
.venv/bin/python libraries/resampy/tests/run_phase3_tests.py
.venv/bin/python scripts/run_all_tests.py
.venv/bin/python libraries/resampy/tests/vectors/generate_resample_vectors.py --check
```

Benchmarks:

```bash
.venv/bin/python libraries/resampy/benchmarks/run_benchmarks.py
```

All numerical builds must use `--fp-mode contract=off`; the default
`contract=fast` can change Float64 results.

## Licensing and release

- Repository license: Apache-2.0.
- Upstream license: ISC; the notice is retained in
  [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).
- The only committed coefficient data is the synthetic 8-coefficient resource.
- Production coefficient redistribution is unresolved. This project makes no
  legal conclusion and does not assume the ISC license settles the data-file
  question.
- **Do not publish a release or distribute the production table until written
  clearance is recorded.** Exact requirement:
  [`RELEASE_READINESS.md`](RELEASE_READINESS.md) §8.

## Documents

- [API scope](docs/api-scope.md) · [Resampling design](docs/resampling-design.md)
- [Reference audit](docs/reference-audit.md) · [Licensing audit](docs/licensing-audit.md)
- [Representation design](docs/representation-design.md) · [Toolchain feasibility](docs/toolchain-feasibility.md)
- [Benchmark design](docs/benchmark-design.md) · [Benchmark report](benchmarks/reports/BENCHMARK_REPORT.md)
- [Release readiness](RELEASE_READINESS.md) · [Changelog](CHANGELOG.md) · [Release notes draft](RELEASE_NOTES_v0.1.0.md)
