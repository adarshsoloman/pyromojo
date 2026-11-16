# Changelog

All notable changes to the `audioop` native Mojo port will be documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
[Semantic Versioning](https://semver.org/).

## [audioop-v0.1.0] — 2026-11-16 (pre-release, pending tag)

Initial native Mojo implementation of CPython 3.12's `audioop` module — **26/26 public operations**, verified and benchmarked.

### Added

- **Sample representation** (`samples.mojo`) — widths 1–4, native byte order, fragment validation, signed decode/encode with exact sign extension and 24-bit handling. Validated at all four widths, empty fragments, misaligned inputs, and{min,max} boundaries (`test_samples.mojo`, 13 tests).
- **Arithmetic** (`arithmetic.mojo`) — `add` (saturating), `bias` (wrapping), `mul` (clamp-then-floor), `reverse`, `byteswap`, `lin2lin` (shift-based width conversion). Validated across all widths, empty inputs, and saturation boundaries (`test_arithmetic.mojo`, 19 tests).
- **Statistics** (`statistics.mojo`) — `getsample`, `max` (unsigned absolute), `minmax` (signed pair with sentinel), `avg` (`floor(sum/n)`), `rms` (truncated `sqrt(mean(square))`), `cross` (zero-crossing count). Validated at every width, boundary samples, empty/single-sample inputs, and zero-heavy sequences (`test_statistics.mojo`, 13 tests).
- **Peak analysis and matching** (`peak_analysis.mojo`) — `avgpp`, `maxpp`, `findmax`, `findfactor`, `findfit` with fixed 16-bit search windows, exact floating-point matching, and tie-breaking (`test_peak_analysis.mojo`, 15 tests).
- **Channel operations** (`channels.mojo`) — `tomono` and `tostereo` with integer conversion via the shared sample layer (`test_channels.mojo`, 11 tests).
- **Stateful sample-rate conversion** (`ratecv.mojo`) — `ratecv(fragment, width, nchannels, inrate, outrate, state, weightA, weightB)` with exact phase/filter implementation, GCD-reduced rates/weights, chunk-continuity and empty-chunk semantics (`test_ratecv.mojo`, 11 tests).
- **G.711 codecs** (`g711.mojo`) — `lin2alaw`, `alaw2lin`, `lin2ulaw`, `ulaw2lin` with SoX-derived lookup tables transcribed from the reference (`test_g711.mojo`, 12 tests).
- **Intel/DVI ADPCM** (`adpcm.mojo`) — `lin2adpcm` and `adpcm2lin` with explicit predictor/index updates, nibble ordering, odd-sample handling, and chunk-boundary semantics (`test_adpcm.mojo`, 11 tests).
- **Native CLI and binary protocol** (`cli.mojo`, `protocol.mojo`) — 26 operation opcodes `0x22`–`0x3B` plus 4 infrastructure opcodes, framed as `uint32_be length | body` / `uint32_be length | uint8 status | payload`. See [`docs/cli-opcode-registry.md`](docs/cli-opcode-registry.md).
- **CPython reference oracle** (`python_reference/oracle_samples.py`) and **1,277 golden vectors** (`tests/vectors/audioop_vectors.json`) — deterministic, drift-checked via `--check`.
- **Integrated three-path benchmarks** (`benchmarks/`) — pure Python vs CPython 3.12.3 C vs native Mojo (in-process, 25 samples/cell, 2 runs, median-of-medians) over 250 deterministic workloads plus a separately measured CLI path. Raw results, summary, and environment metadata are retained under `benchmarks/results/`.

### Compatibility

- Verified against **CPython 3.12.3** (isolated venv). All error messages reproduced verbatim where applicable.
- **Known deviations (documented):**
  - `mul`/`tomono`/`tostereo` map NaN results to 0; CPython's `(int)NaN` is undefined (width-4 differs at the byte level; excluded from equality assertions).
  - CLI-only state representations differ structurally from the reference's Python tuples (wire formats in `docs/ratecv.md` / `docs/adpcm.md`); semantics are preserved.
  - ADPCM encoder odd-chunk concatenation is not byte-equal to whole encoding (CPython behaviour, documented).

See [`RELEASE_READINESS.md`](RELEASE_READINESS.md) and [`PHASE9_RESULTS.md`](PHASE9_RESULTS.md) (all 26 operations PASS).

### Toolchain

- Mojo **1.2.0** (`2016d0cd`) via `uv` (`.venv/bin/mojo`).
- Host Python **3.13.14**; reference CPython **3.12.3**.
- `uv`, `ruff`, `pytest` as configured in `pyproject.toml`.

[audioop-v0.1.0]: https://github.com/adarshsoloman/pyromojo/releases/tag/audioop-v0.1.0
