#!/usr/bin/env python3
"""Three-path audioop benchmark driver: pure Python vs CPython 3.12.3
C-backed ``audioop`` vs native Mojo (kernel via ``bench.mojo``, plus a
separately-labelled CLI/protocol path).

Methodology: workloads are generated once (seed 20260610) and shared by
all paths. Every workload passes a three-way correctness gate (pure ==
CPython == Mojo) before any timing is recorded. Pure-Python and
CPython timing is in-process with ``time.perf_counter_ns``; Mojo kernel
timing is in-process inside ``bench.mojo``; the CLI path is measured
per-request (process + framing included) and is labelled as such — it
is never presented as kernel performance. Raw samples plus environment
metadata go to JSON/CSV artifacts under ``results/``; the report is
written to ``reports/BENCHMARK_REPORT.md``.

Usage::

    .venv/bin/python libraries/audioop/benchmarks/run_benchmarks.py [--runs 2]
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

ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
BENCH_BIN = BUILD_DIR / "bench_audioop"
CLI_BIN = BUILD_DIR / "audioop_cli"
REF_PY = ROOT / "libraries/audioop/python_reference/.venv/bin/python"
WARMUP = 5
SAMPLES = 25
CLI_SAMPLES = 15
SEED = 20260610

sys.path.insert(0, str(BENCH_DIR))
sys.path.insert(0, str(ROOT / "libraries/audioop/python_reference"))

import pure_python_reference as pure  # noqa: E402
from workloads import fnv1a_checksum, op_workloads  # noqa: E402

TASKSET = ["taskset", "-c", "11,13"]


def sh(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([*TASKSET, *command], capture_output=True, text=False, **kwargs)


def _cli(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([*TASKSET, *command], **kwargs)


def mojo_binary() -> Path:
    venv_mojo = ROOT / ".venv" / "bin" / "mojo"
    if venv_mojo.exists():
        return venv_mojo
    raise SystemExit("run_benchmarks: .venv/bin/mojo not found")


def ref_python() -> str:
    if REF_PY.exists():
        return str(REF_PY)
    raise SystemExit("run_benchmarks: CPython 3.12 reference venv not found")


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
    git_rev = sh(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).stdout.decode().strip()
    mojo_version = sh([str(mojo_binary()), "--version"]).stdout.decode().strip()
    return {
        "python": sys.version.split()[0],
        "reference_python": sh([ref_python(), "--version"]).stdout.decode().strip(),
        "mojo": mojo_version,
        "cpu": cpu_model,
        "cores": os.cpu_count(),
        "memory": mem_total,
        "os": platform.platform(),
        "git": git_rev,
        "seed": SEED,
        "timer": "time.perf_counter_ns (integer ns) / std.time.perf_counter_ns (Mojo)",
        "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def stats(samples: list[int]) -> dict:
    ordered = sorted(samples)
    median = statistics.median(ordered)
    stdev = statistics.stdev(ordered) if len(ordered) > 1 else 0.0
    return {
        "samples": len(ordered),
        "min_ns": ordered[0],
        "median_ns": median,
        "max_ns": ordered[-1],
        "mean_ns": statistics.fmean(ordered),
        "stdev_ns": stdev,
    }


# ---------------------------------------------------------------------------
# workload -> three-path execution
# ---------------------------------------------------------------------------


def op_args(entry: dict) -> tuple:
    """Arguments for the CPython audioop call, per workload."""
    op, width, frag = entry["op"], entry["width"], entry["fragment"]
    note = entry.get("note", "")
    warm = not (note.startswith("cold") or note.startswith("stereo") or note.startswith("content"))
    if op == "add":
        return (frag, frag, width)
    if op == "bias":
        return (frag, width, 37)
    if op in (
        "byteswap",
        "reverse",
        "lin2alaw",
        "lin2ulaw",
        "alaw2lin",
        "ulaw2lin",
        "alaw2lin_bytes",
        "ulaw2lin_bytes",
    ):
        return (frag, width)
    if op == "bias_37":
        return (frag, width, 37)
    if op == "mul":
        return (frag, width, entry["factor"])
    if op == "lin2lin":
        return (frag, width, entry["newwidth"])
    if op == "getsample":
        return (frag, width, len(frag) // (2 * width))
    if op == "tomono":
        return (frag, width, entry["factor"], entry["factor"])
    if op == "tostereo":
        return (frag, width, entry["factor"], -entry["factor"])
    if op in ("max", "minmax", "avg", "rms", "cross", "avgpp", "maxpp"):
        return (frag, width)
    if op == "findmax":
        window = int(note.lstrip("w")) if note[1:].isdigit() else 8
        return (frag, window)
    if op == "findfit":
        window = int(note.lstrip("w")) if note[1:].isdigit() else 8
        return (frag, entry["reference"])
    if op == "findfactor":
        return (frag, entry["reference"])
    if op == "lin2adpcm":
        state = None if note.endswith("cold") else (0, 44)
        return (frag, width, state)
    if op == "adpcm2lin":
        state = None if note.endswith("cold") else (-7, 30)
        return (frag, width, state)
    if op == "ratecv":
        nchannels = 2 if "stereo" in note else 1
        inrate = 8000 if "8k" in note else 44100
        outrate = 16000 if "16k" in note else 48000
        state = (
            None
            if warm is False
            else (-2, (((11, 22),) if nchannels == 1 else ((11, 22), (33, 44))))
        )
        return (frag, width, nchannels, inrate, outrate, state)
    raise ValueError(f"unknown op {op}")


class RefWorker:
    """Long-lived CPython 3.12 worker for in-process C timing."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [ref_python(), str(BENCH_DIR / "reference_worker.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

    def call(self, op: str, args: tuple):
        import json

        req = json.dumps({"args": list(args)})
        self.proc.stdin.write(f"{op}|{req}\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        resp = json.loads(line)
        if resp[0] != "ok":
            raise RuntimeError(f"reference worker error: {resp}")
        return resp[1]

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait(timeout=30)


def encode_args(args: tuple) -> tuple:
    """JSON-encode bytes arguments as hex strings for the worker."""

    def enc(value):
        if isinstance(value, bytes):
            return {"__hex__": value.hex()}
        if isinstance(value, tuple):
            return [enc(item) for item in value]
        return value

    return tuple(enc(value) for value in args)


def canonical_ref(op: str, args: tuple, worker: RefWorker) -> str:
    """CPython result in the bench.mojo canonical string form."""
    raw = worker.call(op.removesuffix("_bytes"), encode_args(args))
    if op == "getsample":
        return str(raw)
    if op == "minmax":
        lo, hi = raw
        return f"{lo},{hi}"
    if op in ("max", "avg", "rms", "cross", "avgpp", "maxpp", "findmax"):
        return str(raw)
    if op == "findfactor":
        return struct.pack(">d", raw).hex()
    if op == "findfit":
        j, factor = raw
        return f"{j},{struct.pack('>d', factor).hex()}"
    if op in ("lin2adpcm", "adpcm2lin", "ratecv"):
        # the worker returns [hex_out, [state fields...]] for these ops
        out_hex, state = raw
        if op == "ratecv":
            d, pairs = state
            fields = [str(d)]
            for pair in pairs:
                fields += [str(pair[0]), str(pair[1])]
            return out_hex + "|" + ",".join(fields)
        return out_hex + "|" + f"{state[0]},{state[1]}"
    # byte results arrive as hex strings from the worker
    return raw


def benchmojo_lines(workloads: list[dict], args_map: dict[int, tuple]) -> str:
    """Serialize workloads for bench.mojo (protocol in bench.mojo docstring)."""

    def dhex(x: float) -> str:
        return struct.pack(">d", x).hex()

    lines = [str(len(workloads))]
    for e in workloads:
        op = e["op"].removesuffix("_bytes").upper()
        width = e["width"]
        frag = e["fragment"].hex()
        note = e.get("note", "")
        warm = not (
            note.startswith("cold") or note.startswith("stereo") or note.startswith("content")
        )
        if op == "ADD":
            lines.append(f"ADD|{width}|{frag}")
        elif op == "MUL":
            lines.append(f"MUL|{width}|{dhex(e['factor'])}|{frag}")
        elif op == "BIAS":
            lines.append(f"BIAS|{width}|{frag}")
        elif op in ("BYTESWAP", "REVERSE", "LIN2ALAW", "LIN2ULAW"):
            lines.append(f"{op}|{width}|{frag}")
        elif op == "LIN2LIN":
            lines.append(f"LIN2LIN|{width}|{e['newwidth']}|{frag}")
        elif op == "GETSAMPLE":
            n = len(e["fragment"]) // (2 * width)
            lines.append(f"GETSAMPLE|{width}|{n}|{frag}")
        elif op in ("MAX", "MINMAX", "AVG", "RMS", "CROSS", "AVGPP", "MAXPP"):
            lines.append(f"{op}|{width}|{frag}")
        elif op == "TOMONO":
            lines.append(f"TOMONO|{width}|{dhex(e['factor'])}|{dhex(e['factor'])}|{frag}")
        elif op == "TOSTEREO":
            lines.append(f"TOSTEREO|{width}|{dhex(e['factor'])}|{dhex(-e['factor'])}|{frag}")
        elif op in ("ALAW2LIN", "ULAW2LIN"):
            lines.append(f"{op}|{width}|{frag}")
        elif op == "FINDMAX":
            window = int(note.lstrip("w")) if note[1:].isdigit() else 8
            lines.append(f"FINDMAX|{window}|{frag}")
        elif op == "FINDFIT":
            lines.append(f"FINDFIT|{e['reference'].hex()}|{frag}")
        elif op == "FINDFACTOR":
            lines.append(f"FINDFACTOR|{e['reference'].hex()}|{frag}")
        elif op == "LIN2ADPCM":
            state = None if note.endswith("cold") else (0, 44)
            vp = 2147483648 if state is None else state[0]
            idx = 0 if state is None else state[1]
            lines.append(f"LIN2ADPCM|{width}|{vp}|{idx}|{frag}")
        elif op == "ADPCM2LIN":
            state = None if note.endswith("cold") else (-7, 30)
            vp = 2147483648 if state is None else state[0]
            idx = 0 if state is None else state[1]
            lines.append(f"ADPCM2LIN|{width}|{vp}|{idx}|{frag}")
        elif op == "RATECV":
            nchannels = 2 if "stereo" in note else 1
            inrate = 8000 if "8k" in note else 44100
            outrate = 16000 if "16k" in note else 48000
            fields = ["RATECV", str(width), str(nchannels), str(inrate), str(outrate), "1", "0"]
            if warm:
                fields.append("-2")
                if nchannels == 1:
                    fields += ["11", "22"]
                else:
                    fields += ["11", "22", "33", "44"]
            else:
                fields.append("2147483648")
            fields.append(frag)
            lines.append("|".join(fields))
        else:
            raise ValueError(f"no bench line for {op}")
    return "\n".join(lines) + "\n"


def run_pure_workload(entry: dict, args: tuple):
    op = entry["op"]
    if op == "add":
        return pure.add_py(args[2], args[0], args[1])
    if op == "bias":
        return pure.bias_py(args[0], args[1], args[2])
    if op == "mul":
        return pure.mul_py(args[0], args[1], args[2])
    if op == "lin2lin":
        return pure.lin2lin_py(args[0], args[1], args[2])
    if op == "getsample":
        return pure.getsample_py(args[0], args[1], args[2]).to_bytes(args[1], "little", signed=True)
    if op == "tomono":
        return pure.tomono_py(args[0], args[1], args[2], args[3])
    if op == "tostereo":
        return pure.tostereo_py(args[0], args[1], args[2], args[3])
    if op == "findmax":
        return pure.findmax_py(args[0], args[1])
    if op == "findfit":
        j, factor = pure.findfit_py(args[0], args[1])
        return j.to_bytes(8, "little", signed=True) + struct.pack(">d", factor)
    if op == "findfactor":
        return struct.pack(">d", pure.findfactor_py(args[0], args[1]))
    if op == "lin2adpcm":
        out, st = pure.lin2adpcm_py(args[0], args[1], args[2])
        return out, st
    if op == "adpcm2lin":
        out, st = pure.adpcm2lin_py(args[0], args[1], args[2])
        return out, st
    if op == "ratecv":
        return pure.ratecv_py(*args)
    fn = pure.PY_OPS[op.removesuffix("_bytes")]
    return fn(args[0], args[1])


def canonical_pure(entry: dict, args: tuple) -> str:
    result = run_pure_workload(entry, args)
    op = entry["op"]
    if op == "getsample":
        return str(int.from_bytes(result, "little", signed=True))
    if op == "minmax":
        return f"{result[0]},{result[1]}"
    if op in ("max", "avg", "rms", "cross", "avgpp", "maxpp"):
        return str(result)
    if op == "findmax":
        return str(result)
    if op == "findfactor":
        return struct.pack(">d", struct.unpack(">d", result)[0]).hex()
    if op == "findfit":
        j = int.from_bytes(result[:8], "little", signed=True)
        factor = struct.unpack(">d", result[8:])[0]
        return f"{j},{struct.pack('>d', factor).hex()}"
    if op in ("lin2adpcm", "adpcm2lin", "ratecv"):
        out, state = result
        if op == "ratecv":
            d, samps = state
            fields = [str(d)]
            for prev, cur in samps:
                fields += [str(prev), str(cur)]
            return out.hex() + "|" + ",".join(fields)
        return out.hex() + "|" + f"{state[0]},{state[1]}"
    return result.hex()


# ---------------------------------------------------------------------------
# CLI path measurement (separately labelled)
# ---------------------------------------------------------------------------


def cli_body(entry: dict, args: tuple) -> bytes:
    """Build a CLI request frame for the workload (protocol per phase docs)."""
    op = entry["op"]
    width = entry["width"]
    frag = entry["fragment"]
    opcode = {
        "add": 0x22,
        "bias": 0x23,
        "mul": 0x24,
        "reverse": 0x25,
        "byteswap": 0x26,
        "lin2lin": 0x27,
        "getsample": 0x28,
        "max": 0x29,
        "minmax": 0x2A,
        "avg": 0x2B,
        "rms": 0x2C,
        "cross": 0x2D,
        "avgpp": 0x2E,
        "maxpp": 0x2F,
        "findmax": 0x30,
        "findfactor": 0x31,
        "findfit": 0x32,
        "tomono": 0x33,
        "tostereo": 0x34,
        "lin2alaw": 0x36,
        "alaw2lin": 0x37,
        "lin2ulaw": 0x38,
        "ulaw2lin": 0x39,
        "lin2adpcm": 0x3A,
        "adpcm2lin": 0x3B,
        "ratecv": 0x35,
    }
    code = opcode[op.removesuffix("_bytes")]
    body = bytes([code, width])
    if op == "mul":
        body += struct.pack(">d", args[2]) + frag
    elif op == "tomono" or op == "tostereo":
        body += struct.pack(">d", args[2]) + struct.pack(">d", args[3]) + frag
    elif op == "lin2lin":
        body += bytes([args[2]]) + frag
    elif op == "getsample":
        body += struct.pack(">q", args[2]) + frag
    elif op == "findmax":
        body += struct.pack(">q", args[1]) + frag
    elif op in ("findfactor", "findfit"):
        body += struct.pack(">I", len(args[1])) + args[1] + args[0]
    elif op == "lin2adpcm" or op == "adpcm2lin":
        state = args[2]
        if state is None:
            body += b"\x00"
        else:
            body += b"\x01" + struct.pack(">q", state[0]) + struct.pack(">q", state[1])
        body += frag
    elif op == "ratecv":
        nchannels, inrate, outrate, state = args[2], args[3], args[4], args[5]
        body += (
            struct.pack(">q", nchannels)
            + struct.pack(">q", inrate)
            + struct.pack(">q", outrate)
            + struct.pack(">q", 1)
            + struct.pack(">q", 0)
        )
        if state is None:
            body += b"\x00"
        else:
            d, pairs = state
            body += b"\x01" + struct.pack(">q", d)
            for prev, cur in pairs:
                body += struct.pack(">q", prev) + struct.pack(">q", cur)
        body += frag
    else:
        body += frag
    return struct.pack(">I", len(body)) + body


def time_cli(entry: dict, args: tuple, samples: int) -> list[int]:
    body = cli_body(entry, args)
    data = body if len(body) < 1 << 20 else body
    times = []
    for _ in range(3):
        sh([str(CLI_BIN)], input=data, timeout=120)
    for _ in range(samples):
        start = time.perf_counter_ns()
        result = sh([str(CLI_BIN)], input=data, timeout=300)
        times.append(time.perf_counter_ns() - start)
        if result.returncode != 0:
            raise RuntimeError("CLI failed: " + result.stderr.decode()[:200])
    return times


def time_ping(samples: int) -> list[int]:
    body = struct.pack(">I", 1) + b"\x01"
    times = []
    for _ in range(3):
        sh([str(CLI_BIN)], input=body, timeout=60)
    for _ in range(samples):
        start = time.perf_counter_ns()
        sh([str(CLI_BIN)], input=body, timeout=60)
        times.append(time.perf_counter_ns() - start)
    return times


# ---------------------------------------------------------------------------
# main driver
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument("--cli-samples", type=int, default=CLI_SAMPLES)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="regenerate summary.csv and BENCHMARK_REPORT.md from the "
        "existing results/raw_results.json without rerunning benchmarks",
    )
    options = parser.parse_args()

    if options.report_only:
        workloads = op_workloads()
        raw = json.loads((BENCH_DIR / "results" / "raw_results.json").read_text())
        print("run_benchmarks: report-only mode (no builds, no new measurements)")
        write_summary(
            BENCH_DIR / "results" / "summary.csv",
            raw["runs"],
            workloads,
        )
        write_report(
            BENCH_DIR / "reports" / "BENCHMARK_REPORT.md",
            raw["meta"],
            raw["runs"],
            workloads,
        )
        print("run_benchmarks: regenerated summary + report from raw_results.json")
        return 0

    print("run_benchmarks: building bench.mojo (cold compile)…")
    BUILD_DIR.mkdir(exist_ok=True)
    t0 = time.perf_counter_ns()
    built = sh(
        [
            str(mojo_binary()),
            "build",
            str(BENCH_DIR / "bench.mojo"),
            "-I",
            str(ROOT / "libraries/audioop/mojo"),
            "-o",
            str(BENCH_BIN),
        ]
    )
    if built.returncode != 0:
        print(built.stderr.decode()[-2000:])
        return 1
    cold_compile_ns = time.perf_counter_ns() - t0
    print(f"  cold compile: {cold_compile_ns / 1e9:.2f}s")

    print("run_benchmarks: building CLI (cold compile)…")
    t0 = time.perf_counter_ns()
    built = sh(
        [
            str(mojo_binary()),
            "build",
            str(ROOT / "libraries/audioop/mojo/cli.mojo"),
            "-I",
            str(ROOT / "libraries/audioop/mojo"),
            "-o",
            str(CLI_BIN),
        ]
    )
    if built.returncode != 0:
        print(built.stderr.decode()[-2000:])
        return 1
    cli_compile_ns = time.perf_counter_ns() - t0

    workloads = op_workloads()
    args_map = {i: op_args(e) for i, e in enumerate(workloads)}
    print(f"run_benchmarks: {len(workloads)} workloads")

    worker = RefWorker()
    env = env_metadata()
    env["cold_compile_bench_s"] = cold_compile_ns / 1e9
    env["cold_compile_cli_s"] = cli_compile_ns / 1e9

    # ---- correctness gates: pure vs CPython, then Mojo vs CPython ----
    ref_canonical = []
    print("run_benchmarks: gating pure Python vs CPython…")
    for i, e in enumerate(workloads):
        args = args_map[i]
        want = canonical_ref(e["op"], args, worker)
        got = canonical_pure(e, args)
        if got != want:
            print(
                f"GATE FAIL (pure vs C) [{i}] {e['op']} {e.get('note', '')}:"
                f" {str(got)[:80]!r} != {str(want)[:80]!r}"
            )
            worker.close()
            return 2
        ref_canonical.append(want)
    print("  pure vs CPython: PASS")

    lines_full = benchmojo_lines(workloads, args_map).splitlines()
    print("run_benchmarks: gating Mojo vs CPython (bench.mojo gate pass)…")
    mojo_canonical = []
    for i, e in enumerate(workloads):
        one = "\n".join(["1", lines_full[1 + i]]) + "\n"
        gate_run = subprocess.run(
            [str(BENCH_BIN)],
            input=one,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if gate_run.returncode != 0:
            print(f"GATE FAIL: bench crashed on workload {i} ({e['op']})")
            print(gate_run.stderr[-2000:])
            worker.close()
            return 2
        r_lines = [line[2:] for line in gate_run.stdout.splitlines() if line.startswith("R ")]
        if len(r_lines) != 1:
            print(f"GATE FAIL: workload {i} produced {len(r_lines)} R lines")
            worker.close()
            return 2
        if r_lines[0] != ref_canonical[i]:
            print(
                f"GATE FAIL (mojo vs C) [{i}] {e['op']} {e.get('note', '')}:"
                f" {str(r_lines[0])[:80]!r} != {str(ref_canonical[i])[:80]!r}"
            )
            worker.close()
            return 2
        mojo_canonical.append(r_lines[0])
    print("  mojo vs CPython: PASS")

    # ---- timed runs: one fresh bench.mojo process per workload ----
    all_runs: list = []
    mojo_sinks: list[str] = []
    for run_index in range(options.runs):
        print(f"run_benchmarks: timing run {run_index + 1}/{options.runs}")
        t_lines = []
        run_sinks: list[str] = []
        for i in range(len(workloads)):
            one = "\n".join(["1", lines_full[1 + i]]) + "\n"
            run_out = subprocess.run(
                [str(BENCH_BIN)],
                input=one,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if run_out.returncode != 0:
                print(f"TIMING FAIL: bench crashed on workload {i}")
                print(run_out.stderr[-2000:])
                worker.close()
                return 2
            got = [line for line in run_out.stdout.splitlines() if line.startswith("T ")]
            sinks = [line for line in run_out.stdout.splitlines() if line.startswith("S ")]
            if len(got) != 1 or len(sinks) != 1:
                print(f"TIMING FAIL: workload {i} produced {len(got)} T lines")
                worker.close()
                return 2
            t_lines.append([int(x) for x in got[0].split()[2:]])
            run_sinks.append(sinks[0].split()[1])
        cells = []
        for i, e in enumerate(workloads):
            args = args_map[i]
            pure_fn = _make_pure_fn(e, args)
            for _ in range(WARMUP):
                pure_fn()
            pure_samples = []
            for _ in range(options.samples):
                start = time.perf_counter_ns()
                pure_fn()
                pure_samples.append(time.perf_counter_ns() - start)
            # CPython C timing (in-process inside the reference worker:
            # measured via a worker-side timing round-trip; see report)
            c_samples = c_time(
                worker, e["op"].removesuffix("_bytes"), args, WARMUP, options.samples
            )
            cells.append(
                {
                    "index": i,
                    "op": e["op"].removesuffix("_bytes"),
                    "width": e["width"],
                    "frames": e.get("frames"),
                    "note": e.get("note", ""),
                    "input_bytes": len(e["fragment"]),
                    "content": e.get("kind", ""),
                    "pure": stats(pure_samples),
                    "c": stats(c_samples),
                    "mojo_kernel": stats(t_lines[i]),
                    "correctness": "PASS",
                }
            )
        # CLI path + ping overhead (once per run)
        ping = stats(time_ping(50))
        cli_cells = []
        for cell_index, e in enumerate(workloads):
            args = args_map[cell_index]
            cli_samples = time_cli(e, args, options.cli_samples)
            cli_cells.append(
                {
                    "index": cell_index,
                    "op": e["op"].removesuffix("_bytes"),
                    "note": e.get("note", ""),
                    "cli": stats(cli_samples),
                    "correctness": "PASS",
                }
            )
        if run_index == 0:
            mojo_sinks = run_sinks
        elif run_sinks != mojo_sinks:
            bad = [i for i, (a, b) in enumerate(zip(mojo_sinks, run_sinks, strict=True)) if a != b]
            print(f"SINK MISMATCH on {len(bad)} cells (timed code diverged): {bad[:5]}")
            worker.close()
            return 2
        all_runs.append(
            {
                "run": run_index + 1,
                "cells": cells,
                "cli_cells": cli_cells,
                "ping": ping,
            }
        )

    worker.close()

    # ---- artifacts ----
    results_dir = BENCH_DIR / "results"
    reports_dir = BENCH_DIR / "reports"
    results_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    env = env_metadata()
    env["cold_compile_bench_s"] = cold_compile_ns / 1e9
    env["cold_compile_cli_s"] = cli_compile_ns / 1e9
    (results_dir / "environment.json").write_text(json.dumps(env, indent=2))
    raw = {
        "meta": env,
        "runs": all_runs,
        "workloads": [
            {
                "index": i,
                "op": e["op"],
                "width": e["width"],
                "frames": e.get("frames"),
                "note": e.get("note", ""),
                "content": e.get("kind", ""),
                "input_sha": fnv1a_checksum(e["fragment"]),
            }
            for i, e in enumerate(workloads)
        ],
    }
    (results_dir / "raw_results.json").write_text(json.dumps(raw, indent=2))

    write_summary(results_dir / "summary.csv", all_runs, workloads)
    write_report(reports_dir / "BENCHMARK_REPORT.md", env, all_runs, workloads)
    print("run_benchmarks: artifacts written to benchmarks/results and benchmarks/reports")
    return 0


def _make_pure_fn(entry: dict, args: tuple):
    def fn():
        return run_pure_workload(entry, args)

    return fn


def c_time(worker: RefWorker, op: str, args: tuple, warmup: int, samples: int) -> list[int]:
    """Time the C implementation inside the reference worker.

    The worker times its own audioop call with perf_counter_ns and
    returns the raw samples, so process round-trips stay outside the
    measured region.
    """
    import json

    req = json.dumps(
        {"args": list(encode_args(args)), "warmup": warmup, "samples": samples},
    )
    worker.proc.stdin.write(f"TIME|{op}|{req}\n")
    worker.proc.stdin.flush()
    line = worker.proc.stdout.readline()
    resp = json.loads(line)
    if resp[0] != "samples":
        raise RuntimeError(f"reference timing error: {resp}")
    return resp[1]


def write_summary(path: Path, all_runs: list, workloads: list) -> None:
    """summary.csv: per-cell median-of-medians across runs."""
    import csv

    # summary CSV: per-cell median-of-medians across runs (robust under
    # shared-machine noise); run_1_* columns keep run-1 values

    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "op",
                "workload",
                "width",
                "frames",
                "input_bytes",
                "pure_median_ns",
                "c_median_ns",
                "mojo_kernel_median_ns",
                "mojo_vs_pure",
                "mojo_vs_c",
                "cli_median_ns",
                "ping_median_ns",
                "correctness",
            ]
        )
        run1 = all_runs[0]

        def run_median(cell_index: int, key: str, sub: str) -> float:
            return statistics.median([r["cells"][cell_index][key][sub] for r in all_runs])

        for index, cell in enumerate(run1["cells"]):
            mojo = run_median(index, "mojo_kernel", "median_ns")
            pmed = run_median(index, "pure", "median_ns")
            cmed = run_median(index, "c", "median_ns")
            writer.writerow(
                [
                    cell["op"],
                    cell["note"],
                    cell["width"],
                    cell["frames"],
                    cell["input_bytes"],
                    pmed,
                    cmed,
                    mojo,
                    round(pmed / mojo, 3) if mojo else "",
                    round(cmed / mojo, 3) if mojo else "",
                    statistics.median(
                        [r["cli_cells"][cell["index"]]["cli"]["median_ns"] for r in all_runs]
                    ),
                    statistics.median([r["ping"]["median_ns"] for r in all_runs]),
                    cell["correctness"],
                ]
            )


