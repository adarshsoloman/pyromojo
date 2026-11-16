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


def build_phase4_cases(cases: list[dict[str, object]]) -> None:
    """Coverage for the five Phase 4 peak-analysis/matching operations."""

    def pp_case(case_id, op, width, fragment, notes=None):
        cases.append(
            case(
                case_id,
                op,
                width=width,
                args={"fragment_hex": hexed(fragment)},
                call=lambda op=op, f=fragment, w=width: getattr(audioop, op)(f, w),
                notes=notes,
            )
        )

    # --- avgpp / maxpp ----------------------------------------------------
    for width in range(1, 5):
        fragment = pcm_w(width, 1, 3, 1, 3)
        pp_case(f"p4-avgpp-w{width}", "avgpp", width, fragment)
        pp_case(f"p4-maxpp-w{width}", "maxpp", width, fragment)
    pp_case(
        "p4-avgpp-monotonic",
        "avgpp",
        2,
        pcm(1, 2, 3, 2, 1),
        notes="single peak: first direction is the baseline, so 0",
    )
    pp_case(
        "p4-maxpp-monotonic", "maxpp", 2, pcm(1, 2, 3, 2, 1), notes="single peak never forms a pair"
    )
    pp_case(
        "p4-avgpp-plateau",
        "avgpp",
        2,
        pcm(1, 3, 3, 1, 3, 3, 1),
        notes="equal adjacent samples are skipped entirely",
    )
    pp_case("p4-maxpp-plateau", "maxpp", 2, pcm(1, 3, 3, 1, 3, 3, 1))
    pp_case("p4-avgpp-truncation", "avgpp", 2, pcm(0, 3, 0, 1, 0), notes="mean 7/3 truncates to 2")
    pp_case("p4-avgpp-constant", "avgpp", 2, pcm(5, 5, 5))
    pp_case("p4-maxpp-constant", "maxpp", 2, pcm(5, 5, 5))
    pp_case("p4-avgpp-single", "avgpp", 2, pcm(5), notes="single sample -> 0")
    pp_case("p4-maxpp-single", "maxpp", 2, pcm(5))
    pp_case("p4-avgpp-empty", "avgpp", 2, b"")
    pp_case("p4-maxpp-empty", "maxpp", 2, b"")
    pp_case(
        "p4-avgpp-w4-unsigned-wrap",
        "avgpp",
        4,
        pcm_w(4, 2147483647, -2147483648, 2147483647, -2147483648, 2147483647),
        notes="unsigned 32-bit diff of INT_MAX/INT_MIN pair is 4294967295",
    )
    pp_case(
        "p4-maxpp-w4-unsigned-wrap",
        "maxpp",
        4,
        pcm_w(4, 2147483647, -2147483648, 2147483647, -2147483648, 2147483647),
    )
    pp_case(
        "p4-avgpp-single-v",
        "avgpp",
        2,
        pcm(32767, -32768, 32767),
        notes="one direction change: no pair yet, 0",
    )
    pp_case("p4-maxpp-single-v", "maxpp", 2, pcm(32767, -32768, 32767))
    pp_case(
        "p4-avgpp-misaligned",
        "avgpp",
        2,
        b"\x01\x02\x03",
        notes="alignment error",
    )
    pp_case("p4-maxpp-width-zero", "maxpp", 0, b"")

    # --- findmax (fixed 16-bit, no width argument) -------------------------
    def findmax_case(case_id, fragment, length, notes=None):
        cases.append(
            case(
                case_id,
                "findmax",
                args={"fragment_hex": hexed(fragment), "length": length},
                call=lambda f=fragment, n=length: audioop.findmax(f, n),
                notes=notes,
            )
        )

    findmax_case("p4-findmax-basic", pcm(0, 100, 200, 300), 2)
    findmax_case(
        "p4-findmax-tie",
        pcm(1, 2, 1, 2),
        2,
        notes="equal energies keep the first window (strict >)",
    )
    findmax_case("p4-findmax-last-window", pcm(0, 0, 5, 5), 2)
    findmax_case("p4-findmax-length-equals-count", pcm(1, 2, 3), 3)
    findmax_case("p4-findmax-length-one", pcm(5, -3, 2), 1)
    findmax_case("p4-findmax-length-zero", pcm(1, 2), 0)
    findmax_case("p4-findmax-empty-length-zero", b"", 0)
    findmax_case("p4-findmax-too-long", pcm(0, 1), 3, notes="length larger than the sample count")
    findmax_case("p4-findmax-negative", pcm(0, 1), -1)
    findmax_case("p4-findmax-odd-bytes", b"\x01\x02\x03", 1)
    findmax_case("p4-findmax-zero-heavy", pcm(0, 0, 0, 7), 2)
    findmax_case(
        "p4-findmax-interprets-w4-as-16bit",
        struct.pack("<3i", 1, 2, 3),
        3,
        notes="fixed 16-bit: 12 bytes are six int16 samples",
    )

    # --- findfactor (fixed 16-bit) -----------------------------------------
    def ff_case(case_id, fragment, reference, notes=None):
        cases.append(
            case(
                case_id,
                "findfactor",
                args={"fragment_hex": hexed(fragment), "reference_hex": hexed(reference)},
                call=lambda f=fragment, r=reference: audioop.findfactor(f, r),
                notes=notes,
            )
        )

    ff_case("p4-findfactor-identical", pcm(1, 2, 3), pcm(1, 2, 3), notes="factor 1.0")
    ff_case("p4-findfactor-scaled", pcm(2, 4, 6), pcm(1, 2, 3), notes="factor 2.0")
    ff_case("p4-findfactor-negative", pcm(-1, -2), pcm(1, 2), notes="factor -1.0")
    ff_case("p4-findfactor-zero-reference", pcm(1, 2), pcm(0, 0), notes="0/0 division: nan")
    ff_case("p4-findfactor-empty", b"", b"", notes="empty: nan")
    ff_case("p4-findfactor-fragment-zero", pcm(0, 0), pcm(1, 2), notes="0/sum(r^2) = 0.0")
    ff_case("p4-findfactor-mismatched", pcm(1, 2), pcm(1, 2, 3))
    ff_case("p4-findfactor-odd", b"\x01\x02\x03", b"\x01\x02\x03\x04")
    ff_case("p4-findfactor-large", pcm(30000, 30000), pcm(1, 1), notes="30000.0")
    ff_case(
        "p4-findfactor-reads-w4-as-16bit",
        struct.pack("<2i", 65536, 1),
        struct.pack("<2i", 32768, 1),
        notes="fixed 16-bit: the int16 halves are compared",
    )

    # --- findfit (fixed 16-bit) ---------------------------------------------
    def fit_case(case_id, fragment, reference, notes=None):
        cases.append(
            case(
                case_id,
                "findfit",
                args={"fragment_hex": hexed(fragment), "reference_hex": hexed(reference)},
                call=lambda f=fragment, r=reference: audioop.findfit(f, r),
                notes=notes,
            )
        )

    fit_case("p4-findfit-exact-at-zero", pcm(1, 2, 3, 4), pcm(1, 2, 3), notes="window at index 0")
    fit_case("p4-findfit-shifted", pcm(9, 1, 2, 3), pcm(1, 2, 3), notes="window at index 1")
    fit_case("p4-findfit-equal-length", pcm(1, 2), pcm(1, 2))
    fit_case("p4-findfit-reference-longer", pcm(1), pcm(1, 2))
    fit_case("p4-findfit-empty-both", b"", b"", notes="(0, nan)")
    fit_case(
        "p4-findfit-zero-window", pcm(0, 0, 5, 6), pcm(0, 0), notes="zero-energy window: nan factor"
    )
    fit_case(
        "p4-findfit-tie",
        pcm(1, 2, 1, 2),
        pcm(1, 2),
        notes="equal errors keep the first window (strict <)",
    )
    fit_case("p4-findfit-scaled", pcm(2, 4, 6, 8), pcm(1, 2, 3), notes="factor 2.0")
    fit_case(
        "p4-findfit-negative-window",
        pcm(1, 2, -1, -2),
        pcm(1, 2),
        notes="negative window loses on strict <",
    )
    fit_case(
        "p4-findfit-zero-mid-search",
        pcm(5, 6, 0, 0, 0, 0),
        pcm(1, 2),
        notes="nan candidate windows never beat a finite best",
    )
    fit_case("p4-findfit-odd", b"\x01\x02\x03", b"\x01\x02")


