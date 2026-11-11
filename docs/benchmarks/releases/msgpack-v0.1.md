# Benchmark release: MessagePack v0.1

Native Mojo codec vs C-backed `msgpack` vs pure-Python `msgpack.fallback`,
measured 2026-11-11 on the machine below. This is a curated release summary;
the raw 25-sample datasets live in the (git-ignored) `*.bench.json` report
produced by the driver, and the full methodology is in
`libraries/msgpack/PHASE7_RESULTS.md`.

## Headline findings

- **Encode: Mojo beats C on 9 of 12 workloads** (0.24x–0.99x the C time,
  i.e. up to ~4x faster on small maps). The wins concentrate in
  integer/float/map/telemetry shapes: typed `List` traversal beats Python
  object traversal.
- **Encode: C beats Mojo on strings (2.1x) and binary (7.4x).** The C
  packer bulk-copies payload bytes; the native codec appends byte by byte.
  This is the clearest optimization target and is reported as a limitation,
  not fixed in this phase.
- **Decode is mixed: C wins 7, Mojo wins 5.** C wins integer/float/string
  payloads (1.6x–3.4x) and binary (8.5x, zero-copy slice vs copy). Mojo wins
  maps (0.6x–0.9x), telemetry (0.78x), and extensions (0.33x, where the C
  path allocates `ExtType`/`Timestamp` objects per value).
- **Fallback is far behind both** (Mojo is 6x–37x faster; C is 6x–53x faster) — except binary, where C leads by only 1.1x/3.8x, fallback sits within 12% of C,
  and fallback beats Mojo outright (encode 6.6x, decode 2.3x). The binary result is unfavorable to Mojo and
  is reported unchanged.
- **The important comparison is Mojo vs C, and it is a draw with shape.**
  Neither implementation is universally faster; per-byte rates converge on
  large payloads (payload_large encode: Mojo 1140 MB/s vs C 875 MB/s;
  decode: C 1082 MB/s vs Mojo 405 MB/s).

No universal-MoJo-faster claim is made. Directions reproduce on a repeat
run; sub-100-microsecond magnitudes vary run to run (see Limitations).

## Environment

| Item | Value |
|---|---|
| CPU | AMD Ryzen 7 6800H with Radeon Graphics (16 cores) |
| Memory | 15528948 kB |
| OS | Linux-7.0.0-28-generic-x86_64-with-glibc2.39 |
| Python | 3.13.14 |
| msgpack | 1.2.4 (C and fallback from the same package) |
| Mojo | 1.2.0 (2016d0cd) |
| Git | 4452627 |
| Timer | `time.perf_counter_ns` (Python), `std.time.perf_counter_ns` (Mojo) |
| Seed / warmup / samples | 20261111 / 5 / 25 |

## Configuration

Workloads are defined in `libraries/msgpack/benchmarks/workloads.py` and
selected in `libraries/msgpack/benchmarks/config.json` (seed 20261111,
warmup 5, samples 25). Each payload is packed once by the C reference;
correctness (byte equality plus FNV-1a value fingerprints) is verified
outside every timed region. Native timing is in-process (`bench.mojo`);
framing I/O, process startup, and IPC are excluded.

## Encode results

Speedup convention: each ratio is `Mojo time / C time` (or `/ fallback
time`) computed on medians. Below 1.0 means Mojo is faster; above 1.0 means
the other implementation is faster. Medians with min/max ns, plus ops/s and
MB/s throughput derived from the medians:

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

## Decode results

Same `Mojo time / other time` convention as above (below 1.0 = Mojo faster):

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

## Compilation and memory (separate from runtime)

| Metric | Value |
|---|---|
| Cold compile (`mojo build bench.mojo`, no prior artifact) | 1.5 s |
| Executable size | 125040 bytes |
| Peak RSS, encode of 1 MB payload (isolated child) | 19292160 bytes |
| Peak RSS, decode of 1 MB payload (isolated child) | 17080320 bytes |

RSS includes process startup and the Mojo runtime; it is not allocator-only.

## Analysis

- Small-operation encode is Mojo's best area (0.24x–0.51x): fixed per-call
  overhead is lower than `packb`'s. The advantage persists but narrows on
  large payloads (0.54x–0.77x), where per-byte cost dominates.
- Bulk byte copies are the native codec's weakness: strings encode 2.1x,
  binary encode 7.4x, binary decode 8.5x slower than C. The C path uses bulk
  memory copies; the Mojo path appends byte by byte. A span-append fast
  path is the obvious future optimization (not implemented in this phase).
- Decode builds a full `Value` tree per item (one node per integer), so
  scalar-dense payloads favor C (ints 2.1x–3.4x, floats 1.6x, strings 2.3x).
  Container-heavy decode favors Mojo (maps 0.6x–0.9x, telemetry 0.78x):
  appending to a typed list beats dict hashing, and flat `Value`s beat
  per-value `ExtType`/`Timestamp` allocation (extensions 0.33x).
- The fallback comparison is reported for completeness only: Mojo is 6x–37x
  faster except binary, where fallback wins. This says nothing about Mojo
  vs optimized code; the C column is the real baseline.

## Limitations

- Sub-100-microsecond medians vary run to run (notably C on tiny payloads
  and both implementations on the binary workload); directions reproduced
  on a repeat run but small-workload magnitudes should be read with their
  min/max bands.
- Page cache was warm for compilation; CPU frequency scaling was not pinned.
- The Mojo-from-Python interop path from the methodology doc is not
  measured: `ctypes`/`PythonModuleBuilder` are out of project scope, so the
  gap is stated, not hidden.
- Peak RSS includes runtime overhead, not just codec allocation.

## Reproduction

```bash
uv sync --extra dev
.venv/bin/python libraries/msgpack/benchmarks/run_benchmarks.py
```

Options: `--only a,b`, `--warmup N`, `--samples N` (>= 15), `--config`,
`--raw-out`. Raw samples plus metadata are written to
`build/msgpack-bench.bench.json` (git-ignored). The driver deletes the old
binary before building, so the reported compile time is fresh every run
(page cache stays warm; this is stated, not hidden).
