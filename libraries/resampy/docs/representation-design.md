# Representation Layer Design: PyroMojo Resampy Phase 3

> **Historical document — superseded by Phase 4.** This records the original
> Phase 3 representation-only design. Phase 4 subsequently introduced the
> `resample`/`output_length` kernel and the `OP_RESAMPLE` CLI opcode. Current
> implementation status is documented in
> [`resampling-design.md`](resampling-design.md). Phase 3 statements below must
> not be interpreted as the current implementation status.

**Status at Phase 3 completion:** representation/verification infrastructure
only. **No resampling algorithm, no `resample`, no `resample_nu`, no
interpolation loop, no filter generation, no upstream coefficient data.**

**Reference:** `resampy` 0.4.3, commit `7c484f8eec54b87e8f566578dc3e48a2be81cc80`
(Phase 1). Approved scope: 1-D Float64 signals, last-axis semantics,
`kaiser_fast` as the eventual first filter, native Mojo execution.

**Labels:** `[V]` verified by executed command · `[I]` engineering decision ·
`[U]` unresolved / deferred.

---

## 1. Signal representation (Component A)

`libraries/resampy/mojo/mojo_resampy/signal.mojo` — `struct Signal`.

`[I]` `List[Float64]` is the owned representation; `Span[Float64, _]` is used
only as a borrowed, read-only view returned by `view()` (lifetime tied to the
Signal via `origin_of`). No tensor/multidimensional abstraction.

| Operation | API | Semantics |
|---|---|---|
| Empty / owned construction | `Signal()`, `Signal(values^)` | exact-size; no dtype conversion |
| Copy a view | `Signal.from_span(span)` | explicit deep copy |
| Zero signal | `Signal.zeros(n)` | rejects `n < 0` |
| Length | `len(s)` (`Sized`) | element count |
| Indexed read | `s[i]` | bounds-checked, raises on out-of-range |
| Read-only view | `s.view()` | borrowed span |
| Explicit copy | `s.copy()` | deep copy of every bit pattern |
| Non-destructive hand-off | `s.take()` | returns an owned copy; Signal stays valid |

`[V]` Verified: empty, single, multiple, ± values, `1e-300`/`1e300`, subnormal
`5e-324`, signed zero, NaN/±Inf, copy independence, `from_span`, `zeros`,
bounds errors, iteration via view — 13 native tests pass.

Ownership/mutation is explicit: `Signal` is immutable by convention (no public
mutator); copies require `copy()`/`take()`; `^` transfers at construction.

## 2. Output representation (Component B)

`output.mojo` — `struct OutputBuffer`.

`[I]` Independent of any interpolation algorithm: it only knows length and
elements. Allocated with `resize(length, 0.0)` (exact zero-init).

| Operation | API | Semantics |
|---|---|---|
| Allocation | `OutputBuffer(n)` | rejects `n < 0`; 0 and 1 valid |
| Indexed read/write | `b[i]`, `b.set(i, v)` | bounds-checked |
| Accumulation | `b.add(i, v)` | for a future kernel |
| Read-only view | `b.view()` | borrowed span |
| Hand-off | `b.take()` | owned copy; buffer stays valid |

`[V]` Verified: 0/1/1000-element alloc, all-zero init, indexed writes incl.
`-0.0` and subnormal, accumulation, copy independence, bounds errors — 10
native tests pass.

## 3. Coefficient resource format (Component C)

`coefficients.mojo` — `FilterMetadata`, `FilterCoefficients`,
`parse_filter_metadata`, `validate_filter_resource`, `load_filter`.

Two-file format (both **synthetic** in Phase 3):

- `resources/synthetic/synthetic_filter.json` — flat JSON metadata:
  `schema_version`, `filter_id`, `coefficient_count`, `precision`, `rolloff`,
  `dtype`, `byte_order`, `resource_bytes`, `resource_sha256`.
- `resources/synthetic/synthetic_filter.bin` — raw **little-endian IEEE-754
  Float64** coefficient bytes (8 bytes each, no header).