def build_phase5_cases(cases: list[dict[str, object]]) -> None:
    """Coverage for the two Phase 5 channel operations."""

    def as_factor(value):
        return float(value) if isinstance(value, str) else value

    def channel_case(case_id, op, width, fragment, lfactor, rfactor, notes=None):
        left = as_factor(lfactor)
        right = as_factor(rfactor)
        cases.append(
            case(
                case_id,
                op,
                width=width,
                args={
                    "fragment_hex": hexed(fragment),
                    "lfactor": lfactor,
                    "rfactor": rfactor,
                },
                call=lambda op=op, f=fragment, w=width, left=left, right=right: getattr(
                    audioop, op
                )(f, w, left, right),
                notes=notes,
            )
        )

    # --- tomono -----------------------------------------------------------
    for width in range(1, 5):
        lo = -(1 << (width * 8 - 1))
        hi = (1 << (width * 8 - 1)) - 1
        channel_case(
            f"p5-tomono-w{width}",
            "tomono",
            width,
            pcm_w(width, lo, hi, -1, 1),
            0.5,
            0.5,
        )
    channel_case(
        "p5-tomono-boundaries",
        "tomono",
        2,
        pcm(32767, 32767, -32768, -32768),
        1.0,
        1.0,
        notes="saturates at both 16-bit extremes",
    )
    channel_case(
        "p5-tomono-w4-boundaries",
        "tomono",
        4,
        pcm_w(4, 2147483647, -2147483648),
        1.0,
        1.0,
        notes="floor(-0.5) = -1",
    )
    channel_case("p5-tomono-empty", "tomono", 2, b"", 1.0, 1.0)
    channel_case(
        "p5-tomono-single-sample",
        "tomono",
        2,
        pcm(5),
        1.0,
        1.0,
        notes="odd sample count is not whole stereo frames",
    )
    channel_case(
        "p5-tomono-odd-count",
        "tomono",
        2,
        pcm(1, 2, 3),
        1.0,
        1.0,
    )
    channel_case(
        "p5-tomono-misaligned",
        "tomono",
        2,
        b"\x01\x02\x03",
        1.0,
        1.0,
    )
    channel_case("p5-tomono-width-zero", "tomono", 0, b"", 1.0, 1.0)
    channel_case(
        "p5-tomono-zero-factors",
        "tomono",
        2,
        pcm(1000, -1000, 5, -5),
        0.0,
        0.0,
    )
    channel_case(
        "p5-tomono-mixed-factors",
        "tomono",
        2,
        pcm(3, -3, -3, 3),
        0.5,
        -0.5,
        notes="floor of fractional sums",
    )
    channel_case(
        "p5-tomono-large-factors",
        "tomono",
        2,
        pcm(1, -1, 2, -2),
        1e6,
        -1e6,
        notes="saturates through huge sums",
    )
    channel_case(
        "p5-tomono-small-factors",
        "tomono",
        2,
        pcm(1000, -1000, 999, -999),
        0.001,
        0.001,
        notes="floor of tiny products",
    )
    channel_case(
        "p5-tomono-inf-factors",
        "tomono",
        2,
        pcm(1, 2, 3, 4),
        "inf",
        "-inf",
        notes="infinities clamp through defined comparisons",
    )
    channel_case(
        "p5-tomono-nan-factor",
        "tomono",
        2,
        pcm(1, 2, 3, 4),
        "nan",
        0.5,
        notes="reference UB; observed result equals the port's NaN->0 policy",
    )
    channel_case(
        "p5-tomono-neg-saturation",
        "tomono",
        2,
        pcm(-32768, -32768),
        1.0,
        1.0,
        notes="clamps at the 16-bit minimum",
    )

    # --- tostereo ----------------------------------------------------------
    for width in range(1, 5):
        lo = -(1 << (width * 8 - 1))
        hi = (1 << (width * 8 - 1)) - 1
        channel_case(
            f"p5-tostereo-w{width}",
            "tostereo",
            width,
            pcm_w(width, lo, hi),
            0.5,
            -0.5,
        )
    channel_case(
        "p5-tostereo-boundaries",
        "tostereo",
        2,
        pcm(32767, -32768),
        2.0,
        2.0,
        notes="saturates at both 16-bit extremes",
    )
    channel_case(
        "p5-tostereo-w4-boundaries",
        "tostereo",
        4,
        pcm_w(4, 2147483647, -2147483648),
        1.0,
        1.0,
    )
    channel_case("p5-tostereo-empty", "tostereo", 2, b"", 1.0, 1.0)
    channel_case(
        "p5-tostereo-single-sample",
        "tostereo",
        2,
        pcm(5),
        1.0,
        1.0,
        notes="one sample expands to one interleaved pair",
    )
    channel_case(
        "p5-tostereo-misaligned",
        "tostereo",
        2,
        b"\x01",
        1.0,
        1.0,
    )
    channel_case("p5-tostereo-width-zero", "tostereo", 0, b"", 1.0, 1.0)
    channel_case(
        "p5-tostereo-zero-factors",
        "tostereo",
        2,
        pcm(1000, -1000),
        0.0,
        0.0,
    )
    channel_case(
        "p5-tostereo-fractional-factors",
        "tostereo",
        2,
        pcm(3, -3),
        0.5,
        0.5,
        notes="floor(1.5) = 1; floor(-1.5) = -2",
    )
    channel_case(
        "p5-tostereo-large-factors",
        "tostereo",
        2,
        pcm(1, -1),
        1e6,
        -1e6,
    )
    channel_case(
        "p5-tostereo-inf-factors",
        "tostereo",
        2,
        pcm(1, 2),
        "inf",
        "-inf",
    )
    channel_case(
        "p5-tostereo-nan-factor",
        "tostereo",
        2,
        pcm(1, 2),
        "nan",
        0.5,
        notes="reference UB; observed result equals the port's NaN->0 policy",
    )


