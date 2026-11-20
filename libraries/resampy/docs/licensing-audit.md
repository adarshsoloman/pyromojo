# Licensing and provenance audit: `resampy` for PyroMojo

**Phase 1 deliverable — dependency and provenance analysis.**
**Reference:** `resampy` 0.4.3, commit `7c484f8eec54b87e8f566578dc3e48a2be81cc80`.
**Status:** research/specification only. **This document makes no legal
conclusions**; it records verified facts and identifies obligations and
questions that require legal review.

**Labels:** `[V]` verified from primary source · `[I]` engineering
classification/recommendation · `[U]` unresolved / requires legal review.

**Related Phase 1 documents:** [reference-audit.md](reference-audit.md) · [api-scope.md](api-scope.md) · [benchmark-design.md](benchmark-design.md) · [library README](../README.md).

---

## 1. Upstream package licence `[V]`

- GitHub API `https://api.github.com/repos/bmcfee/resampy` reports
  `license: ISC` (`spdx_id: "ISC"`).
- `setup.cfg` `[metadata]`: `license = ISC`,
  `license_file = LICENSE.md`, classifier
  `License :: OSI Approved :: ISC License (ISCL)`.
- PyPI `resampy/0.4.3/json` → `info.license = "ISC"`.
- `LICENSE.md` at tag `0.4.3` (743 B), verbatim:

  > ISC License
  >
  > Copyright (c) 2016, Brian McFee
  >
  > Permission to use, copy, modify, and/or distribute this software for any
  > purpose with or without fee is hereby granted, provided that the above
  > copyright notice and this permission notice appear in all copies.
  >
  > THE SOFTWARE IS PROVIDED "AS IS" … [full warranty/liability disclaimer]

- `paper/codemeta.json` also declares `"license": "ISC"` (version field there is
  stale: `"0.1.4"`, `dateCreated 2016-10-25`; it is a JOSS metadata file, not
  the current package metadata).
- `[V]` The JOSS paper (`paper/paper.md`) describes the licence as
  "permissive (BSD-style)"; this is descriptive prose, not the legal text.
  The `LICENSE.md` ISC text governs.