`FilterCoefficients` carries: filter identifier, coefficient count, precision,
rolloff, coefficient values, resource byte order, integrity hash.

Validation is strict and ordered, every failure an actionable `Error` `[V]`:
file existence; metadata parse; `schema_version == 1`; `dtype == "float64"`;
`byte_order == "little"` (explicit LE, **no host-endian inference**); non-empty
`filter_id`; `precision > 0`; `0 < rolloff <= 1`; 64-char lowercase-hex hash;
payload length; SHA-256 of raw bytes matches metadata; decoded count.
**Resource limits (Phase 3.1):** `coefficient_count` is validated to be within
`[0, 1_000_000]` and `resource_bytes` within `[0, 8_000_000]` *before* the
`count * 8` multiplication, so no overflow can occur and no oversized buffer is
allocated. Files are read with a bounded reader (`max_bytes + 1`) so an
over-limit file is rejected before full allocation. Empty (count 0), ordinary,
maximum-permitted (1,000,000), excessive (1,000,001 and 2^61), malformed,
truncated, and corrupt-hash cases are all covered — 18 native tests pass.

`[I]` The loader is generic: a licensed resource can be added later without
touching the kernel. **No upstream `kaiser_fast`/`kaiser_best` coefficient was
copied, extracted, transcribed or approximated** (Phase 1 `licensing-audit.md`
§6 remains unresolved).

## 4. Metadata structure and strict JSON codec

`json_codec.mojo` — Mojo 1.2.0 has **no JSON module** `[V]` (compile probes:
`std.json`, `json`, `std.jsonlib` all absent). Rather than a fragile general
parser, this is a narrow strict reader/writer for a **flat** object with string,
number, bool and null values.

Rejected with precise errors `[V]`: nested objects/arrays, trailing content,
duplicate/unknown keys (via caller), leading zeros, bare identifiers, single
quotes, raw control chars, unsupported escapes, bad `\u` digits. Supported
string escapes: `\" \\ \/ \b \f \n \r \t \uXXXX` (BMP). Serialization emits a
deterministic canonical object in recorded key order. `JsonObject` provides
typed getters (`get_string/get_int/get_float/get_bool/is_null`). 21 native tests
pass.

**Finite-number policy (Phase 3.1).** `get_float` and the numeric parser reject
any token whose Float64 conversion is non-finite (`1e400`, `-1e400`, bare
`nan`/`inf`/`-inf`) — no invalid token silently becomes infinity. `1e-400` is a
finite underflow to `0.0` and is accepted as such. `set_float` rejects non-finite
inputs with an actionable error rather than emitting the invalid JSON bare
tokens `inf`/`nan`. All serialized finite outputs parse with Python's
`json.loads`. This is a strict subset, not full RFC 8259 compliance.

`[I]` Schema keys are **flat** (no nested `reference`/`input`/`expected`
objects) specifically so the strict reader suffices; the Phase 1 conceptual
schema was explicitly non-binding.

## 5. Numerical comparator semantics (Component D)

`numerical_compare.mojo` — `compare_arrays(actual, reference, atol, rtol)`
returns `ComparisonResult` with: `lengths_match`, `compared_count`,
`mismatch_count`, `overflow_pairs`, `max_abs_error`, `rmse`, `mean_abs_error`,
`has_nonfinite`, `nonfinite_pairs`, `error_metrics_valid`, `element_wise_match`,
`passed`, plus `serialize()`.

Per-element condition: `|a - b| <= atol + rtol * |b|` (operand order preserved:
`a` is actual, `b` is the reference used for the relative term). `[I]`
Tolerances are **always caller-supplied**; nothing is hardcoded;
negative/NaN/Inf tolerances are rejected. The final Resampy compatibility
tolerance (`1e-9` in Phase 1 §6) is **not adopted** — it is calibrated only after
the native kernel exists.

