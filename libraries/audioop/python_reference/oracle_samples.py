"""Batch reference oracle for the audioop sample and arithmetic layers.

Reads one JSON request from stdin and writes JSON to stdout. Runs only on
the pinned CPython 3.12 interpreter:

    libraries/audioop/python_reference/.venv/bin/python oracle_samples.py

Decode expectations come from ``audioop.getsample`` (the reference's
sample-level oracle; width/frame validation via ``audioop.max``). Encode
expectations are ``int.to_bytes(width, sys.byteorder, signed=True)`` and
are validated by decoding every value back through ``getsample``. There is
no reference encoder, so out-of-range values surface as ``OverflowError``
and the port applies its documented range check.

Phase 2 adds the six arithmetic/fragment operations. Every result is
produced by the original CPython module, never by a local reimplementation.
Floating-point factors accept JSON numbers or the strings ``nan``, ``inf``
and ``-inf``.
"""

from __future__ import annotations

import json
import sys

try:
    import audioop
except ImportError as exc:  # pragma: no cover - wrong interpreter guard
    raise SystemExit(
        "audioop is unavailable; run with libraries/audioop/python_reference/.venv/bin/python"
    ) from exc


def _decode_one(item: dict) -> dict:
    width = int(item["width"])
    fragment = bytes.fromhex(item["fragment_hex"])
    try:
        audioop.max(fragment, width)
        count = len(fragment) // width
        values = [audioop.getsample(fragment, width, index) for index in range(count)]
        return {"values": values}
    except Exception as exc:  # the reference defines these messages
        return {"error_type": type(exc).__name__, "error_message": str(exc)}


def _encode_one(item: dict) -> dict:
    width = int(item["width"])
    values = [int(value) for value in item["values"]]
    if width not in (1, 2, 3, 4):
        return {"error_type": "error", "error_message": "Size should be 1, 2, 3 or 4"}

    chunks = []
    try:
        for value in values:
            chunks.append(value.to_bytes(width, sys.byteorder, signed=True))
    except OverflowError:
        return {"error_type": "OverflowError", "error_message": "int too big to convert"}

    encoded = b"".join(chunks)
    decoded = [audioop.getsample(encoded, width, index) for index in range(len(values))]
    if decoded != values:
        raise AssertionError("encoded bytes do not round-trip through getsample")
    return {"result_hex": encoded.hex(), "values": decoded}


def _result(value) -> dict:
    if isinstance(value, (bytes, bytearray)):
        return {"result_hex": bytes(value).hex()}
    return {"value": value}


def _call(function, *args) -> dict:
    try:
        return _result(function(*args))
    except Exception as exc:  # the reference defines these messages
        return {"error_type": type(exc).__name__, "error_message": str(exc)}


def _factor(value) -> float:
    if isinstance(value, str):
        return float(value)
    return float(value)


def _add_one(item: dict) -> dict:
    return _call(
        audioop.add,
        bytes.fromhex(item["fragment1_hex"]),
        bytes.fromhex(item["fragment2_hex"]),
        int(item["width"]),
    )


def _bias_one(item: dict) -> dict:
    return _call(
        audioop.bias,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
        int(item["bias"]),
    )


def _mul_one(item: dict) -> dict:
    return _call(
        audioop.mul,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
        _factor(item["factor"]),
    )


