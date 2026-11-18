# Reference audit: `resampy` 0.4.3

**Phase 1 deliverable — upstream audit for PyroMojo Library 05 (Resampy).**
**Audit date:** 2026-11-18. **Status:** research/specification only; no implementation.

**Evidence labels used throughout:** `[V]` verified directly from primary source; `[I]` engineering inference/recommendation; `[U]` unresolved/unverified.

**Related Phase 1 documents:** [api-scope.md](api-scope.md) · [licensing-audit.md](licensing-audit.md) · [benchmark-design.md](benchmark-design.md) · [library README](../README.md).

All upstream evidence below was fetched over the network from the official
`bmcfee/resampy` GitHub repository, the official PyPI project, the official
Read the Docs site, and the primary algorithm reference. The exact tagged
source snapshot was downloaded and inspected locally (outside the repository,
in `/tmp/opencode/resampy_audit/`); no files were added to the PyroMojo repo
except the four Phase 1 documents under `libraries/resampy/docs/`.

---

## 1. Version selection

### 1.1 Release/tag inventory `[V]`

Source: GitHub API `https://api.github.com/repos/bmcfee/resampy/tags?per_page=100`
and `.../releases?per_page=100`, fetched 2026-11-18.

- Repository: `bmcfee/resampy`, description "Efficient sample rate conversion in
  python", default branch `main`, created 2016-04-08, last push 2024-09-30.
- 24 tags; 22 GitHub releases. Stable (non-prerelease) releases, newest first:
  `0.4.3` (2024-03-05), `0.4.2` (2022-09-13), `0.4.1` (2022-09-09),
  `0.4.0` (2022-08-08), `0.3.1` (2022-07-07), `0.3.0` (2022-06-29),
  `0.2.2` (2019-08-16), `0.2.1` (2018-06-04), `0.2.0` (2017-09-16),
  `0.1.5` (2017-02-16), `0.1.4` (2016-07-13), `0.1.3`, `0.1.2`, `0.1.1`,
  `0.1.0` (2016-04-21).
- **Latest stable release: `0.4.3`, published 2024-03-05T20:35:14Z.** PyPI's
  latest version is also `0.4.3` (`https://pypi.org/pypi/resampy/json`); no
  newer PyPI release exists. `[V]`

### 1.2 Exact commit `[V]`

- Tag `0.4.3` is a **lightweight tag** (`git/ref/tags/0.4.3` →
  `{"type": "commit"}`), pointing directly at commit
  **`7c484f8eec54b87e8f566578dc3e48a2be81cc80`**.
- Commit message: "Merge pull request #119 from bmcfee/build-updates /
  updated all actions"; author/committer date 2024-03-05T20:33:19Z.
- Release body (`.../releases/tags/0.4.3`): "This is a maintenance release to
  maintain compatibility with newer versions of Python. … There are **no
  functional changes to the library**." Lists PRs #116 (doc fix), #117
  (importlib_resources), #118 (tests/packaging), #119 (actions).
- `resampy/version.py` at this tag: `short_version = '0.4'`, `version = '0.4.3'`.

### 1.3 Post-release activity on `main` `[V]`

`pushed_at` is 2024-09-30; there are 9 commits on `main` after `0.4.3` and
**no newer release/tag**. Their file lists (GitHub commits API) are:

| Commit | Date | Subject | Files |
|---|---|---|---|
| `67263d6` | 2024-09-30 | python-1.12-compat merge | ci.yml, .readthedocs.yml, docs/conf.py |
| `d31c4c6` | 2024-09-28 | codecov v4 | ci.yml |
| `262780c` | 2024-09-28 | Add RTD config | .readthedocs.yml |
| `84682d6` | 2024-09-24 | scipy-1.13-compat merge | docs/example.rst, core.py, filters.py, scripts/create_filter.py |
| `6cfe8e2` | 2024-09-13 | Fix compatibility with scipy >= 1.13 | docs/example.rst, core.py, filters.py, scripts/create_filter.py |
| `8f6bb93` | 2024-09-13 | Fix compatibility with Python >= 3.12 | docs/conf.py |
| `a9d95eb` | 2024-04-29 | merge #120 | docs/conf.py |
| `a112845` | 2024-04-27 | prefer newer unittest.mock | docs/conf.py |
| `7c484f8` | 2024-03-05 | (the tag itself) | — |