**Overflow handling (Phase 3.1):** for a finite pair, if `abs(a - b)`,
`rtol * |b|`, or `atol + rtol * |b|` overflows to a non-finite value, the pair is
a mismatch, `overflow_pairs` increments, and the metrics are invalidated. Finite
inputs can never pass merely because an intermediate tolerance calculation
overflowed. Accumulated squared errors that overflow also invalidate the
metrics. Computed metrics are checked for finiteness and are reported as `NaN`
when invalid; an infinite RMSE or MAE is never exposed as a valid metric.

## 6. Non-finite value policy

Explicitly documented and tested `[V]`:

- NaN matches NaN only; NaN never matches finite or infinite.
- `+Inf` matches `+Inf` only; `-Inf` matches `-Inf` only.
- A finite value never matches an infinity.
- Different lengths fail outright (`lengths_match=0`, `passed=0`, no element
  comparison, no finite metrics).
- `has_nonfinite` / `nonfinite_pairs` expose involvement; non-finite pairs are
  **never silently discarded**.
- If any pair is non-finite OR any finite computation overflows,
  `max_abs_error`/`rmse`/`mean_abs_error` are `NaN` and `error_metrics_valid=0`
  — reporting a finite number while ignoring NaN/Inf would be misleading.

**Compatibility-gate contract (Phase 3.1).** Two distinct questions are
reported separately:
- `element_wise_match` (and `mismatch_count`) answer "did every pair match under
  the element-wise policy?" — NaN matches NaN, `+Inf` matches `+Inf`, etc. This
  policy is **unchanged** from Phase 3.
- `error_metrics_valid` answers "are the required numerical error metrics
  finite and trustworthy?".

`passed` is the **safe gate decision**: `element_wise_match AND
error_metrics_valid`. A downstream compatibility gate may safely read only
`passed`; it can never accept an all-NaN or all-Inf array whose metrics are
invalid. For example, an all-NaN comparison yields `element_wise_match=1` but
`error_metrics_valid=0` and `passed=0`.

- Empty arrays (equal lengths) pass trivially with zero metrics and a valid gate.

21 native + 15 Python compat comparator tests pass.

## 7. Golden-vector schema (Component E)

`golden_vector.mojo` — schema v1, **flat JSON + Base64 little-endian Float64**.
Keys `[V]`: `schema_version`, `case_id`, `description`, `reference_library`,
`reference_version`, `reference_commit`, `python_version`, `numpy_version`,
`numba_version`, `input_dtype`, `output_dtype`, `byte_order`, `sr_orig`,
`sr_new`, `filter_id`, `input_count`, `expected_count`, `input_encoding`,
`expected_encoding`, `input_data` (Base64), `expected_data` (Base64),
`payload_element_count`, `payload_sha256`, `atol`, `rtol`.

Integrity hash covers the concatenation of raw LE input bytes + raw LE expected
bytes (the exact bits that must round-trip), not the Base64 text or JSON.
Validation `[V]`: schema version, exact key set, dtype/byte_order/encoding,
counts, Base64 decode, payload length, SHA-256, finite non-negative tolerances.
**Metadata is validated independently of the payload hash (Phase 3.1):** a
matching hash must never make inconsistent metadata acceptable. `sr_orig` and
`sr_new` must be positive; `case_id`, `description`, `reference_library`,
`reference_version`, `reference_commit`, `python_version`, `numpy_version`,
`numba_version` and `filter_id` must be non-empty; all numeric tokens must be
finite (non-finite `atol`/`rtol` are rejected); decoded payload element counts
must match the declared counts; `payload_element_count` is capped at
1,000,000 to guard the byte-size multiplication; unsupported schema versions
are rejected. 16 native + 17 Python compat golden-vector tests pass.

`[I]` All Phase 3 vectors are **synthetic** (`reference_library = "synthetic"`),
stored in `tests/vectors/representation_vectors.json` (12 cases: empty, single,
± values, zero/-0.0, subnormal, large finite, NaN/±Inf, repeated, mixed special,
different lengths, explicit tolerances, non-integer ratio). Generated by
`tests/vectors/generate_synthetic.py` with stdlib only; `--check` provides drift
detection. **The Phase 2 upstream calibration corpus is not integrated.**

