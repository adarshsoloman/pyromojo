# Phases 4–5 — Windowed-Sinc Resampling Kernel and Upstream Parity

## Scope

Implemented: a whole-buffer, 1-D, Float64 `resample` kernel plus
`output_length`, callable from native Mojo and through one CLI opcode
(`0x2A`). Sampling rates are integers. Matches the upstream resampy 0.4.3
`kaiser_fast` code path in structure and arithmetic order. Committed tests use
the **synthetic** coefficient resource; the Phase 5 upstream test additionally
uses the production table from the installed upstream package at test time.

Explicitly out of scope for this phase: non-integer sampling rates,
`resample_nu`, `get_filter`, `clear_cache`, `sinc_window`, callable filters,
`kaiser_best`, Float32/complex/integer conversion, N-D and `axis` handling,
non-contiguous input, parallel or SIMD execution, GPU kernels, and a Python
extension module.

## Compatibility basis

- Upstream: `resampy` 0.4.3, commit `7c484f8eec54b87e8f566578dc3e48a2be81cc80`
  (ISC). Behaviour recorded in `reference-audit.md`.
- Coefficients: `resources/synthetic/synthetic_filter.json` /
  `.bin` (`synthetic_tiny_v1`, precision 8, eight coefficients) are the only
  coefficient data committed to the repository. Upstream `kaiser_fast`
  coefficient data is **not** copied or transcribed into the repository;
  `licensing-audit.md` §6 remains unresolved for redistribution.
- Phase 5 test runtime: `resampy==0.4.3`, `numpy==2.5.5`, `numba==0.68.1`,
  `llvmlite==0.50.0` in `.venv`. The upstream test obtains
  `resampy.filters.get_filter("kaiser_fast")`, serializes it to a temporary
  resource, and compares native output against `resampy.resample`.
- The independent stdlib transcription
  (`tests/python_compat/resample_reference.py`) remains the local
  internal-consistency reference.

## Phase 5 production compatibility (verified)

**Status: VERIFIED; distribution conditional on licensing clearance.**

Phase 5 was authorized to install the upstream runtime. The repository `.venv`
now contains:

```text
resampy==0.4.3
numpy==2.5.5
numba==0.68.1
llvmlite==0.50.0
```

Installation was test-only and did not change `pyproject.toml` or `uv.lock`:

```text
uv pip install --python .venv/bin/python "resampy==0.4.3" numpy numba
```

The upstream table is written to a temporary directory by
`tests/python_compat/test_upstream_parity.py`; it is not committed. Measured
metadata for the upstream `kaiser_fast` table:

```text
filter: kaiser_fast_upstream_0_4_3
coefficient_count: 12289
precision: 512
rolloff: 0.8682120372386292
sha256(float64 LE payload): 4c96a90d1b0b93cf0a9620c5f66216416a6b19752bf18a208c837b55b719434b
```

Results:

- Committed upstream parity test: 19 passed (15 finite signal/rate cases and
  4 non-finite/subnormal cases).
- Finite outputs were bit-identical (`atol = rtol = 0`).
- Non-finite outputs matched semantically (NaN positions and infinity signs).
- An extended finite sweep of 1,684 signal/rate combinations produced zero bit
  mismatches.
- Three-way spot checks against the independent stdlib reference also produced
  zero bit mismatches.

Remaining condition: `licensing-audit.md` §6 questions about redistributing the
bundled float64 coefficient tables are unresolved. Runtime parity evidence does
not itself grant permission to commit a standalone coefficient resource. Until
clearance is recorded, the repository keeps only the synthetic resource and the
upstream test regenerates its resource from the installed package.

No upstream-generated golden vectors are committed, avoiding another
redistribution path. The compatibility claim is limited to the tested 1-D
Float64, integer-rate contract.

## Algorithm

For input length `L`, rates `sr_orig`/`sr_new`:

1. `n_out = int(L * float(sr_new) / float(sr_orig))` (truncating; upstream
   semantics). Equal rates are an exact copy.
2. `ratio = sr_new / sr_orig`; `scale = min(1.0, ratio)`;
   `time_increment = 1.0 / ratio`; `index_step = int(scale * precision)`.
3. For each output index `t`: `tau = t * time_increment`; `n = int(tau)`;
   `frac = scale * (tau - n)`; `offset = int(frac * precision)`;
   `eta = frac * precision - offset`.
4. Build `delta[j] = win[j+1] - win[j]` for `j < nwin - 1`,
   `delta[nwin - 1] = 0`.
