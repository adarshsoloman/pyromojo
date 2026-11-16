"""Deterministic audioop benchmark workloads (seed 20260610).

Workload sizes follow `docs/benchmark-design.md` with a documented
adaptation: the primary matrix uses small/medium/large = 160/4096/65536
frames (the 1 Mi-frame tier is omitted because the pure-Python floor
path would dominate run time); content coverage is provided through a
separate content-type sweep rather than every content type in every
cell.
"""

from __future__ import annotations

SEED = 20260610
SMALL_FRAMES = 160  # 20 ms @ 8 kHz
MEDIUM_FRAMES = 4096
LARGE_FRAMES = 65536
FIND_WINDOW = 8


def fnv1a_checksum(data: bytes) -> str:
    h = 0x811C9DC5
    for byte in data:
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def _rng(seed: int):
    state = seed & 0xFFFFFFFF
    while True:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        yield state


def content(width: int, frames: int, kind: str, seed: int = SEED) -> bytes:
    """Deterministic sample content of a given width."""
    lo, hi = -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1
    rng = _rng(seed)
    values: list[int] = []
    if kind == "silence":
        values = [0] * frames
    elif kind == "square":
        values = [hi if i % 2 == 0 else lo for i in range(frames)]
    elif kind == "sine":
        # integer sine approximation via a 1024-entry quarter table
        for i in range(frames):
            phase = (i * 7) % 1024
            t = phase if phase < 512 else 1023 - phase
            s = (t - 256) * (hi // 256) // 255
            values.append(max(lo, min(hi, s)))
    elif kind == "random":
        values = [lo + (next(rng) % (hi - lo + 1)) for _ in range(frames)]
    elif kind == "sparse":
        for _ in range(frames):
            values.append(next(rng) % 97 == 0 and lo or 0)
    elif kind == "ramp":
        step = max(1, (hi - lo) // max(1, frames))
        v = lo
        for _ in range(frames):
            values.append(v)
            v = hi if v + step > hi else v + step
    elif kind == "clipped":
        for i in range(frames):
            values.append(hi if i % 3 == 0 else lo if i % 3 == 1 else 0)
    elif kind == "impulses":
        values = [hi if i % 16 == 0 else 0 for i in range(frames)]
    else:
        raise ValueError(f"unknown content kind {kind}")
    return b"".join(v.to_bytes(width, "little", signed=True) for v in values)


def stereo(width: int, frames: int, kind: str, seed: int = SEED) -> bytes:
    """Interleaved two-channel content (left random, right ramp)."""
    lo, hi = -(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1
    rng = _rng(seed)
    out = bytearray()
    step = max(1, (hi - lo) // max(1, frames))
    v = lo
    for _ in range(frames):
        left = 0 if kind == "silence" else lo + next(rng) % (hi - lo + 1)
        out += left.to_bytes(width, "little", signed=True)
        out += v.to_bytes(width, "little", signed=True)
        v = hi if v + step > hi else v + step
    return bytes(out)


def find_fragment(window: int, mult: int, seed: int = SEED) -> bytes:
    """16-bit fragment of `mult * window` samples for the find* family."""
    return content(2, window * mult, "random", seed)


def adpcm_bytes(count: int, seed: int = SEED) -> bytes:
    rng = _rng(seed)
    return bytes(next(rng) % 256 for _ in range(count))


def op_workloads() -> list[dict]:
    """The primary benchmark matrix: one entry per (op, workload)."""
    w: list[dict] = []

    def add(
        op,
        width,
        frames,
        *,
        kind="random",
        stereo_kind=None,
        factor=1.5,
        newwidth=None,
        note="",
        fragment=None,
    ):
        if fragment is None:
            frag = (
                stereo(width, frames, stereo_kind) if stereo_kind else content(width, frames, kind)
            )
        else:
            frag = fragment
        w.append(
            {
                "op": op,
                "width": width,
                "frames": frames,
                "kind": kind,
                "factor": factor,
                "newwidth": newwidth,
                "note": note,
                "fragment": frag,
            }
        )

    # arithmetic (widths 1/2/4; stereo tomono/tostereo at width 2)
    for width in (1, 2, 4):
        for frames in (SMALL_FRAMES, MEDIUM_FRAMES, LARGE_FRAMES):
            add("add", width, frames)
            add("bias", width, frames)
            add("mul", width, frames, factor=0.5)
            add("byteswap", width, frames)
            add("reverse", width, frames)
    add("add", 2, SMALL_FRAMES, stereo_kind="random")
    add("tomono", 2, SMALL_FRAMES, stereo_kind="random", factor=0.5)
    add("tomono", 2, MEDIUM_FRAMES, stereo_kind="random", factor=0.5)
    add("tomono", 2, LARGE_FRAMES, stereo_kind="random", factor=0.5)
    add("tostereo", 2, SMALL_FRAMES, kind="random", factor=0.5)
    add("tostereo", 2, MEDIUM_FRAMES, kind="random", factor=0.5)
    add("tostereo", 2, LARGE_FRAMES, kind="random", factor=0.5)

    # statistics
    for width in (1, 2, 4):
        for frames in (SMALL_FRAMES, MEDIUM_FRAMES, LARGE_FRAMES):
            for op in ("max", "minmax", "avg", "rms", "cross", "avgpp", "maxpp"):
                add(op, width, frames)

    # getsample: first/middle/last on the large fragment
    for width in (1, 2, 4):
        add("getsample", width, LARGE_FRAMES, note="middle")

    # lin2lin: up and down conversions at width 2, plus 4->1
    for frames in (SMALL_FRAMES, MEDIUM_FRAMES, LARGE_FRAMES):
        add("lin2lin", 2, frames, newwidth=4)
        add("lin2lin", 2, frames, newwidth=1)
    add("lin2lin", 4, MEDIUM_FRAMES, newwidth=1)

    # codecs at width 2 (16-bit is the native codec scale) + width 1/4 spot
    for width in (1, 2, 4):
        for frames in (SMALL_FRAMES, MEDIUM_FRAMES, LARGE_FRAMES):
            add("lin2alaw", width, frames)
            add("lin2ulaw", width, frames)
    add("alaw2lin", 2, SMALL_FRAMES, kind="random")
    add("alaw2lin", 2, MEDIUM_FRAMES, kind="random")
    add("alaw2lin", 2, LARGE_FRAMES, kind="random")
    add("ulaw2lin", 2, SMALL_FRAMES, kind="random")
    add("ulaw2lin", 2, MEDIUM_FRAMES, kind="random")
    add("ulaw2lin", 2, LARGE_FRAMES, kind="random")
    # codec decoders over packed codeword bytes (count = frames)
    for frames in (SMALL_FRAMES, MEDIUM_FRAMES, LARGE_FRAMES):
        w.append(
            {
                "op": "alaw2lin_bytes",
                "width": 2,
                "frames": frames,
                "fragment": bytes((i * 37 + 11) % 256 for i in range(frames)),
            }
        )
        w.append(
            {
                "op": "ulaw2lin_bytes",
                "width": 2,
                "frames": frames,
                "fragment": bytes((i * 91 + 5) % 256 for i in range(frames)),
            }
        )

    # ADPCM: encoder cold/warm, decoder
    for frames in (SMALL_FRAMES, MEDIUM_FRAMES, LARGE_FRAMES):
        add("lin2adpcm", 2, frames, note="cold")
        add("adpcm2lin", 2, frames, fragment=adpcm_bytes((frames + 1) // 2, SEED + 1), note="cold")
    add("lin2adpcm", 2, MEDIUM_FRAMES, note="warm")
    add(
        "adpcm2lin",
        2,
        MEDIUM_FRAMES,
        note="warm",
        fragment=adpcm_bytes(MEDIUM_FRAMES // 2, SEED + 1),
    )

    # ratecv: cold and warm, 8k->16k and 44.1k->48k, mono and stereo
    for frames in (SMALL_FRAMES, MEDIUM_FRAMES, LARGE_FRAMES):
        add("ratecv", 2, frames, note="cold 8k->16k")
        add("ratecv", 2, MEDIUM_FRAMES, note="warm 8k->16k")
        add("ratecv", 2, MEDIUM_FRAMES, note="cold 44100->48000")
        add("ratecv", 2, MEDIUM_FRAMES, note="stereo cold 8k->16k", stereo_kind="random")
    add("ratecv", 1, MEDIUM_FRAMES, note="cold 8k->16k")

    # find* family: 16-bit, windows 1/8/64, fragment 4x window
    for window in (1, 8, 64):
        w.append(
            {
                "op": "findmax",
                "width": 2,
                "frames": window * 4,
                "fragment": find_fragment(window, 4),
                "note": f"w{window}",
            }
        )
        w.append(
            {
                "op": "findfit",
                "width": 2,
                "frames": window * 4,
                "fragment": find_fragment(window, 4),
                "reference": find_fragment(window, 1),
                "note": f"w{window}",
            }
        )
        w.append(
            {
                "op": "findfactor",
                "width": 2,
                "frames": window,
                "fragment": find_fragment(window, 1),
                "reference": find_fragment(window, 1),
                "note": f"w{window}",
            }
        )
    w.append(
        {
            "op": "findmax",
            "width": 2,
            "frames": MEDIUM_FRAMES,
            "fragment": find_fragment(FIND_WINDOW, MEDIUM_FRAMES // FIND_WINDOW),
            "note": "w8-large",
        }
    )

    # content-type sweep: representative subset at width 2 / medium
    for kind in ("silence", "square", "sine", "random", "sparse", "ramp", "clipped", "impulses"):
        for op in ("add", "mul", "max", "rms", "cross", "lin2ulaw", "lin2adpcm", "ratecv"):
            entry = {
                "op": op,
                "width": 2,
                "frames": MEDIUM_FRAMES,
                "kind": kind,
                "factor": 0.5,
                "note": f"content-{kind}",
                "fragment": content(2, MEDIUM_FRAMES, kind),
            }
            if op == "ratecv":
                entry["note"] = f"cold content-{kind}"
            w.append(entry)
    return w