def build_phase6_cases(cases: list[dict[str, object]]) -> None:
    """Coverage for the Phase 6 stateful ratecv operation."""

    def ratecv_case(
        case_id,
        width,
        nchannels,
        inrate,
        outrate,
        fragment,
        state=None,
        weightA=1,
        weightB=0,
        notes=None,
    ):
        args = {
            "fragment_hex": hexed(fragment),
            "width": width,
            "nchannels": nchannels,
            "inrate": inrate,
            "outrate": outrate,
            "weightA": weightA,
            "weightB": weightB,
        }
        if state is not None:
            args["state"] = {
                "d": state[0],
                "channels": [list(pair) for pair in state[1]],
            }

        def call():
            state_arg = None
            if state is not None:
                state_arg = (
                    state[0],
                    tuple(tuple(pair) for pair in state[1]),
                )
            return audioop.ratecv(
                fragment, width, nchannels, inrate, outrate, state_arg, weightA, weightB
            )

        cases.append(
            case(
                case_id,
                "ratecv",
                width=width,
                args=args,
                call=call,
                notes=notes,
            )
        )

    # fresh-state basics for every width
    for width in range(1, 5):
        lo = -(1 << (width * 8 - 1))
        hi = (1 << (width * 8 - 1)) - 1
        fragment = pcm_w(width, lo, hi, -1, 1)
        ratecv_case(
            f"p6-ratecv-w{width}",
            width,
            1,
            8000,
            8000,
            fragment,
            notes="equal rates, boundaries at every width",
        )
    ratecv_case(
        "p6-ratecv-empty",
        2,
        1,
        8000,
        16000,
        b"",
        notes="empty input returns the initial phase in the state",
    )
    ratecv_case("p6-ratecv-one-sample", 2, 1, 8000, 8000, pcm(1000))
    ratecv_case("p6-ratecv-equal-rates", 2, 1, 3, 3, pcm(1000, 2000, 3000))
    ratecv_case(
        "p6-ratecv-upsample",
        2,
        1,
        8000,
        16000,
        pcm(-10, -9, -8, -7, -6),
    )
    ratecv_case(
        "p6-ratecv-downsample",
        2,
        1,
        16000,
        8000,
        pcm(-10, -9, -8, -7, -6),
    )
    ratecv_case(
        "p6-ratecv-non-integer-ratio",
        2,
        1,
        8000,
        44100,
        pcm(1000, 2000, 3000, 4000, 5000),
        notes="outrate not a multiple of inrate",
    )
    ratecv_case(
        "p6-ratecv-2ch-upsample",
        2,
        2,
        8000,
        16000,
        pcm(1, 2, 3, 4),
        notes="channels interleaved in input and output",
    )
    ratecv_case(
        "p6-ratecv-4ch-equal",
        2,
        4,
        8000,
        8000,
        pcm(1, 2, 3, 4, 5, 6, 7, 8),
    )
    ratecv_case(
        "p6-ratecv-w4-upsample",
        4,
        1,
        8000,
        16000,
        pcm_w(4, 2147483647, -2147483648, 0, 1),
        notes="32-bit samples are used unshifted",
    )
    ratecv_case(
        "p6-ratecv-w3-upsample",
        3,
        1,
        8000,
        16000,
        pcm_w(3, -1, 1, 0, 5),
    )
    ratecv_case(
        "p6-ratecv-weights-2-1",
        2,
        1,
        8000,
        8000,
        pcm(1000, -1000, 1000, -1000),
        weightA=2,
        weightB=1,
    )
    ratecv_case(
        "p6-ratecv-weights-3-2",
        2,
        1,
        8000,
        8000,
        pcm(1000, -1000),
        weightA=3,
        weightB=2,
    )
    ratecv_case(
        "p6-ratecv-weights-5-0",
        2,
        1,
        8000,
        8000,
        pcm(1000, -1000),
        weightA=5,
        weightB=0,
        notes="gcd reduction turns (5, 0) into (1, 0)",
    )
    ratecv_case(
        "p6-ratecv-negative-extrema",
        2,
        1,
        8000,
        16000,
        pcm(-32768, 32767),
    )
    ratecv_case(
        "p6-ratecv-alternating",
        2,
        1,
        8000,
        16000,
        pcm(1, -1, 1, -1, 1, -1),
    )

    # continued state: derive the state from a deterministic reference call
    seed_out, seed_state = audioop.ratecv(pcm(-10, -9, -8, -7), 2, 1, 8000, 16000, None)
    ratecv_case(
        "p6-ratecv-continued-state",
        2,
        1,
        8000,
        16000,
        pcm(-6, -5, -4, -3),
        state=seed_state,
        notes="state captured from a deterministic previous reference call",
    )
    seed_out2, seed_state2 = audioop.ratecv(pcm(1, 2, 3, 4), 2, 2, 8000, 16000, None)
    ratecv_case(
        "p6-ratecv-continued-2ch",
        2,
        2,
        8000,
        16000,
        pcm(5, 6, 7, 8),
        state=seed_state2,
    )

    # error cases
    ratecv_case("p6-ratecv-width-zero", 0, 1, 1, 1, b"")
    ratecv_case("p6-ratecv-channels-zero", 2, 0, 1, 1, b"")
    ratecv_case("p6-ratecv-misaligned", 2, 1, 1, 1, b"\x01")
    ratecv_case("p6-ratecv-inrate-zero", 2, 1, 0, 1, b"")
    ratecv_case("p6-ratecv-outrate-zero", 2, 1, 1, 0, b"")
    ratecv_case("p6-ratecv-weightA-zero", 2, 1, 1, 1, b"", weightA=0)
    ratecv_case("p6-ratecv-weightB-negative", 2, 1, 1, 1, b"", weightB=-1)
    ratecv_case(
        "p6-ratecv-huge-rate",
        2,
        1,
        2**40,
        1,
        b"",
        notes="argument conversion precedes body validation",
    )
    ratecv_case(
        "p6-ratecv-huge-channels",
        2,
        2**40,
        1,
        1,
        b"",
        notes="argument conversion precedes body validation",
    )
    ratecv_case(
        "p6-ratecv-width-times-channels-too-big",
        4,
        2**30,
        1,
        1,
        b"",
        notes="width * nchannels exceeds a C int",
    )


