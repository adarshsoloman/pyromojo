#!/usr/bin/env python3
"""Three-way MessagePack benchmark driver: fallback vs C vs native Mojo.

One command from the repository root::

    .venv/bin/python libraries/msgpack/benchmarks/run_benchmarks.py

Methodology: payload bytes are generated once (fixed seed) and shared by all
three paths. Python timing uses ``time.perf_counter_ns`` around pure codec
calls with warmup and repeated samples. Native timing is measured in-process
by ``bench.mojo`` (built once; build time is reported separately as cold
compilation) and excludes stdin framing, process startup, and IPC. Full
correctness checks (byte equality plus value fingerprints) run outside every
timed region. Raw samples plus environment metadata go to a ``*.bench.json``
report (git-ignored); median tables print to stdout for the curated release
summary.
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

import msgpack.fallback

import msgpack

ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
BENCH_BIN = BUILD_DIR / "bench_msgpack"

sys.path.insert(0, str(BENCH_DIR))
sys.path.insert(0, str(ROOT / "libraries" / "msgpack" / "python_reference"))

from generate_vectors import MapPairs  # noqa: E402
from workloads import build_workloads, fingerprint, fnv_single  # noqa: E402


def sh(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=False, **kwargs)


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
    return {
        "python": sys.version.split()[0],
        "msgpack": msgpack.version,
        "mojo": mojo_version,
        "cpu": cpu_model,
        "cores": os.cpu_count(),
        "memory": mem_total,
        "os": platform.platform(),
        "git": git_rev,
        "timer": "time.perf_counter_ns (integer nanoseconds)",
    }


def mojo_binary() -> Path:
    venv_mojo = ROOT / ".venv" / "bin" / "mojo"
    if venv_mojo.exists():
        return venv_mojo
    raise SystemExit("run_benchmarks: .venv/bin/mojo not found; run `uv sync --extra dev`")


def time_op(fn, warmup: int, samples: int) -> list[int]:
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        fn()
        out.append(time.perf_counter_ns() - start)
    return out


def stats(samples: list[int], payload_bytes: int) -> dict:
    ordered = sorted(samples)
    median = statistics.median(ordered)
    ops = 1e9 / median if median > 0 else 0.0
    return {
        "samples": len(ordered),
        "min_ns": ordered[0],
        "median_ns": median,
        "max_ns": ordered[-1],
        "ops_per_s": ops,
        "bytes_per_s": payload_bytes * ops,
    }


def frame(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


def run_mojo(op: str, payload: bytes, warmup: int, samples: int) -> dict:
    result = sh([str(BENCH_BIN), op, str(warmup), str(samples)], input=frame(payload))
    if result.returncode != 0:
        raise SystemExit(f"bench_msgpack {op} failed: {result.stderr.decode()[:500]!r}")
    if result.stderr:
        raise SystemExit(f"bench_msgpack {op} wrote to stderr: {result.stderr[:200]!r}")
    try:
        return json.loads(result.stdout.decode())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"bench_msgpack {op} printed invalid JSON: {exc}") from exc


RSS_WRAPPER = (
    "import subprocess, resource, sys; "
    "inp = open(sys.argv[1], 'rb').read(); "
    "p = subprocess.run(sys.argv[2:], input=inp, capture_output=True); "
    "ru = resource.getrusage(resource.RUSAGE_CHILDREN); "
    "sys.stdout.buffer.write(b'RSS-KB:' + str(ru.ru_maxrss).encode() + b'\\n'); "
    "sys.stdout.buffer.write(p.stdout); "
    "sys.exit(p.returncode)"
)


def run_mojo_isolated(op: str, payload_path: Path, warmup: int, samples: int) -> tuple[dict, int]:
    """Run one bench invocation as the only child, reporting its peak RSS."""
    result = sh(
        [
            sys.executable,
            "-c",
            RSS_WRAPPER,
            str(payload_path),
            str(BENCH_BIN),
            op,
            str(warmup),
            str(samples),
        ]
    )
    if result.returncode != 0:
        raise SystemExit(f"isolated bench_msgpack {op} failed: rc={result.returncode}")
    first, _, rest = result.stdout.partition(b"\n")
    if not first.startswith(b"RSS-KB:"):
        raise SystemExit("isolated wrapper did not report RSS")
    try:
        return json.loads(rest.decode()), int(first.split(b":")[1]) * 1024
    except (json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"isolated bench_msgpack {op} bad output: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=BENCH_DIR / "config.json")
    parser.add_argument("--only", default="", help="comma-separated workload names")
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--raw-out", type=Path, default=BUILD_DIR / "msgpack-bench.bench.json")
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text())
    seed = config["seed"]
    warmup = args.warmup if args.warmup is not None else config["warmup"]
    samples = args.samples if args.samples is not None else config["samples"]
    only = {name.strip() for name in args.only.split(",") if name.strip()}
    if samples < 15:
        raise SystemExit("methodology requires at least 15 samples")

    workloads = [
        (name, desc, value)
        for name, desc, value in build_workloads(seed)
        if not only or name in only
    ]
    if not workloads:
        raise SystemExit("no workloads selected")

    BUILD_DIR.mkdir(exist_ok=True)
    if BENCH_BIN.exists():
        BENCH_BIN.unlink()
    compile_start = time.perf_counter_ns()
    build = sh(
        [
            str(mojo_binary()),
            "build",
            str(BENCH_DIR / "bench.mojo"),
            "-I",
            str(ROOT / "libraries" / "msgpack" / "mojo"),
            "-o",
            str(BENCH_BIN),
        ],
        cwd=ROOT,
    )
    compile_ns = time.perf_counter_ns() - compile_start
    if build.returncode != 0:
        raise SystemExit(f"mojo build failed:\n{build.stderr.decode()[-2000:]}")
    exe_bytes = BENCH_BIN.stat().st_size

    fallback_packer = msgpack.fallback.Packer(use_bin_type=True)
    results: dict[str, dict] = {}
    for name, desc, value in workloads:
        ref = msgpack.packb(value, use_bin_type=True)
        expected_fp = fingerprint(
            msgpack.unpackb(ref, strict_map_key=False, object_pairs_hook=MapPairs)
        )
        assert fingerprint(value) == expected_fp, f"{name}: driver fold mismatch"
        fallback_first = msgpack.fallback.unpackb(
            ref, strict_map_key=False, object_pairs_hook=MapPairs
        )
        assert repr(fallback_first) == repr(
            msgpack.unpackb(ref, strict_map_key=False, object_pairs_hook=MapPairs)
        ), f"{name}: C/fallback decode mismatch"

        entry: dict[str, dict] = {"description": desc, "payload_bytes": len(ref)}
        c_enc = time_op(
            lambda value=value: msgpack.packb(value, use_bin_type=True), warmup, samples
        )
        assert msgpack.packb(value, use_bin_type=True) == ref
        entry["encode_c"] = stats(c_enc, len(ref))
        c_dec = time_op(
            lambda ref=ref: msgpack.unpackb(ref, strict_map_key=False, object_pairs_hook=MapPairs),
            warmup,
            samples,
        )
        assert (
            fingerprint(msgpack.unpackb(ref, strict_map_key=False, object_pairs_hook=MapPairs))
            == expected_fp
        )
        entry["decode_c"] = stats(c_dec, len(ref))

        f_enc = time_op(lambda value=value: fallback_packer.pack(value), warmup, samples)
        assert fallback_packer.pack(value) == ref
        entry["encode_fallback"] = stats(f_enc, len(ref))
        f_dec = time_op(
            lambda ref=ref: msgpack.fallback.unpackb(
                ref, strict_map_key=False, object_pairs_hook=MapPairs
            ),
            warmup,
            samples,
        )
        assert (
            fingerprint(
                msgpack.fallback.unpackb(ref, strict_map_key=False, object_pairs_hook=MapPairs)
            )
            == expected_fp
        )
        entry["decode_fallback"] = stats(f_dec, len(ref))

        mojo_enc = run_mojo("encode", ref, warmup, samples)
        if mojo_enc["verify_checksum"] != fnv_single(ref):
            raise SystemExit(f"{name}: mojo encode bytes differ from reference")
        if mojo_enc["fingerprint"] != expected_fp:
            raise SystemExit(f"{name}: mojo decoded value differs from reference")
        entry["encode_mojo"] = stats(mojo_enc["samples_ns"], len(ref))
        mojo_dec = run_mojo("decode", ref, warmup, samples)
        if mojo_dec["fingerprint"] != expected_fp:
            raise SystemExit(f"{name}: mojo decode value differs from reference")
        entry["decode_mojo"] = stats(mojo_dec["samples_ns"], len(ref))

        results[name] = entry
        print(f"workload {name}: {len(ref)} bytes, checks passed", flush=True)

    for small, large in (("ints_small", "ints_large"), ("maps_small", "maps_large")):
        if small not in results or large not in results:
            continue
        small_total = results[small]["decode_mojo"]["median_ns"]
        large_total = results[large]["decode_mojo"]["median_ns"]
        if not large_total > small_total:
            raise SystemExit(
                f"scaling check failed: {large} decode ({large_total} ns) is not "
                f"slower than {small} ({small_total} ns)"
            )
    for name, entry in results.items():
        for op in (
            "encode_c",
            "decode_c",
            "encode_fallback",
            "decode_fallback",
            "encode_mojo",
            "decode_mojo",
        ):
            if entry[op]["min_ns"] <= 0:
                raise SystemExit(f"timer check failed: {name}/{op} has a zero sample")

    largest = max(results.items(), key=lambda kv: kv[1]["payload_bytes"])[0]
    largest_ref = msgpack.packb(
        next(value for name, _, value in workloads if name == largest),
        use_bin_type=True,
    )
    payload_path = BUILD_DIR / "bench-payload.tmp"
    payload_path.write_bytes(frame(largest_ref))
    _, rss_encode = run_mojo_isolated("encode", payload_path, warmup, samples)
    _, rss_decode = run_mojo_isolated("decode", payload_path, warmup, samples)
    payload_path.unlink()
    report = {
        "meta": {
            **env_metadata(),
            "seed": seed,
            "warmup": warmup,
            "samples": samples,
            "timer_resolution": "nanoseconds (see platform granularity note)",
        },
        "compile": {"cold_compile_ns": compile_ns, "exe_bytes": exe_bytes},
        "rss": {
            "workload": largest,
            "encode_peak_bytes": rss_encode,
            "decode_peak_bytes": rss_decode,
            "note": "isolated ru_maxrss of one bench process on the largest "
            "workload; includes process startup and Mojo runtime overhead",
        },
        "workloads": results,
    }
    args.raw_out.parent.mkdir(parents=True, exist_ok=True)
    args.raw_out.write_text(json.dumps(report, indent=2) + "\n")

    def row(op: str) -> list[str]:
        lines = []
        for name, entry in results.items():
            cells = [name, str(entry["payload_bytes"])]
            for key in (f"{op}_c", f"{op}_fallback", f"{op}_mojo"):
                s = entry[key]
                cells.append(f"{s['median_ns']:.0f} ({s['min_ns']:.0f}/{s['max_ns']:.0f})")
                cells.append(f"{s['ops_per_s']:,.0f}")
            lines.append(" | ".join(cells))
        return lines

    print(
        "\n## encode: workload | bytes | C median (min/max) ns | C ops/s | "
        "fallback median ns | fallback ops/s | mojo median ns | mojo ops/s"
    )
    print("\n".join(row("encode")))
    print(
        "\n## decode: workload | bytes | C median (min/max) ns | C ops/s | "
        "fallback median ns | fallback ops/s | mojo median ns | mojo ops/s"
    )
    print("\n".join(row("decode")))
    print(f"\ncold compile: {compile_ns / 1e9:.1f} s, exe {exe_bytes} bytes")
    print(f"peak RSS on {largest}: encode {rss_encode} B, decode {rss_decode} B")
    print(f"raw report: {args.raw_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
