# API scope: PyroMojo Resampy v0.1.0

**Phase 1 deliverable — public API inventory and compatibility scope.**
**Reference:** `resampy` 0.4.3, commit `7c484f8eec54b87e8f566578dc3e48a2be81cc80`
(see `reference-audit.md`). **Status:** Phase 1 scope specification, reconciled
with Phases 4–6. Current implementation status is tracked in
[`resampling-design.md`](resampling-design.md) and the library
[README](../README.md); the matrix below records v0.1.0 scope status.
Phase 1 tolerance proposals in §6 and the open questions below are historical
planning inputs, not the Phase 4 local gate.

**Labels:** `[V]` verified from upstream source · `[I]` PyroMojo engineering
decision/recommendation · `[U]` unresolved / requires further evidence.

**Related Phase 1 documents:** [reference-audit.md](reference-audit.md) · [licensing-audit.md](licensing-audit.md) · [benchmark-design.md](benchmark-design.md) · [library README](../README.md).

---

## 1. Complete public API inventory `[V]`

Upstream `resampy` 0.4.3 exposes exactly **five documented functions** (confirmed
by `core.__all__`, `filters.__all__`, and the official API page
`https://resampy.readthedocs.io/en/stable/api.html`), plus module attributes and
two filter data resources. There are **no public classes**.

| # | Name | Source | Exposed as |
|---|---|---|---|
| 1 | `resample` | `resampy/core.py:16` | `resampy.resample` |
| 2 | `resample_nu` | `resampy/core.py:181` | `resampy.resample_nu` |
| 3 | `get_filter` | `resampy/filters.py:145` | `resampy.filters.get_filter` |
| 4 | `sinc_window` | `resampy/filters.py:64` | `resampy.filters.sinc_window` |
| 5 | `clear_cache` | `resampy/filters.py:220` | `resampy.filters.clear_cache` |

Also public/module-level (not functions): `resampy.__version__` (`0.4.3`),
`resampy.filters.FILTER_FUNCTIONS = ['sinc_window']`,
`resampy.filters.FILTER_CACHE` (dict), `resampy.filters.load_filter` (public by
name but not in `__all__`), `resampy.version.short_version`/`version`, and the
bundled resources `resampy/data/kaiser_fast.npz`, `kaiser_best.npz`.
`resample_f_s`/`resample_f_p` in `interpn.py` are public by name but are internal
Numba gufuncs, not documented API. `[V]`

> **Scope note `[V]`:** this inventory contradicts any prior assumption that
> Resampy exposes only one `resample` entry point, or that method names such as
> `get_filter`/`sinc_window` are top-level `resampy.*` names. All five verified
> names are enumerated above. No other public callables exist in
> `resampy/*.py`.

---

## 2. Per-function specification `[V]`

### 2.1 `resample`

| Field | Verified upstream behaviour |
|---|---|
| Name | `resample` |
| Source | `resampy/core.py:16` (`__all__` at `:13`) |
| Purpose | Resample `x` from `sr_orig` to `sr_new` along `axis`. |
| Parameters | `x, sr_orig, sr_new, axis=-1, filter="kaiser_best", parallel=False, **kwargs` |
| Input | `np.ndarray`; docstring says `dtype=np.float*`; **actually** float32/64, complex64/128, and integer arrays are accepted (`test_dtype`, `test_dtype_int`). Arbitrary `ndim` ≥ 1 (`test_shape` 3-D, `test_resample_axis` 4-D). |
| Output | `np.ndarray`, shape = input with `shape[axis]` replaced by `int(shape[axis] * float(sr_new)/float(sr_orig))`. dtype = `x.dtype` except integer → `np.float32`. C/F contiguity preserved. |
| Validation | `sr_orig <= 0` → `ValueError`; `sr_new <= 0` → `ValueError`; `sr_orig == sr_new` → `x.copy()` (early return, dtype preserved); `shape[axis] < 1` → `ValueError("Input signal length=… is too small to resample from …->…")`. |
| Errors | `ValueError` (above). Docstring also claims `TypeError` for unsupported dtype but no explicit raise exists at 0.4.3 `[U]`. Bad filter → `NotImplementedError` (from `get_filter`). Bad `sinc_window` kwargs → `ValueError`/`TypeError`. |
| Numerical behaviour | Band-limited windowed-sinc interpolation; `Float64` filter tables; `y[t] += …` accumulation in output dtype; `scale = min(1, sr_new/sr_orig)`; downsampling multiplies kernel by `sample_ratio`; `t_out[j] = j·sr_orig/sr_new`; zero-extension boundaries. See `reference-audit.md` §3. |
| v0.1.0 status | **IN SCOPE** (restricted: see §4). |

