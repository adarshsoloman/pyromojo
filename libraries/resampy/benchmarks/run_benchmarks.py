#!/usr/bin/env python3
"""Four-path Resampy benchmark: upstream warm/cold, native in-process, native CLI.

Usage::

    .venv/bin/python libraries/resampy/benchmarks/run_benchmarks.py

The production ``kaiser_fast`` coefficients are extracted from the pinned
upstream package into a temporary directory, verified, and deleted when the run
finishes. No coefficient data is written into the repository.

Methodology follows ``docs/benchmarks/README.md``: the same deterministic input
is used by every path; every native/CLI result is compared to the upstream
result by SHA-256 before timing is accepted; cold compile and warm execution
are reported separately; timings use 5 warmups and 25 samples per run, with 2
independent runs and median-of-medians aggregation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
BENCH_BIN = BUILD_DIR / "bench_resampy"
CLI_BIN = BUILD_DIR / "resampy_cli"
RESULTS_DIR = BENCH_DIR / "results"
REPORT_DIR = BENCH_DIR / "reports"
TIMEOUT_S = 300

FILTER_NAME = "kaiser_fast"
FILTER_ID = "kaiser_fast_upstream_0_4_3"
FILTER_SHA256 = "4c96a90d1b0b93cf0a9620c5f66216416a6b19752bf18a208c837b55b719434b"
FILTER_COUNT = 12289
FILTER_PRECISION = 512
FILTER_ROLLOFF = 0.8682120388377784
UPSTREAM_VERSION = "0.4.3"
UPSTREAM_COMMIT = "7c484f8eec54b87e8f566578dc3e48a2be81cc80"
OP_RESAMPLE = 0x2A
STATUS_OK = 0

sys.path.insert(0, str(BENCH_DIR))
import workloads  # noqa: E402


def sh(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=False, **kwargs)


def mojo_binary() -> Path:
    path = ROOT / ".venv" / "bin" / "mojo"
    if not path.exists():
        raise SystemExit("run_benchmarks: .venv/bin/mojo not found")
    return path


def stats(samples: list[int]) -> dict:
    ordered = sorted(samples)
    return {
        "samples": len(ordered),
        "min_ns": ordered[0],
        "median_ns": statistics.median(ordered),
        "max_ns": ordered[-1],
        "mean_ns": statistics.fmean(ordered),
        "stdev_ns": statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
    }


def hash_values(values) -> str:
    raw = np.ascontiguousarray(values, dtype="<f8").tobytes(order="C")
    return hashlib.sha256(raw).hexdigest()


def f64le(values) -> bytes:
    return np.ascontiguousarray(values, dtype="<f8").tobytes(order="C")


def pin_cpu() -> int | None:
    try:
        cpus = sorted(os.sched_getaffinity(0))
        if not cpus:
            return None
        cpu = cpus[0]
        os.sched_setaffinity(0, {cpu})
        return cpu
    except (AttributeError, OSError):
        return None


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def memory_total() -> str:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


def make_filter(directory: Path) -> dict:
    import resampy

    if resampy.__version__ != UPSTREAM_VERSION:
        raise SystemExit(f"need resampy=={UPSTREAM_VERSION}, found {resampy.__version__}")
    win, precision, rolloff = resampy.filters.get_filter(FILTER_NAME)
    win = np.asarray(win, dtype="<f8")
    raw = win.tobytes(order="C")
    digest = hashlib.sha256(raw).hexdigest()
    metadata = {
        "schema_version": 1,
        "filter_id": FILTER_ID,
        "coefficient_count": int(win.size),
        "precision": int(precision),
        "rolloff": float(rolloff),
        "dtype": "float64",
        "byte_order": "little",
        "resource_bytes": len(raw),
        "resource_sha256": digest,
    }
    if (
        digest != FILTER_SHA256
        or int(win.size) != FILTER_COUNT
        or int(precision) != FILTER_PRECISION
        or float(rolloff) != FILTER_ROLLOFF
    ):
        raise SystemExit(
            f"kaiser_fast metadata mismatch: count={win.size} precision={precision} "
            f"rolloff={rolloff!r} sha256={digest}"
        )
    meta_bytes = json.dumps(metadata, sort_keys=True).encode("utf-8")
    meta_path = directory / "kaiser_fast.json"
    bin_path = directory / "kaiser_fast.bin"
    meta_path.write_bytes(meta_bytes)
    bin_path.write_bytes(raw)
    return {
        "meta": meta_bytes,
        "resource": raw,
        "meta_path": meta_path,
        "bin_path": bin_path,
        "metadata": metadata,
    }


def build_binaries() -> dict:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    mojo = str(mojo_binary())
    builds = {}
    for name, source, output in (
        ("bench", BENCH_DIR / "bench.mojo", BENCH_BIN),
        ("cli", ROOT / "libraries/resampy/mojo/cli.mojo", CLI_BIN),
    ):
        if output.exists():
            output.unlink()
        start = time.perf_counter_ns()
        result = sh(
            [
                mojo,
                "build",
                str(source),
                "-I",
                str(ROOT / "libraries/resampy/mojo"),
                "--fp-mode",
                "contract=off",
                "-o",
                str(output),
            ],
            cwd=ROOT,
        )
        elapsed = time.perf_counter_ns() - start
        if result.returncode != 0:
            raise SystemExit(
                f"mojo build {name} failed:\n{result.stderr.decode(errors='replace')[-3000:]}"
            )
        builds[name] = {"source": str(source), "binary": str(output), "build_ns": elapsed}
        print(f"built {name}: {elapsed / 1e9:.2f}s", flush=True)
    return builds


def env_metadata(config: dict, filter_info: dict, builds: dict, cpu: int | None) -> dict:
    def version(name: str) -> str:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return "missing"

    git_rev = sh(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).stdout.decode().strip()
    git_dirty = bool(sh(["git", "status", "--short"], cwd=ROOT).stdout.strip())
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git": git_rev,
        "git_dirty": git_dirty,
        "python": sys.version.split()[0],
        "python_build": platform.python_build(),
        "numpy": version("numpy"),
        "resampy": version("resampy"),
        "upstream_commit": UPSTREAM_COMMIT,
        "numba": version("numba"),
        "llvmlite": version("llvmlite"),
        "mojo": sh([str(mojo_binary()), "--version"]).stdout.decode().strip(),
        "cpu": cpu_model(),
        "cores": os.cpu_count(),
        "affinity_cpu": cpu,
        "memory": memory_total(),
        "os": platform.platform(),
        "timer": "time.perf_counter_ns (Python) / std.time.perf_counter_ns (Mojo)",
        "fp_mode": "contract=off",
        "pin_method": "os.sched_setaffinity (single inherited CPU; no taskset wrapper)",
        "interop_path": "unavailable in v0.1.0; reported as a gap, not measured",
        "pure_python_floor": "not measured (optional for v0.1.0)",
        "parallel_upstream": "not measured (sequential parallel=False only)",
        "build_note": "output binary removed before each build; "
        "compiler cache state is toolchain-provided",
        "peak_rss_self_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_children_kb": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "config": config,
        "builds": builds,
        "filter": filter_info["metadata"],
    }


def time_upstream(signal, sr_orig: int, sr_new: int, warmup: int, samples: int):
    import resampy

    args = (signal, sr_orig, sr_new)
    for _ in range(warmup):
        resampy.resample(*args, filter=FILTER_NAME, parallel=False)
    times: list[int] = []
    last = None
    for _ in range(samples):
        start = time.perf_counter_ns()
        last = resampy.resample(*args, filter=FILTER_NAME, parallel=False)
        times.append(time.perf_counter_ns() - start)
    return times, last


def bench_body(signal, sr_orig: int, sr_new: int) -> bytes:
    values = f64le(signal)
    return struct.pack(">III", sr_orig, sr_new, len(signal)) + values


def run_native(meta_path: Path, bin_path: Path, body: bytes, warmup: int, samples: int) -> dict:
    frame = struct.pack(">I", len(body)) + body
    result = sh(
        [
            str(BENCH_BIN),
            str(meta_path),
            str(bin_path),
            str(warmup),
            str(samples),
        ],
        input=frame,
        timeout=TIMEOUT_S,
    )
    if result.returncode != 0:
        raise SystemExit(f"bench_resampy failed:\n{result.stderr.decode(errors='replace')[-2000:]}")
    if result.stderr:
        raise SystemExit(f"bench_resampy wrote stderr: {result.stderr[:500]!r}")
    return json.loads(result.stdout.decode())


def cli_request(signal, sr_orig: int, sr_new: int, meta: bytes, raw: bytes) -> bytes:
    fid = FILTER_ID.encode("utf-8")
    payload = (
        bytes([OP_RESAMPLE])
        + struct.pack(">II", sr_orig, sr_new)
        + struct.pack(">I", len(fid))
        + fid
        + struct.pack(">I", len(meta))
        + meta
        + struct.pack(">I", len(raw))
        + raw
        + struct.pack(">I", len(signal))
        + f64le(signal)
    )
    return struct.pack(">I", len(payload)) + payload


def decode_cli_frame(stdout: bytes, expected_sha: str) -> None:
    if len(stdout) < 5:
        raise SystemExit(f"CLI response too short: {stdout[:40]!r}")
    length = struct.unpack(">I", stdout[:4])[0]
    body = stdout[4:]
    if len(body) != length:
        raise SystemExit(f"CLI frame length {length} != body {len(body)}")
    if body[0] != STATUS_OK:
        raise SystemExit(f"CLI returned status {body[0]}: {body[1:300]!r}")
    payload = body[1:]
    if hashlib.sha256(payload).hexdigest() != expected_sha:
        raise SystemExit("CLI output hash mismatch")


def time_cli(frame: bytes, warmup: int, samples: int, expected_sha: str) -> list[int]:
    for _ in range(warmup):
        result = sh([str(CLI_BIN)], input=frame, timeout=TIMEOUT_S)
        if result.returncode != 0:
            raise SystemExit(f"resampy CLI failed: {result.stderr.decode(errors='replace')[:500]}")
        decode_cli_frame(result.stdout, expected_sha)
    times: list[int] = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        result = sh([str(CLI_BIN)], input=frame, timeout=TIMEOUT_S)
        times.append(time.perf_counter_ns() - start)
        if result.returncode != 0:
            raise SystemExit(f"resampy CLI failed: {result.stderr.decode(errors='replace')[:500]}")
        decode_cli_frame(result.stdout, expected_sha)
    return times


def time_ping(warmup: int, samples: int) -> list[int]:
    frame = struct.pack(">I", 1) + b"\x01"
    expected = hashlib.sha256(b"").hexdigest()
    for _ in range(warmup):
        result = sh([str(CLI_BIN)], input=frame, timeout=TIMEOUT_S)
        if result.returncode != 0:
            raise SystemExit(
                f"resampy CLI ping failed: {result.stderr.decode(errors='replace')[:500]}"
            )
        decode_cli_frame(result.stdout, expected)
    times: list[int] = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        result = sh([str(CLI_BIN)], input=frame, timeout=TIMEOUT_S)
        times.append(time.perf_counter_ns() - start)
        if result.returncode != 0:
            raise SystemExit(
                f"resampy CLI ping failed: {result.stderr.decode(errors='replace')[:500]}"
            )
        decode_cli_frame(result.stdout, expected)
    return times


def cold_child() -> int:
    spec = json.loads(sys.stdin.read())
    import resampy

    if resampy.__version__ != UPSTREAM_VERSION:
        raise SystemExit(f"need resampy=={UPSTREAM_VERSION}, found {resampy.__version__}")
    signal = workloads.signal_values(spec["length"], spec["signal_type"], spec["seed"])
    start = time.perf_counter_ns()
    output = resampy.resample(
        signal, spec["sr_orig"], spec["sr_new"], filter=FILTER_NAME, parallel=False
    )
    elapsed = time.perf_counter_ns() - start
    print(
        json.dumps(
            {
                "elapsed_ns": elapsed,
                "output_count": int(output.size),
                "output_sha256": hash_values(output),
            }
        )
    )
    return 0


def run_cold(spec: dict, runs: int) -> list[dict]:
    records = []
    child = [sys.executable, str(Path(__file__).resolve()), "--cold-child"]
    payload = json.dumps(spec).encode("utf-8")
    for _ in range(runs):
        result = sh(child, input=payload, timeout=TIMEOUT_S)
        if result.returncode != 0:
            raise SystemExit(
                f"cold upstream child failed:\n{result.stderr.decode(errors='replace')[-2000:]}"
            )
        records.append(json.loads(result.stdout.decode()))
    return records


def aggregate_runs(run_results: list[dict], implementation: str) -> dict:
    cells = [run[implementation] for run in run_results]
    return {
        "run_medians_ns": [cell["median_ns"] for cell in cells],
        "median_ns": statistics.median(cell["median_ns"] for cell in cells),
        "min_ns": min(cell["min_ns"] for cell in cells),
        "max_ns": max(cell["max_ns"] for cell in cells),
        "samples_per_run": cells[0]["samples"],
    }


def fmt_ms(ns: float) -> str:
    return f"{ns / 1e6:.3f}"


def write_summary_csv(path: Path, raw: dict) -> None:
    columns = [
        "case_id",
        "length",
        "signal_type",
        "sr_orig",
        "sr_new",
        "output_length",
        "run",
        "implementation",
        "samples",
        "median_ns",
        "min_ns",
        "max_ns",
        "mean_ns",
        "stdev_ns",
        "million_input_samples_per_s",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for cell in raw["cells"]:
            for run_index, run in enumerate(cell["runs"]):
                for implementation in ("upstream_warm", "native", "native_cli"):
                    cell_stats = run[implementation]
                    writer.writerow(
                        [
                            cell["case_id"],
                            cell["length"],
                            cell["signal_type"],
                            cell["sr_orig"],
                            cell["sr_new"],
                            cell["output_length"],
                            run_index,
                            implementation,
                            cell_stats["samples"],
                            cell_stats["median_ns"],
                            cell_stats["min_ns"],
                            cell_stats["max_ns"],
                            cell_stats["mean_ns"],
                            cell_stats["stdev_ns"],
                            cell["length"] / (cell_stats["median_ns"] / 1e9) / 1e6,
                        ]
                    )
            for implementation in ("upstream_warm", "native", "native_cli"):
                cell_stats = cell["aggregate"][implementation]
                writer.writerow(
                    [
                        cell["case_id"],
                        cell["length"],
                        cell["signal_type"],
                        cell["sr_orig"],
                        cell["sr_new"],
                        cell["output_length"],
                        "median",
                        implementation,
                        cell_stats["samples_per_run"],
                        cell_stats["median_ns"],
                        cell_stats["min_ns"],
                        cell_stats["max_ns"],
                        "",
                        "",
                        cell["length"] / (cell_stats["median_ns"] / 1e9) / 1e6,
                    ]
                )


def write_report(path: Path, raw: dict) -> None:
    meta = raw["meta"]
    cells = raw["cells"]
    gate_failures = sum(1 for c in cells if c["gate"]["status"] != "PASS")
    lines = [
        "# Resampy benchmark report",
        "",
        "Generated by `libraries/resampy/benchmarks/run_benchmarks.py`.",
        "",
        "## Summary",
        "",
        f"- {len(cells)} measured cells; {len(raw['exclusions'])} documented exclusions.",
        f"- {meta['config']['runs']} independent runs, "
        f"{meta['config']['warmup']} warmups, {meta['config']['samples']} samples per path.",
        f"- Seed: {meta['config']['seed']}; config: `benchmarks/config.json`.",
        "- Aggregation: each run reports its sample median; each cell reports the "
        "median of the run medians.",
        "- Paths: upstream warm, upstream cold (fresh-process JIT), native Mojo "
        "in-process, native Mojo CLI.",
        f"- Correctness gate: {len(cells) - gate_failures}/{len(cells)} cells PASS; "
        "native and CLI output SHA-256 matched upstream exactly.",
        "- Native in-process timings exclude process startup, framing, filter loading, "
        "and validation.",
        "- CLI timings include process startup, framing, filter validation, and output encoding.",
        "- Python-to-Mojo interop is unavailable in v0.1.0 and is reported as a gap.",
        "",
        "## Environment",
        "",
        f"- Git: `{meta['git']}` (dirty={meta['git_dirty']})",
        f"- CPU: {meta['cpu']} ({meta['cores']} logical cores, "
        f"affinity CPU {meta['affinity_cpu']})",
        f"- RAM: {meta['memory']}",
        f"- OS: {meta['os']}",
        f"- Python: {meta['python']}",
        f"- upstream Resampy: {meta['resampy']} at `{meta['upstream_commit']}`; "
        f"NumPy {meta['numpy']}; Numba {meta['numba']}; llvmlite {meta['llvmlite']}",
        f"- Mojo: {meta['mojo']}",
        f"- Compiler flag: `--fp-mode {meta['fp_mode']}`",
        f"- Pinning: {meta['pin_method']}",
        f"- Driver peak RSS: self {meta['peak_rss_self_kb']} KB, "
        f"children {meta['peak_rss_children_kb']} KB",
        f"- Filter: `{meta['filter']['filter_id']}`, "
        f"{meta['filter']['coefficient_count']} coefficients, "
        f"precision {meta['filter']['precision']}, "
        f"SHA-256 `{meta['filter']['resource_sha256']}`",
        "",
        "## Paths measured",
        "",
        "| Path | Timing scope |",
        "|---|---|",
        "| Upstream warm | `resampy.resample(..., parallel=False)`, in-process, precompiled |",
        "| Upstream cold | first call in a fresh process, including Numba JIT and execution |",
        "| Native in-process | public Mojo `resample`, filter loaded before timing |",
        "| Native CLI | process spawn + framing + filter validation + kernel + framing |",
        "",
        "Not measured: Python-to-Mojo interop (unverified for v0.1.0), optional "
        "pure-Python floor, optional upstream `parallel=True`.",
        "",
        "## Workload matrix",
        "",
        f"- Lengths: {', '.join(str(n) for n in workloads.LENGTHS)} input samples.",
        f"- Signal types: {', '.join(workloads.SIGNAL_TYPES)}.",
        "- Rate pairs: " + ", ".join(f"{a}:{b}" for a, b in workloads.RATE_PAIRS) + ".",
        f"- Full cross product: {len(workloads.LENGTHS)} x {len(workloads.SIGNAL_TYPES)} x "
        f"{len(workloads.RATE_PAIRS)} = "
        f"{len(workloads.LENGTHS) * len(workloads.SIGNAL_TYPES) * len(workloads.RATE_PAIRS)}; "
        f"{len(raw['exclusions'])} excluded, {len(cells)} measured.",
        "",
        "## Cold and process costs",
        "",
        "| Measurement | Median | Notes |",
        "|---|---:|---|",
        f"| Native bench build | {fmt_ms(meta['builds']['bench']['build_ns'])} ms | `bench.mojo` |",
        f"| Native CLI build | {fmt_ms(meta['builds']['cli']['build_ns'])} ms | `cli.mojo` |",
        f"| Upstream first call (JIT + execute) | "
        f"{fmt_ms(statistics.median(r['elapsed_ns'] for r in raw['cold']['runs']))} ms | "
        f"{raw['cold']['spec']['length']} samples, "
        f"{raw['cold']['spec']['sr_orig']}->{raw['cold']['spec']['sr_new']} |",
        f"| CLI ping floor (process + empty frame) | "
        f"{fmt_ms(raw['cli_ping']['median_ns'])} ms | no filter validation or kernel |",
        "",
        f"Build note: {meta['build_note']}. Warm rows below exclude all of the above.",
        "",
        "## Correctness gate",
        "",
        "Every cell compares the upstream output, native in-process output, and native CLI "
        "output by SHA-256 of little-endian Float64 bytes. Output lengths also match exactly.",
        f"- PASS: {len(cells) - gate_failures}; FAIL: {gate_failures}.",
        "- Max absolute error: 0.0; RMSE: 0.0; mismatches: 0 (exact bit equality).",
        "- Per-cell gate records and input/output SHA-256 hashes are in "
        "`results/raw_results.json`.",
        "",
        "## Warm results by rate pair",
        "",
        "Ratios are medians of per-cell ratios; >1 means native is faster than upstream, "
        "and CLI overhead >1 means the CLI path is slower than native in-process.",
        "",
        "| Rate pair | Cells | Upstream median (ms) | Native median (ms) "
        "| Native vs upstream | CLI overhead |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for sr_orig, sr_new in workloads.RATE_PAIRS:
        group = [c for c in cells if (c["sr_orig"], c["sr_new"]) == (sr_orig, sr_new)]
        if not group:
            continue
        native_ratio = statistics.median(
            c["aggregate"]["upstream_warm"]["median_ns"] / c["aggregate"]["native"]["median_ns"]
            for c in group
        )
        cli_ratio = statistics.median(
            c["aggregate"]["native_cli"]["median_ns"] / c["aggregate"]["native"]["median_ns"]
            for c in group
        )
        upstream_ms = (
            statistics.median(c["aggregate"]["upstream_warm"]["median_ns"] for c in group) / 1e6
        )
        native_ms = statistics.median(c["aggregate"]["native"]["median_ns"] for c in group) / 1e6
        lines.append(
            f"| {sr_orig}:{sr_new} | {len(group)} "
            f"| {upstream_ms:.3f} | {native_ms:.3f} "
            f"| {native_ratio:.2f}x | {cli_ratio:.2f}x |"
        )

    lines += [
        "",
        "## Dispersion",
        "",
        "Within-run coefficient of variation (`stdev / median`) is computed per run, "
        "then the median across cells is shown. Cells below 1024 samples are separated "
        "because timer resolution dominates them.",
        "",
        "| Path | Length < 1024 | Length >= 1024 |",
        "|---|---:|---:|",
    ]
    for impl, label in (
        ("upstream_warm", "Upstream warm"),
        ("native", "Native in-process"),
        ("native_cli", "Native CLI"),
    ):
        small = []
        large = []
        for cell in cells:
            for run in cell["runs"]:
                stats = run[impl]
                if stats["median_ns"] <= 0:
                    continue
                cv = stats["stdev_ns"] / stats["median_ns"] * 100.0
                (small if cell["length"] < 1024 else large).append(cv)
        lines.append(
            f"| {label} | {statistics.median(small):.1f}% | {statistics.median(large):.1f}% |"
        )

    run_spread = statistics.median(
        abs(
            c["aggregate"]["native"]["run_medians_ns"][0]
            - c["aggregate"]["native"]["run_medians_ns"][1]
        )
        / c["aggregate"]["native"]["median_ns"]
        * 100.0
        for c in cells
    )
    lines += [
        "",
        f"Median run-to-run spread for native in-process: {run_spread:.1f}% of the cell median.",
        "",
        "## Sine workload detail",
        "",
        "Cells are native / upstream median milliseconds. Lengths are input samples.",
        "",
        "| Rate pair | " + " | ".join(str(n) for n in workloads.LENGTHS) + " |",
        "|---|" + "|".join("---:" for _ in workloads.LENGTHS) + "|",
    ]
    by_key = {(c["sr_orig"], c["sr_new"], c["length"], c["signal_type"]): c for c in cells}
    for sr_orig, sr_new in workloads.RATE_PAIRS:
        row = [f"{sr_orig}:{sr_new}"]
        for length in workloads.LENGTHS:
            cell = by_key.get((sr_orig, sr_new, length, "sine"))
            if cell is None:
                row.append("excluded")
            else:
                native = cell["aggregate"]["native"]["median_ns"] / 1e6
                upstream = cell["aggregate"]["upstream_warm"]["median_ns"] / 1e6
                row.append(f"{native:.3f} / {upstream:.3f}")
        lines.append("| " + " | ".join(row) + " |")

    lines += [
        "",
        "## Observations",
        "",
        "- Upstream warm execution is the fastest path on large inputs; it is a compiled "
        "Numba loop with no per-call protocol or filter-validation cost.",
        "- Native in-process timing measures the public Mojo `resample` entry point, "
        "including filter-table preparation and output allocation per call.",
        "- The CLI path is reported separately because it carries process startup, framed "
        "I/O, SHA-256 filter validation, and output encoding on every request.",
        "- The CLI ping floor sets the minimum possible CLI cost; the 1:1 rate pair is "
        "dominated by that floor because the kernel itself is a copy.",
        "- No universal-speedup claim is made. These numbers characterize this host and "
        "the current native implementation; they are not an optimization result.",
        "",
        "## Methodology deviations",
        "",
        "- Four paths are measured: upstream warm, upstream cold, native in-process, and "
        "native CLI. The binding document also lists a Python-to-Mojo interop path; it is "
        "unavailable in v0.1.0 and is reported here as a gap.",
        "- The correctness gate is exact SHA-256 equality, stronger than the tolerance "
        "proposal in the Phase 1 design.",
        "- CPU affinity uses `os.sched_setaffinity` rather than a `taskset` wrapper; "
        "children inherit the single pinned CPU.",
        "- The optional pure-Python floor and optional upstream `parallel=True` variant "
        "are not measured.",
        "- Aggregates use median-of-medians rather than the Phase 1 proposal's geometric "
        "means; ratios span orders of magnitude and tiny cells would dominate.",
        "- Per-operation peak memory is not isolated; driver and child peak RSS are "
        "reported instead.",
        "- Build wall time is measured after removing the output binary, but the Mojo "
        "compiler cache state is whatever the installed toolchain provides.",
        "",
        "## Exclusions and limitations",
        "",
        "- `length=2, 44100:16000` is excluded because the computed output length is 0; "
        "upstream requires at least one output sample.",
        "- Only 1-D Float64 `kaiser_fast` is measured. Float32, complex, N-D, `kaiser_best`, "
        "and parallel upstream execution are outside scope.",
        "- All timings are single-core pinned. Results are specific to this host and toolchain.",
        "- The coefficient resource was extracted to a temporary directory and deleted; "
        "its SHA-256 is recorded above.",
        "",
        "## Reproduction",
        "",
        "```bash",
        ".venv/bin/python libraries/resampy/benchmarks/run_benchmarks.py",
        "```",
        "",
        "Raw samples: `results/raw_results.json`; environment: `results/environment.json`; "
        "flattened table: `results/summary.csv`.",
        "",
    ]
    path.write_text("\n".join(lines))


def self_check() -> int:
    workloads.self_check()
    signal = workloads.signal_values(64, "sine")
    assert hash_values(signal) == hash_values(signal.copy())
    assert len(cli_request(signal, 1, 2, b"{}", b"")) > len(f64le(signal))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--cold-child" in argv:
        return cold_child()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=BENCH_DIR / "config.json")
    parser.add_argument("--runs", type=int, default=None)
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--cli-samples", type=int, default=None)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)

    if args.self_check:
        return self_check()

    config = json.loads(args.config.read_text())
    if args.runs is not None:
        config["runs"] = args.runs
    if args.samples is not None:
        config["samples"] = args.samples
    if args.cli_samples is not None:
        config["cli_samples"] = args.cli_samples
    for key in ("lengths", "signal_types", "rate_pairs"):
        loaded = config[key]
        expected = getattr(workloads, key.upper())
        if key == "rate_pairs":
            matches = [tuple(v) for v in loaded] == [tuple(v) for v in expected]
        else:
            matches = list(loaded) == list(expected)
        if not matches:
            raise SystemExit(f"config {key} does not match workloads.py")

    import resampy

    if resampy.__version__ != UPSTREAM_VERSION:
        raise SystemExit(f"need resampy=={UPSTREAM_VERSION}, found {resampy.__version__}")

    cases = workloads.cases(config["seed"])
    cold_spec = {
        "length": 4096,
        "signal_type": "sine",
        "sr_orig": 16000,
        "sr_new": 44100,
        "seed": config["seed"],
    }

    with tempfile.TemporaryDirectory(prefix="resampy_bench_filter_") as temp:
        filter_info = make_filter(Path(temp))
        builds = build_binaries()
        cpu = pin_cpu()
        print(f"pinned to CPU {cpu}", flush=True)
        cold_runs = run_cold(cold_spec, config["runs"])
        print(
            f"cold upstream: {statistics.median(r['elapsed_ns'] for r in cold_runs) / 1e9:.2f}s",
            flush=True,
        )
        ping_runs = [
            stats(time_ping(config["warmup"], config["cli_samples"])) for _ in range(config["runs"])
        ]

        prewarm = workloads.signal_values(cold_spec["length"], cold_spec["signal_type"])
        resampy.resample(
            prewarm,
            cold_spec["sr_orig"],
            cold_spec["sr_new"],
            filter=FILTER_NAME,
            parallel=False,
        )

        cell_results: list[dict] = []
        reference_hashes: dict[str, str] = {}
        for index, case in enumerate(cases, 1):
            reference = resampy.resample(
                case["signal"],
                case["sr_orig"],
                case["sr_new"],
                filter=FILTER_NAME,
                parallel=False,
            )
            if int(reference.size) != case["output_length"]:
                raise SystemExit(f"{case['case_id']}: upstream output length mismatch")
            reference_sha = hash_values(reference)
            reference_hashes[case["case_id"]] = reference_sha
            native_body = bench_body(case["signal"], case["sr_orig"], case["sr_new"])
            frame = cli_request(
                case["signal"],
                case["sr_orig"],
                case["sr_new"],
                filter_info["meta"],
                filter_info["resource"],
            )
            run_results = []
            for _ in range(config["runs"]):
                upstream_samples, upstream_out = time_upstream(
                    case["signal"],
                    case["sr_orig"],
                    case["sr_new"],
                    config["warmup"],
                    config["samples"],
                )
                if hash_values(upstream_out) != reference_sha:
                    raise SystemExit(f"{case['case_id']}: upstream timing output changed")
                native = run_native(
                    filter_info["meta_path"],
                    filter_info["bin_path"],
                    native_body,
                    config["warmup"],
                    config["samples"],
                )
                if native["output_sha256"] != reference_sha:
                    raise SystemExit(f"{case['case_id']}: native output mismatch")
                if native["output_count"] != case["output_length"]:
                    raise SystemExit(f"{case['case_id']}: native output length mismatch")
                cli_samples = time_cli(
                    frame,
                    config["warmup"],
                    config["cli_samples"],
                    reference_sha,
                )
                run_results.append(
                    {
                        "upstream_warm": stats(upstream_samples),
                        "native": stats(native["samples_ns"]),
                        "native_cli": stats(cli_samples),
                    }
                )
            cell_results.append(
                {
                    **{
                        k: case[k]
                        for k in (
                            "case_id",
                            "length",
                            "signal_type",
                            "sr_orig",
                            "sr_new",
                            "output_length",
                        )
                    },
                    "input_sha256": hash_values(case["signal"]),
                    "reference_sha256": reference_sha,
                    "gate": {
                        "status": "PASS",
                        "length_match": True,
                        "max_abs_error": 0.0,
                        "rmse": 0.0,
                        "mismatches": 0,
                    },
                    "runs": run_results,
                    "aggregate": {
                        implementation: aggregate_runs(run_results, implementation)
                        for implementation in ("upstream_warm", "native", "native_cli")
                    },
                }
            )
            if index % 24 == 0 or index == len(cases):
                print(f"  ... {index}/{len(cases)} cells", flush=True)

        cold_ref = reference_hashes[
            f"n{cold_spec['length']:05d}-{cold_spec['signal_type']}-"
            f"{cold_spec['sr_orig']}_{cold_spec['sr_new']}"
        ]
        for record in cold_runs:
            if record["output_sha256"] != cold_ref:
                raise SystemExit("cold upstream output mismatch")

        raw = {
            "meta": env_metadata(config, filter_info, builds, cpu),
            "cold": {
                "spec": cold_spec,
                "runs": cold_runs,
                "median_ns": statistics.median(r["elapsed_ns"] for r in cold_runs),
            },
            "cli_ping": {
                "runs": ping_runs,
                "median_ns": statistics.median(r["median_ns"] for r in ping_runs),
            },
            "exclusions": workloads.exclusions(),
            "cells": cell_results,
        }
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "environment.json").write_text(json.dumps(raw["meta"], indent=2) + "\n")
        (RESULTS_DIR / "raw_results.json").write_text(json.dumps(raw, indent=2) + "\n")
        write_summary_csv(RESULTS_DIR / "summary.csv", raw)
        write_report(REPORT_DIR / "BENCHMARK_REPORT.md", raw)
        print(f"wrote {RESULTS_DIR / 'raw_results.json'}")
        print(f"wrote {RESULTS_DIR / 'summary.csv'}")
        print(f"wrote {REPORT_DIR / 'BENCHMARK_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