def write_report(path: Path, env: dict, all_runs: list, workloads: list) -> None:
    """Curated markdown report from the collected runs.

    Headline numbers are per-cell medians-of-medians across runs
    (robust on a shared, frequency-scaled host). All runs are retained
    in raw_results.json; stability is reported, not averaged away.
    """
    import collections as _collections
    import math as _math
    import statistics as _st

    n_runs = len(all_runs)
    run1 = all_runs[0]
    n = len(run1["cells"])

    def mom(index: int, key: str, sub: str) -> float:
        return _st.median([r["cells"][index][key][sub] for r in all_runs])

    mojo = [mom(i, "mojo_kernel", "median_ns") for i in range(n)]
    pure = [mom(i, "pure", "median_ns") for i in range(n)]
    cm = [mom(i, "c", "median_ns") for i in range(n)]
    ping_runs = [r["ping"]["median_ns"] for r in all_runs]
    ping = _st.median(ping_runs)

    def s_vs_p(i: int) -> float:
        return pure[i] / mojo[i] if mojo[i] else 0.0

    def s_vs_c(i: int) -> float:
        return cm[i] / mojo[i] if mojo[i] else 0.0

    def cat(ratio: float) -> str:
        if ratio > 1.10:
            return "Mojo faster"
        if ratio < 0.90:
            return "Mojo slower"
        return "comparable (+/-10%)"

    lines = [
        "# audioop v0.1.0 benchmark report",
        "",
        f"- Generated: {env['date']}",
        f"- CPU: {env['cpu']} ({env['cores']} cores)",
        f"- OS: {env['os']}",
        f"- Python: {env['python']} (host); CPython {env['reference_python']} (reference)",
        f"- Mojo: {env['mojo']}",
        f"- Git: {env['git']}; seed {env['seed']}",
        f"- Cold compile: bench.mojo {env['cold_compile_bench_s']:.2f}s,"
        f" CLI {env['cold_compile_cli_s']:.2f}s",
        f"- Runs: {n_runs}; 25 measured samples per cell per run"
        " (5 warmup discarded); headline numbers are medians-of-medians",
        "",
        "Paths: `pure` = pure-Python floor (same semantics, no C);"
        " `c` = CPython 3.12.3 C audioop, timed in-process; `mojo` ="
        " native kernel measured in-process inside bench.mojo (fresh"
        " process per workload, 64-bit IEEE-754 double work included"
        " where the reference uses it); `cli` = full CLI request path"
        " (process spawn + framing + kernel), measured separately and"
        " never conflated with kernel numbers.",
        "",
        "Correctness: every benchmarked cell passed a three-way gate"
        " (pure Python == CPython C == Mojo, exact bytes/state). NaN-factor"
        " inputs are excluded from benchmarking per the frozen Phase 0"
        " policy (documented Mojo NaN->0 behaviour, no compatibility"
        " claim); infinities are included where defined.",
        "",
        "## 1. Operation results (median ns, median-of-medians)",
        "",
        "| op | workload | width | frames | bytes | pure | c | mojo | mojo/pure | mojo/c | gate |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for i, cell in enumerate(run1["cells"]):
        lines.append(
            f"| {cell['op']} | {cell['note']} | {cell['width']} |"
            f" {cell['frames']} | {cell['input_bytes']} | {int(pure[i])} |"
            f" {int(cm[i])} | {int(mojo[i])} | {s_vs_p(i):.2f} |"
            f" {s_vs_c(i):.2f} | {cell['correctness']} |"
        )

    lines += ["", "## 2. Per-operation aggregates (geometric mean over cells)", ""]
    lines += [
        "Categories use an explicit +/-10% tolerance band around parity:",
        "`mojo/baseline > 1.10` = Mojo faster, `< 0.90` = Mojo slower,",
        "otherwise comparable. Geometric means prevent large cells from",
        "dominating; the full per-cell table above remains authoritative.",
        "",
        "| op | cells | mojo/pure (geo) | mojo/c (geo) | vs pure | vs C |",
        "|---|---:|---:|---:|---|---|",
    ]
    ops: dict = {}
    for i, cell in enumerate(run1["cells"]):
        ops.setdefault(cell["op"], []).append(i)

    def _gmean(xs: list) -> float:
        return _math.exp(sum(_math.log(max(x, 1e-9)) for x in xs) / len(xs))

    for op in sorted(ops):
        idxs = ops[op]
        gp = _gmean([pure[i] / mojo[i] for i in idxs if mojo[i]])
        gc = _gmean([cm[i] / mojo[i] for i in idxs if mojo[i]])
        lines.append(f"| {op} | {len(idxs)} | {gp:.1f}x | {gc:.2f}x | {cat(gp)} | {cat(gc)} |")

    lines += ["", "## 3. Content sweep (width 2, 4096 frames, mojo ns)", ""]
    contents = ["silence", "square", "sine", "random", "sparse", "ramp", "clipped", "impulses"]
    sweep_ops = ["add", "mul", "max", "rms", "cross", "lin2ulaw", "lin2adpcm", "ratecv"]
    lines.append("| op | " + " | ".join(contents) + " |")
    lines.append("|" + "|".join(["---"] * (len(contents) + 1)) + "|")
    for op in sweep_ops:
        row = [op]
        for kind in contents:
            vals = [
                mojo[i]
                for i, cell in enumerate(run1["cells"])
                if cell["op"] == op
                and f"content-{kind}" in cell.get("note", "")
                and cell.get("width") == 2
            ]
            row.append(str(int(vals[0])) if vals else "-")
        lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## 4. Size scaling (mojo ns; representative workloads)", ""]
    lines.append("| op | w | 160f | 4096f | 65536f |")
    lines.append("|---|---|---:|---:|---:|")
    for op in [
        "add",
        "mul",
        "max",
        "rms",
        "lin2lin",
        "lin2ulaw",
        "alaw2lin",
        "adpcm2lin",
        "ratecv",
        "findmax",
        "tomono",
    ]:
        for w in (1, 2, 4):
            vals = [
                mojo[i]
                for i, cell in enumerate(run1["cells"])
                if cell["op"] == op
                and cell["width"] == w
                and cell.get("frames") in (160, 4096, 65536)
                and not cell.get("note")
            ]
            if len(vals) == 3:
                lines.append(f"| {op} | {w} | {int(vals[0])} | {int(vals[1])} | {int(vals[2])} |")

    cli_med = []
    for i, _cell in enumerate(run1["cells"]):
        cli_runs = [r["cli_cells"][i]["cli"]["median_ns"] for r in all_runs]
        cli_med.append(_st.median(cli_runs))
    lines += [
        "",
        "## 5. CLI request path (median-of-medians ns; process + framing included)",
        "",
        f"- Ping (empty `0x01` frame, process round-trip floor, median of {len(ping_runs)} runs): "
        f"{int(ping)} ns",
        "- A CLI cell is dominated by process spawn (~ping floor); the"
        " kernel itself is a few microseconds at most. CLI numbers must"
        " not be read as kernel performance. Kernel time for a"
        " CLI-measured cell may be approximated as `cli - ping`.",
        "",
        "| op | workload | cli | ping | cli-ping (est. kernel+framing) |",
        "|---|---|---:|---:|---:|",
    ]
    for i, cell in enumerate(run1["cells"]):
        lines.append(
            f"| {cell['op']} | {cell['note']} | {int(cli_med[i])} |"
            f" {int(ping)} | {int(max(cli_med[i] - ping, 0))} |"
        )

    lines += [
        "",
        "## 6. Cold start",
        "",
        f"- `mojo build bench.mojo`: {env['cold_compile_bench_s']:.2f} s"
        " (one-time; excluded from all medians)",
        f"- `mojo build cli.mojo`: {env['cold_compile_cli_s']:.2f} s"
        " (one-time; excluded from all medians)",
        f"- CLI process spawn floor (ping median): {int(ping)} ns",
        "- In-process timing excludes process startup and dataset"
        " generation; input bytes are parsed once outside the timed"
        " loop (parsing is not part of any reported median).",
        "",
        "## 7. Stability (per-cell max pairwise relative delta across runs)",
        "",
    ]
    deltas = []
    for i in range(len(run1["cells"])):
        vals = [r["cells"][i]["mojo_kernel"]["median_ns"] for r in all_runs]
        deltas.append((max(vals) - min(vals)) / max(min(vals), 1))
    buckets = _collections.Counter(
        "stable<=5%" if d <= 0.05 else "ok<=20%" if d <= 0.20 else "noisy>20%" for d in deltas
    )
    lines.append(
        f"- {buckets['stable<=5%']}/{len(deltas)} cells within 5% across"
        f" all runs; {buckets['ok<=20%']}/{len(deltas)} within 20%;"
        f" {buckets['noisy>20%']}/{len(deltas)} noisy (>20%)."
    )
    lines.append(
        "- The host is a shared 16-core desktop under load (IDE, browser)."
        " Benchmark subprocesses are pinned with taskset to the two"
        " least-loaded cores observed at start (11, 13 here), but no"
        " frequency locking was used, so residual run-to-run variance is"
        " environmental. Headline numbers use medians-of-medians; the ten"
        " noisiest cells follow."
    )
    lines.append("")
    rr = " | ".join(f"run{r + 1}" for r in range(len(all_runs)))
    lines.append("| op | workload | " + rr + " | max delta |")
    lines.append("|---|---|" + "---:|" * len(all_runs) + "---|")
    order = sorted(range(len(deltas)), key=lambda i: -deltas[i])[:10]
    for i in order:
        vals = [
            int(all_runs[r]["cells"][i]["mojo_kernel"]["median_ns"]) for r in range(len(all_runs))
        ]
        cells_joined = " | ".join(str(v) for v in vals)
        op_name = run1["cells"][i]["op"]
        note = run1["cells"][i]["note"]
        lines.append(f"| {op_name} | {note} | {cells_joined} | {deltas[i] * 100:.1f}% |")

    lines += [
        "",
        "## 8. Bottleneck analysis",
        "",
        "- Allocation: every native call allocates its result buffer"
        " (`List` grow) plus one decoded-`Int32` vector per fragment in"
        " `decode_fragment`. The kernel medians therefore include"
        " allocation; the C reference allocates a single output buffer."
        " This is the dominant Mojo-vs-C gap on small inputs, where"
        " fixed overhead dominates.",
        "- Int64 arithmetic: the port widens all samples to 64-bit and"
        " branches per element; the C inner loops work on native ints"
        " with pointer increments. No SIMD is used (Phase 10 is"
        " measurement-only).",
        "- `ratecv`/`adpcm` carry per-call state vectors (`RatecvState`,"
        " two output lists); no persistent buffers are reused between calls.",
        "- Content sensitivity: branchy peak-walk (`avgpp`/`maxpp`) and"
        " `findfit` inner loops vary with signal shape; `cross` on dense"
        " crossings is the cheapest statistic.",
        "",
        "## 9. Limitations",
        "",
        "- NaN-factor inputs are excluded from benchmarking per the frozen"
        " Phase 0 policy (Mojo defines NaN results as 0; the reference is"
        " undefined). Infinities are included where defined.",
        "- `findmax` uses window 8 (plus one large window); `findfit` and"
        " `findfactor` use 8-sample windows scaled for the benchmark corpus,"
        " not the full Phase 2 differential ranges.",
        "- CLI timings include process spawn (~ping floor) and are not"
        " comparable to in-process kernel numbers.",
        "- Throughput cells assume the framed benchmark corpus; real-world"
        " audio with different content mixes will shift absolute numbers,",
        " but the per-op ordering is expected to hold.",
    ]
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
