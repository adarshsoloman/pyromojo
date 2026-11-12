#!/usr/bin/env python3
"""Generate Levenshtein golden vectors and the typed Mojo case module.

Single source of truth for correctness cases:

* ``libraries/levenshtein/tests/vectors/levenshtein_vectors.json`` --
  language-neutral bundle: one case per operation, inputs, parameters,
  and the expected value or error.
* ``libraries/levenshtein/tests/mojo/generated_vectors.mojo`` -- typed
  ``LevVector`` metadata plus a ``levenshtein_vectors()`` builder for
  native Mojo tests.

Both outputs are deterministic. Run with ``--check`` (as the repo test
runner does) to fail when a committed artifact drifts from the generator.

Reference semantics come from ``rapidfuzz==3.14.6`` (MIT). The
``Levenshtein`` wrapper package (GPL-2.0-or-later) is never imported;
Phase 0 established that every probed behavior is identical.
"""

from __future__ import annotations

import argparse
import difflib
import importlib.metadata
import json
import random
import sys
from pathlib import Path
from typing import Any

from rapidfuzz.distance import Hamming, Indel, Levenshtein

SCHEMA_VERSION = "1.0.0"
GENERATOR_NAME = "levenshtein_vectors"
GENERATOR_VERSION = "1.0.0"
REFERENCE_PACKAGE = "rapidfuzz"
REFERENCE_VERSION = "3.14.6"
SEED = 20260202

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE = ROOT / "libraries/levenshtein/tests/vectors/levenshtein_vectors.json"
DEFAULT_MOJO = ROOT / "libraries/levenshtein/tests/mojo/generated_vectors.mojo"

# Surrogates are excluded: neither JSON->UTF-8 CLI transport nor Mojo
# String can represent them (documented deviation, see unicode-semantics).
_ALPHABET = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-") + [
    "é",
    "è",
    "ê",
    "ë",
    "ß",
    "æ",
    "ñ",
    "ø",
    "ü",
    "中",
    "文",
    "あ",
    "😀",
    "😃",
    "é",
]


def _rand_text(rng: random.Random, max_length: int) -> str:
    return "".join(rng.choice(_ALPHABET) for _ in range(rng.randrange(max_length + 1)))


def _one_substitution(rng: random.Random, text: str) -> str:
    if not text:
        return "a"
    index = rng.randrange(len(text))
    replacement = rng.choice(_ALPHABET)
    if replacement == text[index]:
        replacement = "Z" if replacement != "Z" else "Y"
    return text[:index] + replacement + text[index + 1 :]


def _distance_case(
    case_id: str, s1: str, s2: str, weights: tuple[int, int, int] = (1, 1, 1)
) -> dict[str, Any]:
    return {
        "id": case_id,
        "op": "distance",
        "s1": s1,
        "s2": s2,
        "weights": list(weights),
        "cutoff": None,
        "expected": Levenshtein.distance(s1, s2, weights=weights),
    }


def _cutoff_case(
    case_id: str, s1: str, s2: str, cutoff: int, weights: tuple[int, int, int] = (1, 1, 1)
) -> dict[str, Any]:
    return {
        "id": case_id,
        "op": "distance",
        "s1": s1,
        "s2": s2,
        "weights": list(weights),
        "cutoff": cutoff,
        "expected": Levenshtein.distance(s1, s2, weights=weights, score_cutoff=cutoff),
    }


def _ratio_case(case_id: str, s1: str, s2: str) -> dict[str, Any]:
    return {
        "id": case_id,
        "op": "ratio",
        "s1": s1,
        "s2": s2,
        "expected": Indel.normalized_similarity(s1, s2),
    }


def _hamming_case(case_id: str, s1: str, s2: str, pad: bool = True) -> dict[str, Any]:
    return {
        "id": case_id,
        "op": "hamming",
        "s1": s1,
        "s2": s2,
        "pad": pad,
        "expected": Hamming.distance(s1, s2, pad=pad),
    }


