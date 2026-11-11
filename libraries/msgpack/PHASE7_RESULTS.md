# MessagePack Phase 7 results: benchmarks and final reporting

Phase 7 builds a reproducible three-way benchmark suite (pure-Python
fallback vs C-backed `msgpack` vs native Mojo) with in-process native
timing, separate cold-compilation and memory measurements, and a curated
release summary. No codec semantics were changed for benchmarks; no
benchmark code was optimized beyond correctness. This is the final v0.1
phase.

## Files

Created:

- `libraries/msgpack/benchmarks/bench.mojo` — native benchmark executable:
  reads one framed payload from stdin (prep only), times pure
  `decode_value_exact`/`encode_value` loops in-process with warmup and
  N samples, verifies via checksums and value fingerprints, prints one JSON
  object. No CLI wall-clock timing is used for codec numbers.
- `libraries/msgpack/benchmarks/workloads.py` — 12 deterministic workloads
  (seed 20261111) plus the Python mirror of the Mojo FNV-1a value
  fingerprint used for cross-implementation verification.
- `libraries/msgpack/benchmarks/run_benchmarks.py` — the one-command driver:
  shared payload generation, C/fallback timing, Mojo build (timed) and runs,
  isolated peak-RSS capture, correctness and scaling gates, raw
  `*.bench.json` report, median tables on stdout.
- `libraries/msgpack/benchmarks/config.json` — seed, warmup (5), samples
  (25), workload selection; version-controlled.
- `docs/benchmarks/releases/msgpack-v0.1.md` — curated release summary with
  tables, analysis, and limitations (committed).
- `libraries/msgpack/PHASE7_RESULTS.md` — this report.

Modified:

- `libraries/msgpack/README.md`, `README.md`, `docs/roadmap.md`,
  `docs/benchmarks/README.md` — benchmark status, pointers, and the checked
  Phase 2 benchmark box.

## Workload definitions

All values are built from `random.Random(20261111)` and packed once by the
C reference (`use_bin_type=True`); every implementation processes the same
bytes. No NaN, duplicate keys, or negative ext codes appear, so reference
packing is canonical and byte equality is expected everywhere.

| Workload | Shape | Bytes |
|---|---|---|
| primitives | 19-item mixed scalar array | 275 |
| ints_small | 1,000 mixed-width ints | 4326 |
| ints_large | 100,000 mixed-width ints | 431391 |
| floats | 10,005 float64 incl. extremes | 90048 |
| strings | 1,000 strings, 0..1000 B, some unicode | 178114 |
| binary | 8 blobs, 0..100,000 B | 177071 |
| maps_small | 100 str->int pairs | 925 |
| maps_large | 20,000 str->int pairs | 226334 |
| nested | 12-deep alternating array/map nesting | 193 |
| telemetry | 500 sensor readings with timestamps | 57743 |
| payload_large | ~1 MB mixed document | 1016848 |
| extensions | ext + timestamp values incl. nesting | 396 |

## Measurement methodology

- Warmup 5 iterations excluded; 25 measured samples per workload and
  operation; median/min/max reported; throughput in ops/s and bytes/s.
- Python timing: `time.perf_counter_ns` around pure `packb`/`unpackb`
  (fallback via `Packer.pack`; decode with `object_pairs_hook` on all paths
  so maps compare as ordered pairs). An O(1) result use keeps the call live;
  full repack/fingerprint verification runs outside the timed region.
- Native timing: `std.time.perf_counter_ns` around pure codec calls in one
  process; framing I/O, startup, and IPC excluded by construction. An O(1)
  result use plus a final full checksum/fingerprint keep the work live.
- Correctness gates (fail the run): Mojo encode checksum must equal
  FNV-1a of the reference bytes; Mojo fingerprints must equal the Python
  fold; C and fallback decodes must agree; byte equality of repacks.
- Scaling gates: large variants must take longer than small ones; every
  median must exceed zero (catches timer-resolution artifacts and eliminated
  work). A repeat full run confirmed every directional finding.
- Cold compile, warm execution, peak RSS, and executable size are measured
  separately and never combined. RSS is the isolated `ru_maxrss` of one
  bench process on the largest workload, startup and runtime included.

## Results (official run; medians, lower is faster)

Encode:

| workload | bytes | C med ns | fb med ns | Mojo med ns | Mojo/C | Mojo/fb |
|---|---|---|---|---|---|---|
| primitives | 275 | 1603 | 15389 | 481 | 0.30x | 0.031x |
| ints_small | 4326 | 21761 | 357363 | 11171 | 0.51x | 0.031x |
| ints_large | 431391 | 2245395 | 36306932 | 1209907 | 0.54x | 0.033x |
| floats | 90048 | 150083 | 3353471 | 92244 | 0.61x | 0.028x |
| strings | 178114 | 31740 | 455888 | 67547 | 2.13x | 0.148x |
| binary | 177071 | 11402 | 12684 | 84259 | 7.39x | 6.643x |
| maps_small | 925 | 8846 | 76344 | 2134 | 0.24x | 0.028x |
| maps_large | 226334 | 912297 | 15289161 | 414611 | 0.45x | 0.027x |
| nested | 193 | 1643 | 20909 | 651 | 0.40x | 0.031x |
| telemetry | 57743 | 205096 | 3715682 | 130326 | 0.64x | 0.035x |
| payload_large | 1016848 | 1161997 | 18095752 | 891788 | 0.77x | 0.049x |
| extensions | 396 | 921 | 7333 | 911 | 0.99x | 0.124x |