### 2.2 `resample_nu`

| Field | Verified upstream behaviour |
|---|---|
| Name | `resample_nu` |
| Source | `resampy/core.py:181` |
| Purpose | Interpolate `x` at explicit output positions `t_out` (non-uniform sampling). |
| Parameters | `x, sr_orig, t_out, axis=-1, filter="kaiser_best", parallel=False, **kwargs` |
| Input | `x` as above; `t_out` 1-D `np.ndarray` of output positions (seconds). |
| Output | `np.ndarray`, `shape[axis] = len(t_out)`, same dtype rules as `resample`. |
| Validation | `sr_orig <= 0` → `ValueError`; `t_out.ndim != 1` → `ValueError`; `min(t_out) < 0` or `max(t_out) > (x.shape[axis]-1)/sr_orig` → `ValueError("Output domain … exceeds the data domain …")`; empty/2-D `t_out` → `ValueError` (`test_bad_time_nu`). |
| Errors | `ValueError` as above; docstring claims `TypeError` (no explicit raise) `[U]`. |
| Numerical behaviour | Same loop with `scale=1.0` (no rolloff adaptation); `t_out *= sr_orig` if `sr_orig != 1.0`. Docstring warns results can differ slightly from `resample`. |
| v0.1.0 status | **DEFERRED** — see §5. |

### 2.3 `get_filter`

| Field | Verified upstream behaviour |
|---|---|
| Name | `get_filter` |
| Source | `resampy/filters.py:145` |
| Purpose | Return `(half_window, precision, rolloff)` for a filter name, a registered function name, or a callable. |
| Parameters | `name_or_function, **kwargs` |
| Input | str (`'kaiser_fast'`, `'kaiser_best'`, `'sinc_window'`) or callable returning the 3-tuple. |
| Output | tuple `(np.ndarray float64, int P, float rolloff)`. |
| Validation | If name not in `FILTER_FUNCTIONS`, not callable, and `load_filter` raises `IOError`/`ValueError` → `NotImplementedError("Cannot load filter definition for …")` (`test_filter_missing`). |
| Errors | `NotImplementedError`; propagates `sinc_window` `ValueError`/`TypeError`. |
| Numerical behaviour | For pre-computed filters, `kwargs` are ignored; result cached in `FILTER_CACHE`. `rolloff` returned but discarded by `resample`. |
| v0.1.0 status | **OUT OF SCOPE** as a public API (internal equivalent may be needed). |

### 2.4 `sinc_window`

| Field | Verified upstream behaviour |
|---|---|
| Name | `sinc_window` |
| Source | `resampy/filters.py:64` |
| Purpose | Generate a windowed-sinc half-filter at runtime. |
| Parameters | `num_zeros=64, precision=9, window=None, rolloff=0.945` |
| Input | `window=None` → `np.hanning`; else a callable (e.g. `scipy.signal.windows.hann`, Kaiser). |
| Output | `(interp_window np.ndarray float64 shape (num_zeros·2^precision + 1), num_bits=2^precision, rolloff)`. |
| Validation | `window` not callable/`None` → `TypeError`; `not 0 < rolloff <= 1` → `ValueError`; `num_zeros < 1` → `ValueError`; `precision < 0` → `ValueError`. |
| Errors | `TypeError`, `ValueError`. |
| Numerical behaviour | `rolloff * np.sinc(rolloff * linspace(0, num_zeros, n+1)) * window(2n+1)[n:]`. |
| v0.1.0 status | **OUT OF SCOPE** — runtime filter generation is not needed if only bundled filters ship. |

### 2.5 `clear_cache`

