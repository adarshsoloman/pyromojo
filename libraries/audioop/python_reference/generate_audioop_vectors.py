"""Generate the representative audioop golden corpus from CPython 3.12.

Run with the isolated reference interpreter (audioop was removed in 3.13):

    libraries/audioop/python_reference/.venv/bin/python \
        libraries/audioop/python_reference/generate_audioop_vectors.py

Phase 0 cases cover one or two calls per operation. Phase 1 adds
``sample_decode`` and ``sample_encode`` cases for the internal sample
representation layer: decoding is generated with ``audioop.getsample``
(the reference's only sample-level oracle), and encoding is the canonical
native-order two's-complement bytes validated by decoding each value back
through ``getsample``. Invalid-value encode cases record the port's
documented range check because the reference exposes no encoder; the
boundaries themselves come from the reference's signed ranges.

Output is deterministic; re-running must reproduce the file byte for byte.
Pass ``--check`` to compare without writing (used by CI/dev tooling).
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
import warnings
from pathlib import Path

warnings.simplefilter("ignore", DeprecationWarning)

try:
    import audioop
except ImportError as exc:  # pragma: no cover - guards the wrong interpreter
    raise SystemExit(
        "audioop is unavailable; run this with libraries/audioop/python_reference/.venv/bin/python"
    ) from exc

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "libraries" / "audioop" / "tests" / "vectors" / "audioop_vectors.json"

SCHEMA_VERSION = "1.0.0"
SEED = 20260610


def pcm(*samples: int) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def pcm_w(width: int, *samples: int) -> bytes:
    return b"".join(value.to_bytes(width, sys.byteorder, signed=True) for value in samples)


def hexed(data: bytes) -> str:
    return data.hex()


def value_of(result: object) -> object:
    if isinstance(result, float):
        if result != result:
            return "nan"
        if result == float("inf"):
            return "inf"
        if result == float("-inf"):
            return "-inf"
        return result
    if isinstance(result, (bytes, bytearray)):
        return {"result_hex": bytes(result).hex()}
    if isinstance(result, tuple):
        return [value_of(item) for item in result]
    return result


def case(
    case_id: str,
    op: str,
    *,
    width: int | None = None,
    args: dict[str, object] | None = None,
    call,
    notes: str | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": case_id,
        "op": op,
    }
    if width is not None:
        entry["width"] = width
    entry["args"] = args or {}
    try:
        result = call()
    except Exception as exc:  # the reference defines these messages
        entry["expected"] = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
    else:
        if isinstance(result, bytes):
            entry["expected"] = {"result_hex": hexed(result)}
        elif isinstance(result, tuple) and result and isinstance(result[0], bytes):
            entry["expected"] = {
                "result_hex": hexed(result[0]),
                "state": value_of(result[1]),
            }
        else:
            entry["expected"] = {"value": value_of(result)}
    if notes:
        entry["notes"] = notes
    return entry


def build_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []

    # --- arithmetic -------------------------------------------------------
    left = pcm(1000, -2000, 30000, -32768)
    right = pcm(500, -500, 1000, -1)
    for width, name in ((2, "w2"),):
        cases.append(
            case(
                f"add-{name}",
                "add",
                width=width,
                args={
                    "fragment1_hex": hexed(left),
                    "fragment2_hex": hexed(right),
                },
                call=lambda width=width: audioop.add(left, right, width),
                notes="clamps at both 16-bit extremes",
            )
        )
    cases.append(
        case(
            "add-w1",
            "add",
            width=1,
            args={"fragment1_hex": "7f80", "fragment2_hex": "0101"},
            call=lambda: audioop.add(bytes([0x7F, 0x80]), bytes([1, 1]), 1),
        )
    )
    cases.append(
        case(
            "add-empty",
            "add",
            width=2,
            args={"fragment1_hex": "", "fragment2_hex": ""},
            call=lambda: audioop.add(b"", b"", 2),
        )
    )
    cases.append(
        case(
            "add-bad-width",
            "add",
            width=5,
            args={"fragment1_hex": "", "fragment2_hex": ""},
            call=lambda: audioop.add(b"", b"", 5),
        )
    )
    cases.append(
        case(
            "add-ragged",
            "add",
            width=2,
            args={"fragment1_hex": "0102", "fragment2_hex": "0102"},
            call=lambda: audioop.add(b"\x01\x02\x03", b"\x04\x05\x06", 2),
            notes="three bytes at width two is not a whole number of frames",
        )
    )

    cases.append(
        case(
            "bias-w2",
            "bias",
            width=2,
            args={"fragment_hex": hexed(left), "bias": 10000},
            call=lambda: audioop.bias(left, 2, 10000),
            notes="wraps, it does not clamp",
        )
    )
    cases.append(
        case(
            "mul-w2-fraction",
            "mul",
            width=2,
            args={"fragment_hex": hexed(pcm(3, -3, 1, 2)), "factor": 0.5},
            call=lambda: audioop.mul(pcm(3, -3, 1, 2), 2, 0.5),
            notes="floor-then-clamp: 3*0.5=1, -3*0.5=-2",
        )
    )
    cases.append(
        case(
            "mul-w2-nan",
            "mul",
            width=2,
            args={"fragment_hex": hexed(pcm(1, -1)), "factor": "nan"},
            call=lambda: audioop.mul(pcm(1, -1), 2, float("nan")),
            notes="reference result is undefined behaviour; recorded as observed",
        )
    )
    cases.append(
        case(
            "mul-w2-inf",
            "mul",
            width=2,
            args={"fragment_hex": hexed(pcm(1, -1, 0)), "factor": "inf"},
            call=lambda: audioop.mul(pcm(1, -1, 0), 2, float("inf")),
        )
    )

    # --- statistics ------------------------------------------------------
    stats_fragment = pcm(100, -200, 300, -32768)
    for op_name in ("max", "avg", "rms", "avgpp", "maxpp"):
        cases.append(
            case(
                f"{op_name}-w2",
                op_name,
                width=2,
                args={"fragment_hex": hexed(stats_fragment)},
                call=lambda op_name=op_name: getattr(audioop, op_name)(stats_fragment, 2),
            )
        )
    cases.append(
        case(
            "minmax-empty",
            "minmax",
            width=2,
            args={"fragment_hex": ""},
            call=lambda: audioop.minmax(b"", 2),
            notes="empty returns the sentinel pair from the reference",
        )
    )
    cases.append(
        case(
            "minmax-w2",
            "minmax",
            width=2,
            args={"fragment_hex": hexed(stats_fragment)},
            call=lambda: audioop.minmax(stats_fragment, 2),
        )
    )
    cases.append(
        case(
            "cross-w2",
            "cross",
            width=2,
            args={"fragment_hex": hexed(pcm(1, -1, 1, -1))},
            call=lambda: audioop.cross(pcm(1, -1, 1, -1), 2),
            notes="counts sign changes; starts at -1 so an all-positive run yields 0",
        )
    )
    cases.append(
        case(
            "cross-empty",
            "cross",
            width=2,
            args={"fragment_hex": ""},
            call=lambda: audioop.cross(b"", 2),
            notes="empty input returns the -1 sentinel",
        )
    )
    cases.append(
        case(
            "findfactor-w2",
            "findfactor",
            width=2,
            args={
                "fragment_hex": hexed(pcm(1000, -2000, 3000)),
                "reference_hex": hexed(pcm(500, -1000, 1500)),
            },
            call=lambda: audioop.findfactor(pcm(1000, -2000, 3000), pcm(500, -1000, 1500)),
        )
    )
    cases.append(
        case(
            "findfactor-empty",
            "findfactor",
            width=2,
            args={"fragment_hex": "", "reference_hex": ""},
            call=lambda: audioop.findfactor(b"", b""),
            notes="fixed 16-bit; C double division by zero yields nan",
        )
    )
    cases.append(
        case(
            "findfit-empty",
            "findfit",
            width=2,
            args={"fragment_hex": "", "reference_hex": ""},
            call=lambda: audioop.findfit(b"", b""),
            notes="fixed 16-bit; factor is nan when both inputs are empty",
        )
    )
    cases.append(
        case(
            "findfit-w2",
            "findfit",
            width=2,
            args={
                "fragment_hex": hexed(pcm(1000, -2000, 3000, -4000)),
                "reference_hex": hexed(pcm(500, -1000, 1500, -2000)),
            },
            call=lambda: audioop.findfit(
                pcm(1000, -2000, 3000, -4000), pcm(500, -1000, 1500, -2000)
            ),
        )
    )
    cases.append(
        case(
            "findmax-w2",
            "findmax",
            width=2,
            args={
                "fragment_hex": hexed(pcm(0, 100, 200, 300)),
                "length": 2,
            },
            call=lambda: audioop.findmax(pcm(0, 100, 200, 300), 2),
        )
    )
    cases.append(
        case(
            "findmax-too-short",
            "findmax",
            width=2,
            args={"fragment_hex": hexed(pcm(0, 1)), "length": 3},
            call=lambda: audioop.findmax(pcm(0, 1), 3),
            notes="length is in 16-bit samples; fixed width, no width argument",
        )
    )

    # --- fragments -------------------------------------------------------
    stereo = pcm(1000, 2000, 3000, 4000)
    cases.append(
        case(
            "reverse-w2",
            "reverse",
            width=2,
            args={"fragment_hex": hexed(pcm(1, 2, 3))},
            call=lambda: audioop.reverse(pcm(1, 2, 3), 2),
        )
    )
    cases.append(
        case(
            "getsample-w2",
            "getsample",
            width=2,
            args={"fragment_hex": hexed(stereo), "index": 2},
            call=lambda: audioop.getsample(stereo, 2, 2),
        )
    )
    cases.append(
        case(
            "getsample-out-of-range",
            "getsample",
            width=2,
            args={"fragment_hex": hexed(stereo), "index": 4},
            call=lambda: audioop.getsample(stereo, 2, 4),
        )
    )
    cases.append(
        case(
            "byteswap-w2",
            "byteswap",
            width=2,
            args={"fragment_hex": hexed(pcm(1, 256, -2))},
            call=lambda: audioop.byteswap(pcm(1, 256, -2), 2),
        )
    )

    # --- linear conversions ---------------------------------------------
    cases.append(
        case(
            "lin2lin-w2-to-w1",
            "lin2lin",
            width=2,
            args={
                "fragment_hex": hexed(pcm(256, 255, -256, -255)),
                "new_width": 1,
            },
            call=lambda: audioop.lin2lin(pcm(256, 255, -256, -255), 2, 1),
            notes="down-conversion truncates via arithmetic shift",
        )
    )
    cases.append(
        case(
            "lin2lin-w1-to-w3",
            "lin2lin",
            width=1,
            args={"fragment_hex": "7f80ff00", "new_width": 3},
            call=lambda: audioop.lin2lin(bytes([0x7F, 0x80, 0xFF, 0x00]), 1, 3),
        )
    )
    cases.append(
        case(
            "lin2lin-w4-to-w2",
            "lin2lin",
            width=4,
            args={
                "fragment_hex": struct.pack("<2i", 32768, -32769).hex(),
                "new_width": 2,
            },
            call=lambda: audioop.lin2lin(struct.pack("<2i", 32768, -32769), 4, 2),
        )
    )

    # --- u-law / A-law ---------------------------------------------------
    lin = pcm(0, 1000, -1000, 32767, -32768)
    ulaw = audioop.lin2ulaw(lin, 2)
    alaw = audioop.lin2alaw(lin, 2)
    cases.append(
        case(
            "lin2ulaw-w2",
            "lin2ulaw",
            width=2,
            args={"fragment_hex": hexed(lin)},
            call=lambda: audioop.lin2ulaw(lin, 2),
        )
    )
    cases.append(
        case(
            "ulaw2lin-w2",
            "ulaw2lin",
            width=2,
            args={"fragment_hex": hexed(ulaw), "new_width": 2},
            call=lambda: audioop.ulaw2lin(ulaw, 2),
        )
    )
    cases.append(
        case(
            "lin2alaw-w2",
            "lin2alaw",
            width=2,
            args={"fragment_hex": hexed(lin)},
            call=lambda: audioop.lin2alaw(lin, 2),
        )
    )
    cases.append(
        case(
            "alaw2lin-w2",
            "alaw2lin",
            width=2,
            args={"fragment_hex": hexed(alaw), "new_width": 2},
            call=lambda: audioop.alaw2lin(alaw, 2),
        )
    )

    # --- ADPCM -----------------------------------------------------------
    adpcm_source = pcm(0, 1000, 2000, 3000, 4000)
    adpcm_bytes, _ = audioop.lin2adpcm(adpcm_source, 2, None)
    cases.append(
        case(
            "lin2adpcm-w2",
            "lin2adpcm",
            width=2,
            args={"fragment_hex": hexed(adpcm_source), "state": None},
            call=lambda: audioop.lin2adpcm(adpcm_source, 2, None),
            notes="returns (encoded bytes, state tuple)",
        )
    )
    cases.append(
        case(
            "lin2adpcm-odd-sample",
            "lin2adpcm",
            width=2,
            args={"fragment_hex": hexed(pcm(0, 1000, 2000)), "state": None},
            call=lambda: audioop.lin2adpcm(pcm(0, 1000, 2000), 2, None),
            notes="trailing odd sample is dropped by the reference",
        )
    )
    cases.append(
        case(
            "adpcm2lin-w2",
            "adpcm2lin",
            width=2,
            args={"fragment_hex": hexed(adpcm_bytes), "new_width": 2, "state": None},
            call=lambda: audioop.adpcm2lin(adpcm_bytes, 2, None),
        )
    )

    # --- rate conversion -------------------------------------------------
    rate_source = pcm(*range(20))
    rate_bytes, _ = audioop.ratecv(rate_source, 2, 1, 8000, 16000, None)
    cases.append(
        case(
            "ratecv-upsample",
            "ratecv",
            width=2,
            args={
                "fragment_hex": hexed(rate_source),
                "nchannels": 1,
                "inrate": 8000,
                "outrate": 16000,
                "state": None,
            },
            call=lambda: audioop.ratecv(rate_source, 2, 1, 8000, 16000, None),
        )
    )
    cases.append(
        case(
            "ratecv-downsample",
            "ratecv",
            width=2,
            args={
                "fragment_hex": hexed(rate_source),
                "nchannels": 1,
                "inrate": 16000,
                "outrate": 8000,
                "state": None,
            },
            call=lambda: audioop.ratecv(rate_source, 2, 1, 16000, 8000, None),
        )
    )

    # --- stereo ----------------------------------------------------------
    cases.append(
        case(
            "tomono-w2",
            "tomono",
            width=2,
            args={"fragment_hex": hexed(stereo), "lfactor": 0.5, "rfactor": 0.5},
            call=lambda: audioop.tomono(stereo, 2, 0.5, 0.5),
        )
    )
    cases.append(
        case(
            "tostereo-w2",
            "tostereo",
            width=2,
            args={
                "fragment_hex": hexed(pcm(1000, -1000)),
                "lfactor": 0.5,
                "rfactor": 0.25,
            },
            call=lambda: audioop.tostereo(pcm(1000, -1000), 2, 0.5, 0.25),
        )
    )

    return cases


def sample_decode_case(
    case_id: str,
    width: int,
    fragment: bytes,
    *,
    notes: str | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": case_id,
        "op": "sample_decode",
        "width": width,
        "args": {"fragment_hex": hexed(fragment)},
    }
    try:
        audioop.max(fragment, width)
    except Exception as exc:
        entry["expected"] = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        if notes:
            entry["notes"] = notes
        return entry
    count = len(fragment) // width
    entry["expected"] = {"values": [audioop.getsample(fragment, width, i) for i in range(count)]}
    if notes:
        entry["notes"] = notes
    return entry


def sample_encode_case(
    case_id: str,
    width: int,
    values: list[int],
    *,
    notes: str | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": case_id,
        "op": "sample_encode",
        "width": width,
        "args": {"values": list(values)},
    }
    if width not in (1, 2, 3, 4):
        entry["expected"] = {
            "error_type": "error",
            "error_message": "Size should be 1, 2, 3 or 4",
        }
        if notes:
            entry["notes"] = notes
        return entry

    chunks = []
    try:
        for value in values:
            chunks.append(int(value).to_bytes(width, sys.byteorder, signed=True))
    except OverflowError:
        entry["expected"] = {
            "error_type": "error",
            "error_message": (f"sample value {value} out of range for width {width}"),
        }
        entry["notes"] = notes or "port range check (no reference encoder)"
        return entry

    encoded = b"".join(chunks)
    decoded = [audioop.getsample(encoded, width, index) for index in range(len(values))]
    if decoded != list(values):
        raise AssertionError(f"{case_id}: encoding does not round-trip through getsample")
    entry["expected"] = {"result_hex": hexed(encoded)}
    if notes:
        entry["notes"] = notes
    return entry


def build_sample_cases(cases: list[dict[str, object]]) -> None:
    for width in range(1, 5):
        lo = -(1 << (width * 8 - 1))
        hi = (1 << (width * 8 - 1)) - 1
        fragment = b"".join(
            value.to_bytes(width, sys.byteorder, signed=True) for value in (lo, hi, 0, -1, 1)
        )
        cases.append(
            sample_decode_case(
                f"sample-decode-w{width}",
                width,
                fragment,
                notes="signed boundaries, zero and +/-1",
            )
        )
        cases.append(
            sample_encode_case(
                f"sample-encode-w{width}",
                width,
                [lo, hi, 0, -1, 1],
                notes="signed boundaries, zero and +/-1",
            )
        )
        cases.append(
            sample_encode_case(
                f"sample-encode-w{width}-underflow",
                width,
                [lo - 1],
                notes="port range check (no reference encoder)",
            )
        )
        cases.append(
            sample_encode_case(
                f"sample-encode-w{width}-overflow",
                width,
                [hi + 1],
                notes="port range check (no reference encoder)",
            )
        )

    cases.append(sample_decode_case("sample-decode-empty-w2", 2, b"", notes="valid empty fragment"))
    cases.append(
        sample_decode_case(
            "sample-decode-partial-w2", 2, b"\x01\x02\x03", notes="incomplete trailing sample"
        )
    )
    cases.append(
        sample_decode_case(
            "sample-decode-partial-w3",
            3,
            b"\x01\x02\x03\x04\x05",
            notes="incomplete trailing sample",
        )
    )
    cases.append(sample_decode_case("sample-decode-width-0", 0, b""))
    cases.append(sample_decode_case("sample-decode-width-5", 5, b""))
    cases.append(sample_encode_case("sample-encode-empty-w2", 2, [], notes="empty samples"))
    cases.append(sample_encode_case("sample-encode-width-0", 0, []))
    cases.append(sample_encode_case("sample-encode-width-5", 5, []))


def build_phase2_cases(cases: list[dict[str, object]]) -> None:
    """Coverage for the six Phase 2 operations; existing cases are untouched."""

    def add_case(case_id, width, left, right, notes=None):
        cases.append(
            case(
                case_id,
                "add",
                width=width,
                args={"fragment1_hex": hexed(left), "fragment2_hex": hexed(right)},
                call=lambda: audioop.add(left, right, width),
                notes=notes,
            )
        )

    add_case("p2-add-pos-pos", 2, pcm(1000, 2000), pcm(500, 600))
    add_case("p2-add-neg-neg", 2, pcm(-1000, -2000), pcm(-500, -600))
    add_case("p2-add-mixed", 3, pcm_w(3, 1000, -2000), pcm_w(3, -500, 600))
    add_case(
        "p2-add-w1-max-saturate",
        1,
        bytes([127, 126]),
        bytes([1, 2]),
        notes="clamps at the 8-bit maximum",
    )
    add_case(
        "p2-add-w1-min-saturate",
        1,
        bytes([128, 129]),
        bytes([255, 254]),
        notes="clamps at the 8-bit minimum",
    )
    add_case(
        "p2-add-w4-saturate",
        4,
        pcm_w(4, 2147483647, -2147483648),
        pcm_w(4, 1, -1),
        notes="32-bit addition saturates instead of wrapping",
    )
    add_case(
        "p2-add-length-mismatch",
        2,
        pcm(1, 2),
        pcm(3),
        notes="equal lengths are required",
    )
    add_case("p2-add-w3-mixed", 3, pcm_w(3, -8388608, 8388607), pcm_w(3, 1, -1))

    def bias_case(case_id, width, fragment, offset, notes=None):
        cases.append(
            case(
                case_id,
                "bias",
                width=width,
                args={"fragment_hex": hexed(fragment), "bias": offset},
                call=lambda: audioop.bias(fragment, width, offset),
                notes=notes,
            )
        )

    bias_case("p2-bias-zero", 2, pcm(1000, -1000), 0)
    bias_case("p2-bias-positive", 1, bytes([0, 100, 127]), 10)
    bias_case("p2-bias-negative", 1, bytes([255, 100, 128]), -10)
    bias_case("p2-bias-max-overflow", 2, pcm(32767, 10), 1, notes="wraps, never clamps")
    bias_case("p2-bias-min-overflow", 2, pcm(-32768, -10), -1, notes="wraps, never clamps")
    bias_case(
        "p2-bias-w4-wrap",
        4,
        pcm_w(4, 2147483647),
        1,
        notes="wraps to the 32-bit minimum",
    )
    bias_case("p2-bias-empty", 2, b"", 100)
    bias_case(
        "p2-bias-too-large",
        2,
        pcm(1),
        2147483648,
        notes="argument conversion rejects values outside the C int range",
    )

    def mul_case(case_id, width, fragment, factor, notes=None):
        cases.append(
            case(
                case_id,
                "mul",
                width=width,
                args={"fragment_hex": hexed(fragment), "factor": factor},
                call=lambda: audioop.mul(fragment, width, factor),
                notes=notes,
            )
        )

    mul_case("p2-mul-zero", 2, pcm(1000, -1000), 0)
    mul_case("p2-mul-one", 2, pcm(1000, -1000), 1)
    mul_case("p2-mul-negative-one", 2, pcm(1000, -1000), -1)
    mul_case(
        "p2-mul-negative-fraction",
        2,
        pcm(-3, 3, -1, 1),
        -0.5,
        notes="floor after clamp: 3*-0.5=-2, -3*-0.5=1",
    )
    mul_case("p2-mul-greater", 2, pcm(1000, -1000), 2.5)
    mul_case("p2-mul-small", 2, pcm(1000, -1000), 0.001)
    mul_case(
        "p2-mul-boundary-saturate",
        1,
        bytes([127, 128]),
        100,
        notes="saturates at both 8-bit bounds",
    )
    mul_case("p2-mul-empty", 2, b"", 2.0)
    cases.append(
        case(
            "p2-mul-neg-inf",
            "mul",
            width=2,
            args={"fragment_hex": hexed(pcm(1000, -1000)), "factor": "-inf"},
            call=lambda: audioop.mul(pcm(1000, -1000), 2, float("-inf")),
            notes="infinities clamp through the defined comparisons",
        )
    )

    def reverse_case(case_id, width, fragment, notes=None):
        cases.append(
            case(
                case_id,
                "reverse",
                width=width,
                args={"fragment_hex": hexed(fragment)},
                call=lambda: audioop.reverse(fragment, width),
                notes=notes,
            )
        )

    reverse_case("p2-reverse-empty", 2, b"")
    reverse_case("p2-reverse-one", 2, pcm(1234))
    reverse_case("p2-reverse-two", 2, pcm(1, -2))
    reverse_case("p2-reverse-w1", 1, bytes([1, 2, 3, 4]))
    reverse_case("p2-reverse-w3", 3, pcm_w(3, -1, 0, 8388607))
    reverse_case("p2-reverse-w4", 4, pcm_w(4, 2147483647, -2147483648))

    def byteswap_case(case_id, width, fragment, notes=None):
        cases.append(
            case(
                case_id,
                "byteswap",
                width=width,
                args={"fragment_hex": hexed(fragment)},
                call=lambda: audioop.byteswap(fragment, width),
                notes=notes,
            )
        )

    byteswap_case("p2-byteswap-empty", 2, b"")
    byteswap_case("p2-byteswap-w1", 1, bytes([1, 2, 3]))
    byteswap_case("p2-byteswap-w3", 3, pcm_w(3, 1, -2))
    byteswap_case("p2-byteswap-w4", 4, pcm_w(4, 1, -2))
    byteswap_case(
        "p2-byteswap-negative",
        2,
        pcm(-1, -256, -2),
        notes="sample order is unchanged; only bytes within samples move",
    )

    combos = [
        (1, 1),
        (1, 2),
        (1, 4),
        (2, 2),
        (2, 3),
        (2, 4),
        (3, 1),
        (3, 2),
        (3, 3),
        (3, 4),
        (4, 1),
        (4, 3),
        (4, 4),
    ]
    for width, new_width in combos:
        lo = -(1 << (width * 8 - 1))
        hi = (1 << (width * 8 - 1)) - 1
        fragment = pcm_w(width, lo, hi, -1, 0, 1)
        cases.append(
            case(
                f"p2-lin2lin-w{width}-to-w{new_width}",
                "lin2lin",
                width=width,
                args={"fragment_hex": hexed(fragment), "new_width": new_width},
                call=lambda width=width, new_width=new_width, fragment=fragment: audioop.lin2lin(
                    fragment, width, new_width
                ),
                notes="signed boundaries, zero and +/-1",
            )
        )
    cases.append(
        case(
            "p2-lin2lin-empty",
            "lin2lin",
            width=2,
            args={"fragment_hex": "", "new_width": 3},
            call=lambda: audioop.lin2lin(b"", 2, 3),
        )
    )


def build_phase3_cases(cases: list[dict[str, object]]) -> None:
    """Coverage for the six Phase 3 statistics operations."""

    def stat_case(case_id, op, width, fragment, *, index=None, notes=None):
        args = {"fragment_hex": hexed(fragment)}
        if index is not None:
            args["index"] = index
            cases.append(
                case(
                    case_id,
                    op,
                    width=width,
                    args=args,
                    call=lambda f=fragment, w=width, i=index: audioop.getsample(f, w, i),
                    notes=notes,
                )
            )
        else:
            cases.append(
                case(
                    case_id,
                    op,
                    width=width,
                    args=args,
                    call=lambda op=op, f=fragment, w=width: getattr(audioop, op)(f, w),
                    notes=notes,
                )
            )

    # --- getsample --------------------------------------------------------
    for width in range(1, 5):
        fragment = pcm_w(width, -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1, 0, -1, 1)
        stat_case(f"p3-getsample-w{width}-first", "getsample", width, fragment, index=0)
        stat_case(f"p3-getsample-w{width}-last", "getsample", width, fragment, index=4)
    stat_case(
        "p3-getsample-negative-index",
        "getsample",
        2,
        pcm(1, 2, 3),
        index=-1,
        notes="negative indices are not Python-style",
    )
    stat_case(
        "p3-getsample-index-equals-count",
        "getsample",
        2,
        pcm(1, 2, 3),
        index=3,
    )
    stat_case(
        "p3-getsample-empty",
        "getsample",
        2,
        b"",
        index=0,
        notes="empty fragment has no samples",
    )
    stat_case(
        "p3-getsample-misaligned",
        "getsample",
        2,
        b"\x01\x02\x03",
        index=0,
    )
    stat_case(
        "p3-getsample-width-zero",
        "getsample",
        0,
        b"",
        index=0,
    )

    # --- max --------------------------------------------------------------
    for width in range(1, 5):
        fragment = pcm_w(width, -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1, 0, -1, 1)
        stat_case(f"p3-max-w{width}", "max", width, fragment)
    stat_case(
        "p3-max-w4-int-min-only",
        "max",
        4,
        struct.pack("<i", -2147483648),
        notes="unsigned absolute value: 2147483648",
    )
    stat_case(
        "p3-max-negative-only",
        "max",
        2,
        pcm(-1, -9, -3),
        notes="magnitude of the most negative sample",
    )
    stat_case("p3-max-empty", "max", 2, b"")
    stat_case(
        "p3-max-w1-boundaries",
        "max",
        1,
        bytes([127, 128]),
        notes="128 -> absolute 128",
    )

    # --- minmax -----------------------------------------------------------
    for width in range(1, 5):
        fragment = pcm_w(width, -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1, 0, -1, 1)
        stat_case(f"p3-minmax-w{width}", "minmax", width, fragment)
    stat_case(
        "p3-minmax-empty",
        "minmax",
        2,
        b"",
        notes="sentinel pair (2147483647, -2147483648)",
    )
    stat_case(
        "p3-minmax-w4-int-min-only",
        "minmax",
        4,
        struct.pack("<i", -2147483648),
        notes="both bounds are the same sample",
    )
    stat_case("p3-minmax-single", "minmax", 1, bytes([5]))
    stat_case("p3-minmax-negative-only", "minmax", 2, pcm(-9, -3))

    # --- avg --------------------------------------------------------------
    stat_case(
        "p3-avg-w2-floor-negative",
        "avg",
        2,
        pcm(-1, -2),
        notes="floor(-1.5) = -2, not truncation (-1)",
    )
    stat_case(
        "p3-avg-w2-floor-negative-3",
        "avg",
        2,
        pcm(-1, -2, -4),
        notes="floor(-7/3) = -3, not truncation (-2)",
    )
    stat_case(
        "p3-avg-w2-floor-positive",
        "avg",
        2,
        pcm(1, 2, 4),
        notes="floor(7/3) = 2",
    )
    stat_case("p3-avg-w2-exact", "avg", 2, pcm(-3))
    stat_case("p3-avg-empty", "avg", 2, b"")
    stat_case(
        "p3-avg-w4-all-int-min",
        "avg",
        4,
        struct.pack("<3i", -2147483648, -2147483648, -2147483648),
        notes="mean of the 32-bit minimum is exactly representable",
    )
    stat_case(
        "p3-avg-w4-mixed",
        "avg",
        4,
        struct.pack("<2i", 2147483647, -2147483648),
        notes="floor(-0.5) = -1",
    )
    for width in range(1, 5):
        fragment = pcm_w(width, -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1, 0, -1, 1)
        stat_case(f"p3-avg-w{width}", "avg", width, fragment)

    # --- rms --------------------------------------------------------------
    stat_case(
        "p3-rms-w2-trunc",
        "rms",
        2,
        pcm(2, -2, 2, -3),
        notes="sqrt(17/4) = 2.06 -> 2 (truncated)",
    )
    stat_case(
        "p3-rms-w2-trunc-2",
        "rms",
        2,
        pcm(1, 2),
        notes="sqrt(2.5) = 1.58 -> 1",
    )
    stat_case("p3-rms-w2-single", "rms", 2, pcm(3))
    stat_case("p3-rms-empty", "rms", 2, b"")
    stat_case(
        "p3-rms-w4-all-int-min",
        "rms",
        4,
        struct.pack("<2i", -2147483648, -2147483648),
        notes="unsigned result exceeds the signed 32-bit range",
    )
    stat_case("p3-rms-zeros", "rms", 2, pcm(0, 0, 0, 0))
    for width in range(1, 5):
        fragment = pcm_w(width, -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1, -1, 1)
        stat_case(f"p3-rms-w{width}", "rms", width, fragment)

    # --- cross ------------------------------------------------------------
    stat_case("p3-cross-empty", "cross", 2, b"", notes="sentinel -1")
    stat_case("p3-cross-single", "cross", 2, pcm(5), notes="first sample always transitions")
    stat_case("p3-cross-zeros-only", "cross", 2, pcm(0, 0, 0), notes="zero behaves like positive")
    stat_case("p3-cross-pos-neg", "cross", 2, pcm(1, -1))
    stat_case(
        "p3-cross-zero-between",
        "cross",
        2,
        pcm(1, 0, -1),
        notes="zero is in the non-negative class; one transition",
    )
    stat_case("p3-cross-neg-zero-pos", "cross", 2, pcm(-1, 0, 1))
    stat_case("p3-cross-alternating", "cross", 2, pcm(1, -1, 1), notes="two transitions")
    stat_case("p3-cross-zero-then-pos", "cross", 2, pcm(0, 1), notes="same class: zero crossings")
    stat_case("p3-cross-negative-only", "cross", 2, pcm(-1, -1))
    stat_case(
        "p3-cross-w4-int-min",
        "cross",
        4,
        struct.pack("<2i", -2147483648, 1),
        notes="the 32-bit minimum is negative",
    )
    for width in range(1, 5):
        fragment = pcm_w(width, 1, -1, 1, -1)
        stat_case(f"p3-cross-w{width}", "cross", width, fragment)

    # --- error cases for the remaining operations -------------------------
    stat_case("p3-max-width-zero", "max", 0, b"")
    stat_case("p3-minmax-misaligned", "minmax", 2, b"\x01\x02\x03")
    stat_case("p3-avg-width-zero", "avg", 0, b"")
    stat_case("p3-rms-misaligned", "rms", 2, b"\x01\x02\x03")
    stat_case("p3-cross-width-zero", "cross", 0, b"")


def main() -> int:
    check = "--check" in sys.argv[1:]
    cases = build_cases()
    build_sample_cases(cases)
    build_phase2_cases(cases)
    build_phase3_cases(cases)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": "audioop_vectors", "version": SCHEMA_VERSION},
        "reference": {
            "package": "audioop",
            "python_version": sys.version.split()[0],
        },
        "host": {"byte_order": sys.byteorder},
        "seed": SEED,
        "cases": cases,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if check:
        if not OUTPUT.exists():
            print(f"missing {OUTPUT}")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != text:
            print(f"vector drift: {OUTPUT} does not match the generator")
            return 1
        print(f"{len(cases)} cases match {OUTPUT}")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"wrote {len(cases)} cases to {OUTPUT}")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
