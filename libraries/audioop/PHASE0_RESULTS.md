# Audioop — Phase 0 results

Status: investigation complete. **No production code was written.** Every
claim below is either read from the pinned C source, observed with the probe
suite, or produced by a named experiment. Nothing claims an unrun experiment
passed.

Evidence:

- Reference probe: `python_reference/probe_audioop.py` → 416 cases
  (`/tmp` output, not committed).
- Equivalence proof: `python_reference/verify_reference.py` → **416 cases,
  0 mismatches** (distro build vs pristine 3.12.3 build).
- Toolchain experiments: `experiments/audioop_toolchain/01…17` → **17/17
  passed** (`run_experiments.py`).
- Representative vectors: `tests/vectors/audioop_vectors.json` → **42 cases,
  all 26 functions**, deterministic (sha256
  `a25f9db15ecda91ce73bc318f18c9d9ff8333c0ee196248e1b1390a5cd6dd39a`).
- Docs: `docs/reference-audit.md`, `docs/api-scope.md`,
  `docs/algorithm-analysis.md`, `docs/licensing-audit.md`,
  `docs/benchmark-design.md`.

## 1. Reference audit

Pinned to CPython **3.12.3** (`Modules/audioop.c`, 2003 lines, sha256
`3ad415f1…31f620d`). Tarball checksum matches the official SPDX document and
the GitHub tag `v3.12.3` commit `f6650f9a…`. `audioop` was deprecated in 3.11
and removed in 3.13, so the reference is available only on 3.11/3.12.

The distribution build was proven identical to a pristine rebuild of the
pinned source over all 416 probe cases. No distro patch influences any
recorded behaviour.

Provenance: the u-law/A-law code derives from SoX 12.17.7 `g777.c`/`g771.c`
and carries a Sun Microsystems unrestricted-use notice; the file ships in
CPython under PSF-2.0. Details and the port's handling are in
`docs/licensing-audit.md`.

## 2. API scope (v0.1, frozen)

All **26 functions** plus `audioop.error`:

`add`, `bias`, `mul`, `max`, `minmax`, `avg`, `rms`, `cross`, `findfactor`,
`findfit`, `findmax`, `avgpp`, `maxpp`, `getsample`, `byteswap`, `reverse`,
`lin2lin`, `lin2ulaw`, `ulaw2lin`, `lin2alaw`, `alaw2lin`, `lin2adpcm`,
`adpcm2lin`, `ratecv`, `tomono`, `tostereo`.

Frozen decisions: native byte order only; bytes fragments only (no arbitrary
buffer protocol); `find*` stay fixed 16-bit; sentinel values preserved
(empty `minmax`, `cross`, `findfactor`/`findfit`); error messages reproduced
verbatim; `mul` with `nan`/`inf` follows a documented port policy because the
reference is undefined. Full rationale and deferrals: `docs/api-scope.md`.

## 3. Semantics established

The audit records, with evidence:

- widths 1–4 are signed two's-complement, native byte order;
- validation order: width, then frame alignment, then function checks;
- `add` clamps (width 4 computed in double to avoid C overflow), `bias`
  wraps, `mul` floors after clamping (`−3×0.5 = −2`);
- `max` uses unsigned absolute value (`abs(−2^31) = 2^31`);
- `avg`/`avgpp` truncate toward zero; `rms` floors `sqrt`;
- empty-input sentinels: `minmax → (2147483647, −2147483648)`,
  `cross → −1`, statistics → `0`, `findfactor → nan`,
  `findfit → (0, nan)`;
- `cross` counts sign transitions with an initial `−1` bias;
- `findfactor`/`findfit`/`findmax` are fixed 16-bit; `findmax` uses samples,
  not bytes;
- `lin2lin` widens by left shift and narrows by arithmetic right shift;
- u-law/A-law are table-driven on decode and branch-exact on encode;
- ADPCM works in a 16-bit domain regardless of fragment width, packs the
  first sample in the high nibble, and drops a trailing odd sample;
- `ratecv` reduces rates/weights by GCD, interpolates in double on a 32-bit
  domain, truncates to int, over-allocates then trims, and returns
  `(bytes, d, ((prev, cur), …))`.

Reference quirks and porting hazards are tabulated in
`docs/reference-audit.md` §6 and `docs/algorithm-analysis.md` §6.

## 4. Mojo 1.2.0 capabilities (verified)