def build_phase7_cases(cases: list[dict[str, object]]) -> None:
    """Coverage for the four Phase 7 G.711 codec operations."""

    def codec_case(case_id, op, width, fragment, notes=None):
        cases.append(
            case(
                case_id,
                op,
                width=width,
                args={"fragment_hex": hexed(fragment)},
                call=lambda op=op, f=fragment, w=width: getattr(audioop, op)(f, w),
                notes=notes,
            )
        )

    # encoders: every width, boundaries, alternating, repeated, segment values
    for width in range(1, 5):
        lo = -(1 << (width * 8 - 1))
        hi = (1 << (width * 8 - 1)) - 1
        fragment = pcm_w(width, lo, hi, -1, 1, 0)
        codec_case(f"p7-lin2alaw-w{width}", "lin2alaw", width, fragment)
        codec_case(f"p7-lin2ulaw-w{width}", "lin2ulaw", width, fragment)
    # width-specific scaling: w1 x64 (ulaw) / x32 (alaw); w2 >>2 (ulaw) /
    # >>3 (alaw); w3 >>10 (ulaw) / >>11 (alaw); w4 >>18 / >>19
    codec_case(
        "p7-lin2ulaw-w1-scale",
        "lin2ulaw",
        1,
        bytes([127, 128, 64]),
        notes="8-bit samples are multiplied by 64 into the 14-bit range",
    )
    codec_case(
        "p7-lin2alaw-w1-scale",
        "lin2alaw",
        1,
        bytes([127, 128, 64]),
        notes="8-bit samples are multiplied by 32 into the 13-bit range",
    )
    codec_case(
        "p7-lin2ulaw-w2-scale",
        "lin2ulaw",
        2,
        pcm(8191, -8192, 8192, -8193),
        notes="16-bit samples shift right by 2 (arithmetic)",
    )
    codec_case(
        "p7-lin2alaw-w2-scale",
        "lin2alaw",
        2,
        pcm(4095, -4096, 4096, -4097),
        notes="16-bit samples shift right by 3 (arithmetic)",
    )
    codec_case(
        "p7-lin2ulaw-w3-scale",
        "lin2ulaw",
        3,
        pcm_w(3, 819199, -819200, 0, 1),
        notes="24-bit samples shift right by 10 (arithmetic)",
    )
    codec_case(
        "p7-lin2alaw-w3-scale",
        "lin2alaw",
        3,
        pcm_w(3, 409599, -409600, 0, 1),
        notes="24-bit samples shift right by 11 (arithmetic)",
    )
    codec_case(
        "p7-lin2ulaw-w4-scale",
        "lin2ulaw",
        4,
        pcm_w(4, 2147483647, -2147483648, 0, 1),
        notes="32-bit samples shift right by 18 (arithmetic)",
    )
    codec_case(
        "p7-lin2alaw-w4-scale",
        "lin2alaw",
        4,
        pcm_w(4, 2147483647, -2147483648, 0, 1),
        notes="32-bit samples shift right by 19 (arithmetic)",
    )
    # A-law segment boundaries: 13-bit values around seg_aend
    alaw_bounds = [
        30,
        31,
        32,
        62,
        63,
        64,
        126,
        127,
        128,
        254,
        255,
        256,
        510,
        511,
        512,
        1022,
        1023,
        1024,
        2046,
        2047,
        2048,
        4094,
        4095,
        4096,
        0,
        -1,
        -2,
    ]
    # these are 13-bit values; feed them at width 4 unshifted means
    # val32 >> 19: use val << 19 scaled samples
    for value in alaw_bounds:
        encoded_value = value << 19
        if encoded_value > 2147483647 or encoded_value < -2147483648:
            continue
        codec_case(
            f"p7-lin2alaw-bound-{value}",
            "lin2alaw",
            4,
            pcm_w(4, encoded_value),
        )
    # mu-law segment boundaries: 14-bit values around seg_uend (+33 bias)
    ulaw_bounds = [
        30,
        31,
        32,
        62,
        63,
        64,
        126,
        127,
        128,
        254,
        255,
        256,
        510,
        511,
        512,
        1022,
        1023,
        1024,
        2046,
        2047,
        2048,
        4094,
        4095,
        4096,
        8190,
        8191,
        0,
        -1,
        -2,
    ]
    for value in ulaw_bounds:
        encoded_value = value << 18
        if encoded_value > 2147483647 or encoded_value < -2147483648:
            continue
        codec_case(
            f"p7-lin2ulaw-bound-{value}",
            "lin2ulaw",
            4,
            pcm_w(4, encoded_value),
        )
    codec_case("p7-lin2alaw-empty", "lin2alaw", 2, b"")
    codec_case("p7-lin2ulaw-empty", "lin2ulaw", 2, b"")
    codec_case("p7-lin2alaw-width-zero", "lin2alaw", 0, b"")
    codec_case("p7-lin2ulaw-width-zero", "lin2ulaw", 0, b"")
    codec_case("p7-lin2alaw-misaligned", "lin2alaw", 2, b"\x01\x02\x03")
    codec_case("p7-lin2ulaw-misaligned", "lin2ulaw", 2, b"\x01")

    # decoders: exhaustive 256 codewords at width 2, plus other widths
    for code in range(256):
        codec_case(
            f"p7-alaw2lin-code-{code:02x}",
            "alaw2lin",
            2,
            bytes([code]),
            notes="exhaustive decoder verification" if code == 0 else None,
        )
    for code in range(256):
        codec_case(
            f"p7-ulaw2lin-code-{code:02x}",
            "ulaw2lin",
            2,
            bytes([code]),
        )
    # decoder widths: same codewords at widths 1, 3, 4 (sampled set)
    for code in (0x00, 0x55, 0x2A, 0x7F, 0x80, 0xD5, 0xAA, 0xFF):
        for width in (1, 3, 4):
            codec_case(
                f"p7-alaw2lin-w{width}-code-{code:02x}",
                "alaw2lin",
                width,
                bytes([code]),
            )
            codec_case(
                f"p7-ulaw2lin-w{width}-code-{code:02x}",
                "ulaw2lin",
                width,
                bytes([code]),
            )
    # decoder byte order: multi-byte sequences
    codec_case(
        "p7-alaw2lin-sequence",
        "alaw2lin",
        2,
        bytes([0x00, 0xD5, 0x55, 0x2A, 0x7F, 0x80, 0xFF, 0xAA]),
        notes="mixed codewords decode in order",
    )
    codec_case(
        "p7-ulaw2lin-sequence",
        "ulaw2lin",
        2,
        bytes([0x00, 0x7F, 0x80, 0xFF, 0x55, 0xAA, 0x01, 0xFE]),
        notes="mixed codewords decode in order",
    )
    codec_case("p7-alaw2lin-empty", "alaw2lin", 2, b"")
    codec_case("p7-ulaw2lin-empty", "ulaw2lin", 2, b"")
    codec_case("p7-alaw2lin-width-zero", "alaw2lin", 0, b"")
    codec_case("p7-ulaw2lin-width-zero", "ulaw2lin", 0, b"")
    # round trips
    lin = pcm(1000, -1000, 32767, -32768, 0, 1, -1)
    codec_case(
        "p7-alaw-roundtrip",
        "alaw2lin",
        2,
        audioop.lin2alaw(lin, 2),
        notes="round trip through the reference encoder",
    )
    codec_case(
        "p7-ulaw-roundtrip",
        "ulaw2lin",
        2,
        audioop.lin2ulaw(lin, 2),
        notes="round trip through the reference encoder",
    )


