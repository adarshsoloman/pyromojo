"""Build and run every audioop toolchain experiment; record the outcome.

Usage (from the repository root):
    python experiments/audioop_toolchain/run_experiments.py [--out PATH]

Each experiment is compiled with the project Mojo toolchain and executed.
Compile failures and non-zero exits are recorded, never hidden. The default
report lands in the git-ignored ``reports/generated/`` tree.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOJO = ROOT / ".venv" / "bin" / "mojo"


def run_one(source: Path, build_dir: Path) -> dict[str, object]:
    binary = build_dir / source.stem
    started = time.perf_counter()
    compile_result = subprocess.run(
        [str(MOJO), "build", str(source), "-o", str(binary)],
        capture_output=True,
        text=True,
    )
    compile_seconds = time.perf_counter() - started
    if compile_result.returncode != 0:
        return {
            "name": source.name,
            "status": "compile-failed",
            "compile_seconds": round(compile_seconds, 2),
            "detail": compile_result.stderr.strip().splitlines()[-1]
            if compile_result.stderr.strip()
            else "",
        }
    started = time.perf_counter()
    run_result = subprocess.run([str(binary)], capture_output=True, text=True)
    run_seconds = time.perf_counter() - started
    stdout_lines = run_result.stdout.strip().splitlines()
    return {
        "name": source.name,
        "status": "pass" if run_result.returncode == 0 else "runtime-failed",
        "compile_seconds": round(compile_seconds, 2),
        "run_seconds": round(run_seconds, 2),
        "exit_code": run_result.returncode,
        "last_line": stdout_lines[-1] if stdout_lines else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports" / "generated" / "audioop_toolchain.md"),
    )
    args = parser.parse_args()

    if not MOJO.exists():
        print(f"missing Mojo toolchain: {MOJO}", file=sys.stderr)
        return 2

    experiments = sorted((ROOT / "experiments" / "audioop_toolchain").glob("*.mojo"))
    if not experiments:
        print("no experiments found", file=sys.stderr)
        return 2

    results = []
    with tempfile.TemporaryDirectory() as tmp:
        build_dir = Path(tmp)
        for source in experiments:
            outcome = run_one(source, build_dir)
            results.append(outcome)
            print(f"{outcome['status']:16} {outcome['name']}")

    report_path = Path(args.out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({"mojo": str(MOJO), "results": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    failures = [r for r in results if r["status"] != "pass"]
    print(f"\n{len(results) - len(failures)}/{len(results)} passed")
    print(f"report: {report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