All verified by compiling and running the named experiment with the project
toolchain (`.venv/bin/mojo`, Mojo 1.2.0 `2016d0cd`).

| Capability | Result | Experiment |
| --- | --- | --- |
| `UInt8` buffers, slicing to `Span`, iteration, copy independence | works | 01 |
| Signed 8/16/32 decode, both byte orders | exact | 02 |
| 24-bit sign extension/encoding | exact at both extremes | 03 |
| 32-bit arithmetic with clamped saturation | exact; `Int64` accumulator | 04 |
| Integer overflow | **wraps silently**, no trap | 05 |
| Narrowing conversions | truncate silently; two's complement holds | 06 |
| `floor`/`sqrt`/`trunc`, IEEE-754 doubles | available, matching | 07 |
| `fbound` floor+clamp rule | exact; NaN undefined | 08 |
| Encode/decode widths 1–4, LE and BE | exact | 09 |
| In-place strided sample loops | works | 10 |
| Exact-size allocation and growth | works | 11 |
| Mutable state structs, value-copy isolation | works with `RegisterPassable, ImplicitlyCopyable` | 12 |
| Compile-time and runtime tables | `StaticTuple` + `List` | 13 |
| Arithmetic shifts and width masks | exact | 14 |
| Runtime width dispatch and typed overloads | works | 15 |
| `Error` raise/catch with exact messages | works | 16 |
| `//` floors (Python), C truncation needs a helper | verified; helper added | 17 |

Notable constraints recorded for Phase 1:

- `fn` was removed in Mojo 1.2.0; use `def`.
- Float→int conversion is **undefined** for `nan`/`inf`/out-of-range (all
  returned the same garbage value); clamp before converting.
- `comptime List[...]` cannot be indexed at runtime; use `StaticTuple`.
- Tuple literals are not iterable; index them or use `StaticTuple`.
- Plain structs are not implicitly copyable; declare
  `(RegisterPassable, ImplicitlyCopyable)` (int fields) or implement
  `__copyinit__` with the lifecycle traits.
- `List.resize(n, fill)` requires the fill argument.
- Returning a `List` requires `^` transfer or `.copy()`.

## 5. Golden-vector schema

`tests/vectors/audioop_vectors.json`:

```json
{
  "schema_version": "1.0.0",
  "generator": {"name": "audioop_vectors", "version": "1.0.0"},
  "reference": {"package": "audioop", "python_version": "3.12.3"},
  "host": {"byte_order": "little"},
  "seed": 20260610,
  "cases": [
    {
      "id": "add-w2",
      "op": "add",
      "width": 2,
      "args": {"fragment1_hex": "…", "fragment2_hex": "…"},
      "expected": {"result_hex": "…"},
      "notes": "clamps at both 16-bit extremes"
    }
  ]
}
```

Rules:

- `op` is the reference function name; `width` appears only when the
  function takes one.
- Byte arguments use `*_hex`; scalars are JSON numbers; special floats are
  the strings `"nan"`, `"inf"`, `"-inf"` (audioop returns no strings, so
  this is unambiguous).
- `expected` is exactly one of `result_hex` (bytes),
  `result_hex` + `state` (stateful codecs), `value` (int/float/tuple), or
  `error_type` + `error_message`.
- `host.byte_order` is bit order metadata: the vectors were generated on a
  little-endian host and are only directly comparable there.
- The corpus is **representative** (one or two cases per function plus the
  recorded edge cases). Full generation, randomized differential cases, and
  a big-endian guard belong to Phase 1.

## 6. Benchmark design

`docs/benchmark-design.md` fixes the three paths (naive Python, reference C,
native Mojo), sizes from 0 frames through 1 Mi-frame, realistic 20 ms audio
frames, contents including silence/full-scale/random/sparse/ramp, and per-
group targets that are hypotheses, not release gates. Correctness failure
aborts a run before timing is reported. No benchmark was executed in Phase 0.

## 7. Risk register

