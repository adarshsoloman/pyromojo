# audioop (Mojo Port)

**Native Mojo implementation of CPython's `audioop` — all 26 operations, verified and benchmarked.**

- **Status:** `audioop-v0.1.0` — 26/26 operations implemented and benchmarked (pre-release, pending release review)
- **Reference:** CPython **3.12.3** `audioop` (C extension, PSF-2.0)
- **License:** Apache-2.0 ([root LICENSE](../../LICENSE)) with Sun/MIT notices retained — see [Licensing](#14-licensing)

## 1. Overview

`audioop` provides legacy operations on raw audio samples — gain, bias, clipping, RMS/peak analysis, channel conversion, sample-rate conversion, G.711 companding, and ADPCM. It shipped in the Python standard library until Python 3.13 (removed under PEP 594). This port reimplements the full v0.1.0 surface natively in Mojo for code that depends on the historical API.

- **26 public operations** across 8 Mojo modules, plus a shared sample-representation layer.
- **Verified against CPython 3.12.3** via an isolated reference interpreter, a framed binary CLI, a Python oracle, and **1,277 golden vectors** (drift-checked).
- **105 native Mojo tests + 136 Python compatibility tests**, all passing.
- **Three-way benchmarks** (pure Python / CPython C / Mojo, with CLI path measured separately).

Detailed design: [`docs/reference-audit.md`](docs/reference-audit.md) · [`docs/licensing-audit.md`](docs/licensing-audit.md) · [`PHASE0_RESULTS.md`](PHASE0_RESULTS.md)

## 2. Why Audioop?

The module is small, self-contained, and widely depended-on in legacy audio and telephony code. Its removal leaves a compatibility gap. A native port preserves the exact sample semantics (including overflow, rounding, and sentinel values) without requiring the CPython C extension.

The port is also a proving ground for the PyroMojo workflow: a well-specified, reference-audited C extension is an ideal candidate for native verification, golden-vector coverage, and honest benchmarking.

## 3. Implementation status — 26/26 `audioop-v0.1.0` (pre-release)

| Phase | Scope | Status |
|---|---|---|
| 1 — Sample representation | widths 1–4, native byte order, 24-bit sign extension | Complete — [`docs/sample-representation.md`](docs/sample-representation.md) · [`PHASE1_RESULTS.md`](PHASE1_RESULTS.md) |
| 2 — Arithmetic | `add` (saturating), `bias` (wrapping), `mul` (clamp-then-floor), `reverse`, `byteswap`, `lin2lin` | Complete — [`docs/arithmetic-operations.md`](docs/arithmetic-operations.md) · [`PHASE2_RESULTS.md`](PHASE2_RESULTS.md) |
| 3 — Statistics | `getsample`, `max` (absolute), `minmax`, `avg` (floor), `rms`, `cross` | Complete — [`docs/statistics-operations.md`](docs/statistics-operations.md) · [`PHASE3_RESULTS.md`](PHASE3_RESULTS.md) |
| 4 — Peak analysis | `avgpp`, `maxpp`, `findmax`, `findfactor`, `findfit` | Complete — [`docs/peak-analysis.md`](docs/peak-analysis.md) · [`PHASE4_RESULTS.md`](PHASE4_RESULTS.md) |
| 5 — Channel | `tomono`, `tostereo` | Complete — [`docs/channel-operations.md`](docs/channel-operations.md) · [`PHASE5_RESULTS.md`](PHASE5_RESULTS.md) |
| 6 — Rate conversion | `ratecv` (stateful) | Complete — [`docs/ratecv.md`](docs/ratecv.md) · [`PHASE6_RESULTS.md`](PHASE6_RESULTS.md) |
| 7 — G.711 | `lin2alaw`, `alaw2lin`, `lin2ulaw`, `ulaw2lin` | Complete — [`docs/g711.md`](docs/g711.md) · [`PHASE7_RESULTS.md`](PHASE7_RESULTS.md) |
| 8 — ADPCM | `lin2adpcm`, `adpcm2lin` (stateful) | Complete — [`docs/adpcm.md`](docs/adpcm.md) · [`PHASE8_RESULTS.md`](PHASE8_RESULTS.md) |
| 10 — Benchmarks | 250-workload, three-path measurement | Complete — [`benchmarks/reports/BENCHMARK_REPORT.md`](benchmarks/reports/BENCHMARK_REPORT.md) · [`PHASE10_RESULTS.md`](PHASE10_RESULTS.md) |

**Remaining work:** release mechanics only (tag `audioop-v0.1.0`, GitHub release). No implementation work remains.

## 4. Complete 26-operation API

All signatures match CPython 3.12.3 (bytes fragments, `int` widths, native-order samples, error messages preserved):

| Operation | Module | CLI opcode | Notes |
|---|---|---|---|
| `add(fragment, fragment, width)` | `arithmetic` | `0x22` | saturating addition |
| `bias(fragment, width, bias)` | `arithmetic` | `0x23` | wrapping addition |
| `mul(fragment, width, factor)` | `arithmetic` | `0x24` | clamp-then-floor |
| `reverse(fragment, width)` | `arithmetic` | `0x25` | sample-order reversal |
| `byteswap(fragment, width)` | `arithmetic` | `0x26` | byte-order swap |
| `lin2lin(fragment, width, newwidth)` | `arithmetic` | `0x27` | width conversion via shifts |
| `getsample(fragment, width, index)` | `statistics` | `0x28` | single-sample decode |
| `max(fragment, width)` | `statistics` | `0x29` | unsigned absolute maximum |
| `minmax(fragment, width)` | `statistics` | `0x2A` | signed `(min, max)` |
| `avg(fragment, width)` | `statistics` | `0x2B` | `floor(sum/n)` |
| `rms(fragment, width)` | `statistics` | `0x2C` | truncated `sqrt(mean(square))` |
| `cross(fragment, width)` | `statistics` | `0x2D` | zero-crossing count |
| `avgpp(fragment, width)` | `peak_analysis` | `0x2E` | truncated mean of peak differences |
| `maxpp(fragment, width)` | `peak_analysis` | `0x2F` | maximum peak difference |
| `findmax(fragment, length)` | `peak_analysis` | `0x30` | fixed 16-bit window search |
| `findfactor(fragment, reference)` | `peak_analysis` | `0x31` | fixed 16-bit least-squares |
| `findfit(fragment, reference)` | `peak_analysis` | `0x32` | fixed 16-bit windowed fit |
| `tomono(fragment, width, lfactor, rfactor)` | `channels` | `0x33` | interleaved → mono |
| `tostereo(fragment, width, lfactor, rfactor)` | `channels` | `0x34` | mono → interleaved stereo |
| `ratecv(fragment, width, nchannels, inrate, outrate, state, weightA, weightB)` | `ratecv` | `0x35` | stateful resampler |
| `lin2alaw(fragment, width)` | `g711` | `0x36` | 1 byte per sample |
| `alaw2lin(fragment, width)` | `g711` | `0x37` | `width` bytes per input byte |
| `lin2ulaw(fragment, width)` | `g711` | `0x38` | 1 byte per sample |
| `ulaw2lin(fragment, width)` | `g711` | `0x39` | `width` bytes per input byte |
| `lin2adpcm(fragment, width, state)` | `adpcm` | `0x3A` | packed 4-bit, high nibble first |
| `adpcm2lin(fragment, width, state)` | `adpcm` | `0x3B` | two samples per input byte |

Full opcode map: [`docs/cli-opcode-registry.md`](docs/cli-opcode-registry.md)

## 5. Compatibility scope

- Exact CPython 3.12.3 behaviour reproduced, including error messages (`Size should be 1, 2, 3 or 4`, `not a whole number of frames`, `Index out of range`, `Lengths should be the same`, `bad state`, `Python int too large to convert to C int`, `width * nchannels too big for a C int`, etc.).
- Native byte order only (no endianness parameter, matching the reference); `bytes` fragments.
- Two deliberate, documented deviations (not bugs):
  - `mul`/`tomono`/`tostereo` map NaN results to 0; CPython's `(int)NaN` is undefined (frozen since Phase 0).
  - CLI-only state representations differ structurally from the reference's Python tuples (wire formats in `docs/ratecv.md` / `docs/adpcm.md`); semantics are preserved.
- Out of scope for v0.1.0 (frozen since Phase 0): big-endian I/O, buffer-protocol / NumPy inputs, streaming APIs beyond the reference state tuples, SIMD/batch variants, explicit Python bindings.

Details: [`docs/api-scope.md`](docs/api-scope.md)

## 6. Supported sample widths

| Width | Bytes/sample | Signed range |
|---|---:|---|
| 1 | 1 | −128 … 127 |
| 2 | 2 | −32 768 … 32 767 |
| 3 | 3 | −8 388 608 … 8 388 607 |
| 4 | 4 | −2 147 483 648 … 2 147 483 647 |

`findmax`/`findfactor`/`findfit` are **fixed 16-bit** (reference design: `fragment->len >> 1` samples, no width argument). Empty fragments are valid for every operation that accepts a fragment (returning 0, the documented sentinel pair, or an empty output).

## 7. Stateful operations

Three operations carry state across calls (chunk boundaries verified against the reference):

- **`ratecv`** — phase accumulator and per-channel filter history `(prev_i, cur_i)` scaled to the 32-bit position. Returns `(bytes, (d, ((prev, cur)…)))`; GCD reduction of rates/weights; empty chunks compose; chunked processing is byte- and state-identical to whole-fragment processing. See [`docs/ratecv.md`](docs/ratecv.md).
- **`lin2adpcm`** / **`adpcm2lin`** — predictor (`valpred` ∈ [−32768, 32767]) and step index ([0, 88]). `lin2adpcm` drops an odd trailing nibble but the state still advances; decoder chunks of any size compose. See [`docs/adpcm.md`](docs/adpcm.md).

CLI state blocks round-trip between requests (verified in `test_ratecv_cli.py` / `test_adpcm_cli.py`).

## 8. Native CLI and binary protocol

Every request is `uint32_be length | body`, every response `uint32_be length | uint8 status | payload` (`0` = OK, `1` = error). Over-64-MiB frames and truncated headers terminate with a non-zero exit.

- Build the CLI: `.venv/bin/mojo build libraries/audioop/mojo/cli.mojo -I libraries/audioop/mojo -o build/audioop_cli`
- 26 operation opcodes `0x22`–`0x3B` plus 4 infrastructure opcodes (`0x01` ping, `0x02` echo, `0x20`/`0x21` sample layer) — see [opcode registry](docs/cli-opcode-registry.md).
- Scalars are returned as ASCII decimals; `minmax` as two decimals; `findfactor`/`findfit` factors as 8 big-endian IEEE-754 bytes (bit-exact, including NaN); `findfit` index as a decimal plus one space plus 8 bytes.

## 9. Installation and development setup

Requires **Mojo 1.2.0**, Python ≥ 3.11, and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/adarshsoloman/pyromojo
cd pyromojo
uv sync --extra dev          # provisions .venv, Mojo 1.2.0, ruff, pytest
```

Audioop reference environment (isolated CPython 3.12.3):

```bash
uv run python -m venv libraries/audioop/python_reference/.venv
libraries/audioop/python_reference/.venv/bin/pip install --quiet .
# or via the helper used in CI — see python_reference/README if present
```

Mojo is available as `.venv/bin/mojo` (never the system `mojo` 1.0.0).

## 10. Running tests

Full verification (lint, vector drift, pytest, 8 native Mojo suites):

```bash
.venv/bin/python scripts/run_all_tests.py
```

Targeted:

```bash
# Python compatibility (136 audioop cases)
.venv/bin/python -m pytest libraries/audioop/tests/python_compat -q

# Single native suite
.venv/bin/mojo build libraries/audioop/tests/mojo/test_g711.mojo \
  -I libraries/audioop/mojo -I libraries/audioop/tests/mojo \
  -o /tmp/g711 && /tmp/g711
```

## 11. Golden-vector verification

**1,277 cases** (42 original + 24 sample + 50 arithmetic + 69 statistics + 58 peak + 33 channel + 31 ratecv + 645 G.711 (all 256×2 decoder codewords) + 325 ADPCM (all 256 decoder bytes)):

```bash
libraries/audioop/python_reference/.venv/bin/python \
  libraries/audioop/python_reference/generate_audioop_vectors.py --check
# → 1277 cases match
```

## 12. Benchmark summary

Three-way comparison (naive Python, CPython 3.12.3 C, Mojo, with CLI path measured separately) over 250 deterministic workloads (`benchmarks/workloads.py`, seed `20260610`). See [`benchmarks/reports/BENCHMARK_REPORT.md`](benchmarks/reports/BENCHMARK_REPORT.md) (`benchmarks/README.md` for methodology).

- **Mojo is ~40× pure Python** (per-op 15–110×).
- **Mojo is ~0.26× CPython C** (C typically 2–20× faster; `getsample` excepted at ~2.7× Mojo-faster). The gap is dominated by per-call allocation and 64-bit scalar arithmetic; no SIMD work was done.
- **CLI ~16 ms** per request (process spawn) — not a kernel measure.

All 250 benchmark cells passed a three-way exact gate before timing.

## 13. Known deviations

- NaN policy as above (width-4 NaN differs at the byte level; excluded from equality assertions with a clear explanation, per `docs/api-scope.md`).
- Reference-only tuple state errors are not CLI-reachable (the wire format is structural).
- Odd-chunk ADPCM encoder concatenation is not byte-equal to whole encoding (CPython behaviour, documented).
- 1-MiB tier from the benchmark design doc is deferred (would dominate wall time on the pure-Python path).

## 14. Licensing

- Port license: **Apache-2.0** — see root [`LICENSE`](../../LICENSE).
- G.711 decode tables and IMA/DVI ADPCM tables are transcribed from CPython 3.12.3 `Modules/audioop.c` and retain the embedded **Sun Microsystems unrestricted-use notice**, recorded in full in [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) (added Phase 9; licensing audit updated).
- Golden vectors are observed outputs (derived data), not source.

Details: [`docs/licensing-audit.md`](docs/licensing-audit.md)

## 15. Release information

- **Version:** `audioop-v0.1.0` (first public port release; not yet tagged/published — pending review).
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md)
- **Release notes:** [`RELEASE_NOTES_v0.1.0.md`](RELEASE_NOTES_v0.1.0.md) (copy-ready GitHub description)
- **Release readiness:** [`RELEASE_READINESS.md`](RELEASE_READINESS.md)
- **Benchmark report:** [`benchmarks/reports/BENCHMARK_REPORT.md`](benchmarks/reports/BENCHMARK_REPORT.md) with raw results under `benchmarks/results/`