**Obligation recorded `[V]`:** the ISC text requires the copyright notice and
permission notice to appear in all copies. PyroMojo's
`THIRD_PARTY_NOTICES.md` policy (§"Attribution", "Retain all required
copyright and attribution notices … when in doubt, keep the upstream notice
and add an entry to this file") is the mechanism to satisfy this.
`[U]` Whether a from-scratch Mojo reimplementation that does not copy source
files but **does** transcribe `.npz` coefficient tables constitutes a "copy"
requiring that notice is a legal question — see §6.

---

## 2. Bundled filter resources provenance `[V]` + `[U]`

`resampy/data/kaiser_fast.npz` and `kaiser_best.npz` are distributed as
`package_data` (`setup.cfg [options.package_data] resampy = data/*`) inside the
ISC-licensed distribution. Exact contents verified in `reference-audit.md` §6:

| File | `half_window` | `precision` (P) | `rolloff` |
|---|---|---|---|
| `kaiser_fast.npz` | float64 × 12,289 | 512 | 0.8682120388377784 |
| `kaiser_best.npz` | float64 × 409,601 | 8192 | 0.9173473712608761 |

- `[V]` They were **generated offline** by `scripts/create_filter.py` using
  `optuna` (TPE, seed `20220629`), `scipy.signal.freqz`/`kaiser`, and
  `resampy.filters.sinc_window`; parameters are documented in
  `resampy/filters.py:10-28`. Changelog v0.3.0 #98: "Automate pre-computed
  filter generation. Regenerated and improved kaiser_fast and kaiser_best
  filters."
- `[V]` The coefficients are **numeric data** (windowed-sinc × Kaiser window),
  not prose or copied source. No third-party copyright header appears inside
  the `.npz` files (they contain only three `.npy` arrays).
- `[V]` Provenance chain verified: the tagged source `.npz` files are
  **byte-identical** to those in the official PyPI wheel `0.4.3`
  (SHA-256 checks in `reference-audit.md` §1.5/§6).
- `[U]` **Unresolved:** whether transcribing these float64 tables into Mojo
  (a) is permissible without additional notice, (b) requires retaining the ISC
  notice, and (c) counts as "distributing a copy" of upstream data. Also
  `[U]`: whether the Kaiser-window / band-limited-sinc design method carries
  any third-party rights (the upstream README/paper cite Smith's *Digital Audio
  Resampling Home Page* and compare to `libsamplerate`; the paper notes
  `libsamplerate` has a different licence). **No legal conclusion is made.**

**Recommendation `[I]`:** until legal review, (1) do **not** copy the `.npz`
files verbatim into the repository; (2) treat any coefficient transcription as
derived data recorded with full provenance (upstream version, commit, file,
SHA-256, generation method) in `docs/` and `THIRD_PARTY_NOTICES.md`;
(3) retain the ISC notice text verbatim in the attribution entry. Phase 1 does
**not** regenerate, approximate, or transcribe any coefficients.

---

## 3. Dependency table `[V]` source facts / `[U]` licence details

Source: `setup.cfg` (`install_requires`, `extras_require`), `pyproject.toml`
(build-system), `resampy/*.py` imports, `tests/*.py`, `scripts/create_filter.py`,
`.github/workflows/*.yml`, and PyPI JSON metadata (read-only; **no installation
performed**).

| Package | Constraint (upstream) | Category | Why needed | Upstream code that uses it | Needed by native Mojo? | Avoid/replace | Licence (metadata observed) |
|---|---|---|---|---|---|---|---|
| `numpy` | `>=1.17` | Runtime / **A** reference | arrays, `np.sinc`, `np.diff`, `np.zeros_like`, `np.arange`, `np.load` `.npz`, dtype/shape | `core.py`, `filters.py`, `interpn.py` (via gufunc) | **No** `[I]` | Replace with Mojo `List[Float64]` + IEEE-754 wire | PyPI `license_expression`: `BSD-3-Clause AND 0BSD AND …` (current latest 2.5.5) `[U]` for pinned version |
| `numba` | `>=0.53` | Runtime / **A** reference | `@guvectorize`, `@jit(nopython=True)`, `prange` — the compiled interpolation loop; `numba.TypingError` | `interpn.py` (all), `core.py:7,153,291` | **No** `[I]` | Replace by native Mojo loop | PyPI `license: BSD`, classifier BSD (latest 0.68.1) `[U]` pinned |
| `importlib_resources` | `; python_version < "3.9"` | Runtime (conditional) / **A** | backport for `importlib.resources` used to locate `.npz` | `filters.py:51-55,211-213` | **No** `[I]` | Plain file/embedded table in Mojo | PyPI `license_expression: Apache-2.0` (latest 7.1.0) `[U]` pinned |
| `scipy` | `>=1.1` (`tests` extra); **not** in `install_requires` | **C** development/tests | doctest windows (`scipy.signal.hann/blackman`), `scripts/create_filter.py` (`freqz`, `kaiser`), `tests/test_core.py`, `test_filters.py` | doctests, tests, filter generator | **No** | Not needed for v0.1 (bundled filters only) | PyPI classifier BSD (latest 1.18.1) `[U]` pinned |
| `optuna` | `>=2.10.0` (`design` extra) | **C** development | Bayesian search over Kaiser β / rolloff to design filters | `scripts/create_filter.py` | **No** | n/a — offline design only | PyPI classifier MIT (latest 5.1.0) `[U]` pinned |
| `pytest` | `<8` (`tests` extra) | **C** development | upstream test runner | `tests/*`, CI | **No** | PyroMojo uses its own pytest | PyPI `license_expression: MIT` `[U]` pinned |
| `pytest-cov` | (`tests` extra) | **C** development | coverage | CI / `setup.cfg [tool:pytest]` | **No** | n/a | `[U]` |
| `pytest-doctestplus` | CI install only | **C** development | doctests | `.github/workflows/ci.yml` | **No** | n/a | `[U]` |
| `numpydoc` | `>=0.5` (`docs` extra, `docs/requirements.txt`) | **C** docs | Sphinx docstring rendering | `docs/conf.py` | **No** | n/a | PyPI classifier BSD `[U]` pinned |
| `sphinx` | `!=1.3.1` (`docs` extra) | **C** docs | build docs | `docs/` | **No** | n/a | PyPI `license_expression: BSD-2-Clause` `[U]` pinned |
| `setuptools>=48`, `wheel>=0.29.0` | build-system | **C** build | packaging | `pyproject.toml`, `setup.py` | **No** | n/a | `[U]` |
| `librosa` | **not** a dependency | **C** examples only | docs examples load audio | `docs/example.rst` (explicitly: "resampy does not depend on librosa") | **No** | n/a | n/a |

`[V]` **Important discrepancies:**
- `docs/index.rst:20-22` states "Its dependencies are numpy, scipy, and
  numba." `setup.cfg install_requires` lists only `numpy`, `numba`, and the
  conditional `importlib_resources`. **SciPy is not a runtime dependency** of
  0.4.3 (it appears only in doctests, tests, examples, and the offline filter
  generator).
- `docs/index.rst`/README also mention Cython historically; 0.4.3's core is
  Numba (`interpn.py`), not Cython.
- `setup.cfg` declares `python_requires >= 3.6` with classifiers through 3.12;
  PyPI 0.4.3 `requires_python` is empty. `[U]` exact supported interpreter set
  for the pinned deps.

---

## 4. Dependency separation (A / B / C) `[I]`

**A. Reference dependencies** — required only to run upstream Python Resampy
and generate expected outputs, in an **isolated, pinned reference venv**:

- `resampy==0.4.3`, `numpy>=1.17` (pin exact), `numba>=0.53` (pin exact),
  `importlib_resources` only if the reference interpreter is <3.9.
- Possibly `scipy` if any reference test/doctest path is executed (not needed
  for the core `resample` path).
- These are **never imported by the Mojo implementation**.

**B. Native implementation dependencies** — required by the Mojo port itself:

- **None** `[I]`. The intended architecture (`docs/architecture.md:85-86`,
  `CONTRIBUTING.md`) forbids delegating the measured native path to Python/FFI.
  Required Mojo-side capabilities are stdlib-level: `List[Float64]`, `Span`,
  `bitcast`/IEEE-754 handling, `floor`/`sqrt`/`trunc` (verified for audioop),
  and — if runtime filter generation is ever added — `sin`/`cos` (`[U]`, not
  verified in this toolchain). Filter coefficients for v0.1 are **static data**,
  so no `np.sinc`/window library is needed at runtime.
- Shared infrastructure extension: a **tolerance comparator** and float-array
  wire codec belong initially **inside `libraries/resampy/`**, not `shared/`
  (`docs/architecture.md:38` requires two consumers before promotion). `[I]`

**C. Development dependencies** — PyroMojo's existing toolchain only:
`pytest`, `ruff`, `pytest-benchmark`, `uv`, Mojo 1.2.0. Plus **A** in the
reference venv for oracle/vector generation. No new tooling is required for
Phase 1; **nothing was installed**.

**Architecture constraints `[V]`/`[I]`:** Python may be the upstream reference;
Python must **not** become a runtime dependency of the native Mojo
implementation; the native implementation must perform the numerical work.
`THIRD_PARTY_NOTICES.md` §"License compatibility" requires a compatibility
review for any **copyleft** dependency before distribution — none of the
observed licences above is copyleft, but `[U]` each pinned version's licence
must be confirmed and recorded rather than assumed from "latest" metadata.

---

## 5. Algorithmic material provenance `[V]` / `[U]`

- `[V]` Method: **band-limited sinc interpolation**, cited by upstream
  `README.md:12-16`, `docs/index.rst:9-12`, `paper/paper.md:20` to
  Smith, *Digital Audio Resampling Home Page*, CCRMA Stanford,
  `https://ccrma.stanford.edu/~jos/resample/` (reachable 2026-11-18).
  `paper/paper.bib` records `@BOOK{RESAMPLE, AUTHOR="Julius O. Smith",
  TITLE="Digital Audio Resampling Home Page", YEAR=2002, PUBLISHER=URL}`.
- `[V]` The paper compares functionality to `libsamplerate` (Secret Rabbit
  Code, `paper/paper.bib` `@misc{libsamplerate, 2005}`) and notes Resampy has a
  permissive licence while libsamplerate does not. **No libsamplerate code is
  vendored** in `resampy/`.
- `[V]` Upstream tests use `scipy.signal.windows.hann`, `blackman`, `kaiser`
  only as window callables / quality references.
- `[I]` The mathematical method (windowed-sinc interpolation) is a general
  signal-processing technique; implementing the same mathematics in Mojo does
  not by itself copy upstream source. However, **the specific precomputed
  coefficient tables are upstream data files** (§2), and the exact loop
  structure in `interpn.py` is upstream source. PyroMojo's own policy
  (`docs/architecture.md:85-86`, `CONTRIBUTING.md:23-24`) requires an
  independent native implementation with documented deviations; a
  line-by-line translation of `interpn.py` should be reviewed.
- `[U]` Whether reproducing the algorithm's exact numerical behaviour (needed
  for compatibility) creates any obligation beyond the ISC notice; whether the
  Kaiser-window design / Smith reference requires citation in PyroMojo docs;
  whether the JOSS paper's "BSD-style" phrasing has any bearing. **No legal
  conclusion.**

