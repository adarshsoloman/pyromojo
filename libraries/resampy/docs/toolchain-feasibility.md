# Toolchain & Numerical Feasibility: PyroMojo Resampy v0.1.0

**Phase 2 deliverable — experimental feasibility assessment.**
**Audit date:** 2026-11-18. **Status:** research only; **no implementation**.
**Reference:** `resampy` 0.4.3, commit `7c484f8eec54b87e8f566578dc3e48a2be81cc80`
(Phase 1 `reference-audit.md`). Phase 1 scope is authoritative: 1-D Float64
signals, last-axis semantics, `kaiser_fast`, native Mojo numerical execution.

**Labels:** `[V]` directly verified by an executed command · `[I]` engineering
inference/recommendation · `[U]` unresolved / not established.

**Related Phase 2/Phase 1 documents:** [reference-audit.md](reference-audit.md) ·
[api-scope.md](api-scope.md) · [licensing-audit.md](licensing-audit.md) ·
[benchmark-design.md](benchmark-design.md) · [library README](../README.md).

All experimental code, binaries, virtual environments and generated data live
in **`/tmp/pyromojo_resampy_phase2/`** (outside the repository). The only
repository artifact created is this document.

---

## 1. Environment and toolchain versions `[V]`

| Item | Value | Verification |
|---|---|---|
| Git branch / HEAD | `main` / `eb865ad3759fefd4e9a2f4ad66c2cf884620585a` | `git status`, `git rev-parse HEAD` |
| OS | `Linux 7.0.0-28-generic x86_64 GNU/Linux`, glibc 2.39 | `uname -srmo`, `platform.platform()` |
| Host Python (repo `.venv`) | 3.13.14 | `.venv/bin/python --version` |
| System Python 3.12 | 3.12.3 (`/usr/bin/python3.12`) | `/usr/bin/python3.12 --version` |
| Mojo compiler | **Mojo 1.2.0 (2016d0cd)** | `.venv/bin/mojo --version` |
| Mojo stdlib | compiled `std.mojoc` in `.venv/lib/python3.13/site-packages/modular/lib/mojo/` | `find` |
| Build command used | `<mojo> build <src>.mojo -o <bin>` (and `--emit shared-lib` for interop) | probe driver |
| Default optimisation | `-O3`, `--fp-mode contract=fast` | `mojo build --help` (§5, §8) |

`[V]` `mojo doc` cannot introspect the precompiled package:
`mojo doc .venv/.../std.mojoc` fails with
`error: package 'ffi' does not contain 'OptionalPointer'`. Therefore all API
availability below was established **empirically by compiling probes**, not from
docs. This is important: do not assume stdlib symbol names from other languages.

**Baseline compile cost:** a trivial Mojo probe compiles in ~2.2–2.9 s; a
12,289-element `StaticTuple` literal compiles in ~11.3 s (§5). These are cold
`mojo build` wall times on this host, not benchmark numbers.

---

## 2. Reference environment selection and verification `[V]` / `[I]`

### 2.1 Version selection (official PyPI metadata, read before installing)

`[V]` Fetched `https://pypi.org/pypi/<pkg>/<version>/json` for candidate
versions and inspected `requires_python`, `requires_dist`, and wheel `cp3xx`
tags:

| Package | Version | `requires_python` | Wheel cp tags | Declared constraints |
|---|---|---|---|---|
| numba | 0.60.0 | `>=3.9` | cp39/310/311/312 | `numpy <2.1,>=1.22`; `llvmlite <0.44,>=0.43.0dev0` |
| numpy | 1.26.4 | `>=3.9` | cp39/310/311/312 | — |
| llvmlite | 0.43.0 | `>=3.9` | cp39/310/311/312 | — |
| resampy | 0.4.3 | (empty) | py3-none-any | `numpy>=1.17`, `numba>=0.53`, `importlib_resources; python_version<"3.9"` |

`[V]` Also checked alternatives: `numba 0.53.0` declares `requires_python
">=3.6,<3.10"` (Phase 1 `licensing-audit.md` §3 flagged this); `numba 0.61.2`
ships cp313 wheels and requires `numpy <2.3,>=1.24`, `llvmlite <0.45,>=0.44`.

`[I]` **Selected: Python 3.12.3 + numpy 1.26.4 + llvmlite 0.43.0 + numba
0.60.0 + resampy 0.4.3.** Rationale:
- 3.12 is the last interpreter explicitly in resampy 0.4.3's `setup.cfg`
  classifiers and in upstream `ci.yml`; the repo's existing audioop reference
  venv is also CPython 3.12.3 — consistent precedent.
- numba 0.60.0 wheels exist for cp312, and its numpy/llvmlite constraints are
  satisfied exactly by numpy 1.26.4 / llvmlite 0.43.0 (all three have cp312
  wheels). No dependency resolution guesswork.
- Deliberately **did not** use the host Python 3.13.14 (would require numba
  0.61.x and numpy 2.x — a newer, less-audited combination), and **did not** use
  numba 0.53 (excludes Python ≥3.10).

### 2.2 Environment creation and verification (exact commands)

```
/usr/bin/python3.12 -m venv /tmp/pyromojo_resampy_phase2/refvenv
/tmp/pyromojo_resampy_phase2/refvenv/bin/pip install --no-cache-dir \
    "numpy==1.26.4" "llvmlite==0.43.0" "numba==0.60.0" "resampy==0.4.3"
# -> Successfully installed llvmlite-0.43.0 numba-0.60.0 numpy-1.26.4 resampy-0.4.3 (exit 0)
```

`[V]` `verify_env.py` (in the workspace) reported:

```
python 3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]  CPython  x86_64
os Linux-7.0.0-28-generic-x86_64-with-glibc2.39  byte_order little
numpy 1.26.4   numba 0.60.0   llvmlite 0.43.0   resampy 0.4.3
```

`[V]` All four required checks passed:

1. **Import Resampy** — `import resampy; resampy.__version__ == "0.4.3"`.
2. **Load `kaiser_fast`** — `resampy.filters.get_filter("kaiser_fast")` returned
   `float64 (12289,)`, `precision=512`, `rolloff=0.8682120388377784`;
   `half[0] == rolloff` is `True`. This **exactly matches** Phase 1
   `reference-audit.md` §6 (parsed from the `.npz` without NumPy).
3. **Execute resampling** — `resampy.resample(sine16, 16, 32,
   filter="kaiser_fast")` → `float64 (32,)`, first 6 values
   `[0.04497260432656087, 0.44802871496326196, 0.8803609021849131,
   1.0258155253425072, 0.7463577777908869, 0.177619558325081]`.
4. **Deterministic output** — same-process repeat is bit-identical
   (`y.tobytes() == y2.tobytes()` → `True`); 3 fresh processes all produced
   SHA-256 `59cac037640520a02e86f3a17974f0beddb91676a3c1dd3639795e31c8091803`.

`[V]` **Cold JIT cost:** first `resample` call in a fresh process took
**568.03 ms**; subsequent warm calls **0.476, 0.223, 0.194, 0.156, 0.150 ms**.
Numba compiles the gufuncs on first call (`interpn.py` has no `cache=True`),
so JIT time is ~1000–3600× warm time — benchmark methodology must exclude it
(Phase 1 `benchmark-design.md` §6 already requires this).

`[U]` Whether the reference venv should be committed as a pinned
`python_reference/requirements.txt` (and which exact NumPy/Numba patch versions
for other hosts) is a Phase 3 decision; this environment is intentionally
outside the repo and **no dependency was installed into the repo**.

---

## 3. Float64 capability results `[V]`

Probes `01_float64_basic`, `02_float64_span` (workspace
`probes/01_float64_basic.mojo`, `02_float64_span.mojo`); command
`<mojo> build probes/XX.mojo -o bin/XX && ./bin/XX`.

```mojo
var a: Float64 = 1.5
var b: Float64 = 2.25
var s = a + b            # 3.75
var d = a - b            # -0.75
var p = a * b            # 3.375
var q = a / b            # 0.6666666666666666
var vals = List[Float64]()
vals.append(1.0); vals.append(2.0); vals.append(3.0)
var acc: Float64 = 0.0
for i in range(len(vals)):
    acc += vals[i]       # 6.0
var f_from_i = Float64(7)     # 7.0
var i_from_f = Int(Float64(3.75))  # 3
vals[1] = 9.5                 # indexed write: 1.0 9.5 3.0
```

`[V]` Results: all **PASS**. `sum_span(s: Span[Float64, _])` compiled and
returned `5.0` for a 5-element list; `Span(vals)` construction works; copying
element-wise into a new list and mutating it left the original unchanged
(`0.0` vs `100.0`) — value independence confirmed.

**What this proves `[V]`:** Float64 scalars, `+ - * /`, loop accumulation,
`Int→Float64` and `Float64→Int` (truncating toward zero), `List[Float64]`
indexed read/write, `Span[Float64, _]` parameter passing, and copy
independence all work on Mojo 1.2.0.
**What it does not prove `[U]`:** exact IEEE-754 conformance of every operation
under all optimisation levels (see §8), or performance on large arrays.

---

## 4. Mathematical function availability `[V]`

All discovered by compiling one probe per symbol (`probes/03`–`05`, `23`–`40`,
`41`, `45`–`48`). Exact import paths recorded.

