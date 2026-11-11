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

## Results (official run)

Speedup convention: each ratio is `Mojo time / C time` (or `/ fallback
time`) computed on medians. Below 1.0 means Mojo is faster; above 1.0 means
the other implementation is faster. Throughput columns derive from the same
medians. The `*.bench.json` raw report stores min, median, max, sample
count, and both throughputs per workload and operation (25 samples each);
the tables below reproduce those aggregates in full.

Encode:

| workload | bytes | C med ns (min/max) | C ops/s | C MB/s | fb med ns | Mojo med ns (min/max) | Mojo ops/s | Mojo MB/s | Mojo/C | Mojo/fb | C/fb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primitives | 275 | 1603 (1543/5540) | 623.8K | 171.6 | 15389 | 481 (461/571) | 2.08M | 571.7 | 0.30x | 0.031x | 0.104x |
| ints_small | 4326 | 21761 (21691/34635) | 46.0K | 198.8 | 357363 | 11171 (11111/15479) | 89.5K | 387.3 | 0.51x | 0.031x | 0.061x |
| ints_large | 431391 | 2245395 (2176787/3643987) | 445 | 192.1 | 36306932 | 1209907 (1142950/1481117) | 827 | 356.5 | 0.54x | 0.033x | 0.062x |
| floats | 90048 | 150083 (148900/159831) | 6.7K | 600.0 | 3353471 | 92244 (90560/165271) | 10.8K | 976.2 | 0.61x | 0.028x | 0.045x |
| strings | 178114 | 31740 (30417/61716) | 31.5K | 5611.7 | 455888 | 67547 (63078/288853) | 14.8K | 2636.9 | 2.13x | 0.148x | 0.070x |
| binary | 177071 | 11402 (10751/12283) | 87.7K | 15529.8 | 12684 | 84259 (52629/133532) | 11.9K | 2101.5 | 7.39x | 6.643x | 0.899x |
| maps_small | 925 | 8846 (8726/9067) | 113.0K | 104.6 | 76344 | 2134 (2113/2415) | 468.6K | 433.5 | 0.24x | 0.028x | 0.116x |
| maps_large | 226334 | 912297 (892169/936312) | 1.1K | 248.1 | 15289161 | 414611 (406375/472760) | 2.4K | 545.9 | 0.45x | 0.027x | 0.060x |
| nested | 193 | 1643 (1613/2063) | 608.6K | 117.5 | 20909 | 651 (641/1052) | 1.54M | 296.5 | 0.40x | 0.031x | 0.079x |
| telemetry | 57743 | 205096 (202140/341162) | 4.9K | 281.5 | 3715682 | 130326 (129053/167285) | 7.7K | 443.1 | 0.64x | 0.035x | 0.055x |
| payload_large | 1016848 | 1161997 (1146918/1231687) | 861 | 875.1 | 18095752 | 891788 (821516/1566528) | 1.1K | 1140.2 | 0.77x | 0.049x | 0.064x |
| extensions | 396 | 921 (872/1072) | 1.09M | 430.0 | 7333 | 911 (891/1212) | 1.10M | 434.7 | 0.99x | 0.124x | 0.126x |

Decode:

| workload | bytes | C med ns (min/max) | C ops/s | C MB/s | fb med ns | Mojo med ns (min/max) | Mojo ops/s | Mojo MB/s | Mojo/C | Mojo/fb | C/fb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primitives | 275 | 1152 (1132/1563) | 868.1K | 238.7 | 15309 | 872 (852/34575) | 1.15M | 315.4 | 0.76x | 0.057x | 0.075x |
| ints_small | 4326 | 12985 (12844/23695) | 77.0K | 333.2 | 643401 | 44504 (43762/241223) | 22.5K | 97.2 | 3.43x | 0.069x | 0.020x |
| ints_large | 431391 | 2168862 (2094522/2862706) | 461 | 198.9 | 66445174 | 4545494 (4408256/5279435) | 220 | 94.9 | 2.10x | 0.068x | 0.033x |
| floats | 90048 | 142217 (141506/147818) | 7.0K | 633.2 | 7630249 | 224362 (196590/372230) | 4.5K | 401.4 | 1.58x | 0.029x | 0.019x |
| strings | 178114 | 61987 (61696/71645) | 16.1K | 2873.4 | 854819 | 144842 (143269/348747) | 6.9K | 1229.7 | 2.34x | 0.169x | 0.073x |
| binary | 177071 | 5640 (5270/6021) | 177.3K | 31395.6 | 21310 | 48121 (47740/80211) | 20.8K | 3679.7 | 8.53x | 2.258x | 0.265x |
| maps_small | 925 | 16992 (16771/17343) | 58.9K | 54.4 | 124354 | 15740 (15018/54462) | 63.5K | 58.8 | 0.93x | 0.127x | 0.137x |
| maps_large | 226334 | 3721262 (3210461/5189004) | 269 | 60.8 | 27096289 | 2254563 (2233352/3440764) | 444 | 100.4 | 0.61x | 0.083x | 0.137x |
| nested | 193 | 1914 (1883/2024) | 522.5K | 100.8 | 28003 | 2064 (2034/2134) | 484.5K | 93.5 | 1.08x | 0.074x | 0.068x |
| telemetry | 57743 | 390034 (384824/449325) | 2.6K | 148.0 | 6836324 | 304894 (297440/457490) | 3.3K | 189.4 | 0.78x | 0.045x | 0.057x |
| payload_large | 1016848 | 939849 (926213/1328780) | 1.1K | 1081.9 | 33147695 | 2508110 (2488142/2586828) | 399 | 405.4 | 2.67x | 0.076x | 0.028x |
| extensions | 396 | 2404 (2324/2615) | 416.0K | 164.7 | 13646 | 791 (661/901) | 1.26M | 500.6 | 0.33x | 0.058x | 0.176x |

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