Decode:

| workload | bytes | C med ns | fb med ns | Mojo med ns | Mojo/C | Mojo/fb |
|---|---|---|---|---|---|---|
| primitives | 275 | 1152 | 15309 | 872 | 0.76x | 0.057x |
| ints_small | 4326 | 12985 | 643401 | 44504 | 3.43x | 0.069x |
| ints_large | 431391 | 2168862 | 66445174 | 4545494 | 2.10x | 0.068x |
| floats | 90048 | 142217 | 7630249 | 224362 | 1.58x | 0.029x |
| strings | 178114 | 61987 | 854819 | 144842 | 2.34x | 0.169x |
| binary | 177071 | 5640 | 21310 | 48121 | 8.53x | 2.258x |
| maps_small | 925 | 16992 | 124354 | 15740 | 0.93x | 0.127x |
| maps_large | 226334 | 3721262 | 27096289 | 2254563 | 0.61x | 0.083x |
| nested | 193 | 1914 | 28003 | 2064 | 1.08x | 0.074x |
| telemetry | 57743 | 390034 | 6836324 | 304894 | 0.78x | 0.045x |
| payload_large | 1016848 | 939849 | 33147695 | 2508110 | 2.67x | 0.076x |
| extensions | 396 | 2404 | 13646 | 791 | 0.33x | 0.058x |

Compilation and memory:

| Metric | Value |
|---|---|
| Cold compile (`mojo build bench.mojo`, no prior artifact) | 1.5 s |
| Executable size | 125040 bytes |
| Peak RSS, encode of 1 MB payload | 19292160 bytes |
| Peak RSS, decode of 1 MB payload | 17080320 bytes |

## Analysis

Mojo vs C is a draw with shape, and that is the honest headline. Mojo
encodes integers, floats, maps, telemetry, and the 1 MB document faster
(0.24x–0.77x) thanks to lower per-call overhead and typed traversal, but
loses bulk byte copies (strings 2.1x, binary 7.4x: `memcpy` vs a
byte-at-a-time append loop). Decode reverses on scalar-dense payloads
(ints 2.1x–3.4x, floats 1.6x, strings 2.3x, binary 8.5x) where a flat
`Value` tree costs more than C's direct object construction, while
container-heavy decode favors Mojo (maps 0.6x–0.9x, telemetry 0.78x,
extensions 0.33x). Throughput converges on large payloads rather than
diverging, which is the expected shape for two competent implementations.

The fallback comparison is reported because the methodology requires it,
not because it proves anything about optimized code: Mojo is 6x–37x
faster except binary, where fallback wins outright (encode 6.6x, decode
2.3x) and sits within 12% of C. That unfavorable result is kept in the
tables; the span-append fast path it points to is future work, explicitly
not implemented here.

## Verification

Toolchain: Mojo 1.2.0 (2016d0cd), Python 3.13.14, pytest 9.2.0,
ruff 0.17.4, msgpack 1.2.4, uv 0.12.5.

```text
$ uv sync --extra dev
Resolved 20 packages in 0.91ms
Checked 19 packages in 55ms

$ .venv/bin/python scripts/run_all_tests.py
run_all_tests: all suites passed

$ .venv/bin/python scripts/check_compatibility.py
check_compatibility: all compatibility suites passed

$ .venv/bin/ruff check libraries shared scripts
All checks passed!

$ .venv/bin/ruff format --check libraries shared scripts
29 files already formatted

$ .venv/bin/python libraries/msgpack/python_reference/generate_vectors.py --check
vectors: 162 cases, committed artifacts are current

$ .venv/bin/python libraries/msgpack/benchmarks/run_benchmarks.py
workload primitives: 275 bytes, checks passed
workload ints_small: 4326 bytes, checks passed
workload ints_large: 431391 bytes, checks passed
workload floats: 90048 bytes, checks passed
workload strings: 178114 bytes, checks passed
workload binary: 177071 bytes, checks passed
workload maps_small: 925 bytes, checks passed
workload maps_large: 226334 bytes, checks passed
workload nested: 193 bytes, checks passed
workload telemetry: 57743 bytes, checks passed
workload payload_large: 1016848 bytes, checks passed
workload extensions: 396 bytes, checks passed
cold compile: 1.5 s, exe 125040 bytes
peak RSS on payload_large: encode 19292160 B, decode 17080320 B
raw report: build/msgpack-bench.bench.json
```

Every workload passed correctness gates (byte equality + fingerprint match
on all three paths) and scaling/timer gates; a second full run reproduced
every directional finding. `jsonschema` validation was not run (optional
dependency absent). No Phase 1–6 test regressed: 129 pytest plus all 79
native tests pass inside `run_all_tests.py`.

## Remaining limitations and future work

- Bulk byte copies (strings/binary encode, binary decode) are the measured
  weakness; a span-append fast path is the obvious next optimization.
- `Value`-per-scalar decode allocation costs on scalar-dense payloads;
  flatter or lazily-decoded representations are future work.
- Mojo-from-Python interop is not measured (`ctypes`/`PythonModuleBuilder`
  are out of project scope); the gap is stated in the release summary.
- Sub-100-microsecond medians vary run to run; read them with their min/max
  bands. CPU frequency scaling was not pinned; page cache was warm.
- Benchmarks cover the v0.1 type set only; no adversarial or
  pathological-input performance characterization was done.