---

## 6. Obligations and questions requiring legal review `[U]`

**Recorded obligations (facts, not conclusions):**

1. ISC `LICENSE.md` requires the copyright + permission notice in all copies
   (`reference-audit.md` §1). `THIRD_PARTY_NOTICES.md` already exists as the
   project's attribution mechanism and currently carries an audioop/Sun
   Microsystems entry — a Resampy/ISC entry would follow that pattern.
2. `CONTRIBUTING.md:31`: "Do not add a dependency without stating why and
   confirming its license." `CONTRIBUTING.md:62-64`: new third-party
   dependencies must be documented; copyleft requires explicit review.
3. `THIRD_PARTY_NOTICES.md` §"Per-library documentation" requires each library
   to document the pinned upstream package/version, upstream licence and terms,
   transitive dependencies, and deviations.

**Questions for legal review (unresolved, no conclusions made):**

- Q1. Does transcribing the `kaiser_fast`/`kaiser_best` float64 coefficient
  arrays into Mojo count as distributing a copy of upstream material requiring
  the ISC notice? If yes, what exact notice text/location is required?
- Q2. Is a **from-scratch** Mojo implementation that reproduces `interpn.py`'s
  arithmetic a derivative work? (Clean-room status is **not** claimed here —
  `[U]`. The repository's audioop precedent describes an "independent native
  implementation" with transcribed, licensed tables and retained notices.)
- Q3. Confirm licences of the **exact pinned** `numpy`/`numba`/`scipy`/
  `importlib_resources` versions selected for the reference venv; metadata
  observed here was for current latest versions, which may differ.
- Q4. Confirm no copyleft dependency enters the reference venv transitively
  (e.g. `llvmlite`, which Numba depends on) that would trigger
  `THIRD_PARTY_NOTICES.md`'s copyleft review. `[U]` — not audited in Phase 1.
- Q5. Does the Smith/CCRMA algorithm reference or the JOSS paper require
  citation in PyroMojo documentation? (Academic attribution, likely low risk,
  but not decided.)
- Q6. Are the `.npz` filter files themselves covered by the ISC `LICENSE.md`
  or by a separate notice? (No separate header was found inside the files.)

**Explicitly not done in Phase 1:** no licence file was modified, no dependency
was installed or pinned, no `pyproject.toml`/`uv.lock` change, no coefficient
transcription, no clean-room or derivative-work claim.

**Phase 5 execution note:** with explicit user authorization, the repository
`.venv` was populated test-only with `resampy==0.4.3`, `numpy==2.5.5`,
`numba==0.68.1`, and `llvmlite==0.50.0` via `uv pip install`; `pyproject.toml`
and `uv.lock` were not changed. The parity test reads the installed upstream
`kaiser_fast` table into a temporary directory and does not commit or
redistribute it. Q1/Q6 remain unresolved for committing a standalone
coefficient resource. No legal conclusion is made.

**Phase 7 release gate:** the unresolved coefficient-data question is a release
blocker. The repository contains only the synthetic resource. A v0.1.0 release
must not commit, embed, package, or distribute the production `kaiser_fast`
table until written clearance permits redistribution, or an alternative
production filter resource with explicitly documented compatible terms is
provided. The exact requirement and current verdict are recorded in
[`../RELEASE_READINESS.md`](../RELEASE_READINESS.md) §8.

---

## 7. Summary `[I]`

- Upstream licence: **ISC** (permissive), verified from three independent
  primary sources. `[V]`
- Runtime deps: `numpy`, `numba`, conditional `importlib_resources`; **no SciPy
  runtime dependency** at 0.4.3. `[V]`
- Native Mojo implementation: **zero runtime dependencies**; a validated
  external filter resource is supplied by the caller. The repository commits
  only a synthetic resource. `[I]`
- The two upstream float64 filter tables are data files whose redistribution
  is the main provenance question. `[V]` facts / `[U]` legal review. Neither
  production table is included in this repository.
- All licence-specific conclusions are deferred; six questions listed for
  review. No legal determination, no clean-room claim, no dependency changes.
