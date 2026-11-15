"""Reference probe suite for CPython's ``audioop`` module.

Runs only against the real CPython 3.12 ``audioop`` (stdlib C extension) and
records exact outputs and exceptions. No Mojo code, no reimplementation.

Usage::

    libraries/audioop/python_reference/.venv/bin/python \
        libraries/audioop/python_reference/probe_audioop.py --out /tmp/audioop-probes.json

The output JSON is the authoritative record for the behaviours documented in
``docs/reference-audit.md`` and is reused by ``verify_reference.py`` to prove
that the installed build matches the pristine upstream source.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import struct
import sys
import warnings
from typing import Any

SEED = 20260610
WIDTHS = (1, 2, 3, 4)
RANGES = {
    1: (-128, 127),
    2: (-32768, 32767),
    3: (-8388608, 8388607),
    4: (-2147483648, 2147483647),
}


_MODULE: Any = None


def require_reference() -> Any:
    """Import the real standard-library audioop, refusing anything else."""
    global _MODULE
    if _MODULE is not None:
        return _MODULE
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"probe_audioop: need CPython 3.12, got {sys.version.split()[0]}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import audioop  # noqa: PLC0415

    if audioop.__name__ != "audioop" or "lib-dynload" not in str(audioop.__file__):
        raise SystemExit(f"probe_audioop: unexpected module at {audioop.__file__}")
    _MODULE = audioop
    return audioop


def pack(samples: tuple[int, ...], width: int) -> bytes:
    """Encode signed samples in the reference's native byte order."""
    return b"".join(int(s).to_bytes(width, sys.byteorder, signed=True) for s in samples)


def unpack(data: bytes, width: int) -> tuple[int, ...]:
    return tuple(
        int.from_bytes(data[i : i + width], sys.byteorder, signed=True)
        for i in range(0, len(data), width)
    )