| Risk | Evidence | Mitigation |
| --- | --- | --- |
| Native-endian assumption | audit §3, §7 | v0.1 little-endian; vectors carry `host.byte_order`; big-endian guard test in Phase 1 |
| Float parity (`rms`, `find*`, `ratecv`) | audit §5 | same `Float64` operations and order; differential tests on exact integers where possible |
| `mul` NaN/Inf undefined | probe + vector | documented policy; excluded from equality gates |
| Reference C `int` overflow (`avg`/`add` w4) | source | port uses `Int64`; divergence documented as defined behaviour |
| State restart parity | audit §5 | vectors include non-`None` state cases; differential restart test in Phase 1 |
| Error text stability | 46 exceptions / 19 messages | pinned 3.12.3; exact-message tests |
| Python 3.13+ cannot run reference | removal | all reference runs use the isolated 3.12 venv |
| Mojo float→int UB | experiment 08 | explicit clamp/`is_nan` guards before conversion |
| Mojo `//` floors | experiment 17 | truncating helper for C-style division |
| Mojo struct copy rules | experiment 12 | declare traits or implement lifecycle methods |
| Performance vs C | benchmark design | targets are hypotheses; report honestly |
| Licensing of derived tables | licensing audit | regenerate tables from standards; retain Sun notice |

## 8. Project conventions (unchanged)

- Library layout mirrors the existing ports: `mojo/`, `tests/{mojo,
  python_compat,vectors}/`, `python_reference/`, `docs/`, `benchmarks/`,
  `experiments/`.
- Interop uses the framed Mojo CLI; no Python extension in v0.1.
- Generated reports are not committed; curated summaries are.
- No files in `libraries/msgpack/`, `libraries/levenshtein/`, or
  `libraries/bitarray/` were modified.

## 9. Phase 0 exit criteria

| Criterion | Status |
| --- | --- |
| Reference pinned, provenance verified, build equivalence proven | met |
| Complete surface and signatures recorded | met (26 functions + error) |
| Numerical semantics and edge cases observed | met (416 probes, 46 exceptions) |
| Licensing/provenance recorded, no copied code | met |
| Mojo toolchain risks identified with runnable evidence | met (17/17 experiments) |
| Golden-vector schema designed with a representative corpus | met (42 cases, 26 ops) |
| Benchmark design fixed | met (not executed) |
| No implementation, no commits, no release actions | met |

## 10. Phase 1 readiness and next actions

Recommended Phase 1 order:

1. Module skeleton and sample access (`get/set` for widths 1–4), validation
   helpers, and `error` mapping; wire the framed CLI.
2. Arithmetic + statistics (shared loops), gated by golden vectors and the
   differential suite.
3. Fragment transforms and `lin2lin`.
4. u-law/A-law (generate tables from the standard formula; validate).
5. ADPCM, then `ratecv` (state layout and double arithmetic).
6. Python-compat harness extensions and full vector generation.
7. Benchmark implementation only after correctness gates pass.

Open questions (none block starting):

- CLI binary layout (single vs grouped) — follow the bitarray precedent.
- Final `mul` NaN policy wording (observed build vs clamped/zero policy).
- Where the Sun attribution lives (library README and/or shared notices).

## 11. Experiment inventory

| # | File | Proves |
| --- | --- | --- |
| 01 | `01_byte_buffer.mojo` | buffers, spans, iteration, copies |
| 02 | `02_signed_decode.mojo` | 8/16/32 sign extension, both orders |
| 03 | `03_sign_extend_24.mojo` | 24-bit exactness at extremes |
| 04 | `04_int32_arithmetic.mojo` | clamped saturation for widths 1–4 |
| 05 | `05_overflow.mojo` | wraparound is silent |
| 06 | `06_int_conversions.mojo` | widening/narrowing behaviour |
| 07 | `07_float_math.mojo` | floor/sqrt/trunc and double exactness |
| 08 | `08_rounding.mojo` | `fbound` and NaN hazard |
| 09 | `09_byte_encode.mojo` | get/set sample, all widths/orders |
| 10 | `10_sample_loops.mojo` | strided in-place transforms |
| 11 | `11_allocation.mojo` | exact-size output buffers |
| 12 | `12_state_struct.mojo` | mutable state and value copies |
| 13 | `13_lookup_tables.mojo` | comptime/runtime tables |
| 14 | `14_shifts_masks.mojo` | shifts and width masks |
| 15 | `15_dispatch.mojo` | width dispatch and overloads |
| 16 | `16_error_handling.mojo` | error text and catching |
| 17 | `17_int_division.mojo` | C truncation vs Mojo floor division |

Reproduce: `python experiments/audioop_toolchain/run_experiments.py`
(writes a JSON report under the git-ignored `reports/generated/`).