## 8. Endianness and Float64 bit preservation

`float_codec.mojo` — `float64_to_bits`/`bits_to_float64` via `std.memory.bitcast`;
`encode_f64le`/`decode_f64le` explicit little-endian; `bytes_to_hex`/
`hex_to_bytes`; `base64_encode_bytes`/`base64_decode_bytes` (reusing the verified
`std.base64`, wrapped with a strict canonical-form validator because the stdlib
decoder silently accepts whitespace and missing padding).

`[V]` Bit-exact round trips verified for signed zero, subnormal `5e-324`,
infinity, NaN payload `0x7FF8123456789ABC`, large finite values, empty vectors —
17 native + 7 Python compat tests.

`[V]` **Toolchain finding:** Mojo 1.2.0 constant-folds inline `1.0 / 0.0` to a
non-IEEE value (`9223372036854775807`); runtime division yields correct
`+inf` (`0x7FF0000000000000`), `-inf`, NaN. All tests construct specials at
runtime. Documented so future kernels do not use folded literal infinities.

`sha256.mojo` — self-contained pure-Mojo FIPS 180-4 SHA-256 (no stdlib module
exists `[V]`; `std.hash.hash` is a 64-bit non-cryptographic hash). Verified
against Python `hashlib` for empty, `abc`, `hello`, 256-byte and 200-byte
multi-block payloads, plus padding-boundary lengths 55, 56, 57, 63, 64, 65,
119, 120, 127, 128 and 129 with independently computed vectors. No third-party
dependency, no Python at native runtime. 18 native SHA-256/codec tests pass.

## 9. CLI integration (Component F)

`mojo/mojo_resampy/protocol.mojo` + `mojo/cli.mojo`. Framing is **identical**
to the four shipped ports `[V]`: `uint32_be length | body`; request body
`uint8 opcode | payload`; response body `uint8 status | payload`;
`MAX_FRAME_BYTES = 64 MiB`; clean EOF ends session; `STATUS_OK=0`/`ERROR=1`;
`OP_PING=0x01`, `OP_ECHO=0x02`; Phase 3 ops `0x20`–`0x29`. There is **no
resampling opcode**; the framed protocol was not changed.

**Allocation and response limits (Phase 3.1).** A semantic output length from
`OP_OUTPUT_ALLOC`/`OP_OUTPUT_SET` is bounded to `MAX_OUTPUT_ELEMENTS = 1_000_000`
(8 MB) *before* any allocation or element-count-to-byte-size multiplication;
`OP_OUTPUT_ALLOC(20_000_000)` is rejected with a controlled `STATUS_ERROR`
frame (no OOM abort), and the session continues. Response frames are capped at
`MAX_RESPONSE_BYTES = 16 MiB` and an oversized reply is rejected before writing.
Partial reads/writes, EOF, truncation, oversized-frame rejection and
multi-frame sessions are unchanged.

| Opcode | Operation |
|---|---|
| `0x20` | signal info / metadata |
| `0x21` | output buffer alloc (zeros) |
| `0x22` | output buffer indexed set |
| `0x23` | Float64 vector → Base64 |
| `0x24` | Base64 → Float64 vector |
| `0x25` | SHA-256 hex |
| `0x26` | numerical comparator |
| `0x27` | golden-vector parse |
| `0x28` | golden-vector serialize |
| `0x29` | synthetic coefficient resource load |

`[V]` Malformed requests return one `STATUS_ERROR` frame and the session
continues (no unexpected crash); framing errors follow the audioop convention
(one error frame, then a non-zero exit). Verified via batched native CLI tests
and 21 Python compat CLI tests. `Signal.view()` immutability is enforced by the
Mojo type system (a compile-failure fixture asserts that writing through the
view does not compile).

## 10. Floating-point build policy