The two commits touching `core.py`/`filters.py` were inspected via their
`patch`: they only change **doctest examples** from `scipy.signal.hann` /
`scipy.signal.kaiser` to `scipy.signal.windows.hann` /
`scipy.signal.windows.kaiser`. **No numerical/runtime code changed after
0.4.3.** `[V]` `docs/changes.rst` confirms v0.4.3's only change is
"`#117 … Update to remove deprecated usage of pkg_resources`".

### 1.4 Proposed reference target `[I]`

> **Target `resampy` 0.4.3, commit `7c484f8eec54b87e8f566578dc3e48a2be81cc80`.**

Rationale:

- It is the **latest stable release** and the version PyPI actually ships; no
  newer release exists.
- It is a **maintenance release with no functional changes**, so its numerical
  behaviour equals the well-tested 0.4.x line (0.4.0–0.4.2) plus the
  long-standing correctness fixes documented in `docs/changes.rst`: #113
  (rounding error in output-buffer length), #115 (buffer-length overflow),
  #111 (length calculation edge case), #90 (high-dimensional bug), #88
  (equal-rate bypass), #68 (C/F contiguity preservation).
- Post-0.4.3 `main` changes are doc/CI-only, so targeting the tag avoids
  chasing an unreleased branch.
- Its dependencies (`numpy>=1.17`, `numba>=0.53`) are permissively licensed and
  installable in an isolated reference venv; this must be verified in Phase 2
  (see §7 and `licensing-audit.md`). `[I]`
- **Not** selecting `0.2.2`/`0.3.x`: those predate the buffer-length and
  high-dimensional fixes. **Not** selecting untagged `main`: no release
  artifact, and no numerical benefit. `[I]`

`[U]` Whether a hypothetical future `0.4.4` would be a better target is out of
scope; if one is released, this decision must be re-opened.

### 1.5 Artifact provenance `[V]`

| Artifact | SHA-256 | Notes |
|---|---|---|
| GitHub tarball `refs/tags/0.4.3` | `271a6d24457721dd8bb5396612aa84166d3fa5c3f350df04daba991f37583e96` | downloaded from `codeload.github.com` |
| PyPI wheel `resampy-0.4.3-py3-none-any.whl` | `ad2ed64516b140a122d96704e32bc0f92b23f45419e8b8f478e5a05f83edcebd` | from `pypi.org/pypi/resampy/json` |

All five `resampy/*.py` files in the wheel are **byte-identical** to the tagged
source, and both bundled `.npz` filter files are byte-identical between wheel
and tagged source (verified with `zipfile` + SHA-256). So the released artifact
and the audited source are the same code. `[V]`

---

## 2. Repository and source audit `[V]`

Source tree at `7c484f8` (GitHub `git/trees/...?recursive=1`, 43 entries,
`truncated: false`), confirmed against the extracted tarball:

| Path | Size (B) | Role |
|---|---:|---|
| `resampy/__init__.py` | 171 | package init; `__version__`, imports |
| `resampy/version.py` | 106 | `short_version`, `version` |
| `resampy/core.py` | 9,045 | public `resample`, `resample_nu` |
| `resampy/filters.py` | 7,248 | `sinc_window`, `get_filter`, `load_filter`, `clear_cache` |
| `resampy/interpn.py` | 2,368 | Numba `_resample_loop`, gufuncs |
| `resampy/data/kaiser_fast.npz` | 99,100 | bundled filter |
| `resampy/data/kaiser_best.npz` | 3,277,596 | bundled filter |
| `scripts/create_filter.py` | 4,391 | offline filter-generation (optuna + scipy) |
| `tests/test_core.py` | 6,299 | shape/dtype/validation/axis tests |
| `tests/test_filters.py` | 1,543 | filter tests |
| `tests/test_quality.py` | 4,045 | accuracy/quality tests |
| `setup.cfg`, `setup.py`, `pyproject.toml` | 1,541 / 69 / 117 | packaging & deps |
| `LICENSE.md` | 743 | ISC license text |
| `README.md`, `docs/*`, `paper/*` | — | docs, JOSS paper, codemeta |
| `.github/workflows/{ci,ci-minimal,lint_python,publish}.yml` | — | upstream CI |

Package init (`resampy/__init__.py`):

```python
from .version import version as __version__
from . import filters
from .core import *
```

`core.__all__ = ["resample", "resample_nu"]`; `filters.__all__ = ['get_filter',
'clear_cache'] + ['sinc_window']`. So the top-level namespace exposes
`resampy.resample`, `resampy.resample_nu`, `resampy.__version__` and the
`resampy.filters` submodule. `get_filter`/`sinc_window`/`clear_cache` are
accessible as `resampy.filters.*`, not as top-level names. `[V]`

