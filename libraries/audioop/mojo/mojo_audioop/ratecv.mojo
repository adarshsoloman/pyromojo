"""Phase 6 stateful sample-rate conversion (`ratecv`).

Faithful port of CPython 3.12.3 ``Modules/audioop.c`` ``audioop_ratecv``:

- Validation order: argument integer ranges (C ``int`` conversion,
  raising ``Python int too large to convert to C int``), then sample
  width, then ``nchannels >= 1``, then the ``width * nchannels`` C-int
  overflow check, then weights (``weightA >= 1``, ``weightB >= 0``),
  then fragment alignment in whole frames, then ``inrate/outrate > 0``.
- ``inrate``/``outrate`` and ``weightA``/``weightB`` are reduced by
  their greatest common divisors before use.
- Samples are scaled to the 32-bit position exactly like the
  reference's ``GETSAMPLE32``/``SETSAMPLE32`` (multiplied by
  ``2^(32 - 8*width)``), so all filtering happens at the same scale.
- The filter recurrence is
  ``cur_i = (int)((weightA*cur_i + weightB*prev_i) / (weightA+weightB))``
  evaluated in double with C truncation toward zero; the output
  interpolation is
  ``cur_o = (int)((prev_i*d + cur_i*(outrate-d)) / outrate)``, also
  truncated toward zero. Output samples are stored through the same
  top-aligned shift the reference uses.
- State is ``(d, (prev_i, cur_i) per channel)``. A fresh state starts
  with ``d = -outrate`` (after reduction) and all-zero filter history.
  Output is produced only in the ``d >= 0`` phase; input is consumed
  only in the ``d < 0`` phase, so processing is exactly chunk-composable
  (verified against the reference).
"""

from std.collections import List

from mojo_audioop.samples import (
    decode_fragment,
    encode_fragment,
    validate_width,
)


struct RatecvState:
    """Filter history: phase accumulator and per-channel 32-bit samples."""

    var d: Int64
    var prev_i: List[Int64]
    var cur_i: List[Int64]

    def __init__(out self, d: Int64, var prev_i: List[Int64], var cur_i: List[Int64]):
        self.d = d
        self.prev_i = prev_i^
        self.cur_i = cur_i^


struct RatecvResult:
    """Converted fragment plus the state to feed into the next call."""

    var output: List[UInt8]
    var state: RatecvState

    def __init__(out self, var output: List[UInt8], var state: RatecvState):
        self.output = output^
        self.state = state^


def _gcd(a: Int64, b: Int64) -> Int64:
    """Reference gcd: Euclid on non-negative values (b == 0 returns a)."""
    var x = a if a >= 0 else -a
    var y = b if b >= 0 else -b
    while y != 0:
        var tmp = x % y
        x = y
        y = tmp
    return x


def _check_c_int(value: Int64) raises:
    if value < -2147483648 or value > 2147483647:
        raise Error("Python int too large to convert to C int")


def _ratecv_run(
    fragment: Span[UInt8, _],
    width: Int,
    nchannels: Int64,
    inrate: Int64,
    outrate: Int64,
    weight_a: Int64,
    weight_b: Int64,
    continued: Bool,
    var state: RatecvState,
) raises -> RatecvResult:
    # C argument conversion happens left-to-right before any body checks.
    _check_c_int(nchannels)
    _check_c_int(inrate)
    _check_c_int(outrate)
    _check_c_int(weight_a)
    _check_c_int(weight_b)

    validate_width(width)
    var chans = Int(nchannels)
    if nchannels < 1:
        raise Error("# of channels should be >= 1")
    if Int64(width) > Int64(2147483647) // nchannels:
        raise Error("width * nchannels too big for a C int")
    if weight_a < 1 or weight_b < 0:
        raise Error("weightA should be >= 1, weightB should be >= 0")
    if len(fragment) % (width * chans) != 0:
        raise Error("not a whole number of frames")
    if inrate <= 0 or outrate <= 0:
        raise Error("sampling rate not > 0")

    var divisor = _gcd(inrate, outrate)
    var in_reduced = inrate // divisor
    var out_reduced = outrate // divisor
    var weight_div = _gcd(weight_a, weight_b)
    var wa = weight_a // weight_div
    var wb = weight_b // weight_div

    if not continued:
        state.d = 0 - out_reduced
        state.prev_i = List[Int64](capacity=chans)
        state.cur_i = List[Int64](capacity=chans)
        for _ in range(chans):
            state.prev_i.append(0)
            state.cur_i.append(0)

    var shift = Int64((4 - width) * 8)
    var samples = decode_fragment(fragment, width)
    var frames = len(samples) // chans

    var out_values = List[Int64]()
    var frame_index: Int = 0
    while True:
        while state.d < 0:
            if frame_index == frames:
                var output = encode_fragment(Span(out_values), width)
                return RatecvResult(output^, state^)
            for chan in range(chans):
                state.prev_i[chan] = state.cur_i[chan]
                var raw = Int64(samples[frame_index * chans + chan]) << shift
                var filtered = (
                    Float64(wa) * Float64(raw) + Float64(wb) * Float64(state.prev_i[chan])
                ) / (Float64(wa) + Float64(wb))
                state.cur_i[chan] = Int64(filtered)
            frame_index += 1
            state.d += out_reduced
        while state.d >= 0:
            for chan in range(chans):
                var mixed = (
                    Float64(state.prev_i[chan]) * Float64(state.d)
                    + Float64(state.cur_i[chan]) * Float64(out_reduced - state.d)
                ) / Float64(out_reduced)
                out_values.append(Int64(mixed) >> shift)
            state.d -= in_reduced

    # ponytail: unreachable; the d<0 phase always finalizes


def ratecv(
    fragment: Span[UInt8, _],
    width: Int,
    nchannels: Int64,
    inrate: Int64,
    outrate: Int64,
    weight_a: Int64 = 1,
    weight_b: Int64 = 0,
) raises -> RatecvResult:
    """Convert sample rate with a fresh filter state (reference ``state=None``)."""
    var fresh = RatecvState(0, List[Int64](), List[Int64]())
    return _ratecv_run(
        fragment, width, nchannels, inrate, outrate, weight_a, weight_b, False, fresh^
    )


def ratecv_continue(
    fragment: Span[UInt8, _],
    width: Int,
    nchannels: Int64,
    inrate: Int64,
    outrate: Int64,
    var state: RatecvState,
    weight_a: Int64 = 1,
    weight_b: Int64 = 0,
) raises -> RatecvResult:
    """Convert sample rate continuing from a previously returned state."""
    return _ratecv_run(
        fragment, width, nchannels, inrate, outrate, weight_a, weight_b, True, state^
    )
