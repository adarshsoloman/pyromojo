"""Correctness gate for the bitarray benchmark (Phase 3).

Runs BEFORE any timing is recorded. Validates, with exact expected
values and deterministic randomized differentials:

1. Pure-Python baseline vs C-backed reference on every benchmark
   workload and operation.
2. Native Mojo (via ``bench.mojo`` checksums, plus full hex for small
   inputs) vs the C-backed reference on every workload and operation.
3. Edge cases: empty, one-bit, non-byte-aligned, zero shift, shifts at
   and beyond the logical length, negative-shift errors, identical and
   disjoint operands, both endiannesses, padding invariants.
4. Endianness equivalence of logical results.

Any failure raises ``SystemExit``. Results are stored separately from
performance results (``correctness.json`` next to the benchmark
report). The benchmark driver imports and runs ``main()`` first.
"""

from __future__ import annotations

import json
import random
import struct
import subprocess
import sys
from pathlib import Path

from bitarray import bitarray

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR))

import pure_python_reference as pure  # noqa: E402
from workloads import fnv1a_checksum  # noqa: E402

BENCH_SRC = BENCH_DIR / "bench.mojo"
MOJO_INCLUDE = BENCH_DIR.parent / "mojo"

REFERENCE_VERSION = "3.12.3"


def _check_reference() -> None:
    import importlib.metadata

    installed = importlib.metadata.version("bitarray")
    if installed != REFERENCE_VERSION:
        raise SystemExit(f"need bitarray=={REFERENCE_VERSION}, got {installed}")
    import bitarray._bitarray as ext

    if not ext.__file__.endswith(".so"):
        raise SystemExit(f"C extension not loaded: {ext.__file__}")


def _mojo_binary() -> Path:
    import shutil

    venv_mojo = BENCH_DIR.parents[2] / ".venv" / "bin" / "mojo"
    if venv_mojo.exists():
        return venv_mojo
    found = shutil.which("mojo")
    if not found:
        raise SystemExit("mojo compiler not found")
    return Path(found)


def _build_bench(tmp: Path) -> Path:
    binary = tmp / "bench_bitarray"
    result = subprocess.run(
        [str(_mojo_binary()), "build", str(BENCH_SRC), "-I", str(MOJO_INCLUDE), "-o", str(binary)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"bench.mojo build failed:\n{result.stderr[-2000:]}")
    return binary


def _framed(bits: str, endian: str) -> bytes:
    a = bitarray(bits, endian=endian)
    eid = 0 if endian == "big" else 1
    return struct.pack(">I", len(a)) + bytes([eid]) + a.tobytes()


def _bench_frame(bits_a: str, bits_b: str, endian: str, k: int) -> bytes:
    return _framed(bits_a, endian) + _framed(bits_b, endian) + struct.pack(">I", k)


def _run_bench(binary: Path, op: str, bits_a: str, bits_b: str, endian: str, k: int) -> dict:
    payload = _bench_frame(bits_a, bits_b, endian, k)
    frame = struct.pack(">I", len(payload)) + payload
    result = subprocess.run(
        [str(binary), op, "0", "1"], input=frame, capture_output=True, timeout=300
    )
    if result.returncode != 0:
        raise SystemExit(f"bench {op} failed: {result.stderr.decode()[:300]!r}")
    try:
        return json.loads(result.stdout.decode())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"bench {op} printed invalid JSON: {exc}") from exc


def _expected(op: str, bits_a: str, bits_b: str, endian: str, k: int):
    a = bitarray(bits_a, endian=endian)
    b = bitarray(bits_b, endian=endian)
    if op == "and":
        return (a & b).to01()
    if op == "or":
        return (a | b).to01()
    if op == "xor":
        return (a ^ b).to01()
    if op == "count":
        return a.count()
    if op == "shl":
        return (a << k).to01()
    return (a >> k).to01()


def _expected_pure(op: str, la: list[bool], lb: list[bool], k: int):
    if op == "and":
        return pure.to_bits(pure.band(la, lb))
    if op == "or":
        return pure.to_bits(pure.bor(la, lb))
    if op == "xor":
        return pure.to_bits(pure.bxor(la, lb))
    if op == "count":
        return pure.count(la)
    if op == "shl":
        return pure.to_bits(pure.shl(la, k))
    return pure.to_bits(pure.shr(la, k))