Hosted docs `https://resampy.readthedocs.io/en/stable/api.html` list exactly
five documented API ids: `resampy.core.resample`, `resampy.core.resample_nu`,
`resampy.filters.clear_cache`, `resampy.filters.get_filter`,
`resampy.filters.sinc_window`. Note its `<title>` says **"resampy 0.4.2
documentation"** — the deployed "stable" docs lag the 0.4.3 release; the
authoritative API is the tagged source. `[V]`

---

## 3. Algorithmic analysis `[V]` (math) + `[I]` (interpretation)

### 3.1 Mathematical formulation

Upstream describes the method as **band-limited sinc interpolation** for sample
rate conversion, citing Smith, *Digital Audio Resampling Home Page*
(`https://ccrma.stanford.edu/~jos/resample/`, reachable 2026-11-18). `[V]`
See `README.md:12-16`, `docs/index.rst:9-12`, `paper/paper.md:20`.

Conceptually the continuous-time reconstruction of a discrete signal is

```
x(t) = Σ_n x[n] · sinc(t − n),   sinc(u) = sin(πu)/(πu)  (NumPy's np.sinc)
```

Resampy replaces the infinite ideal interpolator with a **finite, windowed,
band-limited** kernel, evaluated from a precomputed discrete table. `[I]`

### 3.2 Filter coefficient generation — `resampy/filters.py:sinc_window` `[V]`

```python
def sinc_window(num_zeros=64, precision=9, window=None, rolloff=0.945):
    if window is None:
        window = np.hanning
    elif not callable(window):
        raise TypeError(...)
    if not 0 < rolloff <= 1:
        raise ValueError(...)
    if num_zeros < 1:
        raise ValueError(...)
    if precision < 0:
        raise ValueError(...)
    num_bits = 2**precision
    n = num_bits * num_zeros
    sinc_win = rolloff * np.sinc(rolloff * np.linspace(0, num_zeros, num=n + 1, endpoint=True))
    taper = window(2 * n + 1)[n:]
    interp_win = taper * sinc_win
    return interp_win, num_bits, rolloff
```

- Right-wing table `h[j]`, `j = 0 … N`, with `N = num_zeros · P`, `P = 2^precision`
  (samples per zero-crossing). Table length `N+1`.
- `h[j] = rolloff · sinc(rolloff · j/P) · w(j/P)`, where `w` is the right half
  (including centre) of a symmetric length-`(2N+1)` window. Default `np.hanning`;
  bundled filters use a **Kaiser window** (see §6).
- `rolloff` is a fraction of Nyquist and also the amplitude prefactor:
  `h[0] = rolloff · sinc(0) · w(0) = rolloff` (Kaiser/Hann peak = 1 at centre).
  This is confirmed by the bundled files (§6): `kaiser_fast.half_window[0] =
  0.8682120388377784` equals its stored `rolloff`, and `kaiser_best[0] =
  0.9173473712608761` equals its `rolloff`. `[V]`
- `precision` returned is `num_bits = 2^precision` (i.e. `P`), **not** the
  exponent. `get_filter`'s docstring calls it "the number of samples between
  zero-crossings"; `sinc_window`'s docstring calls it "number of bits of
  precision". Naming inconsistency — see §8. `[V]`
- `np.diff(interp_win, append=interp_win[-1])` in `core.py` produces
  `Δ[j] = h[j+1] − h[j]` with `Δ[N] = 0` (last increment zero). `[I]` from NumPy
  `diff` semantics; the call itself is `[V]`.

### 3.3 Core resampling loop — `resampy/interpn.py:_resample_loop` `[V]`

Inputs: `x` (length `n_orig`), `t_out` (length `n_out`), `interp_win`
(`nwin = N+1`), `interp_delta`, `num_table` (= `P`), `scale`, and a
**pre-zeroed** output `y`. `y` is allocated by `core.py` with
`np.zeros_like(x, dtype=dtype, shape=shape)` and passed as the gufunc output
buffer; the loop accumulates with `y[t] += …`. `[V]` + `[I]` on gufunc semantics.