| Field | Verified upstream behaviour |
|---|---|
| Name | `clear_cache` |
| Source | `resampy/filters.py:220` |
| Purpose | `FILTER_CACHE.clear()` — force packaged filters to reload next use. |
| Parameters | none. Returns `None`. |
| v0.1.0 status | **OUT OF SCOPE** — cache is a Python-implementation detail (`test_filter_cache_reset`). |

---

## 3. Input/output semantics summary `[V]`

- **Output length:** `int(L * float(sr_new)/float(sr_orig))`, truncation toward
  zero. Verified by `test_resample_length_rounding` (12499→15001 ⇒ 15001) and
  `test_shape`. Not `round`, not `ceil`.
- **dtype rules:** float32→float32, float64→float64, complex64→complex64,
  complex128→complex128, integer→float32. Equal-rate `x.copy()` preserves the
  original dtype (including integer).
- **Axis:** any valid axis incl. negative; implemented by `swapaxes(-1, axis)`.
- **Dimensions:** arbitrary `ndim` (docs show 1-D, 2-D, 4-D).
- **Contiguity:** C/F flags preserved.
- **`parallel`:** default `False` in code (docstring "Default: True" is stale);
  `True` attempts Numba-parallel gufunc with fallback on `numba.TypingError`.
- **`filter`:** `'kaiser_best'` (default), `'kaiser_fast'`, `'sinc_window'`, or
  any callable. `**kwargs` only used by `sinc_window`/callables.

---

## 4. v0.1.0 scope `[I]`

**Guiding principle:** a defensible first release reproduces `resample` for the
most common, testable case with measured exact agreement against the pinned
upstream reference — **not** full NumPy/Resampy API coverage. Phase 4 local
reference agreement is exact, and Phase 5 upstream parity is bit-identical;
see §6. Phase 0 established that PyroMojo has no general
multidimensional-array abstraction and only 1-D `List`/`Span`.

**IN SCOPE (required):**

| ID | Behaviour | Rationale |
|---|---|---|
| S1 | `resample(x, sr_orig, sr_new)` for **1-D float64** signal, `axis` fixed to last/only, **integer sampling rates** | Matches the dominant use case and the repository's 1-D data model. Non-integer rates are out of scope; see §4.1. |
| S2 | Output length = `int(L * float(sr_new)/float(sr_orig))`; exact `sr_orig == sr_new` copy; `sr_orig <= 0` / `sr_new <= 0` / `shape[axis] < 1` → `ValueError` with upstream message text (upstream Python contract; Phase 4 Mojo behaviour differs, see §4.1) | Cheap, deterministic, directly testable (`test_bad_sr`, `test_short_signal`, `test_resample_length_rounding`). |
| S3 | Bundled **`kaiser_fast`** filter (12,289 float64) — **Phase 5 status: NUMERICALLY VERIFIED**; synthetic resource committed, upstream table used only from the installed package in tests | Small (~98 KB); avoids the 3.2 MB `kaiser_best` table. Redistribution still requires licensing clearance. |
| S4 | The exact interpolation loop: `n=int(τ)`, `frac`, `offset`, `eta`, `index_step`, `interp_delta`, left/right wings, `scale = min(1, ratio)`, downsampling gain compensation, zero-extension boundaries | This is the numerical contract; see `reference-audit.md` §3. |
| S5 | Upsampling and downsampling with integer rates and integer or non-integer `sr_new/sr_orig` ratios | Covers both `scale=1` and `scale<1` branches. Non-integer **rates** are not required. |
| S6 | Deterministic golden vectors + drift check; native Mojo tests; Python compatibility tests against an independent reference; pinned-0.4.3 parity tests | Repository convention (`docs/architecture.md`, four shipped ports). Upstream parity is covered by `test_upstream_parity.py`. |
| S7 | Framed binary CLI following the audioop convention (`uint32_be length | uint8 opcode | payload` → `uint8 status | payload`), including `OP_RESAMPLE = 0x2A` | Only interop surface that is verified to work in this repo. |
| S8 | Documented numerical tolerance policy for upstream comparison | Phase 5 measured exact finite agreement (`atol = rtol = 0`) for 1-D Float64 integer rates; §6 below. |

> **Phase 5 status note:** S3 (`kaiser_fast`) numerical parity is verified
> against an installed Resampy 0.4.3 runtime. The repository still commits only
> the synthetic resource, and redistributing a standalone coefficient resource
> remains conditional on licensing clearance. S6 includes both the independent
> local reference and the upstream parity test.

