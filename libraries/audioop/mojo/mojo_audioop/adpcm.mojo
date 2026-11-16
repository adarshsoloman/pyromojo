"""Phase 8 Intel/DVI ADPCM encoding and decoding.

Faithful port of CPython 3.12.3 ``Modules/audioop.c`` ``audioop_lin2adpcm``
and ``audioop_adpcm2lin``:

- Both use the IMA/DVI step-size table (89 entries) and index adjustment
  table (16 entries).
- ``lin2adpcm`` validates width and alignment first, then the state
  (``None`` -> ``(0, 0)``; a non-tuple raises ``TypeError state must be
  a tuple or None`` in the reference; out-of-range predictor or index
  raises ``ValueError bad state``). Input samples are read at the
  32-bit position and shifted right by 16 (width 1 is scaled up by 256,
  width 2 is unchanged, width 3 shifts right by 8, width 4 by 16). The
  predictor is updated with the **quantized reconstructed difference**,
  not the input sample, then clamped to [-32768, 32767]; the step index
  is clamped to [0, 88]. Nibbles pack high-nibble-first; an odd
  trailing sample updates the state but its nibble is dropped (the
  reference allocates ``len / (width*2)`` output bytes).
- ``adpcm2lin`` validates the width only (any input byte length is
  accepted), decodes the high nibble of each byte first, reconstructs
  the predictor the same way, clamps identically, and stores
  ``valpred << 16`` through the top-aligned shift (like the G.711
  decoders). Two output samples per input byte.
- State is the pair ``(valpred, index)`` — identical structure for
  encoder and decoder, returned unchanged for empty input.

Chunk composition: even-sized encoder chunks concatenate exactly;
odd-sized chunks do NOT (each call starts a fresh nibble buffer, so an
odd chunk drops its trailing nibble and shifts the next chunk's first
sample into a high nibble). Decoder chunks always compose.
"""

from std.collections import List
from std.utils import StaticTuple

from mojo_audioop.samples import (
    decode_fragment,
    encode_fragment,
    validate_fragment,
    validate_width,
)


comptime INDEX_TABLE = StaticTuple[Int64, 16](
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8,
)
comptime STEPSIZE_TABLE = StaticTuple[Int64, 89](
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
    5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
)


struct AdpcmState:
    """Reference state ``(valpred, index)``; predictor and step index."""

    var valpred: Int64
    var index: Int64

    def __init__(out self, valpred: Int64, index: Int64):
        self.valpred = valpred
        self.index = index


def _check_state(state: AdpcmState) raises:
    if state.valpred >= 32768 or state.valpred < -32768:
        raise Error("bad state")
    if state.index < 0 or state.index >= 89:
        raise Error("bad state")


struct AdpcmResult:
    """Encoded/decoded bytes plus the updated ``(valpred, index)`` state."""

    var output: List[UInt8]
    var state: AdpcmState

    def __init__(out self, var output: List[UInt8], var state: AdpcmState):
        self.output = output^
        self.state = state^


def lin2adpcm(
    fragment: Span[UInt8, _], width: Int, var state: AdpcmState
) raises -> AdpcmResult:
    """Encode samples to packed 4-bit ADPCM nibbles (high nibble first).

    The returned ``AdpcmState`` is ``(valpred, index)`` after every
    input sample, including a dropped odd trailing sample.
    """
    validate_fragment(fragment, width)
    _check_state(state)
    var step = STEPSIZE_TABLE[state.index]
    var outputbuffer: Int64 = 0
    var bufferstep = True
    var in_shift = Int64((4 - width) * 8)
    var samples = decode_fragment(fragment, width)
    var out = List[UInt8](capacity=len(samples) // 2)
    for sample_index in range(len(samples)):
        var val = Int64(samples[sample_index]) << in_shift >> Int64(16)
        var diff: Int64
        var sign: Int64 = 0
        if val < state.valpred:
            diff = state.valpred - val
            sign = 8
        else:
            diff = val - state.valpred
        var delta: Int64 = 0
        var vpdiff = step >> 3
        if diff >= step:
            delta = 4
            diff -= step
            vpdiff += step
        step = step >> 1
        if diff >= step:
            delta = delta | 2
            diff -= step
            vpdiff += step
        step = step >> 1
        if diff >= step:
            delta = delta | 1
            vpdiff += step
        if sign != 0:
            state.valpred -= vpdiff
        else:
            state.valpred += vpdiff
        if state.valpred > 32767:
            state.valpred = 32767
        elif state.valpred < -32768:
            state.valpred = -32768
        delta = delta | sign
        state.index += INDEX_TABLE[delta]
        if state.index < 0:
            state.index = 0
        if state.index > 88:
            state.index = 88
        step = STEPSIZE_TABLE[state.index]
        if bufferstep:
            outputbuffer = (delta * 16) & 0xF0
        else:
            out.append(UInt8((delta & 0x0F) | outputbuffer))
        bufferstep = not bufferstep
    return AdpcmResult(out^, state^)


def adpcm2lin(
    fragment: Span[UInt8, _], width: Int, var state: AdpcmState
) raises -> AdpcmResult:
    """Decode packed ADPCM nibbles to samples (two per input byte)."""
    validate_width(width)
    _check_state(state)
    var step = STEPSIZE_TABLE[state.index]
    var out = List[Int64](capacity=len(fragment) * 2)
    var out_shift = Int64((4 - width) * 8)
    for byte_index in range(len(fragment)):
        var inputbuffer = Int64(fragment[byte_index])
        for nibble_index in range(2):
            var delta = (inputbuffer >> Int64(4 - nibble_index * 4)) & 0xF
            state.index += INDEX_TABLE[delta]
            if state.index < 0:
                state.index = 0
            if state.index > 88:
                state.index = 88
            var sign = delta & 8
            delta = delta & 7
            var vpdiff = step >> 3
            if (delta & 4) != 0:
                vpdiff += step
            if (delta & 2) != 0:
                vpdiff += step >> 1
            if (delta & 1) != 0:
                vpdiff += step >> 2
            if sign != 0:
                state.valpred -= vpdiff
            else:
                state.valpred += vpdiff
            if state.valpred > 32767:
                state.valpred = 32767
            elif state.valpred < -32768:
                state.valpred = -32768
            step = STEPSIZE_TABLE[state.index]
            out.append(state.valpred << Int64(16) >> out_shift)
    var output = encode_fragment(Span(out), width)
    return AdpcmResult(output^, state^)