```
index_step = int(scale * num_table)
for t in prange(n_out):                      # parallel=... ; behaves as range when parallel=False
    τ = t_out[t]
    n   = int(τ)                             # integer part (τ ≥ 0 → truncation toward zero)
    f   = scale * (τ − n)                   # fractional position, scaled
    o   = int(f * num_table); η = f*num_table − o        # table offset + interpolation factor
    i_max = min(n + 1, (nwin − o) // index_step)
    for i in range(i_max):                  # LEFT wing: x[n], x[n−1], …
        q = o + i*index_step
        weight = interp_win[q] + η * interp_delta[q]
        y[t] += weight * x[n − i]
    f = scale − f; o = int(f*num_table); η = f*num_table − o
    k_max = min(n_orig − n − 1, (nwin − o) // index_step)
    for k in range(k_max):                  # RIGHT wing: x[n+1], x[n+2], …
        q = o + k*index_step
        weight = interp_win[q] + η * interp_delta[q]
        y[t] += weight * x[n + k + 1]
```

Interpretation `[I]`: `weight ≈ h(q + η)` is a **first-order (linear)
interpolation** of the filter table at a fractional table index; the two wings
evaluate the symmetric kernel around the interpolation instant. `prange`
parallelises over independent output samples (no cross-output reduction), which
is why `tests/test_quality.py::test_quality_sine_parallel` can demand
`np.testing.assert_allclose(y_seq, y_par, rtol=1e-13)`.

There are **two compiled variants**, both `@guvectorize("(n),(m),(p),(p),(),()->(m)", nopython=True)`
wrapping `jit(nopython=True, nogil=True, parallel=…)`:
`resample_f_p` (parallel) and `resample_f_s` (sequential). **No `cache=True`**,
so Numba compiles on first call in each process. `[V]`

### 3.4 Orchestration — `resampy/core.py:resample` `[V]`

1. `sr_orig <= 0` → `ValueError("Invalid sample rate: sr_orig={}")`;
   `sr_new <= 0` → `ValueError("Invalid sample rate: sr_new={}")`.
2. `sr_orig == sr_new` → `return x.copy()` (no interpolation; **original dtype
   preserved**). Tests: `test_resample_matched`.