### 4.1 Phase 4 Mojo contract clarifications

The Phase 4 Mojo implementation does not expose Python exception types or
message text. The S2 `ValueError`/message behaviour describes upstream Python
only; the Mojo API raises `Error` and the CLI returns a `STATUS_ERROR` frame.

- Sampling rates are integers: `sr_orig`/`sr_new` are `Int` in the Mojo API
  and `u32_be` on the CLI. Non-integer sampling rates are **out of scope** for
  v0.1.0. Non-integer rate ratios derived from integer rates (for example
  `44100 -> 48000`) remain in scope.
- `sr_orig <= 0` and `sr_new <= 0` are rejected, but as Mojo `Error` with a
  diagnostic message.
- A zero-length result (including empty input or truncation) returns an empty
  `OutputBuffer`, and the CLI returns a successful empty payload. Upstream
  raises `ValueError` for a zero-length output. Callers that need the upstream
  exception must derive it from the inputs and `output_length`.
- A single-sample input that truncates to zero follows the same empty-result
  rule.
- Filter validation failures (for example a missing resource or an invalid
  precision) are Mojo `Error`s, not `NotImplementedError` or `ValueError`.
- Resources loaded through `load_filter` are fully validated by the loader.
  Kernel-level filter-table checks (`precision > coefficient_count` for a
  non-empty table and non-finite filter coefficients) occur when interpolation
  is performed.
- Equal-rate and zero-output paths return before kernel-level filter
  inspection. A filter supplied on those paths is not evaluated; the result is
  an exact copy or an empty output respectively.

**DEFERRED (valuable, not first release):** `kaiser_best`; `resample_nu`;
2-D multi-channel; arbitrary `axis`/N-D; float32; complex dtypes; integer input
→ float32; C/F contiguity preservation; `parallel`; `sinc_window`/callable
filters; custom `**kwargs`; `get_filter`/`clear_cache`/`load_filter` as public
API; non-integer sampling rates; NaN/Inf parity with upstream beyond documented
IEEE propagation; non-contiguous arrays.

**OUT OF SCOPE (not planned for v0.1.0):** full NumPy ndarray compatibility;
SciPy/Numba runtime parity; Python-extension/interop API; runtime filter
regeneration from Kaiser/window parameters; `optuna`-based filter design;
bit-exact equality with the Numba-compiled reference.

**Phase 4 Mojo API shape `[I]`** — implemented as:
`resample(fragment: Span[Float64, _], sr_orig: Int, sr_new: Int, filter: …)
raises -> List[Float64]`, with validation helpers and a wire codec in
`mojo_resampy/`. Names are local, not upstream names. Rates are integer-only.

---

## 5. Deferred/excluded features and rationale `[I]`

| Feature | Category | Why deferred/excluded |
|---|---|---|
| `resample_nu` | DEFERRED | Distinct API (explicit `t_out`, domain checks, `scale=1.0`); adds a second wire format and tolerance surface. Valuable but not needed to prove the core loop. |
| `kaiser_best` | DEFERRED | 409,601 float64 coefficients (~3.2 MB). Embedding/compile cost is disproportionate for a first port; `kaiser_fast` exercises the identical algorithm. |
| 2-D / N-D / arbitrary `axis` | DEFERRED | Phase 0: no multidimensional array abstraction in Mojo; requires shape/stride encoding and strided loops. Upstream `swapaxes`+gufunc broadcast is NumPy-specific. |
| float32 / complex | DEFERRED | Each adds a separate accumulation dtype and tolerance regime; complex requires complex arithmetic not yet probed in this repo. |
| Integer input → float32 | DEFERRED | An upstream convenience conversion; not needed for the numerical core. |
| C/F contiguity, non-contiguous arrays | DEFERRED / `[U]` | NumPy memory-layout semantics; no equivalent in the 1-D `List` model. Non-contiguous gufunc behaviour is also unverified upstream. |
| `parallel=True` | OUT OF SCOPE | A Numba multi-threading flag; no Mojo equivalent. Changelog v0.4.0 made sequential the default; sequential is the deterministic reference. |
| `sinc_window`, callable filters, `**kwargs` | OUT OF SCOPE | Requires runtime `np.sinc`, a window function, and `sin`/`cos` — none verified in the installed Mojo 1.2.0 toolchain (Phase 0). Bundled filters avoid this. |
| `get_filter`/`load_filter`/`clear_cache`/`FILTER_CACHE` | OUT OF SCOPE | Python cache/IO semantics, not part of the numerical contract. |
| NaN/Inf, extreme ratios | `[U]` | No upstream tests; behaviour must be probed in Phase 2 before any promise. |
| Python-to-Mojo interop API | OUT OF SCOPE | See `benchmark-design.md` §3 — repository's interop experiment is unverified/stale. |

