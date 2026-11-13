#!/usr/bin/env python3
"""Generate bitarray golden vectors and the typed Mojo case module.

Single source of truth for serialization cases:

* ``libraries/bitarray/tests/vectors/bitarray_vectors.json`` --
  language-neutral bundle: logical bits, endianness, packed bytes
  (from ``tobytes()``), and the canonical framed payload.
* ``libraries/bitarray/tests/mojo/generated_vectors.mojo`` -- typed
  ``BitCase`` metadata plus a ``bitarray_vectors()`` builder for
  native Mojo tests.

Both outputs are deterministic. Run with ``--check`` (as the repo test
runner does) to fail when a committed artifact drifts from the generator.

Reference semantics come from ``bitarray==3.12.3`` (PSF-2.0).
"""

from __future__ import annotations

import argparse
import difflib
import importlib.metadata
import json
import random
import struct
from pathlib import Path
from typing import Any

from bitarray import bitarray

SCHEMA_VERSION = "1.0.0"
GENERATOR_NAME = "bitarray_vectors"
GENERATOR_VERSION = "1.0.0"
REFERENCE_PACKAGE = "bitarray"
REFERENCE_VERSION = "3.12.3"
SEED = 20260607

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE = ROOT / "libraries/bitarray/tests/vectors/bitarray_vectors.json"
DEFAULT_MOJO = ROOT / "libraries/bitarray/tests/mojo/generated_vectors.mojo"

LENGTHS = [0, 1, 2, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65]


def _patterns(n: int, rng: random.Random) -> list[str]:
    if n == 0:
        return [""]
    out = [
        "0" * n,
        "1" * n,
        "".join("1" if i % 2 == 0 else "0" for i in range(n)),
        "".join("0" if i % 2 == 0 else "1" for i in range(n)),
        "1" + "0" * (n - 1),
        "0" * (n - 1) + "1",
    ]
    if n > 2:
        out.append("0" * (n // 2) + "1" + "0" * (n - n // 2 - 1))
    # Deterministic sparse (two ones), dense (two zeros), random.
    sparse = ["0"] * n
    for i in rng.sample(range(n), min(2, n)):
        sparse[i] = "1"
    out.append("".join(sparse))
    dense = ["1"] * n
    for i in rng.sample(range(n), min(2, n)):
        dense[i] = "0"
    out.append("".join(dense))
    out.append("".join(rng.choice("01") for _ in range(n)))
    # Deduplicate, preserving order.
    return list(dict.fromkeys(out))


def _framed_hex(bits: str, endian: str) -> tuple[str, str, int]:
    a = bitarray(bits, endian=endian)
    packed = a.tobytes()
    assert len(packed) == (len(bits) + 7) // 8
    assert a.padbits == (8 - len(bits) % 8) % 8
    endian_id = 0 if endian == "big" else 1
    framed = struct.pack(">I", len(bits)) + bytes([endian_id]) + packed
    return packed.hex(), framed.hex(), a.padbits


def _build_cases() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    cases: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for n in LENGTHS:
        for bits in _patterns(n, rng):
            for endian in ("big", "little"):
                if (bits, endian) in seen:
                    continue
                seen.add((bits, endian))
                packed_hex, framed_hex, padbits = _framed_hex(bits, endian)
                cases.append(
                    {
                        "id": f"len{n:02d}-{endian}-{len(cases):03d}",
                        "bits": bits,
                        "endian": endian,
                        "nbits": n,
                        "packed_hex": packed_hex,
                        "padbits": padbits,
                        "framed_hex": framed_hex,
                    }
                )
    return cases


def _mojo_bytes(hexed: str) -> str:
    if not hexed:
        return "List[UInt8]()"
    lines = [f"List[UInt8](capacity={len(hexed) // 2})"]
    return lines[0]


def _mojo_text(bundle: dict[str, Any]) -> str:
    cases = bundle["cases"]
    lines = [
        '"""Golden bitarray vectors. DO NOT EDIT BY HAND.',
        "",
        "Regenerate with:",
        "",
        "    .venv/bin/python libraries/bitarray/python_reference/generate_vectors.py",
        "",
        "and use ``--check`` to detect drift.",
        '"""',
        "",
        "from std.collections import List",
        "",
        "",
        "struct BitCase:",
        "    var bits: String",
        "    var big_endian: Bool",
        "    var nbits: Int",
        "    var packed: List[UInt8]",
        "    var framed: List[UInt8]",
        "",
        "    def __init__(",
        "        out self,",
        "        bits: String,",
        "        big_endian: Bool,",
        "        nbits: Int,",
        "        var packed: List[UInt8],",
        "        var framed: List[UInt8],",
        "    ):",
        "        self.bits = bits",
        "        self.big_endian = big_endian",
        "        self.nbits = nbits",
        "        self.packed = packed^",
        "        self.framed = framed^",
        "",
        "",
        "def bitarray_vectors() -> List[BitCase]:",
        f"    var out = List[BitCase](capacity={len(cases)})",
    ]
    for k, case in enumerate(cases):
        endian = "True" if case["endian"] == "big" else "False"
        lines.append(f"    var packed{k} = {_mojo_bytes(case['packed_hex'])}")
        for i in range(0, len(case["packed_hex"]), 2):
            lines.append(f"    packed{k}.append(UInt8(0x{case['packed_hex'][i : i + 2]}))")
        lines.append(f"    var framed{k} = {_mojo_bytes(case['framed_hex'])}")
        for i in range(0, len(case["framed_hex"]), 2):
            lines.append(f"    framed{k}.append(UInt8(0x{case['framed_hex'][i : i + 2]}))")
        bits = case["bits"]
        nbits = case["nbits"]
        lines.append(f'    out.append(BitCase("{bits}", {endian},')
        lines.append(f"        {nbits}, packed{k}^, framed{k}^))")
    lines.append("    return out^")
    lines.append("")
    return "\n".join(lines)


def _json_text(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _check(path: Path, text: str, label: str) -> bool:
    if not path.exists():
        print(f"drift: missing {label} at {path}")
        return False
    current = path.read_text(encoding="utf-8")
    if current != text:
        print(f"drift: {label} at {path} differs from generator output")
        for line in difflib.unified_diff(
            current.splitlines(),
            text.splitlines(),
            fromfile=str(path),
            tofile="<generated>",
            lineterm="",
        ):
            print(line)
        return False
    print(f"ok: {label} at {path} matches generator output")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--mojo", type=Path, default=DEFAULT_MOJO)
    args = parser.parse_args(argv)

    try:
        installed = importlib.metadata.version(REFERENCE_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        parser.exit(2, f"reference package {REFERENCE_PACKAGE} is not installed.\n")
    if installed != REFERENCE_VERSION:
        parser.exit(
            2,
            f"reference package {REFERENCE_PACKAGE}=={installed}, "
            f"need exactly {REFERENCE_VERSION}.\n",
        )

    cases = _build_cases()
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "reference": {"package": REFERENCE_PACKAGE, "version": REFERENCE_VERSION},
        "seed": SEED,
        "cases": cases,
    }
    bundle_text = _json_text(bundle)
    mojo_text = _mojo_text(bundle)

    if args.check:
        ok = _check(args.bundle, bundle_text, "bundle")
        ok = _check(args.mojo, mojo_text, "mojo") and ok
        return 0 if ok else 1

    _write(args.bundle, bundle_text)
    _write(args.mojo, mojo_text)
    print(f"wrote {len(cases)} cases to {args.bundle} and {args.mojo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
