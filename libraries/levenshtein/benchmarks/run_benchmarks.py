#!/usr/bin/env python3
"""Three-way Levenshtein benchmark driver: naive Python vs RapidFuzz
pure-Python fallback vs RapidFuzz C++ vs native Mojo.

One command from the repository root::

    .venv/bin/python libraries/levenshtein/benchmarks/run_benchmarks.py

Methodology: string pairs are generated once (fixed seed) and shared by
all paths. Python timing uses ``time.perf_counter_ns`` around pure calls
with warmup and repeated samples. Native timing is measured in-process
by ``bench.mojo`` (built once; build time is reported separately as cold
compilation) and excludes stdin framing, process startup, and IPC. Full
correctness checks (exact integers, bit-exact float64 ratio) run outside
every timed region. Raw samples plus environment metadata go to a
``*.bench.json`` report (git-ignored); median tables print to stdout for
the curated release summary.

Implementation labels, used consistently everywhere:

- ``naive`` — local pure-Python two-row dynamic programming (the honest
  algorithmic floor; NOT the RapidFuzz fallback).
- ``py`` — ``rapidfuzz.distance.*_py`` pure-Python fallback
  (bit-parallel over big ints; algorithmic parity with C++).
- ``cpp`` — ``rapidfuzz.distance`` optimized C++ (the ceiling).
- ``mojo`` — native production entry points.
- ``mojo_dp`` / ``mojo_myers`` — internal Mojo algorithms, timed
  separately for the DP-vs-Myers comparison.
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

from rapidfuzz.distance import Hamming, Hamming_py, Indel, Indel_py, Levenshtein, Levenshtein_py

ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
BENCH_BIN = BUILD_DIR / "bench_levenshtein"
CLI_BIN = BUILD_DIR / "levenshtein_cli_bench"

sys.path.insert(0, str(BENCH_DIR))

from workloads import build_workloads, workload_meta  # noqa: E402


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
    import rapidfuzz

    return {
        "python": sys.version.split()[0],
        "rapidfuzz": rapidfuzz.__version__,
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


# ---------------------------------------------------------------------------
# Naive pure-Python baselines (the floor, not the RapidFuzz fallback).
# ---------------------------------------------------------------------------


def naive_distance(s1: str, s2: str) -> int:
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, start=1):
        cur = [i] + [0] * len(s2)
        for j, c2 in enumerate(s2, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (c1 != c2))
        prev = cur
    return prev[-1]


def naive_lcs(s1: str, s2: str) -> int:
    if not s1 or not s2:
        return 0
    prev = [0] * (len(s2) + 1)
    for c1 in s1:
        cur = [0] * (len(s2) + 1)
        for j, c2 in enumerate(s2, start=1):
            if c1 == c2:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = prev[j] if prev[j] >= cur[j - 1] else cur[j - 1]
        prev = cur
    return prev[-1]


def naive_ratio(s1: str, s2: str) -> float:
    total = len(s1) + len(s2)
    if total == 0:
        return 1.0
    return 1.0 - (total - 2 * naive_lcs(s1, s2)) / total


def naive_hamming(s1: str, s2: str, pad: bool = True) -> int:
    if len(s1) != len(s2) and not pad:
        raise ValueError("Sequences are not the same length.")
    edits = abs(len(s1) - len(s2)) if pad else 0
    for c1, c2 in zip(s1, s2, strict=False):
        if c1 != c2:
            edits += 1
    return edits


def time_op(
    fn, args: tuple, warmup: int, samples: int, kwargs: dict | None = None
) -> tuple[list[int], object]:
    kwargs = kwargs or {}
    for _ in range(warmup):
        fn(*args, **kwargs)
    out = []
    result = None
    for _ in range(samples):
        start = time.perf_counter_ns()
        result = fn(*args, **kwargs)
        out.append(time.perf_counter_ns() - start)
    return out, result


def stats(samples: list[int]) -> dict:
    ordered = sorted(samples)
    median = statistics.median(ordered)
    ops = 1e9 / median if median > 0 else 0.0
    return {
        "samples": len(ordered),
        "min_ns": ordered[0],
        "median_ns": median,
        "max_ns": ordered[-1],
        "ops_per_s": ops,
    }


def frame(s1: str, s2: str) -> bytes:
    b1 = s1.encode("utf-8")
    b2 = s2.encode("utf-8")
    body = struct.pack(">I", len(b1)) + b1 + struct.pack(">I", len(b2)) + b2
    return struct.pack(">I", len(body)) + body


def run_mojo(op: str, s1: str, s2: str, warmup: int, samples: int) -> dict:
    result = sh([str(BENCH_BIN), op, str(warmup), str(samples)], input=frame(s1, s2))
    if result.returncode != 0:
        raise SystemExit(f"bench_levenshtein {op} failed: {result.stderr.decode()[:500]!r}")
    if result.stderr:
        raise SystemExit(f"bench_levenshtein {op} wrote to stderr: {result.stderr[:200]!r}")
    try:
        return json.loads(result.stdout.decode())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"bench_levenshtein {op} printed invalid JSON: {exc}") from exc


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
        raise SystemExit(f"isolated bench_levenshtein {op} failed: rc={result.returncode}")
    first, _, rest = result.stdout.partition(b"\n")
    if not first.startswith(b"RSS-KB:"):
        raise SystemExit("isolated wrapper did not report RSS")
    try:
        return json.loads(rest.decode()), int(first.split(b":")[1]) * 1024
    except (json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"isolated bench_levenshtein {op} bad output: {exc}") from exc


def float_bits(value: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=BENCH_DIR / "config.json")
    parser.add_argument("--only", default="", help="comma-separated workload names")
    parser.add_argument("--warmup", type=int, default=None)
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--raw-out", type=Path, default=BUILD_DIR / "levenshtein-bench.bench.json")
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text())
    seed = config["seed"]
    warmup = args.warmup if args.warmup is not None else config["warmup"]
    samples = args.samples if args.samples is not None else config["samples"]
    naive_budget = config["naive_cell_budget"]
    only = {name.strip() for name in args.only.split(",") if name.strip()}
    if samples < 25:
        raise SystemExit("methodology requires at least 25 samples")

    workloads = [
        (name, desc, s1, s2)
        for name, desc, s1, s2 in build_workloads(seed)
        if not only or name in only
    ]
    if not workloads:
        raise SystemExit("no workloads selected")

    BUILD_DIR.mkdir(exist_ok=True)
    for path in (BENCH_BIN, CLI_BIN):
        if path.exists():
            path.unlink()
    compile_start = time.perf_counter_ns()
    build = sh(
        [
            str(mojo_binary()),
            "build",
            str(BENCH_DIR / "bench.mojo"),
            "-I",
            str(ROOT / "libraries" / "levenshtein" / "mojo"),
            "-o",
            str(BENCH_BIN),
        ],
        cwd=ROOT,
    )
    compile_ns = time.perf_counter_ns() - compile_start
    if build.returncode != 0:
        raise SystemExit(f"mojo build bench.mojo failed:\n{build.stderr.decode()[-2000:]}")
    exe_bytes = BENCH_BIN.stat().st_size
    cli_build = sh(
        [
            str(mojo_binary()),
            "build",
            str(ROOT / "libraries" / "levenshtein" / "mojo" / "cli.mojo"),
            "-I",
            str(ROOT / "libraries" / "levenshtein" / "mojo"),
            "-o",
            str(CLI_BIN),
        ],
        cwd=ROOT,
    )
    if cli_build.returncode != 0:
        raise SystemExit(f"mojo build cli.mojo failed:\n{cli_build.stderr.decode()[-2000:]}")

    results: dict[str, dict] = {}
    for name, desc, s1, s2 in workloads:
        meta = workload_meta(s1, s2)
        entry: dict = {
            "description": desc,
            **meta,
            "naive_measured": bool(len(s1) * len(s2) <= naive_budget),
        }
        cells = max(len(s1) * len(s2), 1)

        # ---- reference values (untimed correctness anchors) ----
        ref_dist = Levenshtein.distance(s1, s2)
        ref_ratio = Indel.normalized_similarity(s1, s2)
        ref_ham = Hamming.distance(s1, s2, pad=True)

        # ---- distance ----
        if entry["naive_measured"]:
            naive_samples, naive_result = time_op(naive_distance, (s1, s2), warmup, samples)
            if naive_result != ref_dist:
                raise SystemExit(f"{name}: naive distance {naive_result} != C++ {ref_dist}")
            entry["distance_naive"] = stats(naive_samples)
        py_first = Levenshtein_py.distance(s1, s2)
        if py_first != ref_dist:
            raise SystemExit(f"{name}: _py distance {py_first} != C++ {ref_dist}")
        py_samples, _ = time_op(Levenshtein_py.distance, (s1, s2), warmup, samples)
        entry["distance_py"] = stats(py_samples)
        cpp_samples, cpp_result = time_op(Levenshtein.distance, (s1, s2), warmup, samples)
        if cpp_result != ref_dist:
            raise SystemExit(f"{name}: C++ distance moved between calls")
        entry["distance_cpp"] = stats(cpp_samples)

        mojo_dp = run_mojo("distance_dp", s1, s2, warmup, samples)
        if mojo_dp["result"] != ref_dist:
            raise SystemExit(f"{name}: Mojo DP {mojo_dp['result']} != C++ {ref_dist}")
        if (mojo_dp["cp_len1"], mojo_dp["cp_len2"]) != (len(s1), len(s2)):
            raise SystemExit(f"{name}: Mojo DP code-point lengths disagree")
        entry["distance_mojo_dp"] = stats(mojo_dp["samples_ns"])
        mojo_myers = run_mojo("distance_myers", s1, s2, warmup, samples)
        if mojo_myers["result"] != mojo_dp["result"]:
            raise SystemExit(
                f"{name}: Mojo Myers {mojo_myers['result']} != Mojo DP {mojo_dp['result']}"
            )
        entry["distance_mojo_myers"] = stats(mojo_myers["samples_ns"])
        mojo_prod = run_mojo("distance", s1, s2, warmup, samples)
        if mojo_prod["result"] != ref_dist:
            raise SystemExit(f"{name}: Mojo production {mojo_prod['result']} != C++ {ref_dist}")
        entry["distance_mojo"] = stats(mojo_prod["samples_ns"])

        # ---- ratio (bit-exact float64) ----
        if entry["naive_measured"]:
            naive_r_samples, naive_r = time_op(naive_ratio, (s1, s2), warmup, samples)
            if naive_r != ref_ratio:
                raise SystemExit(f"{name}: naive ratio {naive_r!r} != C++ {ref_ratio!r}")
            entry["ratio_naive"] = stats(naive_r_samples)
        py_r = Indel_py.normalized_similarity(s1, s2)
        if py_r != ref_ratio:
            raise SystemExit(f"{name}: _py ratio {py_r!r} != C++ {ref_ratio!r}")
        py_r_samples, _ = time_op(Indel_py.normalized_similarity, (s1, s2), warmup, samples)
        entry["ratio_py"] = stats(py_r_samples)
        cpp_r_samples, cpp_r = time_op(Indel.normalized_similarity, (s1, s2), warmup, samples)
        if cpp_r != ref_ratio:
            raise SystemExit(f"{name}: C++ ratio moved between calls")
        entry["ratio_cpp"] = stats(cpp_r_samples)
        mojo_r = run_mojo("ratio", s1, s2, warmup, samples)
        if mojo_r["result_bits"] != float_bits(ref_ratio):
            raise SystemExit(
                f"{name}: Mojo ratio bits {mojo_r['result_bits']} != C++ {float_bits(ref_ratio)}"
            )
        entry["ratio_mojo"] = stats(mojo_r["samples_ns"])

        # ---- hamming (pad=True; naive runs at all sizes: it is linear) ----
        ham_naive_samples, ham_naive = time_op(naive_hamming, (s1, s2), warmup, samples)
        if ham_naive != ref_ham:
            raise SystemExit(f"{name}: naive hamming {ham_naive} != C++ {ref_ham}")
        entry["hamming_naive"] = stats(ham_naive_samples)
        ham_py = Hamming_py.distance(s1, s2, pad=True)
        if ham_py != ref_ham:
            raise SystemExit(f"{name}: _py hamming {ham_py} != C++ {ref_ham}")
        ham_py_samples, _ = time_op(Hamming_py.distance, (s1, s2), warmup, samples, {"pad": True})
        entry["hamming_py"] = stats(ham_py_samples)
        ham_cpp_samples, ham_cpp = time_op(
            Hamming.distance, (s1, s2), warmup, samples, {"pad": True}
        )
        if ham_cpp != ref_ham:
            raise SystemExit(f"{name}: C++ hamming moved between calls")
        entry["hamming_cpp"] = stats(ham_cpp_samples)
        mojo_h = run_mojo("hamming", s1, s2, warmup, samples)
        if mojo_h["result"] != ref_ham:
            raise SystemExit(f"{name}: Mojo hamming {mojo_h['result']} != C++ {ref_ham}")
        entry["hamming_mojo"] = stats(mojo_h["samples_ns"])

        # ---- validation behavior (untimed): pad=False must raise identically ----
        if len(s1) != len(s2):
            for label, fn in (
                ("naive", lambda s1=s1, s2=s2: naive_hamming(s1, s2, pad=False)),
                ("C++", lambda s1=s1, s2=s2: Hamming.distance(s1, s2, pad=False)),
                ("_py", lambda s1=s1, s2=s2: Hamming_py.distance(s1, s2, pad=False)),
            ):
                try:
                    fn()
                except ValueError as exc:
                    if str(exc) != "Sequences are not the same length.":
                        raise SystemExit(
                            f"{name}: {label} hamming message drift: {exc!r}"
                        ) from None
                else:
                    raise SystemExit(f"{name}: {label} hamming pad=False did not raise")

        entry["cells"] = cells
        results[name] = entry
        print(f"workload {name}: {len(s1)}x{len(s2)} cp, checks passed", flush=True)

    # ---- Mojo validation behavior through the Phase 1 CLI (live check) ----
    s1_field = struct.pack(">I", 2) + b"ab"
    s2_field = struct.pack(">I", 3) + b"abc"
    cli_body = b"\x22\x00" + s1_field + s2_field
    cli_result = sh([str(CLI_BIN)], input=struct.pack(">I", len(cli_body)) + cli_body)
    if cli_result.returncode != 0:
        raise SystemExit("levenshtein CLI validation probe failed")
    (length,) = struct.unpack(">I", cli_result.stdout[:4])
    body = cli_result.stdout[4 : 4 + length]
    if body[0] != 1 or b"Sequences are not the same length." not in body[1:]:
        raise SystemExit(f"Mojo CLI hamming validation drift: {body!r}")
    print("cli validation probe: pad=False error frame correct", flush=True)

    # ---- gates ----
    for name, entry in results.items():
        for key, value in entry.items():
            if not key.endswith(("_naive", "_py", "_cpp", "_mojo", "_mojo_dp", "_mojo_myers")):
                continue
            if not isinstance(value, dict):
                continue
            if value["min_ns"] <= 0:
                raise SystemExit(f"timer check failed: {name}/{key} has a zero sample")
            if value["samples"] != samples:
                raise SystemExit(f"timer check failed: {name}/{key} has {value['samples']} samples")

    def chain(names: list[str], impl: str, op: str) -> None:
        medians = [results[n][f"{op}_{impl}"]["median_ns"] for n in names if n in results]
        if len(medians) < 2:
            return
        for lo, hi in zip(medians, medians[1:], strict=False):
            if not hi > lo:
                raise SystemExit(
                    f"scaling check failed: {op}/{impl} not slower at larger size ({lo} vs {hi})"
                )

    random_chain = [
        "short_ascii_random",
        "medium_ascii_random",
        "long_ascii_random",
        "xlong_ascii_random",
        "huge_ascii_random",
    ]
    chain(random_chain, "mojo", "distance")
    chain(random_chain, "cpp", "distance")
    chain(random_chain, "mojo", "ratio")
    chain(["size_0064_random", "size_0256_random", "size_1024_random"], "mojo", "distance")

    largest = max(results.items(), key=lambda kv: kv[1]["cells"])[0]
    largest_pair = next((s1, s2) for name, _, s1, s2 in workloads if name == largest)
    payload_path = BUILD_DIR / "lev-bench-payload.tmp"
    payload_path.write_bytes(frame(*largest_pair))
    _, rss = run_mojo_isolated("distance", payload_path, warmup, samples)
    payload_path.unlink()
    report = {
        "meta": {
            **env_metadata(),
            "seed": seed,
            "warmup": warmup,
            "samples": samples,
            "naive_cell_budget": naive_budget,
            "timer_resolution": "nanoseconds (see platform granularity note)",
            "ratio_policy": (
                "bit-exact float64 equality vs C++ (struct bits); any mismatch fails the run"
            ),
            "labels": {
                "naive": "local pure-Python two-row DP (floor)",
                "py": "rapidfuzz *_py pure-Python fallback (algorithmic parity)",
                "cpp": "rapidfuzz C++ (ceiling)",
                "mojo": "native production entry point",
                "mojo_dp": "internal Mojo two-row DP oracle",
                "mojo_myers": "internal Mojo blocked Myers",
            },
        },
        "compile": {"cold_compile_ns": compile_ns, "exe_bytes": exe_bytes},
        "rss": {
            "workload": largest,
            "distance_peak_bytes": rss,
            "note": "isolated ru_maxrss of one bench process on the largest "
            "workload; includes process startup and Mojo runtime overhead",
        },
        "workloads": results,
    }
    args.raw_out.parent.mkdir(parents=True, exist_ok=True)
    args.raw_out.write_text(json.dumps(report, indent=2) + "\n")

    def row(op: str, keys: list[str]) -> list[str]:
        lines = []
        for name, entry in results.items():
            meta = workload_meta(*next((s1, s2) for n, _, s1, s2 in workloads if n == name))
            cells = [f"{name} {meta['cp_len1']}x{meta['cp_len2']}"]
            for key in keys:
                value = entry.get(f"{op}_{key}")
                if value is None:
                    cells += ["n/a", "n/a"]
                else:
                    cells.append(
                        f"{value['median_ns']:.0f} ({value['min_ns']:.0f}/{value['max_ns']:.0f})"
                    )
                    cells.append(f"{value['ops_per_s']:,.0f}")
            lines.append(" | ".join(cells))
        return lines

    def ratios(op: str, pairs: list[tuple[str, str]]) -> list[str]:
        lines = []
        for name, entry in results.items():
            cells = [name]
            for num, den in pairs:
                upper = entry.get(f"{op}_{num}")
                lower = entry.get(f"{op}_{den}")
                if upper is None or lower is None:
                    cells.append("n/a")
                else:
                    cells.append(f"{upper['median_ns'] / lower['median_ns']:.2f}x")
            lines.append(" | ".join(cells))
        return lines

    dist_keys = ["naive", "py", "cpp", "mojo_dp", "mojo_myers", "mojo"]
    cells = " | ".join(f"{k} med ns (min/max) | {k} ops/s" for k in dist_keys)
    print("\n## distance: workload cps | " + cells)
    print("\n".join(row("distance", dist_keys)))
    print(
        "\n## distance ratios (median Mojo/x; below 1.0 = Mojo faster): "
        "workload | Myers/DP | Mojo/C++ | Mojo/py | Mojo/naive"
    )
    print(
        "\n".join(
            ratios(
                "distance",
                [("mojo_myers", "mojo_dp"), ("mojo", "cpp"), ("mojo", "py"), ("mojo", "naive")],
            )
        )
    )
    for op in ("ratio", "hamming"):
        keys = ["naive", "py", "cpp", "mojo"]
        cells = " | ".join(f"{k} med ns (min/max) | {k} ops/s" for k in keys)
        print(f"\n## {op}: workload cps | " + cells)
        print("\n".join(row(op, keys)))
        print(f"\n## {op} ratios: workload | Mojo/C++ | Mojo/py | Mojo/naive")
        print("\n".join(ratios(op, [("mojo", "cpp"), ("mojo", "py"), ("mojo", "naive")])))

    print(f"\ncold compile: {compile_ns / 1e9:.1f} s, exe {exe_bytes} bytes")
    print(f"peak RSS on {largest}: distance {rss} B")
    print(f"raw report: {args.raw_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
