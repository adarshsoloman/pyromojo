#!/usr/bin/env python3
"""Probe how msgpack 1.2.4 handles deeply nested values.

Each probe runs in a fresh subprocess so a crash or recursion error cannot take
down the caller. Results are printed as JSON and summarized in
``libraries/msgpack/PHASE1_RESULTS.md``.

    .venv/bin/python libraries/msgpack/python_reference/probe_reference_depth.py
"""

from __future__ import annotations

import json
import subprocess
import sys

DEPTHS = [64, 128, 129, 1000, 1024, 1025, 5000, 100_000]

CHILD = r"""
import json
import sys

import msgpack
import msgpack.fallback as fallback
from msgpack.fallback import Packer as FallbackPacker

mode = sys.argv[1]
depth = int(sys.argv[2])


def describe(exc):
    return {"status": "error", "type": type(exc).__name__, "message": str(exc)[:160]}


if mode == "pack":
    value = 0
    for _ in range(depth):
        value = [value]
    results = {}
    for name, module in (("c", msgpack), ("fallback", fallback)):
        try:
            if name == "c":
                encoded = module.packb(value, use_bin_type=True)
            else:
                encoded = FallbackPacker(use_bin_type=True).pack(value)
            results[name] = {"status": "ok", "bytes": len(encoded)}
        except BaseException as exc:
            results[name] = describe(exc)
    print(json.dumps(results))
else:
    raw = b"\x91" * depth + b"\x00"
    results = {}
    for name, module in (("c", msgpack), ("fallback", fallback)):
        try:
            decoded = module.unpackb(raw, strict_map_key=False)
            walked = 0
            current = decoded
            while isinstance(current, list) and len(current) == 1:
                walked += 1
                current = current[0]
            results[name] = {"status": "ok", "depth": walked}
        except BaseException as exc:
            results[name] = describe(exc)
    print(json.dumps(results))
"""


def probe(mode: str, depth: int) -> dict:
    try:
        result = subprocess.run(
            [sys.executable, "-c", CHILD, mode, str(depth)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    if result.returncode != 0:
        return {
            "status": "crashed",
            "returncode": result.returncode,
            "stderr": result.stderr.strip()[-300:],
        }
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return {"status": "no-output", "stderr": result.stderr.strip()[-300:]}
    return json.loads(lines[-1])


def main() -> int:
    report = []
    for depth in DEPTHS:
        report.append(
            {
                "depth": depth,
                "pack": probe("pack", depth),
                "unpack": probe("unpack", depth),
            }
        )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