---

## 6. Numerical compatibility specification `[I]` (historical Phase 1 proposal) + `[V]` (evidence)

**Evidence available `[V]`:**
- Bundled filter tables are float64 (`reference-audit.md` §6).
- Upstream `tests/test_quality.py` gates are `mean(|y − y_pred|)` vs an *ideal
  sine*: `kaiser_fast 1e-4`, `kaiser_best 1e-7`, `sinc_window 1e-6` (sweep
  `1e-1`). These are **accuracy-vs-ideal**, not port-vs-reference tolerances.
- `test_quality_sine_parallel` uses `np.testing.assert_allclose(y_seq, y_par,
  rtol=1e-13)` — i.e. upstream's own sequential/parallel paths agree at
  ~`1e-13` relative. This is the strongest available evidence for the
  reproducibility floor of the algorithm.
- `test_resample_matched` uses `np.allclose(x, y)` (defaults `rtol=1e-5`).
- All PyroMojo ports to date use **exact** equality (hex/bits); no tolerance
  helper exists (`reference-audit.md` Phase 0 findings).
- Phase 5 executed Resampy 0.4.3 `kaiser_fast` against the native kernel:
  15 finite committed cases plus a 1,684-case sweep were bit-identical;
  non-finite cases matched position-wise. `atol = rtol = 0` is measured for
  the supported 1-D Float64 integer-rate contract.

> **Historical Phase 1 proposal — not the Phase 4 local contract.** Phase 4
> Mojo/reference tests use exact equality (`atol = 0.0`, `rtol = 0.0`) against
> the independent local reference, as documented in `resampling-design.md`. The
> `atol = rtol = 1e-9` values below were not adopted. Phase 5 instead measured
> bit-identical finite output against the pinned Resampy 0.4.3 runtime.

**Policy proposal `[I]` — not an upstream requirement:**

| Aspect | Proposed rule |
|---|---|
| Primary metric | **Maximum absolute error** over the whole output, `max_i |y_mojo[i] − y_ref[i]|`, plus **RMSE** as a secondary summary. Both are recorded per vector. |
| Secondary metric | `np.testing.assert_allclose`-style combined `|a−b| <= atol + rtol·|b|`, reported but not the sole gate. |
| Upstream tolerance (float64, `kaiser_fast`) | **Superseded:** Phase 5 measured bit-identical finite output (and 275/275 exact benchmark gates), so the proposed `atol = rtol = 1e-9` gate was not adopted. |
| Future upstream tolerance (float32, if later) | `[U]` — separate, looser regime (accumulation in float32); must be measured, not guessed. |
| NaN / Inf | Match position-wise: NaN⇔NaN, Inf⇔Inf with sign. `[V]` Phase 5 upstream execution; semantic match. |
| Determinism | Same input → bit-identical Mojo output across runs and process boundaries; reference generated once in the pinned venv and committed. |
| Equal-rate path | Exact copy (bit-identical), no tolerance needed. |
| Length | Exact integer equality, no tolerance. |

**Golden-vector fields `[I]`** (wire representation is a recommendation only,
**not implemented** in Phase 1):

```
schema_version, generator{name,version}, reference{package:"resampy",
version:"0.4.3", commit:"7c484f8…", python, numpy, numba},
host{byte_order, endian}, seed, cases[]
case:
  id, op:"resample", sr_orig, sr_new, filter:"kaiser_fast",
  axis (null/omitted for v0.1 1-D), dtype:"float64",
  input_signal, expected_output, expected_length,
  tolerance{atol, rtol, max_abs}, reference_version, notes
```