def extremes(width: int) -> tuple[int, ...]:
    lo, hi = RANGES[width]
    return (0, 1, -1, lo, hi, lo + 1, hi - 1, (lo + hi) // 2, -(hi // 2) - 1)


def random_walk(rng: random.Random, width: int, n: int) -> tuple[int, ...]:
    lo, hi = RANGES[width]
    value = 0
    out = []
    for _ in range(n):
        value = max(lo, min(hi, value + rng.randint(-hi // 8 - 1, hi // 8 + 1)))
        out.append(value)
    return tuple(out)


def enc(value: Any) -> dict[str, Any]:
    """JSON-safe, lossless encoding of a reference value."""
    if value is None:
        return {"type": "none"}
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {"type": "bytes", "hex": raw.hex(), "length": len(raw)}
    if isinstance(value, bool):
        return {"type": "int", "value": int(value)}
    if isinstance(value, int):
        return {"type": "int", "value": value}
    if isinstance(value, float):
        return {"type": "float", "repr": repr(value)}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [enc(item) for item in value]}
    raise TypeError(f"cannot encode {type(value)!r}")


def dec(value: dict[str, Any]) -> Any:
    """Inverse of enc() for values accepted by the reference functions."""
    kind = value["type"]
    if kind == "none":
        return None
    if kind == "bytes":
        return bytes.fromhex(value["hex"])
    if kind == "int":
        return value["value"]
    if kind == "float":
        return float(value["repr"])
    if kind == "str":
        return value["value"]
    if kind == "tuple":
        return tuple(dec(item) for item in value["items"])
    raise TypeError(f"cannot decode {kind!r}")


def enc_float_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """NaN-aware equality for encoded values (used by verify_reference.py)."""
    if left == right:
        return True
    if left.get("type") == "float" and right.get("type") == "float":
        return math.isnan(float(left["repr"])) and math.isnan(float(right["repr"]))
    if left.get("type") == "tuple" and right.get("type") == "tuple":
        return len(left["items"]) == len(right["items"]) and all(
            enc_float_equal(a, b) for a, b in zip(left["items"], right["items"], strict=True)
        )
    return False


def _case(cid: str, op: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "id": cid,
        "op": op,
        "args": [enc(a) for a in args],
        "kwargs": {k: enc(v) for k, v in kwargs.items()},
    }


def build_cases() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    cases: list[dict[str, Any]] = []

    def add(cid: str, op: str, *args: Any, **kwargs: Any) -> None:
        cases.append(_case(cid, op, *args, **kwargs))

    # ---- sample representation and validation -----------------------------
    for width in WIDTHS:
        lo, hi = RANGES[width]
        frag = pack((lo, -1, 0, 1, hi), width)
        add(f"repr/roundtrip/w{width}", "probe_roundtrip", frag, width)
        add(f"repr/getsample/w{width}/first", "getsample", frag, width, 0)
        add(f"repr/getsample/w{width}/last", "getsample", frag, width, 4)
        add(f"repr/getsample/w{width}/negative", "getsample", frag, width, -1)
        add(f"repr/getsample/w{width}/past-end", "getsample", frag, width, 5)

    add("repr/getsample/empty", "getsample", b"", 2, 0)
    add("repr/bytes/empty-max", "max", b"", 2)
    add("repr/bytes/empty-minmax", "minmax", b"", 2)
    add("repr/bytes/empty-avg", "avg", b"", 2)
    add("repr/bytes/empty-rms", "rms", b"", 2)
    add("repr/bytes/empty-cross", "cross", b"", 2)
    add("repr/bytes/empty-maxpp", "maxpp", b"", 2)
    add("repr/bytes/empty-avgpp", "avgpp", b"", 2)
    add("repr/bytes/empty-add", "add", b"", b"", 2)
    add("repr/bytes/empty-mul", "mul", b"", 2, 2.0)
    add("repr/bytes/empty-reverse", "reverse", b"", 2)
    add("repr/bytes/empty-byteswap", "byteswap", b"", 2)
    add("repr/bytes/empty-tomono", "tomono", b"", 2, 1.0, 1.0)
    add("repr/bytes/empty-tostereo", "tostereo", b"", 2, 1.0, 1.0)
    add("repr/bytes/empty-lin2lin", "lin2lin", b"", 2, 2)
    add("repr/bytes/empty-lin2ulaw", "lin2ulaw", b"", 2)
    add("repr/bytes/empty-lin2alaw", "lin2alaw", b"", 2)
    add("repr/bytes/empty-ulaw2lin", "ulaw2lin", b"", 2)
    add("repr/bytes/empty-alaw2lin", "alaw2lin", b"", 2)
    add("repr/bytes/empty-lin2adpcm", "lin2adpcm", b"", 2, None)
    add("repr/bytes/empty-adpcm2lin", "adpcm2lin", b"", 2, None)

    # byte order is native, not a parameter: same bytes read differently
    be_bytes = (1).to_bytes(2, "big", signed=True) + (-2).to_bytes(2, "big", signed=True)
    add("repr/byteorder/native-read", "minmax", be_bytes, 2)
    add("repr/byteorder/byteswap", "byteswap", be_bytes, 2)

    # invalid / unusual width and fragments
    for bad_width in (0, 5, -1, 100):
        add(f"invalid/width/{bad_width}", "max", b"\x00\x00", bad_width)
    for width in WIDTHS:
        add(f"invalid/width/{width}/newsupersample", "lin2lin", pack((0,), width), width, 5)
    for width in (2, 3, 4):
        add(f"invalid/padding/w{width}", "max", b"\x00" * (width + 1), width)
    add("invalid/getsample/padding", "getsample", b"\x00" * 3, 2, 0)
    add("invalid/tomono/odd-frames", "tomono", pack((0, 0, 0), 2), 2, 1.0, 1.0)
    add("invalid/add/length-mismatch", "add", pack((0,), 2), pack((0, 0), 2), 2)
    add("invalid/width/float", "max", b"\x00\x00", 2.0)
    add("invalid/fragment/str", "max", "aa", 2)
    add("invalid/fragment/int", "max", 3, 2)
    add("invalid/bias/overflow", "bias", b"\x00\x00", 2, 2**31)
    add("invalid/ratecv/bad-rate", "ratecv", b"\x00\x00", 2, 1, 0, 8000, None)
    add("invalid/ratecv/bad-channels", "ratecv", b"\x00\x00", 2, 0, 8000, 8000, None)
    add("invalid/ratecv/bad-weights", "ratecv", b"\x00\x00", 2, 1, 8000, 8000, None, 0, 0)
    add("invalid/ratecv/bad-state", "ratecv", b"\x00\x00", 2, 1, 8000, 8000, (1,))
    add("invalid/ratecv/state-type", "ratecv", b"\x00\x00", 2, 1, 8000, 8000, 7)
    add("invalid/adpcm/state-type", "lin2adpcm", b"\x00\x00", 2, 7)
    add("invalid/adpcm/state-range", "lin2adpcm", b"\x00\x00", 2, (0x8000, 0))
    add("invalid/adpcm/state-index", "lin2adpcm", b"\x00\x00", 2, (0, 89))
    add("invalid/adpcm/state-arity", "lin2adpcm", b"\x00\x00", 2, (0, 0, 0))
    add("invalid/adpcm/decode-state-type", "adpcm2lin", b"\x00", 2, 7)

    # ---- arithmetic --------------------------------------------------------
    for width in WIDTHS:
        lo, hi = RANGES[width]
        vals = extremes(width)
        frag = pack(vals, width)
        add(f"add/w{width}/extremes", "add", frag, frag, width)
        add(f"add/w{width}/overflow", "add", pack((hi,), width), pack((hi,), width), width)
        add(f"add/w{width}/underflow", "add", pack((lo,), width), pack((lo,), width), width)
        add(f"bias/w{width}/zero", "bias", frag, width, 0)
        add(f"bias/w{width}/positive", "bias", frag, width, 17)
        add(f"bias/w{width}/negative", "bias", frag, width, -17)
        add(f"bias/w{width}/wrap", "bias", frag, width, hi)
        add(f"bias/w{width}/wrap-negative", "bias", frag, width, lo)
        add(f"reverse/w{width}/extremes", "reverse", frag, width)
        add(f"byteswap/w{width}/extremes", "byteswap", frag, width)
        for factor in (0.0, 1.0, -1.0, 0.5, 2.0, 100.0, -100.0, 1.0 / 3.0):
            add(f"mul/w{width}/f{factor!r}", "mul", frag, width, factor)
        add(f"mul/w{width}/nan", "mul", frag, width, float("nan"))
        add(f"mul/w{width}/inf", "mul", frag, width, float("inf"))

    # rounding direction of fbound (floor, then clamp)
    add("mul/rounding/negative", "mul", pack((-3, -1, 0, 1, 3), 2), 2, 0.5)
    add("mul/rounding/positive", "mul", pack((-3, -1, 0, 1, 3), 2), 2, 1.5)
    add("mul/rounding/clip-low", "mul", pack((-32768,), 2), 2, 1.0)
    add("mul/rounding/clip-just-below", "mul", pack((-32767,), 2), 2, 1.0001)

    # ---- conversion --------------------------------------------------------
    for src in WIDTHS:
        for dst in WIDTHS:
            add(f"lin2lin/w{src}-to-w{dst}", "lin2lin", pack(extremes(src), src), src, dst)
    add("lin2lin/truncation/16-to-8", "lin2lin", pack((255, 256, -1, -256), 2), 2, 1)
    add("lin2lin/expansion/8-to-32", "lin2lin", pack((-128, -1, 0, 127), 1), 1, 4)

    # ---- analysis ----------------------------------------------------------
    for width in WIDTHS:
        frag = pack(extremes(width), width)
        add(f"max/w{width}/extremes", "max", frag, width)
        add(f"minmax/w{width}/extremes", "minmax", frag, width)
        add(f"avg/w{width}/extremes", "avg", frag, width)
        add(f"rms/w{width}/extremes", "rms", frag, width)
        add(f"maxpp/w{width}/extremes", "maxpp", frag, width)
        add(f"avgpp/w{width}/extremes", "avgpp", frag, width)
        add(f"cross/w{width}/extremes", "cross", frag, width)
        add(f"max/w{width}/single", "max", pack((RANGES[width][0],), width), width)
        add(f"max/w{width}/all-min", "max", pack((RANGES[width][0],) * 3, width), width)
        add(f"minmax/w{width}/single", "minmax", pack((7,), width), width)
        add(f"cross/w{width}/single", "cross", pack((7,), width), width)
        add(f"cross/w{width}/zeros", "cross", pack((0, 0, 0), width), width)
        add(f"rms/w{width}/all-min", "rms", pack((RANGES[width][0],) * 5, width), width)

    add("avg/rounding/negative", "avg", pack((-1, -2), 2), 2)
    add("avg/rounding/positive", "avg", pack((1, 2), 2), 2)
    add("rms/rounding/truncate", "rms", pack((3, 0), 2), 2)
    add("max/absolute-min-32", "max", pack((-2147483648,), 4), 4)

    wave = pack((-100, -50, 0, 50, 100, 50, 0, -50, -100), 2)
    add("maxpp/waveform", "maxpp", wave, 2)
    add("avgpp/waveform", "avgpp", wave, 2)
    add("cross/waveform", "cross", wave, 2)
    add("reverse/waveform", "reverse", wave, 2)

    # ---- channel conversion -------------------------------------------------
    stereo = pack((-1000, 1000, 2000, -2000, 32767, -32768), 2)
    add("tomono/basic", "tomono", stereo, 2, 0.5, 0.5)
    add("tomono/weights", "tomono", stereo, 2, 1.0, 2.0)
    add("tomono/clip", "tomono", stereo, 2, 2.0, 2.0)
    add("tomono/negative-weights", "tomono", stereo, 2, -1.0, -1.0)
    mono = pack((-1000, 0, 1000), 2)
    add("tostereo/basic", "tostereo", mono, 2, 0.5, 0.5)
    add("tostereo/weights", "tostereo", mono, 2, 1.0, 2.0)
    add("tostereo/clip", "tostereo", mono, 2, 10.0, -10.0)
    for width in WIDTHS:
        pair = pack((RANGES[width][0], RANGES[width][1]), width)
        add(f"tomono/w{width}", "tomono", pair, width, 0.5, 0.5)
        add(f"tostereo/w{width}", "tostereo", pair, width, 1.0, 1.0)

    # ---- rate conversion ----------------------------------------------------
    ramp = pack(tuple(range(-10, 10)), 2)
    add("ratecv/upsample", "ratecv", ramp, 2, 1, 8000, 16000, None)
    add("ratecv/downsample", "ratecv", ramp, 2, 1, 16000, 8000, None)
    add("ratecv/same-rate", "ratecv", ramp, 2, 1, 8000, 8000, None)
    add("ratecv/empty", "ratecv", b"", 2, 1, 8000, 16000, None)
    add("ratecv/weights", "ratecv", ramp, 2, 1, 8000, 16000, None, 3, 1)
    add("ratecv/weights-reduced", "ratecv", ramp, 2, 1, 8000, 16000, None, 6, 2)
    add("ratecv/stereo", "ratecv", stereo, 2, 2, 8000, 16000, None)
    add("ratecv/w1", "ratecv", pack((0, 50, 100, -50), 1), 1, 1, 8000, 11025, None)
    add("ratecv/w3", "ratecv", pack((0, 500000, -500000, 8388607), 3), 3, 1, 8000, 4000, None)
    add("ratecv/w4", "ratecv", pack((0, 10**9, -(10**9)), 4), 4, 2, 8000, 16000, None)
    state = audioop_state_after_first_half(ramp[:10], 2, 1, 8000, 16000)
    add("ratecv/state-continuation", "ratecv", ramp[10:], 2, 1, 8000, 16000, state)
    add("ratecv/state-initial", "ratecv", ramp, 2, 1, 8000, 16000, (-16000, ((0, 0),)))
    add("ratecv/irrational-ratio", "ratecv", ramp, 2, 1, 44100, 48000, None)
    add("ratecv/zero-input-frames", "ratecv", b"", 2, 2, 8000, 16000, None)

    # ---- companding ---------------------------------------------------------
    for width in WIDTHS:
        frag = pack(extremes(width), width)
        add(f"lin2ulaw/w{width}", "lin2ulaw", frag, width)
        add(f"lin2alaw/w{width}", "lin2alaw", frag, width)
    add("lin2ulaw/sweep16", "lin2ulaw", pack(tuple(range(-32768, 32768, 257)), 2), 2)
    add("lin2alaw/sweep16", "lin2alaw", pack(tuple(range(-32768, 32768, 257)), 2), 2)
    add(
        "lin2ulaw/segment-boundaries",
        "lin2ulaw",
        pack(
            tuple(
                v
                for e in (0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF, 0x3FFF)
                for v in (e - 1, e, e + 1, -e + 1, -e, -e - 1)
            ),
            2,
        ),
        2,
    )
    add(
        "lin2alaw/segment-boundaries",
        "lin2alaw",
        pack(
            tuple(
                v
                for e in (0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF)
                for v in (e - 1, e, e + 1, -e + 1, -e, -e - 1)
            ),
            2,
        ),
        2,
    )
    add("ulaw2lin/all-bytes", "ulaw2lin", bytes(range(256)), 2)
    add("alaw2lin/all-bytes", "alaw2lin", bytes(range(256)), 2)
    for width in WIDTHS:
        add(f"ulaw2lin/all-bytes-w{width}", "ulaw2lin", bytes(range(256)), width)
        add(f"alaw2lin/all-bytes-w{width}", "alaw2lin", bytes(range(256)), width)

    # ---- ADPCM --------------------------------------------------------------
    for width in WIDTHS:
        samples = random_walk(rng, width, 33)
        add(f"lin2adpcm/w{width}/walk", "lin2adpcm", pack(samples, width), width, None)
        add(
            f"lin2adpcm/w{width}/single", "lin2adpcm", pack((RANGES[width][0],), width), width, None
        )
        add(f"lin2adpcm/w{width}/state", "lin2adpcm", pack(samples, width), width, (1000, 40))
    add("lin2adpcm/odd-sample-count", "lin2adpcm", pack((100, 200, 300), 2), 2, None)
    add("lin2adpcm/one-sample", "lin2adpcm", pack((100,), 2), 2, None)
    add("adpcm2lin/all-nibbles", "adpcm2lin", bytes(range(256)), 2, None)
    add("adpcm2lin/all-nibbles-state", "adpcm2lin", bytes(range(256)), 2, (-1000, 20))
    add("adpcm2lin/odd-byte-count", "adpcm2lin", b"\x01\x02\x03", 2, None)
    add("adpcm2lin/widths", "adpcm2lin", b"\x12\x34", 3, None)
    for width in WIDTHS:
        add(f"adpcm2lin/w{width}", "adpcm2lin", bytes(range(0, 64)), width, None)
        add(
            f"adpcm/roundtrip/w{width}",
            "adpcm_roundtrip",
            pack(random_walk(rng, width, 17), width),
            width,
        )

    # ---- matching -----------------------------------------------------------
    ref = pack((1000, -2000, 3000, -4000), 2)
    hay = pack((0, 0, 900, -1800, 2700, -3600, 0, 0), 2)
    add("findfactor/basic", "findfactor", hay, ref)
    add("findfactor/identical", "findfactor", ref, ref)
    add("findfactor/zeros-reference", "findfactor", ref, pack((0, 0, 0, 0), 2))
    add("findfactor/zeros-both", "findfactor", pack((0, 0), 2), pack((0, 0), 2))
    add("findfactor/empty-both", "findfactor", b"", b"")
    add("findfactor/length-mismatch", "findfactor", hay, pack((0,), 2))
    add("findfactor/odd-length", "findfactor", b"\x00\x00\x00", ref)
    add("findfit/basic", "findfit", hay, ref)
    add("findfit/identical", "findfit", ref, ref)
    add("findfit/reference-longer", "findfit", ref, hay)
    add("findfit/zeros-reference", "findfit", hay, pack((0, 0, 0, 0), 2))
    add("findfit/empty-both", "findfit", b"", b"")
    add("findfit/odd-length", "findfit", b"\x00", ref)
    add("findmax/basic", "findmax", hay, 4)
    add("findmax/length-zero", "findmax", hay, 0)
    add("findmax/length-negative", "findmax", hay, -1)
    add("findmax/length-in-range", "findmax", hay, 5)
    add("findmax/length-equal", "findmax", hay, 8)
    add("findmax/length-greater", "findmax", hay, 9)
    add("probe/error-type", "probe_error_type")
    add("findmax/empty-zero", "findmax", b"", 0)
    add("findmax/odd-length", "findmax", b"\x00", 0)

    # ---- randomized differential corpus -------------------------------------
    for width in WIDTHS:
        for index in range(3):
            left = random_walk(rng, width, 40 + index * 7)
            right = random_walk(rng, width, 40 + index * 7)
            add(f"random/w{width}/{index}/add", "add", pack(left, width), pack(right, width), width)
            add(
                f"random/w{width}/{index}/mul",
                "mul",
                pack(left, width),
                width,
                (index - 1) * 0.75 + 0.5,
            )
            add(f"random/w{width}/{index}/rms", "rms", pack(left, width), width)
            add(f"random/w{width}/{index}/avgpp", "avgpp", pack(left, width), width)
            add(f"random/w{width}/{index}/ulaw", "lin2ulaw", pack(left, width), width)
            add(f"random/w{width}/{index}/alaw", "lin2alaw", pack(left, width), width)
            add(
                f"random/w{width}/{index}/adpcm",
                "lin2adpcm",
                pack(left[: len(left) // 2 * 2], width),
                width,
                None,
            )

    return cases


def audioop_state_after_first_half(
    fragment: bytes, width: int, nchannels: int, inrate: int, outrate: int
) -> tuple[Any, ...]:
    """Return the continuation state produced by the real reference module."""
    return require_reference().ratecv(fragment, width, nchannels, inrate, outrate, None)[1]


def _call(module: Any, op: str, args: list[Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    if op == "probe_error_type":
        return enc(tuple(cls.__name__ for cls in module.error.__mro__))
    if op == "probe_roundtrip":
        fragment, width = (dec(a) for a in args)
        return enc(unpack(fragment, width))
    if op == "adpcm_roundtrip":
        fragment, width = (dec(a) for a in args)
        encoded, state = module.lin2adpcm(fragment, width, None)
        decoded, state2 = module.adpcm2lin(encoded, width, state)
        return enc((encoded, state, decoded, state2))
    return enc(
        getattr(module, op)(*(dec(a) for a in args), **{k: dec(v) for k, v in kwargs.items()})
    )


def run_cases(module: Any, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        record = {"id": case["id"], "op": case["op"]}
        try:
            record["result"] = _call(module, case["op"], case["args"], case["kwargs"])
        except BaseException as exc:  # noqa: BLE001 - exceptions are data here
            record["exception"] = {
                "type": type(exc).__name__,
                "module": type(exc).__module__,
                "message": str(exc),
            }
        results.append(record)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=argparse.FileType("w"), default="-")
    args = parser.parse_args(argv)

    audioop = require_reference()
    cases = build_cases()
    results = run_cases(audioop, cases)
    report = {
        "reference": {
            "module": audioop.__name__,
            "file": audioop.__file__,
            "python": sys.version,
            "implementation": sys.implementation.name,
            "byteorder": sys.byteorder,
            "pointer_bits": 8 * struct.calcsize("P"),
            "seed": SEED,
        },
        "case_count": len(cases),
        "cases": results,
    }
    json.dump(report, args.out, indent=1, sort_keys=True)
    args.out.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