5. Left wing: `i_max = min(n + 1, (nwin - offset) // index_step)`.
   Right wing: `k_max = min(L - n - 1, (nwin - offset) // index_step)`.
   Each tap is `(win[q] + eta * delta[q]) * x[...]` with
   `q = offset + i * index_step`; taps outside `[0, L)` are skipped
   (zero-extension).
6. When downsampling (`ratio < 1`), every window coefficient is multiplied by
   `ratio` before accumulation.

Accumulation is strictly sequential (no reassociation, no FMA). All numerical
builds use `--fp-mode contract=off`.

## Numerics and calibration

- The CLI kernel and the independent Python reference agree **bit for bit**
  (`max_abs = 0.0`) across identity, integer/non-integer up/downsampling,
  impulses at both boundaries, constant, sine, deterministic pseudo-random,
  short, single-sample, zero, alternating, and empty inputs.
- Golden vectors therefore commit `atol = 0.0`, `rtol = 0.0`. This is a
  measured result, not an assumption. Re-calibrate if the Mojo/LLVM toolchain
  or FP flags change; do not silently loosen it.
- The `atol = rtol = 1e-9` policy in `api-scope.md` §6 is a historical Phase 1
  proposal for a future upstream comparison; it is not the Phase 4 local gate.
- A hand-checkable case uses `win = [1, 0]`, `precision = 1`: the kernel then
  performs exact linear interpolation, asserted against the analytic result.

## Error handling

- Non-positive `sr_orig`/`sr_new` are rejected.
- `int(scale * precision) < 1` (ratio too small for the filter precision) is
  rejected instead of dividing by zero.
- `precision <= 0` or `> 1_000_000`, and an empty coefficient list, are
  rejected. For a non-empty coefficient table, `precision > coefficient_count`
  is also rejected (it would otherwise produce silent zero output); an empty
  resource remains loadable for representation-only use but cannot be
  resampled.
- Non-finite filter coefficients are rejected by the resource loader and by the
  kernel. Non-finite input samples are allowed and propagate through the normal
  IEEE-754 arithmetic.
- Output length above `1_000_000` samples is rejected before allocation; the
  equality-rate copy path also enforces the `OutputBuffer` allocation limit.
- Coefficient access is bounds-checked; `n` is clamped defensively for FP edge
  cases.
- **Documented deviation:** an empty/zero-length result returns an empty
  `OutputBuffer`; upstream raises `ValueError` for a zero-length output. This
  keeps whole-buffer batch use practical; callers that require the upstream
  exception should check `output_length` first. The CLI therefore returns a
  successful response with an empty payload for these cases.
- **Error type:** the Mojo API raises `Error` and the CLI returns a
  `STATUS_ERROR` frame, not Python `ValueError`/`NotImplementedError`; message
  text is diagnostic and is not covered by an upstream-compatibility promise.
  The S2 `ValueError`/message contract in `api-scope.md` describes upstream
  Python behaviour, not the Phase 4 Mojo surface.

## Upstream-vs-Mojo compatibility

Labels: `[V]` verified from upstream source or an executed check; `[I]`
inferred from source inspection without an executed check; `[U]`
unresolved/unverified. The Phase 5 upstream runtime is installed and the
production `kaiser_fast` rows are execution-verified.

| Behaviour | Upstream resampy 0.4.3 | Phase 4 Mojo | Evidence |
|---|---|---|---|
| 1-D Float64, integer sample rates | Supported | Supported | `[V]` upstream source; local native/compat tests |
| Non-integer sample rates | Supported | **Out of scope**; `Int`/`u32_be` only | `[V]` upstream source; `[V]` Mojo signature/CLI |
| Non-integer rate ratios from integer rates | Supported | Supported | `[V]` golden vectors and compat tests |
| Zero-length output | `ValueError` | Empty `OutputBuffer`; empty CLI success | `[V]` upstream source; local source/tests; documented deviation |
| Output length above 1,000,000 | No explicit cap observed | Rejected before allocation | `[I]` upstream source inspection; `[V]` local limit/tests |
| `precision > coefficient_count` | No matching guard found | Rejected | `[I]` upstream source inspection; `[V]` local validation/tests; upstream runtime not tested |
| Non-finite filter coefficients | No explicit guard found | Rejected by loader and kernel | `[I]` upstream source inspection; `[V]` local validation/tests; upstream runtime not tested |
| Non-positive sample rates | `ValueError` | Mojo `Error`; CLI `STATUS_ERROR` | `[V]` upstream source; local tests |
| Production `kaiser_fast` coefficients | Bundled | Supported through a validated resource; synthetic resource committed | `[V]` Phase 5 upstream execution; `[V]` 1,684-case bit-exact sweep; redistribution licensing unresolved |
| Non-finite input samples | Allowed; IEEE propagation | Allowed; IEEE propagation | `[V]` Phase 5 upstream execution; semantic match |
| N-D, arbitrary `axis`, float32/complex, `parallel` | Supported | Out of scope | `[V]` upstream API/source; Phase 4 scope |
| Bit-exact equality with upstream output | Not promised; Numba-compiled | Bit-exact on tested finite contract | `[V]` Phase 5 upstream execution; 1,684 finite cases, zero bit mismatches |