**Wire representation for numerical data `[I]`:** prefer **hex-encoded IEEE-754
float64 bytes** (or base64 of the little-endian raw buffer) over JSON decimal
numbers. Reasons: JSON decimal round-tripping is not guaranteed bit-exact for
all float64 values across parsers; a long float64 signal (e.g. 100k samples)
is far more compact as base64 binary (~1.07 MB) than as decimal text; hex/base64
allows exact reconstruction of the reference bits and of the expected output.
Keep scalar metadata (rates, tolerance, version) as plain JSON numbers/strings;
record `host.byte_order` (audioop precedent) and generate vectors on the same
endianness as the comparison. Do **not** implement this layer in Phase 1.

---

## 7. Compatibility matrix `[I]`

| Public API item / behaviour | Upstream | PyroMojo v0.1.0 |
|---|---|---|
| `resample` 1-D float64, integer rates | `[V]` supported | **IN SCOPE** |
| `resample` non-integer rates | `[V]` supported | **OUT OF SCOPE** for v0.1.0; integer rates only |
| `resample` non-integer ratios with integer rates | `[V]` supported | **IN SCOPE** |
| `resample` up/down-sampling | `[V]` supported | **IN SCOPE** |
| `sr_orig == sr_new` copy | `[V]` supported | **IN SCOPE** |
| Validation (`<=0` rates, too-short signal) | `[V]` supported | **IN SCOPE** |
| `kaiser_fast` filter | `[V]` bundled | **VERIFIED NUMERICALLY** — synthetic resource committed; upstream parity test passes; redistribution licensing unresolved |
| `kaiser_best` filter | `[V]` bundled | DEFERRED |
| `resample_nu` | `[V]` supported | DEFERRED |
| 2-D / N-D / arbitrary `axis` | `[V]` supported | DEFERRED |
| float32 / complex64/128 | `[V]` supported | DEFERRED |
| integer input → float32 | `[V]` supported | DEFERRED |
| C/F contiguity preservation | `[V]` supported | DEFERRED |
| non-contiguous arrays | `[U]` | DEFERRED / unresolved |
| `parallel` flag | `[V]` supported | OUT OF SCOPE |
| `sinc_window` + `window`/`num_zeros`/`precision`/`rolloff` | `[V]` supported | OUT OF SCOPE |
| callable filters / `**kwargs` | `[V]` supported | OUT OF SCOPE |
| `get_filter`, `load_filter`, `clear_cache`, `FILTER_CACHE` | `[V]` public | OUT OF SCOPE |
| `resampy.__version__`, `version.py` | `[V]` public | OUT OF SCOPE (Mojo port has its own version) |
| NaN/Inf, extreme ratios, empty/single-sample | `[U]` | **PARTIAL** — empty/single-sample is a documented deviation; NaN/Inf propagation matches upstream in Phase 5 tests |
| Python-to-Mojo interop API | n/a | OUT OF SCOPE |
| Exact bit-equality with Numba output | `[U]` | **VERIFIED** for tested 1-D Float64 finite contract; deferred modes uncovered |

---

## 8. Open questions `[U]`

1. Phase 5 measured exact finite upstream parity for the supported contract.
   Re-calibrate only if the upstream version or Mojo/LLVM FP behaviour changes;
   the historical `1e-9` proposal is not the adopted gate.
2. Whether `kaiser_best` (3.2 MB) can be embedded without unacceptable compile
   time / binary size — decide with a Phase 2 toolchain probe.
3. Whether `resample_nu` should be added in v0.1 if the wire/tolerance cost is
   lower than expected.
4. Whether 2-D multi-channel should be promoted after v0.1.0. It is deferred
   for v0.1.0, and the README compatibility objective is limited to supported
   1-D/mono input (`README.md:46`).
5. Empty/single-sample remains a documented deviation. NaN/Inf propagation
   matched upstream in Phase 5; extreme ratios remain partially unprobed.
6. Whether Mojo 1.2.0 can store/iterate a 12,289-element float64 `StaticTuple`
   or needs a runtime `List[Float64]` (Phase 2 probe; Phase 0 verified
   `StaticTuple` only for small tables).
7. Reference interpreter choice (Python 3.9 vs 3.12/3.13) for NumPy/Numba pins.
