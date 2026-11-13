#!/usr/bin/env python3
"""Three-way bitarray benchmark driver: pure Python vs C-backed bitarray
vs native Mojo.

One command from the repository root::

    .venv/bin/python libraries/bitarray/benchmarks/run_benchmarks.py

Methodology: workloads are generated once (fixed seed) and shared by all
paths. Python timing uses ``time.perf_counter_ns`` with warmup and
repeated samples. Native timing is measured in-process by ``bench.mojo``
(built once; build time is reported separately as cold compilation) and
excludes stdin framing, process startup, and IPC. Every Mojo result is
verified against the C reference outside the timed region. Raw samples
plus environment metadata go to a JSON report; median tables print to
stdout for the curated summary.

Implementation labels, used consistently everywhere:

- ``pure`` -- local pure-Python list-of-bool operations (the honest
  algorithmic floor; no NumPy/Cython/Numba).
- ``c`` -- ``bitarray==3.12.3`` C extension (the ceiling).
- ``mojo`` -- the released native Mojo operations on packed storage.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import struct
import subprocess
import sys
import time
from pathlib import Path

from bitarray import bitarray

ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
BENCH_BIN = BUILD_DIR / "bench_bitarray"

sys.path.insert(0, str(BENCH_DIR))

import pure_python_reference as pure  # noqa: E402
import validate_results  # noqa: E402
from workloads import build_workloads, fnv1a_checksum  # noqa: E402

REFERENCE_VERSION = "3.12.3"


def sh(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=False, **kwargs)


def mojo_binary() -> Path:
    venv_mojo = ROOT / ".venv" / "bin" / "mojo"
    if venv_mojo.exists():
        return venv_mojo
    raise SystemExit("run_benchmarks: .venv/bin/mojo not found; run `uv sync --extra dev`")


def env_metadata() -> dict:
    cpu_model, mem_total = "unknown", "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                mem_total = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    try:
        git_rev = sh(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).stdout.decode().strip()
    except OSError:
        git_rev = "unknown"
    try:
        mojo_version = sh([str(mojo_binary()), "--version"]).stdout.decode().strip()
    except OSError:
        mojo_version = "unknown"
    import importlib.metadata

    return {
        "python": sys.version.split()[0],
        "bitarray": importlib.metadata.version("bitarray"),
        "mojo": mojo_version,
        "cpu": cpu_model,
        "cores": os.cpu_count(),
        "memory": mem_total,
        "os": platform.platform(),
        "git": git_rev,
        "timer": "time.perf_counter_ns (integer nanoseconds)",
    }


def time_op(fn, args: tuple, warmup: int, samples: int) -> tuple[list[int], object]:
    for _ in range(warmup):
        fn(*args)
    out = []
    result = None
    for _ in range(samples):
        start = time.perf_counter_ns()
        result = fn(*args)
        out.append(time.perf_counter_ns() - start)
    return out, result


def stats(samples: list[int]) -> dict:
    ordered = sorted(samples)
    median = statistics.median(ordered)
    mean = statistics.fmean(ordered)
    stdev = statistics.stdev(ordered) if len(ordered) > 1 else 0.0
    return {
        "samples": len(ordered),
        "min_ns": ordered[0],
        "median_ns": median,
        "max_ns": ordered[-1],
        "mean_ns": mean,
        "stdev_ns": stdev,
        "ops_per_s": 1e9 / median if median > 0 else 0.0,
    }


def framed(bits: str, endian: str) -> bytes:
    a = bitarray(bits, endian=endian)
    eid = 0 if endian == "big" else 1
    return struct.pack(">I", len(a)) + bytes([eid]) + a.tobytes()


def bench_frame(bits_a: str, bits_b: str, endian: str, k: int) -> bytes:
    return framed(bits_a, endian) + framed(bits_b, endian) + struct.pack(">I", k)


def run_mojo(op: str, frame: bytes, warmup: int, samples: int) -> dict:
    result = sh(
        [str(BENCH_BIN), op, str(warmup), str(samples)],
        input=struct.pack(">I", len(frame)) + frame,
    )
    if result.returncode != 0:
        raise SystemExit(f"bench_bitarray {op} failed: {result.stderr.decode()[:300]!r}")
    if result.stderr:
        raise SystemExit(f"bench_bitarray {op} wrote to stderr: {result.stderr[:200]!r}")
    try:
        return json.loads(result.stdout.decode())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"bench_bitarray {op} printed invalid JSON: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=BENCH_DIR / "config.json")
    parser.add_argument(
        "--raw-out", type=Path, default=BENCH_DIR / "results" / "bitarray_v0.1.0_results.json"
    )
    parser.add_argument(
        "--summary-out", type=Path, default=BENCH_DIR / "results" / "bitarray_v0.1.0_summary.md"
    )
    parser.add_argument("--sizes", type=int, nargs="*", default=None)
    parser.add_argument("--dists", nargs="*", default=None)
    parser.add_argument("--samples", type=int, default=None)
    args = parser.parse_args(argv)

    import importlib.metadata

    if importlib.metadata.version("bitarray") != REFERENCE_VERSION:
        raise SystemExit(f"need bitarray=={REFERENCE_VERSION}")
    import bitarray._bitarray as ext

    if not ext.__file__.endswith(".so"):
        raise SystemExit(f"C extension not loaded: {ext.__file__}")

    config = json.loads(args.config.read_text())
    warmup = config["warmup"]
    samples = args.samples or config["samples"]
    if args.sizes is not None:
        config = {**config, "sizes": args.sizes}
    if args.dists is not None:
        config = {**config, "distributions": args.dists}
    workloads = build_workloads(config["seed"], config)

    print("=== correctness gate (validate_results) ===", flush=True)
    validate_results.main()

    print("=== building bench_bitarray (cold compile timed separately) ===", flush=True)
    build_start = time.perf_counter_ns()
    build = sh(
        [
            str(mojo_binary()),
            "build",
            str(BENCH_DIR / "bench.mojo"),
            "-I",
            str(ROOT / "libraries" / "bitarray" / "mojo"),
            "-o",
            str(BENCH_BIN),
        ],
        cwd=ROOT,
    )
    build_ns = time.perf_counter_ns() - build_start
    if build.returncode != 0:
        raise SystemExit(f"mojo build bench.mojo failed:\n{build.stderr.decode()[-2000:]}")
    print(f"cold compile: {build_ns / 1e9:.2f}s", flush=True)

    results: dict[str, dict] = {}
    ncells = 0
    for wl in workloads:
        n, endian = wl["nbits"], wl["endian"]
        la = pure.from_bits(wl["bits_a"])
        lb = pure.from_bits(wl["bits_b"])
        entry: dict = {
            "description": f"{n}-bit {wl['dist']} ({endian}-endian)",
            "nbits": n,
            "dist": wl["dist"],
            "endian": endian,
        }
        variants: list[tuple[str, tuple, tuple]] = []
        ref_a = bitarray(wl["bits_a"], endian=endian)
        ref_b = bitarray(wl["bits_b"], endian=endian)
        variants.append(("and", (la, lb), (ref_a, ref_b)))
        variants.append(("or", (la, lb), (ref_a, ref_b)))
        variants.append(("xor", (la, lb), (ref_a, ref_b)))
        variants.append(("count", (la,), (ref_a,)))
        for k in wl["shifts"]:
            variants.append((f"shl@{k}", (la, k), (ref_a, k)))
            variants.append((f"shr@{k}", (la, k), (ref_a, k)))
        for key, pure_args, ref_args in variants:
            op = key.split("@")[0]
            k = int(key.split("@")[1]) if "@" in key else 0
            # Pure Python (in-process).
            pure_fn = {
                "and": pure.band,
                "or": pure.bor,
                "xor": pure.bxor,
                "count": pure.count,
                "shl": pure.shl,
                "shr": pure.shr,
            }[op]
            pure_samples, pure_res = time_op(pure_fn, pure_args, warmup, samples)
            # C-backed reference (in-process).
            ref_fn = {
                "and": lambda a, b: a & b,
                "or": lambda a, b: a | b,
                "xor": lambda a, b: a ^ b,
                "count": lambda a: a.count(),
                "shl": lambda a, k: a << k,
                "shr": lambda a, k: a >> k,
            }[op]
            c_samples, c_res = time_op(ref_fn, ref_args, warmup, samples)
            # Native Mojo (in-process binary; startup excluded).
            frame = bench_frame(wl["bits_a"], wl["bits_b"], endian, k)
            mojo_out = run_mojo(op, frame, warmup, samples)
            # Verify the Mojo result against the C reference.
            if op == "count":
                if mojo_out["count"] != ref_a.count():
                    raise SystemExit(f"mojo count mismatch on {wl['id']}/{key}")
            else:
                ref_bits = {
                    "and": (ref_a & ref_b).to01(),
                    "or": (ref_a | ref_b).to01(),
                    "xor": (ref_a ^ ref_b).to01(),
                    "shl": (ref_a << k).to01(),
                    "shr": (ref_a >> k).to01(),
                }[op]
                ref_packed = bitarray(ref_bits, endian=endian).tobytes()
                eid = 0 if endian == "big" else 1
                if mojo_out["checksum"] != str(fnv1a_checksum(n, eid, ref_packed)):
                    raise SystemExit(f"mojo checksum mismatch on {wl['id']}/{key}")
            entry[key] = {
                "pure": stats(pure_samples),
                "c": stats(c_samples),
                "mojo": stats(mojo_out["samples_ns"]),
            }
            ncells += 1
        results[wl["id"]] = entry
        if len(results) % 24 == 0:
            print(f"  ... {len(results)}/{len(workloads)} workloads", flush=True)

    # ---- gates ----
    for name, entry in results.items():
        for key, value in entry.items():
            if not isinstance(value, dict) or "mojo" not in value:
                continue
            for impl in ("pure", "c", "mojo"):
                cell = value[impl]
                if cell["min_ns"] <= 0:
                    raise SystemExit(f"timer check failed: {name}/{key}/{impl} has a zero sample")
                if cell["samples"] != samples:
                    raise SystemExit(f"timer check failed: {name}/{key}/{impl} sample count")
    # Scaling spot-check on large sizes only (small-size noise dominates).
    for op in ("and", "or", "xor", "count", "shl@8", "shr@8"):
        for dist in ("uniform", "zeros"):
            for endian in ("big", "little"):
                chain = [f"n{n:07d}-{dist}-{endian}" for n in (4096, 16384, 65536, 262144, 1048576)]
                medians = [
                    results[nm][op]["mojo"]["median_ns"]
                    for nm in chain
                    if nm in results and op in results[nm]
                ]
                for lo, hi in zip(medians, medians[1:], strict=False):
                    if not hi >= lo:
                        raise SystemExit(
                            f"scaling check failed: mojo/{op}/{dist}/{endian} ({lo} vs {hi})"
                        )

    report = {
        "meta": {**env_metadata(), "config": config, "cells": ncells},
        "workloads": results,
    }
    args.raw_out.parent.mkdir(parents=True, exist_ok=True)
    args.raw_out.write_text(json.dumps(report, indent=2) + "\n")

    _print_tables(results)
    print(f"raw report: {args.raw_out}")
    _write_summary(args.summary_out, report)
    print(f"summary: {args.summary_out}")
    return 0


def _bps(nbits: int, median_ns: float) -> float:
    return nbits / (median_ns / 1e9) if median_ns > 0 else 0.0


def _write_summary(path: Path, report: dict) -> None:
    meta = report["meta"]
    workloads = report["workloads"]
    lines = [
        "# Bitarray v0.1.0 benchmark summary (generated, do not edit by hand)",
        "",
        "Regenerate with:",
        "",
        "```bash",
        ".venv/bin/python libraries/bitarray/benchmarks/run_benchmarks.py",
        "```",
        "",
        "## Environment",
        "",
        *[f"- {k}: {v}" for k, v in meta.items() if k != "config"],
        "- config: " + json.dumps(meta["config"]),
        "",
        "## Results (median ns | Mbit/s | speedup vs pure | speedup vs C)",
        "",
    ]
    variants: list[str] = []
    for entry in workloads.values():
        for key in entry:
            if key not in ("description", "nbits", "dist", "endian") and key not in variants:
                variants.append(key)
    order = {"and": 0, "or": 1, "xor": 2, "count": 3}
    variants.sort(key=lambda k: (order.get(k, 4), k))
    for op in variants:
        lines.append(f"### {op}")
        lines.append("")
        lines.append("| workload | nbits | pure | c | mojo | mojo vs pure | mojo vs C |")
        lines.append("|---|---|---|---|---|---|---|")
        for name in sorted(workloads):
            entry = workloads[name]
            if op not in entry:
                continue
            cells = {impl: entry[op][impl] for impl in ("pure", "c", "mojo")}
            med = {impl: cells[impl]["median_ns"] for impl in cells}
            row = (
                f"| {name} | {entry['nbits']} "
                f"| {med['pure']:.0f} ({_bps(entry['nbits'], med['pure']) / 1e6:.1f}) "
                f"| {med['c']:.0f} ({_bps(entry['nbits'], med['c']) / 1e6:.1f}) "
                f"| {med['mojo']:.0f} ({_bps(entry['nbits'], med['mojo']) / 1e6:.1f}) "
                f"| {med['pure'] / med['mojo']:.1f}x | {med['c'] / med['mojo']:.1f}x |"
            )
            lines.append(row)
        lines.append("")
    lines.append("Speedup = baseline median / mojo median; >1 means Mojo is faster.")
    lines.append("Bits/s uses the logical bit length and the median sample.")
    path.write_text("\n".join(lines) + "\n")


def _print_tables(results: dict) -> None:
    for op in ("and", "or", "xor", "count"):
        print(f"\n### {op} (median ns | Mbit/s, speedup vs pure, vs C)")
        print("size/dist/endian | pure | c | mojo | mojo vs pure | mojo vs C")
        for name in sorted(results):
            entry = results[name]
            if op not in entry:
                continue
            p, c, m = (entry[op][i]["median_ns"] for i in ("pure", "c", "mojo"))
            print(
                f"{entry['nbits']}/{entry['dist']}/{entry['endian']} | "
                f"{p:.0f} | {c:.0f} | {m:.0f} | {p / m:.1f}x | {c / m:.1f}x"
            )


if __name__ == "__main__":
    raise SystemExit(main())
