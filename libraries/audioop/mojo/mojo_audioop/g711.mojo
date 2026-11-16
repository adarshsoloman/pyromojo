"""Phase 7 G.711 A-law and mu-law codecs.

Port of CPython 3.12.3 ``Modules/audioop.c`` (SoX-derived g777/g771
code):

- ``lin2ulaw``: each sample is scaled to the 32-bit position
  (``GETSAMPLE32``), shifted right by 18 (arithmetic), then encoded by
  ``st_14linear2ulaw``: magnitude, clip at 32635, add bias 33, find the
  segment against ``seg_uend``, pack ``seg<<4 | (val >> (seg+1)) & 0xF``
  and complement with ``0xFF`` (positive) or ``0x7F`` (negative).
- ``lin2alaw``: 32-bit sample shifted right by 19 (arithmetic), then
  ``st_linear2alaw``: positive values use mask ``0xD5``; negative values
  use ``0x55`` with ``value = -value - 1``; segment against ``seg_aend``
  (first ``val <= seg_aend[i]``); quantization bits
  ``(val >> 1) & 0xF`` for segments 0-1, ``(val >> seg) & 0xF``
  otherwise; XOR with the mask.
- ``ulaw2lin``/``alaw2lin``: width is validated but fragment alignment
  is NOT (any byte length is accepted); every input byte decodes
  through the reference's 256-entry ``int16`` tables and is stored as
  ``decoded16 << 16`` through ``SETSAMPLE32`` (top-aligned truncating
  shift per width).

The decoder tables are embedded verbatim from the reference source and
verified exhaustively (all 256 codewords, both codecs).
"""

from std.collections import List
from std.utils import StaticTuple

from mojo_audioop.samples import (
    decode_fragment,
    encode_fragment,
    validate_fragment,
    validate_width,
)


comptime CLIP: Int64 = 32635
comptime ULAW_BIAS: Int64 = 33
comptime SEG_UEND = StaticTuple[Int64, 8](63, 127, 255, 511, 1023, 2047, 4095, 8191)
comptime SEG_AEND = StaticTuple[Int64, 8](31, 63, 127, 255, 511, 1023, 2047, 4095)


comptime ULAW2LINEAR16 = StaticTuple[Int16, 256](
    -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
    -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
    -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
    -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
    -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
    -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
    -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
    -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
    -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
    -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
    -876, -844, -812, -780, -748, -716, -684, -652,
    -620, -588, -556, -524, -492, -460, -428, -396,
    -372, -356, -340, -324, -308, -292, -276, -260,
    -244, -228, -212, -196, -180, -164, -148, -132,
    -120, -112, -104, -96, -88, -80, -72, -64,
    -56, -48, -40, -32, -24, -16, -8, 0,
    32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
    23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
    15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
    11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
    7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
    5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
    3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
    2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
    1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
    1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
    876, 844, 812, 780, 748, 716, 684, 652,
    620, 588, 556, 524, 492, 460, 428, 396,
    372, 356, 340, 324, 308, 292, 276, 260,
    244, 228, 212, 196, 180, 164, 148, 132,
    120, 112, 104, 96, 88, 80, 72, 64,
    56, 48, 40, 32, 24, 16, 8, 0,
)

comptime ALAW2LINEAR16 = StaticTuple[Int16, 256](
    -5504, -5248, -6016, -5760, -4480, -4224, -4992, -4736,
    -7552, -7296, -8064, -7808, -6528, -6272, -7040, -6784,
    -2752, -2624, -3008, -2880, -2240, -2112, -2496, -2368,
    -3776, -3648, -4032, -3904, -3264, -3136, -3520, -3392,
    -22016, -20992, -24064, -23040, -17920, -16896, -19968, -18944,
    -30208, -29184, -32256, -31232, -26112, -25088, -28160, -27136,
    -11008, -10496, -12032, -11520, -8960, -8448, -9984, -9472,
    -15104, -14592, -16128, -15616, -13056, -12544, -14080, -13568,
    -344, -328, -376, -360, -280, -264, -312, -296,
    -472, -456, -504, -488, -408, -392, -440, -424,
    -88, -72, -120, -104, -24, -8, -56, -40,
    -216, -200, -248, -232, -152, -136, -184, -168,
    -1376, -1312, -1504, -1440, -1120, -1056, -1248, -1184,
    -1888, -1824, -2016, -1952, -1632, -1568, -1760, -1696,
    -688, -656, -752, -720, -560, -528, -624, -592,
    -944, -912, -1008, -976, -816, -784, -880, -848,
    5504, 5248, 6016, 5760, 4480, 4224, 4992, 4736,
    7552, 7296, 8064, 7808, 6528, 6272, 7040, 6784,
    2752, 2624, 3008, 2880, 2240, 2112, 2496, 2368,
    3776, 3648, 4032, 3904, 3264, 3136, 3520, 3392,
    22016, 20992, 24064, 23040, 17920, 16896, 19968, 18944,
    30208, 29184, 32256, 31232, 26112, 25088, 28160, 27136,
    11008, 10496, 12032, 11520, 8960, 8448, 9984, 9472,
    15104, 14592, 16128, 15616, 13056, 12544, 14080, 13568,
    344, 328, 376, 360, 280, 264, 312, 296,
    472, 456, 504, 488, 408, 392, 440, 424,
    88, 72, 120, 104, 24, 8, 56, 40,
    216, 200, 248, 232, 152, 136, 184, 168,
    1376, 1312, 1504, 1440, 1120, 1056, 1248, 1184,
    1888, 1824, 2016, 1952, 1632, 1568, 1760, 1696,
    688, 656, 752, 720, 560, 528, 624, 592,
    944, 912, 1008, 976, 816, 784, 880, 848,
)