def _reverse_one(item: dict) -> dict:
    return _call(
        audioop.reverse,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _byteswap_one(item: dict) -> dict:
    return _call(
        audioop.byteswap,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _lin2lin_one(item: dict) -> dict:
    return _call(
        audioop.lin2lin,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
        int(item["new_width"]),
    )


def _getsample_one(item: dict) -> dict:
    return _call(
        audioop.getsample,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
        int(item["index"]),
    )


def _max_one(item: dict) -> dict:
    return _call(
        audioop.max,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _minmax_one(item: dict) -> dict:
    return _call(
        audioop.minmax,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _avg_one(item: dict) -> dict:
    return _call(
        audioop.avg,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _rms_one(item: dict) -> dict:
    return _call(
        audioop.rms,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _cross_one(item: dict) -> dict:
    return _call(
        audioop.cross,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _avgpp_one(item: dict) -> dict:
    return _call(
        audioop.avgpp,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _maxpp_one(item: dict) -> dict:
    return _call(
        audioop.maxpp,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
    )


def _findmax_one(item: dict) -> dict:
    return _call(
        audioop.findmax,
        bytes.fromhex(item["fragment_hex"]),
        int(item["length"]),
    )


def _findfactor_one(item: dict) -> dict:
    return _call(
        audioop.findfactor,
        bytes.fromhex(item["fragment_hex"]),
        bytes.fromhex(item["reference_hex"]),
    )


def _findfit_one(item: dict) -> dict:
    return _call(
        audioop.findfit,
        bytes.fromhex(item["fragment_hex"]),
        bytes.fromhex(item["reference_hex"]),
    )


def _tomono_one(item: dict) -> dict:
    return _call(
        audioop.tomono,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
        _factor(item["lfactor"]),
        _factor(item["rfactor"]),
    )


def _tostereo_one(item: dict) -> dict:
    return _call(
        audioop.tostereo,
        bytes.fromhex(item["fragment_hex"]),
        int(item["width"]),
        _factor(item["lfactor"]),
        _factor(item["rfactor"]),
    )


def _ratecv_one(item: dict) -> dict:
    """Call the reference ratecv; state may be null (fresh) or structured."""
    state = item.get("state")
    if state is None:
        state_tuple = None
    else:
        # JSON round-trips tuples as lists; the reference requires tuples
        state_tuple = (
            int(state["d"]),
            tuple(tuple(int(value) for value in pair) for pair in state["channels"]),
        )
    try:
        out, returned = audioop.ratecv(
            bytes.fromhex(item["fragment_hex"]),
            int(item["width"]),
            int(item["nchannels"]),
            int(item["inrate"]),
            int(item["outrate"]),
            state_tuple,
            int(item.get("weightA", 1)),
            int(item.get("weightB", 0)),
        )
    except Exception as exc:  # the reference defines these messages
        return {"error_type": type(exc).__name__, "error_message": str(exc)}
    return {
        "result_hex": out.hex(),
        "state": {
            "d": returned[0],
            "channels": [[prev, cur] for prev, cur in returned[1]],
        },
    }


def main() -> int:
    request = json.load(sys.stdin)
    response = {
        "decode": [_decode_one(item) for item in request.get("decode", [])],
        "encode": [_encode_one(item) for item in request.get("encode", [])],
        "add": [_add_one(item) for item in request.get("add", [])],
        "bias": [_bias_one(item) for item in request.get("bias", [])],
        "mul": [_mul_one(item) for item in request.get("mul", [])],
        "reverse": [_reverse_one(item) for item in request.get("reverse", [])],
        "byteswap": [_byteswap_one(item) for item in request.get("byteswap", [])],
        "lin2lin": [_lin2lin_one(item) for item in request.get("lin2lin", [])],
        "getsample": [_getsample_one(item) for item in request.get("getsample", [])],
        "max": [_max_one(item) for item in request.get("max", [])],
        "minmax": [_minmax_one(item) for item in request.get("minmax", [])],
        "avg": [_avg_one(item) for item in request.get("avg", [])],
        "rms": [_rms_one(item) for item in request.get("rms", [])],
        "cross": [_cross_one(item) for item in request.get("cross", [])],
        "avgpp": [_avgpp_one(item) for item in request.get("avgpp", [])],
        "maxpp": [_maxpp_one(item) for item in request.get("maxpp", [])],
        "findmax": [_findmax_one(item) for item in request.get("findmax", [])],
        "findfactor": [_findfactor_one(item) for item in request.get("findfactor", [])],
        "findfit": [_findfit_one(item) for item in request.get("findfit", [])],
        "tomono": [_tomono_one(item) for item in request.get("tomono", [])],
        "tostereo": [_tostereo_one(item) for item in request.get("tostereo", [])],
        "ratecv": [_ratecv_one(item) for item in request.get("ratecv", [])],
    }
    json.dump(response, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