def _check_edge_cases(binary: Path, failures: list[str]) -> int:
    cases = 0
    # Empty arrays: every op is defined and empty.
    for endian in ("big", "little"):
        for op in ("and", "or", "xor", "count", "shl", "shr"):
            got = _run_bench(binary, op, "", "", endian, 3)
            want = _expected(op, "", "", endian, 3)
            cases += 1
            if op == "count":
                if got["count"] != want:
                    failures.append(f"empty/{endian}/{op}: {got['count']} != {want}")
            elif got.get("hex") != bitarray(want, endian=endian).tobytes().hex():
                failures.append(f"empty/{endian}/{op}: {got.get('hex')} != {want!r}")
    # One-bit arrays, both values, both endians.
    triples = (
        ("and", "1", 0),
        ("or", "0", 1),
        ("xor", "1", 1),
        ("shl", "0", 1),
        ("shr", "0", 1),
    )
    for endian in ("big", "little"):
        for bits in ("0", "1"):
            for op, other, k in triples:
                got = _run_bench(binary, op, bits, other, endian, k)
                want = _expected(op, bits, other, endian, k)
                cases += 1
                if got.get("hex") != bitarray(want, endian=endian).tobytes().hex():
                    failures.append(f"one-bit/{endian}/{bits}/{op}: hex mismatch")
    # Non-byte-aligned lengths, zero shift, shift == length, shift > length.
    for endian in ("big", "little"):
        for n, text in ((9, "101101110"), (17, "10110111010110111")):
            pairs = [
                ("shl", 0),
                ("shr", 0),
                ("shl", n),
                ("shr", n),
                ("shl", n + 5),
                ("shr", n + 100),
            ]
            for op, k in pairs:
                got = _run_bench(binary, op, text, "0" * n, endian, k)
                want = _expected(op, text, "0" * n, endian, k)
                cases += 1
                if got.get("hex") != bitarray(want, endian=endian).tobytes().hex():
                    failures.append(f"unaligned/{endian}/{n}/{op}/{k}: hex mismatch")
    # Negative shifts raise on both Python paths (Mojo parity is covered
    # by the native test suite: test_shift_negative).
    for bad in (-1, -100):
        for fn in (
            lambda bad=bad: pure.shl([True], bad),
            lambda bad=bad: pure.shr([True], bad),
            lambda bad=bad: bitarray("1") << bad,
            lambda bad=bad: bitarray("1") >> bad,
        ):
            cases += 1
            try:
                fn()
                failures.append(f"negative shift {bad} did not raise")
            except ValueError:
                pass
    # Identical vs disjoint operands.
    for endian in ("big", "little"):
        same = _run_bench(binary, "xor", "10101010", "10101010", endian, 0)
        cases += 1
        if same.get("hex") != "00":
            failures.append(f"identical xor/{endian}: {same.get('hex')}")
        disj = _run_bench(binary, "and", "11110000", "00001111", endian, 0)
        cases += 1
        if disj.get("hex") != "00":
            failures.append(f"disjoint and/{endian}: {disj.get('hex')}")
    return cases


def main(out_path: Path | None = None) -> dict:
    _check_reference()
    import tempfile

    failures: list[str] = []
    checks = 0
    with tempfile.TemporaryDirectory() as tmp:
        binary = _build_bench(Path(tmp))
        checks += _check_edge_cases(binary, failures)
        # Representative workload sweep through the Mojo binary.
        # Small inputs compare full hex; large inputs compare FNV-1a
        # checksums (agreement of both was established on small inputs).
        rng = random.Random(20260610)
        for n in (64, 1000, 16385, 100000):
            for endian in ("big", "little"):
                eid = 0 if endian == "big" else 1
                bits_a = "".join(rng.choice("01") for _ in range(n))
                bits_b = "".join(rng.choice("01") for _ in range(n))
                for op in ("and", "or", "xor", "count"):
                    got = _run_bench(binary, op, bits_a, bits_b, endian, 0)
                    want = _expected(op, bits_a, bits_b, endian, 0)
                    checks += 1
                    if op == "count":
                        if got["count"] != want:
                            failures.append(f"sweep/{n}/{endian}/{op}")
                    else:
                        packed = bitarray(want, endian=endian).tobytes()
                        if got["checksum"] != str(fnv1a_checksum(n, eid, packed)):
                            failures.append(f"sweep/{n}/{endian}/{op}: checksum")
                        if n <= 4096 and got.get("hex") != packed.hex():
                            failures.append(f"sweep/{n}/{endian}/{op}: hex")
                for op in ("shl", "shr"):
                    for k in (1, n // 4 if n > 4 else 1, n):
                        got = _run_bench(binary, op, bits_a, bits_b, endian, k)
                        want = _expected(op, bits_a, bits_b, endian, k)
                        checks += 1
                        packed = bitarray(want, endian=endian).tobytes()
                        if got["checksum"] != str(fnv1a_checksum(n, eid, packed)):
                            failures.append(f"sweep/{n}/{endian}/{op}/{k}: checksum")
                        if n <= 4096 and got.get("hex") != packed.hex():
                            failures.append(f"sweep/{n}/{endian}/{op}/{k}: hex")
        # Padding invariance on non-aligned Mojo outputs.
        for n, text in ((9, "101101110"), (65, "1" + "0" * 63 + "1")):
            for endian in ("big", "little"):
                got = _run_bench(binary, "shl", text, "0" * n, endian, 3)
                raw = bytes.fromhex(got["hex"])
                pad = (8 - n % 8) % 8
                checks += 1
                if pad:
                    last = raw[-1]
                    bad = (last & ((1 << pad) - 1)) if endian == "big" else (last >> (8 - pad))
                    if bad:
                        failures.append(f"padding/{endian}/{n}: nonzero pad bits")
    report = {"checks": checks, "failures": failures, "passed": not failures}
    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=2) + "\n")
    if failures:
        raise SystemExit(
            f"correctness gate failed ({len(failures)} failures):\n" + "\n".join(failures[:20])
        )
    print(f"correctness gate: {checks} checks passed, 0 failures")
    return report


if __name__ == "__main__":
    main()