def _search(value: Int64, table: StaticTuple[Int64, 8]) -> Int64:
    """Reference ``search``: first index with ``value <= table[i]``, else 8."""
    for index in range(8):
        if value <= table[index]:
            return Int64(index)
    return 8


def _linear2ulaw(pcm_val: Int64) -> UInt8:
    """Reference ``st_14linear2ulaw`` on the 14-bit magnitude."""
    var mask: Int64 = 0xFF
    var value = pcm_val
    if value < 0:
        value = -value
        mask = 0x7F
    if value > CLIP:
        value = CLIP
    value += ULAW_BIAS
    var seg = _search(value, SEG_UEND)
    if seg >= 8:
        return UInt8(0x7F ^ mask)
    var uval = (seg << 4) | ((value >> (seg + 1)) & 0xF)
    return UInt8(uval ^ mask)


def _linear2alaw(pcm_val: Int64) -> UInt8:
    """Reference ``st_linear2alaw`` on the 13-bit magnitude."""
    var mask: Int64 = 0xD5
    var value = pcm_val
    if value < 0:
        mask = 0x55
        value = -value - 1
    var seg = _search(value, SEG_AEND)
    if seg >= 8:
        return UInt8(0x7F ^ mask)
    var aval = seg << 4
    if seg < 2:
        aval |= (value >> 1) & 0xF
    else:
        aval |= (value >> seg) & 0xF
    return UInt8(aval ^ mask)


def _ulaw2linear16(code: UInt8) -> Int64:
    """Reference ``_st_ulaw2linear16`` lookup table (256 entries)."""
    return Int64(ULAW2LINEAR16[code])


def _alaw2linear16(code: UInt8) -> Int64:
    """Reference ``_st_alaw2linear16`` lookup table (256 entries)."""
    return Int64(ALAW2LINEAR16[code])


def lin2ulaw(fragment: Span[UInt8, _], width: Int) raises -> List[UInt8]:
    """Encode samples to mu-law; one byte per sample."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    # GETSAMPLE32 then >> 18 composes to this shift per width
    var shift = Int64((4 - width) * 8 - 18)
    var out = List[UInt8](capacity=len(samples))
    for index in range(len(samples)):
        var value = Int64(samples[index])
        if shift > 0:
            value = value << shift
        elif shift < 0:
            value = value >> Int64(-shift)
        out.append(_linear2ulaw(value))
    return out^


def lin2alaw(fragment: Span[UInt8, _], width: Int) raises -> List[UInt8]:
    """Encode samples to A-law; one byte per sample."""
    validate_fragment(fragment, width)
    var samples = decode_fragment(fragment, width)
    var shift = Int64((4 - width) * 8 - 19)
    var out = List[UInt8](capacity=len(samples))
    for index in range(len(samples)):
        var value = Int64(samples[index])
        if shift > 0:
            value = value << shift
        elif shift < 0:
            value = value >> Int64(-shift)
        out.append(_linear2alaw(value))
    return out^


def ulaw2lin(fragment: Span[UInt8, _], width: Int) raises -> List[UInt8]:
    """Decode mu-law bytes to samples at ``width`` (alignment not required)."""
    validate_width(width)
    var out = List[Int64](capacity=len(fragment))
    var shift = Int64((4 - width) * 8)
    for index in range(len(fragment)):
        # decoded16 * 2^16, stored through SETSAMPLE32's top-aligned shift
        out.append(_ulaw2linear16(fragment[index]) << Int64(16) >> shift)
    return encode_fragment(Span(out), width)


def alaw2lin(fragment: Span[UInt8, _], width: Int) raises -> List[UInt8]:
    """Decode A-law bytes to samples at ``width`` (alignment not required)."""
    validate_width(width)
    var out = List[Int64](capacity=len(fragment))
    var shift = Int64((4 - width) * 8)
    for index in range(len(fragment)):
        out.append(_alaw2linear16(fragment[index]) << Int64(16) >> shift)
    return encode_fragment(Span(out), width)
