"""CPython 3.12.3 reference worker for the audioop benchmark.

Protocol (one JSON response per line):
  <op>|<json {"args": [...]}>                -> ["ok", result] / ["err", ...]
  TIME|<op>|<json {"args": [...], "warmup": n, "samples": n}>
                                             -> ["samples", [ns, ...]]

Results: bytes -> hex string; tuples -> lists (bytes as hex); ints,
floats and strings pass through. Timing happens in-process inside this
worker (perf_counter_ns), so process round-trips stay outside the
measured region. Per-line errors are reported, never fatal.
"""

import json
import sys
import time
import warnings

warnings.simplefilter("ignore", DeprecationWarning)
import audioop  # noqa: E402


def decode_args(args):
    out = []
    for value in args:
        if isinstance(value, dict) and "__hex__" in value:
            out.append(bytes.fromhex(value["__hex__"]))
        elif isinstance(value, list):
            out.append(
                tuple(decode_args(item) if isinstance(item, list) else item for item in value)
            )
        else:
            out.append(value)
    return tuple(out)


def convert(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, tuple):
        return [convert(item) for item in value]
    return value


def process_line(line: str) -> None:
    parts = line.rstrip("\n").split("|", 2)
    if parts[0] == "TIME":
        op = parts[1]
        spec = json.loads(parts[2])
        fn = getattr(audioop, op)
        call_args = decode_args(spec["args"])
        for _ in range(spec.get("warmup", 5)):
            fn(*call_args)
        samples = []
        for _ in range(spec.get("samples", 25)):
            start = time.perf_counter_ns()
            fn(*call_args)
            samples.append(time.perf_counter_ns() - start)
        print(json.dumps(["samples", samples]), flush=True)
    else:
        op = parts[0]
        spec = json.loads(parts[1])
        fn = getattr(audioop, op, None)
        if fn is None:
            print(json.dumps(["err", "AttributeError", f"no audioop.{op}"]), flush=True)
            return
        try:
            print(json.dumps(["ok", convert(fn(*decode_args(spec["args"])))]), flush=True)
        except Exception as exc:
            print(json.dumps(["err", type(exc).__name__, str(exc)]), flush=True)


for line in sys.stdin:
    try:
        process_line(line)
    except Exception as exc:
        print(json.dumps(["err", type(exc).__name__, str(exc)]), flush=True)