Accepted Phase 4 deviations are the empty-result success path, integer-only
rates, the 1,000,000-sample output cap, and the added validation rejections.
Within the supported 1-D Float64 integer-rate contract, Phase 5 measured exact
upstream agreement; the deviations remain outside that claim.

## Protocol (`OP_RESAMPLE = 0x2A`)

Request payload:
`u32_be sr_orig | u32_be sr_new | u32_be id_len | filter_id bytes |
u32_be meta_len | metadata JSON | u32_be bin_len | coefficients (f64le) |
u32_be input_count | input (f64le)`

Response payload: little-endian Float64 samples. `filter_id` must equal the
metadata's `filter_id`; trailing payload bytes are rejected. The existing
64 MiB frame and 16 MiB response limits apply.

### Accepted CLI resource limitations

- **Metadata size:** `load_filter` enforces the 64 KiB `MAX_METADATA_BYTES` cap
  when reading metadata from disk. The in-memory `validate_filter_resource`
  path used by `OP_RESAMPLE` validates JSON, Base64, filter id, and coefficient
  fields but does not separately re-enforce the 64 KiB file-loader cap. The
  effective CLI bound is the 64 MiB frame limit; no unbounded read occurs.
  Accepted for Phase 4 and explicitly deferred.
- **Compute cost:** limits bound coefficient count (1,000,000), output samples
  (1,000,000), frame size (64 MiB), and response size (16 MiB) independently,
  but not the arithmetic product of input length, filter taps, and output
  length divided by `index_step`. An adversarial payload can therefore consume
  CPU up to those bounds. Accepted/deferred; Phase 4 has no runtime budget or
  timeout.


## Tests

- Native (`tests/mojo/test_resample.mojo`, 23 cases): validation, equal-rate
  bit-exact copy (including `-0.0`, subnormal, NaN, ±Inf), empty/single/short
  inputs, truncating `output_length`, output cap (including equal rates), safe
  huge-length diagnostics, exact linear interpolation, non-finite signal
  propagation, zero signal, determinism, boundary impulses (including a
  nonzero terminal contribution with `precision < coefficient_count`),
  constant input, ratio-too-small, invalid precision, precision/count and
  non-finite coefficient rejection, empty filter, and the committed synthetic
  resource.
- Python compat (`tests/python_compat/test_resample_cli.py`, 14 tests):
  bit-identical agreement with the independent reference on 17 rate/signal
  combinations, semantic non-finite agreement, analytic linear interpolation,
  a nonzero terminal-impulse case with `precision < coefficient_count`,
  protocol errors (rates, filter-id mismatch, truncation, trailing bytes,
  ratio, non-finite coefficients, precision/count), byte-level determinism, and
  all 17 committed golden vectors.
- Upstream parity (`tests/python_compat/test_upstream_parity.py`, 19 tests):
  imports `resampy==0.4.3`, serializes its `kaiser_fast` table to a temporary
  resource, and requires bit-identical finite output plus semantic non-finite
  agreement. Skipped when the pinned upstream runtime is absent.
- Golden vectors (`tests/vectors/generate_resample_vectors.py`,
  `resampling_vectors.json`) are generated from the independent reference and
  checked for drift with `--check`.

## Known limitations

- The repository commits only the synthetic filter. Production `kaiser_fast`
  parity is verified using the installed upstream table, but redistributing a
  standalone coefficient resource remains conditional on licensing clearance.
- Sampling rates are integer-only; non-integer rate inputs are out of scope.
  Non-integer ratios from integer rates remain supported.
- Upstream parity is verified for the tested 1-D Float64 integer-rate contract;
  deferred dtypes, N-D/axes, and parallel modes are not covered.
- CLI metadata-size and compute-cost limits are accepted/deferred as documented
  in the protocol section.
- No performance claims; benchmarking is deferred (`benchmark-design.md`).