def build_phase8_cases(cases: list[dict[str, object]]) -> None:
    """Coverage for the two Phase 8 ADPCM operations."""

    def adpcm_case(case_id, op, width, fragment, state=None, notes=None):
        args = {"fragment_hex": hexed(fragment), "width": width}
        if state is not None:
            args["state"] = [state[0], state[1]]

        def call():
            state_arg = None if state is None else (state[0], state[1])
            return getattr(audioop, op)(fragment, width, state_arg)

        cases.append(
            case(
                case_id,
                op,
                width=width,
                args=args,
                call=call,
                notes=notes,
            )
        )

    # encoder: every width with boundaries
    for width in range(1, 5):
        lo = -(1 << (width * 8 - 1))
        hi = (1 << (width * 8 - 1)) - 1
        adpcm_case(
            f"p8-lin2adpcm-w{width}",
            "lin2adpcm",
            width,
            pcm_w(width, hi, lo, 0, -1, 1),
        )
    adpcm_case("p8-lin2adpcm-empty", "lin2adpcm", 2, b"")
    adpcm_case(
        "p8-lin2adpcm-empty-state",
        "lin2adpcm",
        2,
        b"",
        state=(100, 50),
        notes="state is returned unchanged for empty input",
    )
    adpcm_case(
        "p8-lin2adpcm-one-sample",
        "lin2adpcm",
        2,
        pcm(1000),
        notes="odd sample count: nibble buffered and dropped",
    )
    adpcm_case("p8-lin2adpcm-two-samples", "lin2adpcm", 2, pcm(1, 2))
    adpcm_case(
        "p8-lin2adpcm-three-samples",
        "lin2adpcm",
        2,
        pcm(1, 2, 3),
        notes="odd sample count drops the trailing nibble",
    )
    adpcm_case("p8-lin2adpcm-alternating", "lin2adpcm", 2, pcm(1, -1, 1, -1, 1, -1))
    adpcm_case("p8-lin2adpcm-repeated", "lin2adpcm", 2, pcm(500, 500, 500, 500))
    adpcm_case(
        "p8-lin2adpcm-abrupt",
        "lin2adpcm",
        2,
        pcm(0, 32767, 0, -32768, 0, 32767),
        notes="abrupt signal changes exercise large steps",
    )
    adpcm_case("p8-lin2adpcm-zeros", "lin2adpcm", 2, bytes(8))
    adpcm_case("p8-lin2adpcm-small-diffs", "lin2adpcm", 2, pcm(0, 1, 2, 3, 4, 5, 6, 7))
    # continued state: derive deterministically from a prior reference call
    _, seed_state = audioop.lin2adpcm(pcm(-10, -9, -8, -7), 2, None)
    adpcm_case("p8-lin2adpcm-continued", "lin2adpcm", 2, pcm(-6, -5, -4, -3), state=seed_state)
    # errors
    adpcm_case("p8-lin2adpcm-width-zero", "lin2adpcm", 0, b"")
    adpcm_case("p8-lin2adpcm-misaligned", "lin2adpcm", 2, b"\x01")
    adpcm_case("p8-lin2adpcm-bad-valpred", "lin2adpcm", 2, b"", state=(32768, 0))
    adpcm_case("p8-lin2adpcm-bad-index-high", "lin2adpcm", 2, b"", state=(0, 89))
    adpcm_case("p8-lin2adpcm-bad-index-negative", "lin2adpcm", 2, b"", state=(0, -1))
    adpcm_case(
        "p8-lin2adpcm-state-extremes",
        "lin2adpcm",
        2,
        b"",
        state=(-32768, 88),
        notes="boundary state values are valid",
    )

    # decoder: all 256 byte values at width 2
    for byte in range(256):
        adpcm_case(
            f"p8-adpcm2lin-byte-{byte:02x}",
            "adpcm2lin",
            2,
            bytes([byte]),
            notes="exhaustive decoder verification" if byte == 0 else None,
        )
    # sampled decoder widths
    for byte in (0x00, 0x7F, 0x80, 0xFF, 0x55, 0xAA, 0x12, 0xED):
        for width in (1, 3, 4):
            adpcm_case(
                f"p8-adpcm2lin-w{width}-byte-{byte:02x}",
                "adpcm2lin",
                width,
                bytes([byte]),
            )
    # all 16 high nibbles from a fresh state
    for nibble in range(16):
        adpcm_case(
            f"p8-adpcm2lin-nibble-{nibble:01x}",
            "adpcm2lin",
            2,
            bytes([nibble << 4]),
        )
    adpcm_case("p8-adpcm2lin-empty", "adpcm2lin", 2, b"")
    adpcm_case(
        "p8-adpcm2lin-odd-bytes",
        "adpcm2lin",
        2,
        b"\x01\x02\x03",
        notes="decoder requires no alignment",
    )
    adpcm_case("p8-adpcm2lin-repeated", "adpcm2lin", 2, bytes([0x7F] * 6))
    adpcm_case("p8-adpcm2lin-alternating", "adpcm2lin", 2, bytes([0x0F, 0xF0, 0x0F, 0xF0]))
    _, dec_seed = audioop.adpcm2lin(b"\x55\xaa\x12", 2, None)
    adpcm_case("p8-adpcm2lin-continued", "adpcm2lin", 2, b"\x34\x78", state=dec_seed)
    adpcm_case("p8-adpcm2lin-custom-state", "adpcm2lin", 2, b"\x08\x08", state=(0, 55))
    adpcm_case("p8-adpcm2lin-width-zero", "adpcm2lin", 0, b"")
    adpcm_case("p8-adpcm2lin-bad-state", "adpcm2lin", 2, b"", state=(0, 100))


def main() -> int:
    check = "--check" in sys.argv[1:]
    cases = build_cases()
    build_sample_cases(cases)
    build_phase2_cases(cases)
    build_phase3_cases(cases)
    build_phase4_cases(cases)
    build_phase5_cases(cases)
    build_phase6_cases(cases)
    build_phase7_cases(cases)
    build_phase8_cases(cases)
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