3. `sample_ratio = float(sr_new) / sr_orig`.
4. Output length: `shape[axis] = int(shape[axis] * float(sr_new) / float(sr_orig))`
   — explicit float multiply/divide to avoid FP round-off (issue #111). Truncates
   toward zero. `if shape[axis] < 1` → `ValueError("Input signal length=… is too
   small to resample from …->…")`.
5. dtype: integer input → `np.float32`; otherwise preserve `x.dtype`.
   `y = np.zeros_like(x, dtype=dtype, shape=shape)` — `np.zeros_like` default
   `order='K'` preserves C/F contiguity (`test_contiguity`).
6. `interp_win, precision, _ = get_filter(filter, **kwargs)` — **the third value
   (`rolloff`) is discarded**.
7. Downsampling (`sample_ratio < 1`): `interp_win = sample_ratio * interp_win`
   (gain compensation; "Make a copy to prevent modifying the filters in place").
8. `interp_delta = np.diff(interp_win, append=interp_win[-1])`.
9. `scale = min(1.0, sample_ratio)`; `time_increment = 1.0 / sample_ratio`;
   `t_out = np.arange(shape[axis]) * time_increment`. So output sample `j` maps
   to input time `τ_j = j · sr_orig / sr_new`.
10. Dispatch `resample_f_s(x.swapaxes(-1, axis), t_out, interp_win,
    interp_delta, precision, scale, y.swapaxes(-1, axis))`; if `parallel=True`,
    try `resample_f_p` and, on `numba.TypingError`, `warnings.warn(... "Fallback
    to the sequential version")` then `resample_f_s`.

`x.swapaxes(-1, axis)` / `y.swapaxes(-1, axis)` move the target axis to the
last position so the gufunc core-dimension `(n)` broadcasts over all leading
dimensions — this is how **arbitrary-dimensional** inputs are handled. `[V]` + `[I]`

### 3.5 Cutoff / upsampling / downsampling `[V]` + `[I]`

- `scale = min(1, sample_ratio)` feeds `index_step = int(scale*P)` and
  `f = scale*(τ−n)`; for downsampling the filter is effectively **stretched**
  in input-sample units (step `S < P`), lowering the cutoff to the new Nyquist.
  Upsampling uses `scale=1` (`S = P`).
- Downsampling additionally multiplies the kernel by `sample_ratio`.
- The stored `rolloff` is **not** used by `resample`; cutoff adaptation is via
  `scale` and amplitude scaling. `resample_nu`'s docstring explicitly notes:
  "the filter `rolloff` is not automatically adapted in case of subsampling …
  results … could be slightly different … if the filter parameters are not
  carefully set". In `resample_nu`, `scale` is hard-coded `1.0`. `[V]`
- `resample_nu` (`core.py:181`): validates `sr_orig > 0`, `t_out.ndim == 1`,
  `0 <= min(t_out)` and `max(t_out) <= (x.shape[axis]-1)/sr_orig`; sets
  `shape[axis] = len(t_out)`; normalises `t_out *= sr_orig` when `sr_orig != 1.0`;
  calls the same loop with `scale=1.0`. `[V]`

### 3.6 Boundary / padding `[V]` + `[I]`

No explicit padding array is built. `i_max = min(n+1, …)` and
`k_max = min(n_orig−n−1, …)` clip the summations to available samples, which is
equivalent to **zero-extension** outside `[0, n_orig−1]`. Output `y` starts at
zero. `[I]`

### 3.7 Floating-point precision & stability `[V]` + `[I]`

- Filter tables are `float64` (`<f8`, little-endian) — verified by parsing the
  `.npy` headers (§6).
- Output dtype = input dtype (float32, float64, complex64, complex128) except
  integer→float32. Accumulation `y[t] +=` therefore occurs in the **output
  dtype**; float32 inputs accumulate in float32. `[V]` + `[I]`
- `tests/test_quality.py` quality gates are on `mean(|y − y_pred|)` against an
  ideal sine: `sinc_window 1e-6`, `kaiser_fast 1e-4`, `kaiser_best 1e-7`
  (sweep tests use `1e-1`); sequential-vs-parallel uses `rtol=1e-13`. These are
  **upstream accuracy-vs-ideal thresholds**, not port-vs-reference equality
  tolerances. `[V]`
- `[U]` Bit-exact reproduction depends on Numba/LLVM code generation, input
  dtype, and accumulation order; this has **not** been verified for a Mojo port
  and is a Phase 2 risk.

---

## 4. Behaviour inventory: edge cases `[V]` source / `[I]` inference / `[U]` unresolved

| Case | Upstream behaviour | Evidence | Label |
|---|---|---|---|
| `sr_orig <= 0` / `sr_new <= 0` | `ValueError` | `core.py:98-102`; `test_bad_sr`, `test_bad_sr_nu` | `[V]` |
| `sr_orig == sr_new` | `x.copy()`, no interpolation, dtype preserved, `OWNDATA` | `core.py:104-106`; `test_resample_matched` | `[V]` |
| Non-integer `sr_orig`/`sr_new` | accepted (docstring says `int > 0` but code uses `float()`) | `core.py:108,114`; docstring `core.py:26-30` | `[V]` |
| Empty input (`shape[axis]=0`) | `shape[axis]=0 < 1` → `ValueError` | `core.py:114-120` | `[I]` (code path, not upstream-tested) |
| Single sample, upsampling | output length `int(1*ratio)` ≥1; loop clipped to one sample | `core.py:114`; `interpn.py:40,60` | `[I]` |
| Single sample, downsampling | `int(1*ratio)=0 < 1` → `ValueError` | `core.py:114-120` | `[I]` |
| "Short signal" | `x=np.zeros(2)`, `resample(x,4,1)` → `ValueError` | `test_short_signal` (xfail strict) | `[V]` |
| Very large downsampling ratio | `[U]` — if `scale*P < 1` then `index_step=0` → division by zero in `(nwin−o)//index_step`; may be pre-empted by the `< 1` length check. Not covered by upstream tests. | `interpn.py:9,40,60` | `[U]` |
| Large upsampling ratio | output size `int(L*ratio)` can be large; no explicit cap | `core.py:114` | `[I]` |
| NaN / Inf in `x` | no explicit validation; propagates through `weight * x[n−i]` | `core.py`, `interpn.py` | `[U]` (no upstream test) |
| NaN/Inf in `sr_*` | no explicit validation beyond `<= 0` | `core.py:98-102` | `[U]` |
| Multi-channel / N-D | `swapaxes(-1, axis)` + gufunc broadcast; docs show 1-D, 2-D, 4-D | `core.py:145-151`; `docs/example.rst`; `test_shape` (3-D), `test_resample_axis` (4-D) | `[V]` |
| `axis` | any valid axis incl. negative; `shape[axis]` and `swapaxes` | `core.py:114,145`; `test_shape` axes 0,1,2; `test_contiguity` axes 0,-1 | `[V]` |
| `np.complex64/128` | supported, output dtype preserved | `test_dtype`, `test_resample_nu_dtype`; changelog #14 | `[V]` |
| Integer dtypes (int16/32/64) | output `np.float32` | `test_dtype_int`, `test_dtype_int_nu`; `docs/example.rst` | `[V]` |
| C/F contiguity | preserved (`np.zeros_like` order='K') | `test_contiguity`, `test_resample_nu_contiguity`; changelog #68 | `[V]` |
| Non-contiguous arrays | `[U]` — `swapaxes` returns a view; gufunc stride handling not tested upstream | `core.py:145` | `[U]` |
| `t_out` 2-D / empty / out-of-domain | `ValueError` (`test_bad_time_nu`, `test_resample_nu_domain`) | `core.py:250-260` | `[V]` |
| Unsupported dtype | docstring claims `TypeError`; **no explicit `raise TypeError` exists in `core.py` at 0.4.3** | `core.py:60-61,220-221` | `[V]` discrepancy; `[U]` actual exception type |
| Missing/invalid filter name | `NotImplementedError` via `get_filter` | `filters.py:185-189`; `test_filter_missing` | `[V]` |

---

## 5. Upstream tests inventory `[V]`

- `tests/test_core.py` (22 test functions): `test_shape`, `test_resample_nu_shape`,
  `test_bad_sr`, `test_bad_sr_nu`, `test_bad_time_nu`, `test_bad_rolloff`,
  `test_bad_precision`, `test_bad_num_zeros`, `test_dtype`, `test_dtype_int`,
  `test_dtype_int_nu`, `test_resample_nu_dtype`, `test_bad_window`,
  `test_short_signal`, `test_resample_nu_short_signal`, `test_good_window`,
  `test_contiguity`, `test_resample_nu_contiguity`, `test_resample_nu_domain`,
  `test_resample_matched`, `test_resample_axis`, `test_resample_length_rounding`
  (`x=np.zeros(12499)`, 12499→15001 ⇒ `len(y)==15001`),
  `test_resample_rates_fixedprecision` (720200 samples, `sr_out=np.int32(4000)`,
  `sr_in=22050`).
- `tests/test_filters.py`: `test_filter_sinc` (grid over filter/window/num_zeros/
  precision/rolloff), `test_filter_load`, `test_filter_missing`,
  `test_filter_cache_reset`.
- `tests/test_quality.py`: `make_tone`, `make_sweep`, `test_quality_sine`,
  `test_quality_sweep`, `test_resample_nu_quality_sine`,
  `test_resample_nu_quality_sweep`, `test_quality_sine_parallel` (rtol 1e-13),
  `test_resample_nu_quality_sine_parallel`.
- Upstream CI (`ci.yml`) tests Python 3.6–3.12 on Linux, plus Windows/macOS
  (3.12), installing `numpy scipy numba pytest pytest-cov pytest-doctestplus`,
  running `pytest tests` and `pytest --doctest-only resampy`; `ci-minimal.yml`
  pins `numpy==1.17 scipy==1.0 numba==0.53` on Python 3.6.

**Relevance to PyroMojo:** these tests are the primary evidence for which
behaviours are contractual. Note they use `np.random.randn` **without a fixed
seed** — they are not golden vectors. PyroMojo must build its own deterministic
corpus (see `api-scope.md` / `benchmark-design.md`). `[I]`

---

## 6. Filter audit `[V]`

Source: `resampy/data/*.npz` at `7c484f8`, parsed with Python stdlib
(`zipfile` + `struct` + `ast`) — no NumPy was installed or used.

Each `.npz` is a ZIP containing three `.npy` v1.0 arrays:
`half_window.npy`, `precision.npy`, `rolloff.npy`.

| Property | `kaiser_fast.npz` | `kaiser_best.npz` |
|---|---|---|
| File size | 99,100 B | 3,277,596 B |
| `half_window` dtype | `<f8` (float64, little-endian) | `<f8` |
| `half_window` shape | `(12289,)` | `(409601,)` |
| `half_window[0]` | `0.8682120388377784` | `0.9173473712608761` |
| min / max | −0.1844828875 / 0.8682120388 | −0.1980741903 / 0.9173473713 |
| `precision` (stored `P`) | `512` (`<i8`) | `8192` (`<i8`) |
| `rolloff` | `0.8682120388377784` (`<f8`) | `0.9173473712608761` (`<f8`) |
| Implied `num_zeros` (`=(len−1)/P`) | `24` | `50` |
| Implied exponent (`log2 P`) | `9` | `13` |

These match the parameters documented verbatim in `resampy/filters.py:10-28`:
`kaiser_best` β=12.9846, roll=0.917347, #zeros=50, precision=13,
attenuation=−120 dB; `kaiser_fast` β=9.90322, roll=0.868212, #zeros=24,
precision=9, attenuation=−93 dB. `[V]`

- **Two bundled filters**, selected by string name `filter='kaiser_fast'` /
  `'kaiser_best'` (default `'kaiser_best'`). `[V]` `core.py:17,130`.
- **Stored, not generated at runtime.** `load_filter` uses
  `importlib_resources.files("resampy") / 'data' / f'{filter_name}.npz'`,
  `np.load(...)`, reads keys `half_window`, `precision`, `rolloff`, and caches in
  `FILTER_CACHE`. Resources are loaded **lazily on first use**, not at import.
  `[V]` `filters.py:192-217`; changelog #99.
- **Custom filters are supported**: a callable passed as `filter=`, or the
  string `'sinc_window'` with `num_zeros`, `precision`, `window`, `rolloff`
  kwargs; `get_filter` calls `name_or_function(**kwargs)` and expects
  `(half_window, precision, rolloff)`. Pre-computed filter kwargs are ignored.
  `[V]` `filters.py:145-189`.
- **Generation (offline, not runtime):** `scripts/create_filter.py` uses
  `optuna` TPE search (seed 20220629) over Kaiser β and rolloff, minimising
  passband deviation + stopband attenuation via `scipy.signal.freqz`, then calls
  `resampy.filters.sinc_window(...)` and `np.savez(...)`. It is **not** a runtime
  dependency. `[V]`
- `clear_cache()` empties `FILTER_CACHE`; `FILTER_FUNCTIONS = ['sinc_window']`.
  `[V]`

**Can the coefficients be ported directly?** `[I]` Yes, mechanically: they are
plain float64 little-endian arrays with no header magic beyond `.npy`, so exact
IEEE-754 values can be transcribed into Mojo without changing any numerical
value. Consequences to plan for: `kaiser_best` is 409,601 float64 values
(~3.2 MB) — a sizeable embedded table; `kaiser_fast` is 12,289 (~98 KB).
Practical v0.1.0 recommendation is to ship `kaiser_fast` first and defer
`kaiser_best`, purely for size/compile reasons, with a documented deviation.
**Licensing** of transcribing these data files is a separate question — see
`licensing-audit.md` §2/§6. **No coefficients were regenerated or approximated
in Phase 1.** `[V]`

---

## 7. Dependency summary `[V]`

Source: `setup.cfg` `[options] install_requires`, `[options.extras_require]`,
`pyproject.toml`, `resampy/*.py` imports, PyPI `requires_dist`. Full table in
`licensing-audit.md`.

- **Runtime:** `numpy>=1.17`, `numba>=0.53`, plus
  `importlib_resources; python_version < "3.9"` (conditional backport).
  `filters.py:51-55` chooses `importlib_resources` for old Python.
- **Not runtime:** `scipy` appears only in doctests/examples and
  `scripts/create_filter.py`; it is **not imported** by `resampy/*.py` runtime
  code. `docs/index.rst:20-22` claiming "Its dependencies are numpy, scipy, and
  numba" is **stale** relative to `setup.cfg`. `[V]` discrepancy.
- `optuna>=2.10.0` (design extra), `numpydoc`/`sphinx` (docs extra),
  `pytest<8`, `pytest-cov`, `scipy>=1.1` (tests extra).
- `interpn.py` imports `guvectorize, jit, prange` from `numba`; `core.py`
  imports `numba` (for `numba.TypingError`) and `numpy`.
- `[U]` Exact dependency licences for the **pinned** versions require a
  per-package check; PyPI metadata for current latest was inspected but is not
  authoritative for pinned versions (see `licensing-audit.md`).

`[I]` A **native Mojo implementation needs none of these at runtime** — the
numerical work (filter table creation/loading, the interpolation loop) must be
Mojo. Python/NumPy/Numba are needed only to produce expected outputs in the
reference venv.

---

## 8. Documented behaviour vs actual implementation `[V]` discrepancies

| # | Documentation says | Source at 0.4.3 does | Impact |
|---|---|---|---|
| 1 | `resample_nu(..., parallel=False)` docstring: "**Default: True**" (`core.py:208`); RTD renders the same | signature is `parallel=False` (`core.py:182`); changelog v0.4.0 "switched to parallel=False by default" | both functions actually default sequential; do not encode "True" |
| 2 | `resample` docstring Raises `TypeError` for unsupported dtype (`core.py:60-61`) | no `raise TypeError` in `core.py`; only `ValueError`s | likely surfaces from Numba typing; `[U]` exact type |
| 3 | `x : np.ndarray, dtype=np.float*` (`core.py:23`) | integer and complex inputs supported and tested | docstring narrower than behaviour |
| 4 | `sinc_window` docstring "num_bits … bits of precision" / "precision : int > 0" / ValueError if `precision < 1` | returns `2**precision`; validation is `precision < 0` (so 0 allowed) | naming/validation mismatch |
| 5 | `docs/index.rst`: dependencies numpy, **scipy**, numba | scipy is not a runtime import | stale docs |
| 6 | `filters.py:7` "constructed by the `create_filters.py` script" | file is `scripts/create_filter.py` (singular) | minor |
| 7 | RTD "stable" API page title says version **0.4.2** | latest release is 0.4.3 | docs deployment lag |
| 8 | `README`/paper describe band-limited sinc; paper says "written in Cython" | 0.4.3 core is Numba (`interpn.py`) | historical, not current |

---

## 9. Source references (primary)

| Topic | URL / path |
|---|---|
| Repository | `https://github.com/bmcfee/resampy` |
| Release `0.4.3` | `https://github.com/bmcfee/resampy/releases/tag/0.4.3` |
| Target commit | `https://github.com/bmcfee/resampy/commit/7c484f8eec54b87e8f566578dc3e48a2be81cc80` |
| `core.py` at tag | `https://github.com/bmcfee/resampy/blob/0.4.3/resampy/core.py` |
| `filters.py` at tag | `https://github.com/bmcfee/resampy/blob/0.4.3/resampy/filters.py` |
| `interpn.py` at tag | `https://github.com/bmcfee/resampy/blob/0.4.3/resampy/interpn.py` |
| `__init__.py` / `version.py` | `https://github.com/bmcfee/resampy/blob/0.4.3/resampy/__init__.py` |
| Filter data | `https://github.com/bmcfee/resampy/tree/0.4.3/resampy/data` |
| Filter generator | `https://github.com/bmcfee/resampy/blob/0.4.3/scripts/create_filter.py` |
| Tests | `https://github.com/bmcfee/resampy/tree/0.4.3/tests` |
| Packaging | `https://github.com/bmcfee/resampy/blob/0.4.3/setup.cfg` |
| License | `https://github.com/bmcfee/resampy/blob/0.4.3/LICENSE.md` |
| Changelog | `https://github.com/bmcfee/resampy/blob/0.4.3/docs/changes.rst` |
| Examples | `https://github.com/bmcfee/resampy/blob/0.4.3/docs/example.rst` |
| PyPI | `https://pypi.org/project/resampy/0.4.3/` · `https://pypi.org/pypi/resampy/json` |
| Official docs (API) | `https://resampy.readthedocs.io/en/stable/api.html` (renders 0.4.2) |
| Algorithm reference | Smith, *Digital Audio Resampling Home Page*, `https://ccrma.stanford.edu/~jos/resample/` |
| JOSS paper | `paper/paper.md`, `paper/paper.bib`, DOI `10.5281/zenodo.163184` |

---

## 10. Open questions `[U]`

1. Exact behaviour for empty/single-sample inputs and very large rate ratios
   (§4) — reasoned from code, not executed; no upstream test coverage.
2. Exact exception type for unsupported dtypes (docstring `TypeError` vs absent
   explicit raise).
3. NaN/Inf propagation semantics (no upstream tests).
4. Non-contiguous / strided array handling through `swapaxes` + gufunc.
5. Whether Numba JIT output is bit-reproducible across Numba/LLVM/OS versions —
   needed to define a defensible tolerance policy (see `api-scope.md` §6).
6. Whether the reference environment must be Python ≤3.9 (conditional
   `importlib_resources`) or a modern 3.12/3.13 with current NumPy/Numba —
   Phase 2 dependency decision, **no installation performed in Phase 1**.
7. Whether `resampy 0.4.3` on PyPI is reproducible from the tag on the target
   platform (wheel is pure-Python `py3-none-any`; verified byte-identical here).
8. Licensing of transcribing bundled `.npz` coefficient tables — legal review
   (`licensing-audit.md` §6).