| Function | Status | Exact import / API | Verified output |
|---|---|---|---|
| `floor` | PASS | `from std.math import floor` | `floor(2.5)=2.0`, `floor(-1.5)=-2.0` |
| `sqrt` | PASS | `from std.math import sqrt` | `sqrt(2.0)=1.4142135623730951` |
| `trunc` | PASS | `from std.math import trunc` | `trunc(-1.9)=-1.0` |
| `sin` | PASS | `from std.math import sin` | `sin(1.0)=0.8414709848078965` |
| `cos` | PASS | `from std.math import cos` | `cos(1.0)=0.5403023058681398` |
| `abs` | PASS | `from std.math import abs` | `abs(-2.5)=2.5` |
| `ceil` | PASS | `from std.math import ceil` | `ceil(2.3)=3.0`, `ceil(-2.3)=-2.0` |
| `round` | PASS | `from std.math import round` | `round(2.5)=2.0` (banker's rounding) |
| `log` | PASS | `from std.math import log` | `log(e)=1.0` |
| `exp` | PASS | `from std.math import exp` | `exp(1.0)=2.718281828459813` |
| `pow` | PASS | `from std.math import pow` | `pow(2.0,10.0)=1024.0` |
| `copysign` | PASS | `from std.math import copysign` | `copysign(1.0,-1.0)=-1.0` |
| `fma` | PASS | `from std.math import fma` | `fma(2.0,3.0,4.0)=10.0` |
| `remainder` | PASS | `from std.math import remainder` | `remainder(5.5,2.0)=-0.5` |
| `isnan` | PASS | `from std.math import isnan` | `isnan(nan)=True`, `isnan(1.0)=False` |
| `isinf` | PASS | `from std.math import isinf` | `isinf(±inf)=True`, `isinf(nan)=False` |
| `isfinite` | PASS | `from std.math import isfinite` | `isfinite(1.0)=True`, `isfinite(inf/nan)=False` |
| `pi`, `e` | PASS | `from std.math import pi, e` | `3.141592653589793`, `2.718281828459045` |
| `inf`, `nan` constants | PASS (dtype-parametric) | `from std.math import inf, nan`; `inf[DType.float64]()` | `inf`, `nan`; `isinf/isnan` True |
| `%` (float) | PASS | builtin `a % b` | `5.5 % 2.0 = 1.5` |
| `//` (int) | PASS | builtin | `-7 // 2 = -4` (Python floor semantics) |
| `bitcast` | PASS | `from std.memory import bitcast` | `bitcast[DType.uint64,1](x)[0]` |

`[V]` **Verified-absent (compile errors, exact diagnostics):**

| Attempted | Diagnostic |
|---|---|
| `fabs` | `error: package 'math' does not contain 'fabs'` |
| `fmod` | `error: package 'math' does not contain 'fmod'` |
| `isnormal` | `error: package 'math' does not contain 'isnormal'` |
| `signbit` | `error: package 'math' does not contain 'signbit'` |
| `is_nan` / `is_inf` | `error: package 'math' does not contain 'is_nan'` / `'is_inf'` |
| `x.is_nan()` / `x.is_inf()` / `x.isnan()` / `x.isfinite()` (methods) | `error: 'Float64' value has no attribute '<name>'` |
| `print(inf, nan)` (uninstantiated) | `error: ... type 'def[dtype: DType]() ...' does not conform to trait 'Writable'` |

`[V]` **Supported alternatives (verified):** use `abs` (not `fabs`), `remainder`
or `%` (not `fmod`), `isnan/isinf/isfinite` free functions (not methods, not
`is_nan`/`is_inf`), `bitcast[DType.uint64,1](x)[0] >> 63` for a sign test
(probe `45_signbit_alt`: `-0.0`→True, `0.0`→False, `-2.5`→True), and
`inf[DType.float64]()` / `nan[DType.float64]()` for constants.

`[V]` **Trigonometric accuracy:** `sin`/`cos` bit patterns at x = 0.0…4.5
step 0.5 were compared to Python `math.sin/cos` via `struct` — **10/10 exact
bit matches** (`probes/58_trig_bits.mojo`).

> **Contradiction with Phase 1 (documented, scope unchanged):** `api-scope.md`
> §5 excluded `sinc_window`/runtime filter generation partly on the grounds
> that "`sin`/`cos` — none verified in the installed Mojo 1.2.0 toolchain
> (Phase 0)". `[V]` `sin`, `cos`, `abs`, `exp`, `log`, `pow`, `pi`, `e`, `fma`
> **are** available and bit-accurate for the probed domain. This weakens *one*
> stated rationale but does not by itself justify promoting `sinc_window` into
> v0.1: runtime Kaiser/Hann window generation would still need to reproduce
> `np.sinc` and `scipy` window functions exactly, which is a separate
> unverified problem. `[I]` **Recommendation:** keep `sinc_window` OUT OF SCOPE
> for v0.1, but correct the rationale in a future `api-scope.md` revision and
> re-open the question in Phase 3. This is a decision for the maintainer.

---

## 5. Coefficient representation experiments `[V]` / `[I]`

Synthetic 12,289-element Float64 table (`i * 0.0001`), **no production filter
resource was copied, regenerated or approximated** (`data/coeffs.bin`,
98,312 bytes, generated with Python `struct.pack('<12289d', ...)`).

| Representation | Probe | Compile | Runtime load/init | Indexed read | Precision |
|---|---|---|---|---|---|
| Runtime `List[Float64]` | `15_runtime_list_12k` | 2.81 s | built in-process (~12k appends) | PASS, sum `7550.361599999995` | exact f64 |
| `StaticTuple[Float64, 12289]` literal | `17_statictuple_12k_generated` | **11.26 s** | none (compile-time) | PASS, identical sum | exact f64 |
| File-loaded binary → `List[Float64]` | `18_file_load_binary` | 2.96 s | 98,312 B read + bitcast loop | PASS, `first=0.0`, `mid=0.6144000000000001`, `last=1.2288000000000001` | exact f64 |
| Small `StaticTuple` (16) | `16_statictuple_small` | 2.41 s | none | PASS, sum `120.0` | exact f64 |

`[V]` File-load probe used the verified API:

```mojo
from std.io import FileHandle
from std.memory import bitcast
var f = FileHandle(String("/tmp/.../data/coeffs.bin"), "r")
var raw = f.read_bytes()
f.close()
# little-endian 8-byte groups reassembled into UInt64, then
# bitcast[DType.float64, 1](SIMD[DType.uint64,1](b))[0]
```

`[V]` Loaded values matched Python's `struct.unpack('<12289d', ...)` exactly
for first/mid/last — bit-exact reconstruction with explicit byte order.

`[V]` **Read-performance comparison** (`51_fair_read_comparison`, 1,000,000
runtime-varying indexed reads, compiles in 11.24 s):
`List[Float64]` 1.59 ms vs `StaticTuple` 0.68 ms, sums bit-identical
(`613854.7000002074`). A naive constant-index loop (`50`) collapsed the
StaticTuple read to 0.02 ms via **constant folding** — so an honest benchmark
must use runtime-varying indices; that result is not usable as performance data.
`[I]` These are single-run wall times on a shared desktop, not reportable
benchmarks.

`[V]` **Compile cost is the key trade-off:** `StaticTuple` with 12,289 literals
costs ~11.3 s (4× baseline) and produces a large literal source; `List` and
file-load cost ~2.8–3.0 s. All three preserve Float64 precision and are
deterministic.

> `[I]` **Answers Phase 1 open question #6** ("can Mojo 1.2.0 store/iterate a
> 12,289-element float64 StaticTuple or is a runtime List needed?"): **both
> work**. Recommendation for v0.1: **runtime `List[Float64]` loaded from a
> committed binary/hex resource** (see §11/§13) — avoids an 11 s compile and a
> ~200 KB generated Mojo literal per filter, keeps the coefficients auditable,
> and leaves `StaticTuple` as an optional later optimisation. If a compile-time
> table is preferred, `--fp-mode contract=off` (§8) must still be fixed.

---

## 6. Indexed-loop experiments `[V]`

`probes/19_indexed_loop_synthetic.mojo` (and downsampling variant
`56_loop_down.mojo`) exercise a **synthetic** loop representative of the
interpolation structure — **not** the Resampy algorithm: indexed input access,
indexed coefficient access, nested loops, Float64 accumulation, integer index
arithmetic (`offset`, `eta`, `index_step = int(scale*P)`), conditional boundary
clipping (`min(n+1, ...)`, `q >= 0`, `q < NW`), and repeated large-table reads.
All inputs/coefficients are synthetic.

`[V]` Results:
- Upsampling-scale variant: compiled 2.60 s, ran, `out_len 128`,
  `sum 5.513758719999999`, `y0 0.02213888`, `ylast 0.0`.
- Downsampling `scale=0.5` variant: `out_len 32`, `sum 2.941603840000001`
  (`-O3` fast) / `2.94160384` (`contract=off`) — see §8.
- Compiler emitted only benign warnings: "this value is borrowed here, so the
  transfer has no effect" (from `^` on borrowed function args). No special
  collection type was required; `List[Float64]` + `Int` indices worked directly.

**What this proves `[V]`:** Mojo 1.2.0 supports the required indexed numerical
loop structure, nested loops, boundary clipping, and repeated large-table
indexed reads, with ordinary `List`/`Span` types.
**What it does not prove `[U]`:** correctness of the actual Resampy
interpolation (not implemented, per phase boundary), or performance parity with
Numba.

---

## 7. Memory and collection behaviour `[V]`

`probes/20_memory_collections.mojo`, `49_return_owned.mojo`:

| Capability | Result |
|---|---|
| `List[Float64]` empty | `len 0` PASS |
| `resize(n, fill)` + single-element | `len 1`, value `1.25` / `0.0` PASS |
| 1,000,000-element allocation | `len 1000000`, first/last `1.25` PASS |
| Copy independence | original `1.25`, copy `-7.0` PASS |
| Return newly allocated output (`return t^`) | PASS for 0/1/12289 elements |
| `Span` read, `List`→copy | PASS (§3) |

`[V]` Practical findings: `List.resize(n, fill)` requires the fill argument
(consistent with Phase 0 audioop findings); returning a `List` uses `^`
transfer; ownership/borrowing is enforced by the compiler (warnings on
redundant `^`, hard errors on use-after-move). Empty and single-element
collections are safe. 1M Float64 (~8 MB) allocation succeeded.

`[U]` Not measured: peak RSS, allocator behaviour under repeated large
transients, or cache behaviour on the real 12,289-element coefficient table in
a long-running CLI process.

---

## 8. NaN/Inf and numerical behaviour `[V]`

### 8.1 IEEE-754 classification and bit patterns

`probes/21_numerical_matrix`, `41_nan_classification`, `42_float64_limits`,
`43_nan_propagation`, `45`, `46`, `48`. Bit patterns obtained with
`bitcast[DType.uint64, 1](x)[0]` and compared to Python `struct.pack('<d', x)`:

| Value | Mojo bits | Python bits | Match |
|---|---|---|---|
| `0.0` | 0 | 0 | ✓ |
| `-0.0` | 9223372036854775808 (`0x8000…`) | same | ✓ |
| `+inf` | 9218868437227405312 (`0x7ff0…`) | same | ✓ |
| `-inf` | 18442240474082181120 (`0xfff0…`) | same | ✓ |
| `nan` | 9221120237041090560 (`0x7ff8000000000000`) | same | ✓ |
| `5e-324` (smallest subnormal) | 1 | 1 | ✓ |

`[V]` Behaviour: `nan != nan` True; all four NaN comparisons (`<`, `>`, `<=`,
`>=`) return False; `0.0 == -0.0` True but bit patterns differ (signed zero
preserved); `nan + 1.0`, `nan * 2.0` keep the NaN bit pattern;
`inf - inf` and `inf / inf` produce NaN; NaN propagates through loop
accumulation; `nan * 0.0` is NaN; subnormals (`5e-324`, `1e-320`) are
representable and `isfinite` True; `1e-320 * 1e-320` underflows to `0.0`.
`isnan/isinf/isfinite` work as free functions (§4). `%` on floats follows
Python-style floor semantics (`-5.5 % 2.0 = 0.5`), `//` floors (`-7 // 2 =
-4`).

`[V]` **Do NOT claim strict IEEE-754 compatibility.** Compiler optimisations
change observable results (next section).

### 8.2 Accumulation and compiler optimisations — critical finding

`[V]` `mojo build --help` documents:
`--optimization-level <0..3>` (default **3**) and
`--fp-mode <MODE>` with feature `contract`, **default `fast`** —
"`contract=fast` is like Clang's `-ffp-contract=fast`: it fuses `a + b*c` into
an FMA across statements and breaking strict IEEE compliance. `contract=off`
disables contraction."

`probes/55_acc_contract.mojo` (accumulation `acc += w2 * xsample`, the exact
shape of the resampy inner `y[t] += weight * x[...]`):

```
<mojo> build probes/55_acc_contract.mojo -O3                     -o bin/55_O3_fast
<mojo> build probes/55_acc_contract.mojo -O3 --fp-mode contract=off -o bin/55_O3_off
<mojo> build probes/55_acc_contract.mojo -O0                     -o bin/55_O0
```

| Build | `acc_bits` | `acc` |
|---|---|---|
| `-O3` (default, contract=fast) | 4637225070590621622 | 106.93175985567981 |
| `-O3 --fp-mode contract=off` | 4637225070590621623 | 106.93175985567983 |
| `-O0` | 4637225070590621623 | 106.93175985567983 |
| Python reference loop | 4637225070590621623 | 106.93175985567983 |

`[V]` **A 1-ULP difference** between default `-O3` and contract-disabled
builds; `contract=off` matches Python exactly. The same divergence appeared in
the synthetic interpolation loop (§6): `2.941603840000001` vs `2.94160384`.
`[V]` Repeated runs of one binary are bit-identical (5/5 runs of
`55_O3_off`), so Mojo output is deterministic **for a fixed build
configuration**.

`[V]` `22_accumulation_order`: `(1e16 + 1) + (-1e16 + 1)` reassociated gives
`0.0` vs sequential `1.0` — association order matters. `21`:
`sum of 0.1 × 1,000,000 = 100000.00000133288` (error 1.33e-6), demonstrating
expected FP accumulation drift. `44_tolerance_comparator`: a `max_abs` loop
with `abs`, `isnan`, `isinf` compiled and returned `1.0000680839006293e-15` ≤
`1e-9` — a tolerance comparator is straightforward to implement natively.

> `[I]` **Implication (new risk, not in Phase 1):** FMA contraction under the
> default toolchain can shift results by ~1 ULP relative to the Numba/LLVM
> reference, whose own contraction behaviour is `[U]` unverified. This is
> small relative to the proposed `1e-9` tolerance but must be controlled:
> **fix a single build configuration (`--fp-mode contract=off`) for the native
> kernel and record it as build metadata**, or accept the ULP-level difference
> inside the tolerance. Do not assume bit-exact parity.

---

## 9. Reference output calibration `[V]` / `[I]`

`calibrate.py` (workspace), `resampy 0.4.3` in the pinned venv,
`filter="kaiser_fast"`, `axis=-1`, `parallel=False`, seed `20260610`. Output:
`/tmp/pyromojo_resampy_phase2/out/calibration_corpus.json` (29,271 B) plus
per-case `.bin` files. **Not integrated into repository tests; not a golden
vector generator.**

| Case | Kind | in | sr_orig→sr_new | out | dtype | expected_sha256 (first 16) |
|---|---|---|---|---|---|---|
| impulse_up | impulse | 16 | 16→32 | 32 | float64 | ca5bbd71ed7d84c2 |
| impulse_down | impulse | 32 | 32→16 | 16 | float64 | 9c41a268b48909c5 |
| constant_up | constant | 16 | 16→32 | 32 | float64 | 513f1dd1db6c2f97 |
| constant_down | constant | 32 | 32→16 | 16 | float64 | 2acc212c565ad647 |
| sine_up | sine | 64 | 64→128 | 128 | float64 | f968c1fadd82abf3 |
| sine_down | sine | 64 | 64→32 | 32 | float64 | 2802375ba3ff48d8 |
| random_up | random | 64 | 64→128 | 128 | float64 | 4f1d0fc3ac35588e |
| random_down | random | 64 | 64→32 | 32 | float64 | 36ec79d38728c24b |
| zero_up | zero | 16 | 16→32 | 32 | float64 | 5341e6b2646979a7 |
| zero_down | zero | 32 | 32→16 | 16 | float64 | 38723a2e5e8a17aa |
| equal_rate | sine | 16 | 16→16 | 16 | float64 | b56aa1480c2d5d43 |
| ratio_22050_16000 | sine | 97 | 22050→16000 | 70 | float64 | eba7cb80f57275bc |
| ratio_44100_16000 | impulse | 100 | 44100→16000 | 36 | float64 | d425b993f8e694ea |
| ratio_3to2 | sine | 48 | 3→2 | 32 | float64 | e7858e12694c432d |

`[V]` Output lengths match `int(L * float(sr_new)/float(sr_orig))` in every
case (e.g. 97→70, 100→36, 16→16 for equal rates). Each record contains
`input_f64le_hex`, `expected_f64le_hex`, `expected_sha256`, `expected_first8`,
input/output dtype, lengths, filter, rates and full `reference` env versions.
`[I]` Deliberately compact (≤128 samples per case); larger outputs stay outside
the repo in `.bin` files.

### 9.1 Numerical sensitivity (`numerical_sensitivity.py`) `[V]`

| Metric | Observed range across 5 cases |
|---|---|
| output `abs_max` | 0.434 – 2.234 |
| output RMS | 0.115 – 0.834 |
| sequential vs `parallel=True` max abs diff | **0.0 (bit-identical)** for all |
| float64 vs float32 output max abs diff | 2.7e-9 – 1.05e-7 |
| output change for 1e-14 relative input perturbation | 4.4e-15 – 2.7e-14 |

`[I]` The resampler is **well-conditioned** at these sizes (input perturbation
∼1e-14 → output change ∼1e-14), and float32/float64 outputs differ by up to
~1e-7 — relevant context but **not** a port-vs-reference tolerance.

---

## 10. Determinism findings `[V]`

`determinism.py`, `determinism_cross.py` (4 representative cases):

| Check | Result |
|---|---|
| 10 same-process repeats | `unique = 1` (bit-identical) for all 4 |
| Cold (first-call, includes JIT) vs warm | identical digest for all 4 |
| `parallel=False` vs `parallel=True` | `bit_identical = True`, `max_abs_diff = 0.0` for all 4 |
| 3 fresh processes × `NUMBA_NUM_THREADS` = 1 / 4 / 8 | `unique = 1` for all 4 cases |

`[V]` Upstream `resampy 0.4.3` output is **bit-identical** across repeated
calls, cold/warm JIT compilation, sequential/parallel paths, fresh processes,
and thread counts on this host. Sequential (`parallel=False`) is used for the
primary corpus as Phase 1 requires.

`[U]` Not established: determinism across different NumPy/Numba/LLVM versions,
CPU architectures, or OS builds. `[I]` The `reference` metadata block in every
vector must therefore capture package versions and host byte order (§11).

---

## 11. Golden-vector representation recommendation `[V]` / `[I]`

Measured with `gv_representations.py` on 139 float64 samples (128 sine + 11
edge values including NaN/Inf/-0.0/subnormal), raw LE = 1,112 B:

| Representation | Payload bytes | Bit-exact round-trip | Notes |
|---|---|---|---|
| JSON decimal | 2,708 | **Yes** (Python `json.dumps`/`loads`, incl. NaN bits) | emits non-standard `NaN`/`Infinity`/`-Infinity` tokens |
| hex IEEE-754 LE | 2,224 | Yes | explicit byte order if documented; 16 B/value |
| base64 LE float64 | 1,484 | Yes | 10.7 B/value; standard ASCII |
| binary file + JSON metadata | 156 (meta) + 1,112 (file) | Yes | smallest JSON; needs two artifacts |

`[V]` Size scaling for realistic random float64 (bytes/value): JSON decimal
20.7, hex 16.0, base64 10.7, raw 8.0. For all-zero data JSON decimal is
smaller (5 B/value) but that is not representative.

`[V]` **Important nuance contradicting a Phase 1 assumption:** `api-scope.md`
§6 states "JSON decimal round-tripping is not guaranteed bit-exact for all
float64 values across parsers". Python's `json.dumps` uses shortest
round-tripping repr and **was bit-exact** for all probed values including
`nextafter(1,2)`, subnormals, `-0.0`, NaN and Inf (`0.1+0.2` →
`0x3fd3333333333334` preserved). However, `NaN`/`Infinity`/`-Infinity` are
**non-standard JSON** (rejected by a strict RFC 8259 parser), and other
languages' parsers/serialisers are `[U]` unverified — so the portability
concern is real but is about **cross-parser semantics and NaN tokens**, not Python
float precision.

> `[I]` **Recommendation: JSON bundle with human-readable metadata + base64
> little-endian IEEE-754 Float64 payload fields** (`input_f64le_b64`,
> `expected_f64le_b64`), with explicit `dtype: "float64"`,
> `endian: "little"`, `count`, per-array `sha256`, `schema_version`,
> `generator{name,version}`, and the full `reference` version block. Reasons:
> exact bit reconstruction of inputs and expected outputs (including NaN/-0.0),
> explicit byte order, compact (10.7 B/value), single self-contained artifact,
> standard ASCII (no NaN tokens), easy schema versioning, and metadata stays
> human-readable. For very large vectors (e.g. >1e6 samples) fall back to
> **binary `.bin` resources with a JSON sidecar** (smallest JSON, exact bytes);
> raw `.bin` files are already the convention for the calibration corpus.
> Avoid JSON decimal as the primary representation because of NaN tokens and
> cross-parser uncertainty. **Not implemented in Phase 2** — no generator, no
> repository integration.

---

## 12. Interoperability investigation `[V]` / `[I]`

### 12.1 What exists in the repository (read-only)

`[V]` `experiments/interop_benchmark/`: `interop.mojo` exports exactly one
function `prng_checksum` via `PythonModuleBuilder` / `@export` / `abi("C")`.
Six Python scripts: `benchmark_recurrence.py`, `recurrence_test.py`,
`benchmark_smoke.py`, `diagnose_timing.py`, `inspect_interop.py`,
`scaling_test.py`. `mojo.importer` exists in the **host `.venv` (py3.13)** at
`.venv/lib/python3.13/site-packages/mojo/importer.py`; it compiles `.mojo`
sources to `.so` on import and caches in `__mojocache__/` (gitignored).

### 12.2 Which experiments are executable

`[V]` Run with `PYTHONPATH=experiments/interop_benchmark <host .venv python>
<script>`:

| Script | Result |
|---|---|
| `recurrence_test.py` | **PASS** (exit 0), "Output verification: PASSED" |
| `benchmark_recurrence.py` | **PASS** (exit 0), reported 22.59× on one workload |
| `benchmark_smoke.py` | **FAIL** `AttributeError: module 'interop' has no attribute 'sum_squares_batch'` |
| `diagnose_timing.py` | **FAIL** same missing symbol |
| `inspect_interop.py` | **FAIL** same missing symbol |
| `scaling_test.py` | **FAIL** same missing symbol |

`[V]` Confirms Phase 1 `benchmark-design.md` §3: 4 of 6 scripts reference a
function that `interop.mojo` does not define; 2 work. No recorded result
artifacts exist. `pyproject.toml` calls these "Legacy Mojo-interop
experiments".

### 12.3 Isolated PoC (outside the repo)

`[V]` Built `/tmp/pyromojo_resampy_phase2/interop_poc/phase2poc.mojo` with
`PythonModuleBuilder`, exporting `scalar_echo` and `sum_floats`:

```mojo
from std.python import Python, PythonObject
from std.python.bindings import PythonModuleBuilder

def sum_floats(py_list: PythonObject) raises -> PythonObject:
    var n = Int(py_list.__len__())
    var total: Float64 = 0.0
    for i in range(n):
        total += Float64(py=py_list[i])   # verified conversion syntax
    return Python.float(total)
```

- `<mojo> build phase2poc.mojo --emit shared-lib -o phase2poc.so` → **exit 0**,
  cold build **1.43 s**, `.so` = 168,856 B.
- `Float64(PythonObject)` and `Int(PythonObject)` **fail to compile**; the
  verified conversion is `Float64(py=obj)` / `Int(py=obj)` (same as the repo's
  `Int(py=seed_obj)`).
- `scalar_echo(3.5) = 7.0`, `sum_floats([1.0,2.5,3.5]) = 7.0` — **PASS**.
- The `.so` also loaded under Python 3.12 (refvenv) via `importlib` and summed
  a **NumPy float64 array** correctly (`45.0`).

`[V]` **Overhead measurement** (per-element Python-object marshalling):

| n | Mojo interop | pure Python loop |
|---|---|---|
| 1,000 | 0.040 ms | 0.018 ms |
| 10,000 | 0.417 ms | 0.157 ms |
| 100,000 | 3.756 ms | 1.604 ms |

Mojo-via-interop is **~2.3× slower than a pure-Python loop** for element-wise
access, because every element crosses the Python↔Mojo boundary as a
`PythonObject`. No zero-copy NumPy buffer marshalling was demonstrated.

> `[I]` **Recommendation: CONDITIONALLY VIABLE, not currently justified.**
> Mojo 1.2.0 *can* build and import a Python extension (`--emit shared-lib` or
> `mojo.importer`), and scalars / Python sequences / NumPy arrays can be
> marshalled element-wise. But (a) the repo's interop harness is stale, (b)
> float-array exchange is per-element and slower than pure Python, (c) there is
> no verified zero-copy buffer path, (d) the reference venv (py3.12) lacks
> `mojo.importer` while the host `.venv` (py3.13) lacks NumPy — a fair
> three-way comparison would need extra environment work. **Do not make interop
> a Resampy v0.1.0 requirement** (Phase 1 decision stands); keep the framed
> binary CLI as the only verified Python↔Mojo bridge. Re-evaluate only with a
> dedicated Phase 3 probe of buffer-protocol marshalling.

`[V]` Running the repo's interop scripts created
`experiments/interop_benchmark/__mojocache__/` (gitignored). It was **removed**
to restore the original state; `git status` shows only the Phase 1 `docs/`
directory.

---

## 13. Recommended native data architecture `[I]`

Kept compatible with Phase 1 scope (1-D Float64, last-axis, `kaiser_fast`,
native Mojo numerical execution). No generic tensor framework.

| Element | Recommendation | Rationale |
|---|---|---|
| Input signal | `List[Float64]` (owned) or `Span[Float64, _]` at API boundary | §3/§7 verified; audioop precedent; 1-D only |
| Output signal | newly allocated `List[Float64]`, `resize(n, 0.0)`, returned with `^` | §7; exact zero-init needed for `y[t] +=` |
| Filter coefficients | **runtime `List[Float64]` loaded from a committed binary/hex resource** (12,289 values, little-endian f64) | §5: avoids 11 s StaticTuple compile and a huge generated literal; bit-exact; auditable |
| Filter metadata | `comptime`/struct: `precision = 512`, `rolloff = 0.8682120388377784`, `num_zeros = 24`, `nwin = 12289`, dtype/endian/sha256 | Phase 1 `reference-audit.md` §6 values, verified in §2; rolloff is not used by `resample` |
| `interp_delta` | derived `List[Float64]` of length 12289: `delta[i] = win[i+1]-win[i]`, `delta[last]=0` | Phase 1 §3.2/§3.3 (NumPy `diff(..., append=last)`) |
| Sampling rates | `Int` for `sr_orig`/`sr_new` at CLI boundary; `Float64` `sample_ratio` internally | §3 conversions; upstream accepts non-integer rates (Phase 1 §3.4) |
| Output length | exact `int(L * float(sr_new)/float(sr_orig))`, with `<1` → error | Phase 1 §3.4; §9 calibration confirmed |
| Interpolation indices | `Int` `n`, `offset`, `index_step`; `Float64` `frac`, `eta`, `tau` | §6 synthetic loop compiled |
| Float accumulation | `Float64` `y[t] += weight * x[...]`, **fix `--fp-mode contract=off`** | §8: default FMA contraction shifts 1 ULP |
| Numerical comparison | native/Py-side `max_abs`, RMSE, `isnan/isinf` position-wise; `abs` not `fabs` | §4/§8 verified comparator (`44`) |
| Wire codec | framed CLI (`uint32_be len | uint8 opcode | payload`), float payload as little-endian f64 bytes | audioop/msgpack/bitarray precedent (Phase 1 `api-scope.md` S7) |
| Golden vectors | JSON metadata + base64 LE f64 payloads (§11) | exact reconstruction, explicit endian/dtype/schema |

`[I]` `[U]` Whether the coefficient resource should be a committed `.bin`,
hex-in-Mojo, or generated `.mojo` literal is a Phase 3 decision; **do not
transcribe the production `kaiser_fast.npz` before the Phase 1 legal questions
(`licensing-audit.md` §6) are resolved**.

---

## 14. Known limitations `[U]` / `[I]`

1. `[U]` **No native Resampy implementation exists**, so the Phase 1 tolerance
   `max_abs ≤ 1e-9` is **NOT validated**. §9 establishes only upstream output
   magnitudes/conditioning and repeatability (§10); port-vs-reference error is
   unmeasurable until Phase 3. Keep the three concepts separate: (a) upstream
   accuracy vs ideal signal (Phase 1 `test_quality.py` thresholds), (b)
   upstream repeatability (§10, bit-identical), (c) future port-vs-reference
   error (unknown).
2. `[U]` FMA contraction of the **Numba/LLVM reference** is unverified; §8
   shows Mojo's default differs by 1 ULP from Python. Bit-exact parity is not
   promised (Phase 1 already excludes it).
3. `[U]` `Float64→Int` conversion for NaN/Inf/out-of-range is undefined
   (Phase 0 audioop probe 08); the interpolation loop must clamp before any
   conversion — no explicit probe was run here beyond confirming the hazard.
4. `[U]` Empty/single-sample/extreme-ratio/NaN-input behaviour of **upstream**
   Resampy was not executed (Phase 1 §4 marked unresolved); §9 used valid
   inputs only. Extreme downsampling may make `index_step = int(scale*P)` zero →
   division by zero (Phase 1 `reference-audit.md` §4 `[U]`).
5. `[U]` Non-contiguous arrays, C/F contiguity preservation, multi-channel /
   arbitrary `axis`, float32/complex — all out of v0.1 scope, not probed.
6. `[U]` Peak memory, long-running CLI allocation behaviour, and real-table
   cache behaviour not measured (§7).
7. `[I]` All timing numbers in this document (compile seconds, ms read loops,
   JIT latency, interop overhead) are **single-run diagnostics on a shared
   desktop**, not reproducible benchmarks per `docs/benchmarks/README.md`. No
   benchmark was run in Phase 2.
8. `[U]` `mojo doc` cannot introspect `std.mojoc`; API availability was probed
   empirically for the symbols listed in §4. Other stdlib symbols may exist but
   were not enumerated.
9. `[I]` Sin/cos availability contradicts one Phase 1 rationale (§4); scope is
   unchanged pending maintainer decision.
10. `[U]` Determinism across different NumPy/Numba/LLVM versions, CPU, or OS
    not established (§10).

---

## 15. Phase 3 recommendations `[I]`

**Do not begin implementation until Phase 2 is approved.** Recommended order:

1. **Decide the open questions first:** (a) confirm v0.1 scope unchanged or
   promote `sinc_window` given §4 contradiction; (b) resolve the 2-D
   multi-channel conflict (`api-scope.md` §8 Q4 vs `libraries/resampy/README.md:28`);
   (c) legal review of `kaiser_fast` coefficient transcription
   (`licensing-audit.md` §6); (d) choose coefficient resource format (§11/§13).
2. **Fix the build contract:** pin `--fp-mode contract=off` (or explicitly
   accept ULP-level divergence) and record Mojo version + optimisation level +
   fp-mode in every report and vector's `reference` block.
3. **Write `python_reference/requirements.txt`** with the verified pins
   (Python 3.12.x, numpy 1.26.4, llvmlite 0.43.0, numba 0.60.0,
   resampy 0.4.3) — but only after approval; do not touch `pyproject.toml`/
   `uv.lock` in Phase 2.
4. **Toolchain probes for the real algorithm shape:** `Float64→Int` clamping for
   NaN/Inf, `index_step = 0` guard for extreme ratios, `sin/cos` inside a real
   loop, and a tolerance comparator on full-length vectors.
5. **Build the native sample/coefficient layer first** (framed CLI, wire codec,
   filter load, validation), then the interpolation loop, then golden vectors
   (base64 f64 + metadata), then native tests + Python compat tests with the
   **calibrated** tolerance.
6. **Calibrate the true tolerance** by comparing the first native outputs
   against §9 corpus: record `max_abs`, RMSE, per-case exceedance counts, and
   freeze `atol/rtol` from measured evidence — do not adopt `1e-9` by default.
7. **Register the library** in `scripts/run_all_tests.py` (`MOJO_SUITES`),
   vector drift checks, `scripts/check_compatibility.py` (`KNOWN_LIBRARIES`,
   currently stale), and the root README/roadmap — Phase 0 §7 integration work.
8. **Benchmarks only after correctness:** follow `benchmark-design.md` §6,
   exclude cold JIT (568 ms measured) and cold Mojo compile (~2–11 s measured),
   report the interop gap explicitly (§12), no interop requirement for v0.1.
9. **Re-evaluate `kaiser_best`** (409,601 coefficients, ~3.2 MB) with a
   dedicated compile/embedding probe if it is promoted later.

---

## Appendix A — Probe inventory and status `[V]`

51 unique probes in `/tmp/pyromojo_resampy_phase2/probes/`, driven by
`run_probes.py` … `run_probes5.py` (each writes `out/results*.json` with exact
source, command, compile/run stdout/stderr and timing). **41 PASS, 10
compile-FAIL** — all 10 failures are **intentional API-negative probes**
(nonexistent `fabs`, `fmod`, `isnormal`, `signbit`, `is_nan`, `is_inf`, and
float method variants), documented in §4. No runtime failures.

| Group | Probes | Result |
|---|---|---|
| Float64 storage/arithmetic/Span | 01, 02, 22 | PASS |
| Math functions / classification | 03–05, 10–12, 23, 25, 27, 28, 31–35, 38–42, 45–48 | PASS (negatives listed above FAIL as expected) |
| Negative API probes | 06–09, 24, 26, 29, 30, 36, 37 | compile-FAIL (expected) |
| Coefficient tables | 15, 16, 17, 18, 50, 51 | PASS |
| Indexed loops | 19, 56 (downsample variant) | PASS |
| Memory/collections | 20, 49 | PASS |
| Numerical matrix / bitcast / accumulation | 14, 21, 43, 44, 52–55, 57, 58 | PASS |
| Interop PoC | `interop_poc/phase2poc.mojo` | PASS (build + import + NumPy array) |

## Appendix B — Mojo capability matrix `[V]`

| Capability | Result | Evidence | Implication |
|---|---|---|---|
| Float64 arithmetic | **PASS** | `01`, `03`, `22` | `+ - * /`, accumulation, conversions all work |
| Float64 collections | **PASS** | `01`, `02`, `15`, `20`, `49` | `List[Float64]`, `Span`, resize, copy, owned return, 1M elements |
| sin/cos | **PASS** | `04`, `57`, `58` (10/10 bit-exact vs Python) | runtime filter generation is *mathematically* possible; scope unchanged |
| Large coefficient table | **PASS** | `15`, `17`, `18`, `51` | `List`, `StaticTuple[12289]`, file-load all exact; StaticTuple costs 11.3 s compile |
| Indexed nested loops | **PASS** | `19`, `56` | boundary clipping, index math, repeated large-table reads work |
| NaN/Inf handling | **PARTIAL** | `12`, `21`, `41–43`, `45–48`, `52–55` | classification/bits match Python; **default `contract=fast` breaks strict IEEE** (1 ULP) |
| File-backed data | **PASS** | `18` | `FileHandle.read_bytes()` + `bitcast` reconstructs f64 exactly with explicit endian |
| Interoperability | **PARTIAL** | §12 PoC + repo scripts | builds/imports, but per-element marshalling ~2.3× slower than Python; stale harness; not justified for v0.1 |

**Overall feasibility `[I]`:** **PASS — Mojo 1.2.0 can support the proposed
Resampy v0.1.0 scope** (1-D Float64, `kaiser_fast`, native numerical execution,
deterministic output, golden-vector testing), provided the build's floating-
point contract is fixed and the tolerance is calibrated in Phase 3. The two
material caveats are FMA contraction (§8) and the absence of a validated
port-vs-reference tolerance (§14).

---

**STOP.** No implementation, no Mojo/Python production sources, no golden-vector
generator, no dependency changes to the repository, no commits. Awaiting review
and explicit approval before Phase 3.