def _error_case(
    case_id: str,
    op: str,
    s1: str,
    s2: str,
    message: str,
    via_cli: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case: dict[str, Any] = {
        "id": case_id,
        "op": op,
        "s1": s1,
        "s2": s2,
        "error_contains": message,
        "via_cli": via_cli,
    }
    if extra:
        case.update(extra)
    return case


def build_cases() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    cases: list[dict[str, Any]] = []

    fixed = [
        ("kitten", "sitting"),
        ("lewenstein", "levenshtein"),
        ("spam", "park"),
        ("abc", "adc"),
        ("ab", "ba"),
        ("a", "b"),
        ("", ""),
        ("", "abc"),
        ("abc", ""),
        ("abc", "abc"),
        ("abc", "xyz"),
        ("aaaa", "aa"),
        ("aa", "aaaa"),
        ("abcdef", "azced"),
    ]
    for index, (left, right) in enumerate(fixed):
        tag = f"fixed_{index:02d}"
        cases.append(_distance_case(f"{tag}_distance", left, right))
        cases.append(_ratio_case(f"{tag}_ratio", left, right))
        cases.append(_hamming_case(f"{tag}_hamming", left, right))

    unicode_pairs = [
        ("é", "e"),
        ("é", "é"),
        ("😀", ""),
        ("😀", "😃"),
        ("a😀b", "ab"),
        ("naïve", "naive"),
        ("straße", "strasse"),
        ("æ", "ae"),
        ("👩‍👩‍👧‍👦", ""),
        ("中文测试", "中文測試"),
        ("あいう", "あえう"),
        ("café 😀 naïve", "cafe 😃 naive"),
    ]
    for index, (left, right) in enumerate(unicode_pairs):
        tag = f"unicode_{index:02d}"
        cases.append(_distance_case(f"{tag}_distance", left, right))
        cases.append(_ratio_case(f"{tag}_ratio", left, right))
        cases.append(_hamming_case(f"{tag}_hamming", left, right))

    weight_sets = [(1, 1, 1), (1, 1, 2), (2, 1, 1), (1, 2, 1), (2, 2, 1), (3, 1, 2)]
    weight_pairs = [
        ("kitten", "sitting"),
        ("lewenstein", "levenshtein"),
        ("abc", "adc"),
        ("", "abc"),
        ("abc", ""),
    ]
    for pair_index, (left, right) in enumerate(weight_pairs):
        for weight_index, weights in enumerate(weight_sets):
            cases.append(
                _distance_case(
                    f"weights_{pair_index:02d}_{weight_index:02d}",
                    left,
                    right,
                    weights,
                )
            )

    cutoff_specs = [
        ("kitten", "sitting", [1, 2, 3, 4]),
        ("abc", "adc", [0, 1, 2]),
        ("abc", "xyz", [0, 1, 2, 3, 4]),
        ("abc", "abc", [0, 1]),
    ]
    for spec_index, (left, right, cutoffs) in enumerate(cutoff_specs):
        for cutoff in cutoffs:
            cases.append(_cutoff_case(f"cutoff_{spec_index:02d}_{cutoff}", left, right, cutoff))

    cases.append(_hamming_case("hamming_pad_shorter", "abc", "ab", pad=True))
    cases.append(_hamming_case("hamming_pad_empty", "abc", "", pad=True))
    cases.append(
        _error_case(
            "hamming_nopad_unequal",
            "hamming",
            "abc",
            "ab",
            "Sequences are not the same length.",
            via_cli=True,
            extra={"pad": False},
        )
    )
    cases.append(
        _error_case(
            "hamming_nopad_empty",
            "hamming",
            "",
            "a",
            "Sequences are not the same length.",
            via_cli=True,
            extra={"pad": False},
        )
    )
    cases.append(
        _error_case(
            "weights_zero",
            "distance",
            "abc",
            "adc",
            "positive integers",
            via_cli=True,
            extra={"weights": [0, 1, 1], "cutoff": None},
        )
    )
    cases.append(
        _error_case(
            "weights_negative",
            "distance",
            "abc",
            "adc",
            "positive integers",
            via_cli=False,
            extra={"weights": [-1, 1, 1], "cutoff": None},
        )
    )
    cases.append(
        _error_case(
            "cutoff_negative",
            "distance",
            "abc",
            "adc",
            "non-negative integer",
            via_cli=False,
            extra={"weights": [1, 1, 1], "cutoff": -1},
        )
    )

    boundary_lengths = [1, 2, 3, 63, 64, 65, 127, 128, 129, 191, 192, 193, 255, 256]
    for length in boundary_lengths:
        left = "".join(rng.choice("abcdef") for _ in range(length))
        right = "".join(rng.choice("abcdef") for _ in range(length))
        cases.append(_distance_case(f"boundary_{length:03d}_random", left, right))
        cases.append(_ratio_case(f"boundary_{length:03d}_random_ratio", left, right))
        repeated = "a" * length
        cases.append(_distance_case(f"boundary_{length:03d}_repeated", repeated, right))
        uniform = "b" * length
        cases.append(_distance_case(f"boundary_{length:03d}_uniform", repeated, uniform))

    for index in range(120):
        left = _rand_text(rng, 48)
        right = _rand_text(rng, 48)
        tag = f"random_{index:03d}"
        cases.append(_distance_case(f"{tag}_distance", left, right))
        cases.append(_ratio_case(f"{tag}_ratio", left, right))

    for length in (500, 1024, 2048):
        left = _rand_text(rng, length)
        right = _rand_text(rng, length)
        cases.append(_distance_case(f"long_{length}_random", left, right))
        cases.append(_ratio_case(f"long_{length}_random_ratio", left, right))
        edited = _one_substitution(rng, left)
        cases.append(_distance_case(f"long_{length}_onesub", left, edited))

    return cases


def build_bundle(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "reference": {"package": REFERENCE_PACKAGE, "version": REFERENCE_VERSION},
        "seed": SEED,
        "cases": cases,
    }


# ---------------------------------------------------------------------------
# Mojo module emitter
# ---------------------------------------------------------------------------


def _mojo_string(text: str) -> str:
    out: list[str] = ['"']
    for char in text:
        point = ord(char)
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif 0x20 <= point <= 0x7E:
            out.append(char)
        elif point <= 0xFFFF:
            out.append(f"\\u{point:04x}")
        else:
            out.append(f"\\U{point:08x}")
    out.append('"')
    return "".join(out)


def _mojo_float(value: float) -> str:
    text = repr(value)
    if "." not in text and "e" not in text and "nan" not in text and "inf" not in text:
        text += ".0"
    return text


def build_mojo(cases: list[dict[str, Any]]) -> str:
    lines = [
        '"""Golden Levenshtein vectors generated from rapidfuzz.',
        "",
        "Do not edit by hand. Regenerate with",
        "``libraries/levenshtein/python_reference/generate_vectors.py``",
        "and use ``--check`` to detect drift.",
        '"""',
        "",
        "from std.collections import List",
        "",
        "",
        "struct LevVector(Copyable, Movable):",
        '    """One golden case: operation, inputs, and expected outcome."""',
        "",
        "    var id: StaticString",
        "    var op: StaticString",
        "    var s1: StaticString",
        "    var s2: StaticString",
        "    var insertion: Int",
        "    var deletion: Int",
        "    var substitution: Int",
        "    var has_cutoff: Bool",
        "    var cutoff: Int",
        "    var pad: Bool",
        "    var has_error: Bool",
        "    var error_contains: StaticString",
        "    var expected_int: Int",
        "    var expected_float: Float64",
        "",
        "    def __init__(",
        "        out self,",
        "        id: StaticString,",
        "        op: StaticString,",
        "        s1: StaticString,",
        "        s2: StaticString,",
        "        insertion: Int,",
        "        deletion: Int,",
        "        substitution: Int,",
        "        has_cutoff: Bool,",
        "        cutoff: Int,",
        "        pad: Bool,",
        "        has_error: Bool,",
        "        error_contains: StaticString,",
        "        expected_int: Int,",
        "        expected_float: Float64,",
        "    ):",
        "        self.id = id",
        "        self.op = op",
        "        self.s1 = s1",
        "        self.s2 = s2",
        "        self.insertion = insertion",
        "        self.deletion = deletion",
        "        self.substitution = substitution",
        "        self.has_cutoff = has_cutoff",
        "        self.cutoff = cutoff",
        "        self.pad = pad",
        "        self.has_error = has_error",
        "        self.error_contains = error_contains",
        "        self.expected_int = expected_int",
        "        self.expected_float = expected_float",
        "",
        "",
        "def levenshtein_vectors() -> List[LevVector]:",
        '    """Every golden case, in generator order."""',
        "    var cases = List[LevVector]()",
    ]
    for case in cases:
        op = case["op"]
        weights = case.get("weights", [1, 1, 1])
        cutoff = case.get("cutoff")
        lines.append("    cases.append(LevVector(")
        lines.append(f"        {_mojo_string(case['id'])},")
        lines.append(f"        {_mojo_string(op)},")
        lines.append(f"        {_mojo_string(case['s1'])},")
        lines.append(f"        {_mojo_string(case['s2'])},")
        lines.append(f"        {weights[0]}, {weights[1]}, {weights[2]},")
        if cutoff is None:
            lines.append("        False, 0,")
        else:
            lines.append(f"        True, {cutoff},")
        lines.append(f"        {'True' if case.get('pad', True) else 'False'},")
        if "error_contains" in case:
            lines.append("        True,")
            lines.append(f"        {_mojo_string(case['error_contains'])},")
            lines.append("        0, 0.0,")
        elif op == "ratio":
            lines.append("        False,")
            lines.append('        "",')
            lines.append(f"        0, {_mojo_float(case['expected'])},")
        else:
            lines.append("        False,")
            lines.append('        "",')
            lines.append(f"        {case['expected']}, 0.0,")
        lines.append("    ))")
    lines.append("    return cases^")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output and drift detection
# ---------------------------------------------------------------------------


def _json_text(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _check(path: Path, text: str, label: str) -> bool:
    if not path.exists():
        print(f"{label}: missing {path}", file=sys.stderr)
        return False
    current = path.read_text(encoding="utf-8")
    if current == text:
        return True
    diff = list(
        difflib.unified_diff(
            current.splitlines(),
            text.splitlines(),
            fromfile=f"{path} (committed)",
            tofile=f"{path} (generated)",
            lineterm="",
            n=2,
        )
    )
    print(f"{label}: drift detected in {path}", file=sys.stderr)
    for line in diff[:80]:
        print(line, file=sys.stderr)
    if len(diff) > 80:
        print(f"... {len(diff) - 80} more diff lines", file=sys.stderr)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--mojo", type=Path, default=DEFAULT_MOJO)
    args = parser.parse_args(argv)

    installed = importlib.metadata.version("rapidfuzz")
    if installed != REFERENCE_VERSION:
        parser.exit(
            2,
            f"rapidfuzz {REFERENCE_VERSION} required, found {installed}. "
            "Install libraries/levenshtein/python_reference/requirements.txt.\n",
        )
    if Indel.normalized_similarity("kitten", "sitting") != 0.6153846153846154:
        parser.exit(2, "oracle self-check failed: ratio is not Indel similarity.\n")

    cases = build_cases()
    bundle = build_bundle(cases)
    bundle_text = _json_text(bundle)
    mojo_text = build_mojo(cases)

    if args.check:
        ok = _check(args.bundle, bundle_text, "bundle")
        ok = _check(args.mojo, mojo_text, "mojo") and ok
        if ok:
            print(f"vectors: {len(cases)} cases, committed artifacts are current")
        return 0 if ok else 1

    _write(args.bundle, bundle_text)
    _write(args.mojo, mojo_text)
    print(f"vectors: wrote {len(cases)} cases to {args.bundle} and {args.mojo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