`[V]` Phase 2 found default `-O3` / `contract=fast` fuses multiply-add and can
shift Float64 accumulation by 1 ULP. **All Phase 3 Mojo builds use
`--fp-mode contract=off`.** This is NOT a global repository change: the global
`scripts/run_all_tests.py` was left untouched.

Build/test commands (run from repo root):

```bash
# CLI
.venv/bin/mojo build libraries/resampy/mojo/cli.mojo \
    -I libraries/resampy/mojo --fp-mode contract=off -o build/resampy_cli

# one native test
.venv/bin/mojo build libraries/resampy/tests/mojo/test_signal.mojo \
    -I libraries/resampy/mojo -I libraries/resampy/tests/mojo \
    --fp-mode contract=off -o build/resampy_test_signal && ./build/resampy_test_signal

# everything (enforces the flag; sets RESAMPY_CLI for the native CLI test)
.venv/bin/python libraries/resampy/tests/run_phase3_tests.py
```

`[I]` `tests/run_phase3_tests.py` is library-local so the requirement is
reproducible without modifying shared/global infrastructure. The `python_compat`
`conftest.py` also builds the CLI with `--fp-mode contract=off`.

`[V]` **Toolchain quirk:** a Mojo-compiled binary launched from a Mojo parent
via `std.subprocess.run` takes ~17 s to start on this host (Python parent:
~0.02 s). The native CLI test therefore batches all requests into one
subprocess call.

## 11. Synthetic-resource restrictions

`[V]` No upstream filter coefficient resource was copied, extracted,
transcribed, redistributed or committed. The synthetic resource
(`synthetic_tiny_v1`, 8 arbitrary Float64 values) is not compatible with
Resampy and is never described as such. No approximation of `kaiser_fast`/
`kaiser_best` was generated. The synthetic vector bundle is not Resampy output.

## 12. Known limitations `[U]`

1. No resampling algorithm, no output-length calculation from sample rates, no
   `resample`/`resample_nu`, no filter generation.
2. Compatibility tolerance not calibrated (no kernel to compare).
3. `kaiser_fast` integration blocked on Phase 1 legal review.
4. 1-D Float64 only; no multi-channel, arbitrary axis, float32, complex,
   non-contiguous arrays, contiguity preservation.
5. Upstream `resample` dtype rules (integer→float32), `resample_nu` domain
   checks, and parallel/sequential behaviour are out of scope.
6. JSON codec is a strict flat subset (no arrays/nesting, BMP-only `\u`);
   sufficient for the schema but not a general JSON library.
7. Base64 payloads are ASCII metadata; very large vectors are bounded by the
   64 MiB frame / practical JSON size.
8. Native SHA-256 is verified against Python `hashlib` for the tested inputs,
   not a formal cryptographic certification.
9. `Signal.take()`/`OutputBuffer.take()` return an owned copy (non-destructive);
   a future kernel may prefer a consuming `^` hand-off.
10. The library-local runner is not registered in the global
    `scripts/run_all_tests.py` (deferred to Phase 4 integration).

## 13. Future integration requirements (Phase 4+)

`[I]` In order: resolve the coefficient licensing question and add the real
`kaiser_fast` resource (bit-exact, with a full provenance/notice entry); add
`interp_delta` derivation; implement the interpolation loop with
`--fp-mode contract=off`; add output-length computation and validation messages;
generate real (non-synthetic) golden vectors from the pinned reference env;
compare against them with the tolerance comparator and **calibrate** the true
tolerance from measured data; register native suites and vector drift checks in
`scripts/run_all_tests.py`; add Python compat tests against upstream resampy;
add benchmark workloads per `benchmark-design.md`.

---

**Related:** [reference-audit.md](reference-audit.md) ·
[api-scope.md](api-scope.md) · [licensing-audit.md](licensing-audit.md) ·
[benchmark-design.md](benchmark-design.md) ·
[toolchain-feasibility.md](toolchain-feasibility.md)
