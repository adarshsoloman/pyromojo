"""Pure-Python floor implementations of all 26 audioop operations.

Readable per-sample Python loops; no NumPy, no C extensions, and no use
of the CPython ``audioop`` module. These reproduce CPython 3.12.3
semantics exactly (the benchmark correctness gate proves it) including
the documented 32-bit scaling conventions, floor/truncation rules, and
the Sun-derived G.711 and IMA/DVI tables.

Two families are exposed:

- ``*_py``: sample-based operations over bytes fragments.
- ``*`` aliases used by the benchmark driver.
"""

from __future__ import annotations

import math

MAXVALS = [0, 0x7F, 0x7FFF, 0x7FFFFF, 0x7FFFFFFF]
MINVALS = [0, -0x80, -0x8000, -0x800000, -0x7FFFFFFF - 1]
MASKS = [0, 0xFF, 0xFFFF, 0xFFFFFF, 0xFFFFFFFF]


def get32(fragment: bytes, width: int, i: int) -> int:
    """GETSAMPLE32: signed sample scaled to the 32-bit position."""
    if width == 1:
        return int.from_bytes(fragment[i : i + 1], "little", signed=True) << 24
    if width == 2:
        return int.from_bytes(fragment[i : i + 2], "little", signed=True) << 16
    if width == 3:
        return int.from_bytes(fragment[i : i + 3], "little", signed=True) << 8
    return int.from_bytes(fragment[i : i + 4], "little", signed=True)


def set32(width: int, value: int) -> bytes:
    """SETSAMPLE32: top-aligned truncating store."""
    shifted = value >> ((4 - width) * 8)
    return shifted.to_bytes(width, "little", signed=True)


def check_width(width: int) -> None:
    if width < 1 or width > 4:
        raise ValueError("Size should be 1, 2, 3 or 4")


def check_fragment(fragment: bytes, width: int) -> None:
    check_width(width)
    if len(fragment) % width != 0:
        raise ValueError("not a whole number of frames")


def fbound(value: float, minimum: int, maximum: int) -> int:
    """Reference fbound: clamp, floor, C (int) truncation."""
    if value != value:
        return 0  # documented port policy for NaN
    clamped = value
    if value > maximum:
        clamped = float(maximum)
    elif value < minimum + 1.0:
        clamped = float(minimum)
    return math.floor(clamped)


def add_py(width: int, f1: bytes, f2: bytes) -> bytes:
    check_fragment(f1, width)
    if len(f1) != len(f2):
        raise ValueError("Lengths should be the same")
    lo, hi = MINVALS[width], MAXVALS[width]
    out = bytearray()
    for i in range(0, len(f1), width):
        a = int.from_bytes(f1[i : i + width], "little", signed=True)
        b = int.from_bytes(f2[i : i + width], "little", signed=True)
        s = a + b
        if s > hi:
            s = hi
        elif s < lo:
            s = lo
        out += s.to_bytes(width, "little", signed=True)
    return bytes(out)


def bias_py(fragment: bytes, width: int, offset: int) -> bytes:
    if offset < -(2**31) or offset > 2**31 - 1:
        raise OverflowError("Python int too large to convert to C int")
    check_fragment(fragment, width)
    mask = MASKS[width]
    bits = width * 8
    out = bytearray()
    for i in range(0, len(fragment), width):
        raw = int.from_bytes(fragment[i : i + width], "little", signed=True)
        raw = (raw + offset) & mask
        if raw & (1 << (bits - 1)):
            raw -= 1 << bits
        out += raw.to_bytes(width, "little", signed=True)
    return bytes(out)


def mul_py(fragment: bytes, width: int, factor: float) -> bytes:
    check_fragment(fragment, width)
    lo, hi = MINVALS[width], MAXVALS[width]
    out = bytearray()
    for i in range(0, len(fragment), width):
        val = float(int.from_bytes(fragment[i : i + width], "little", signed=True))
        out += fbound(val * factor, lo, hi).to_bytes(width, "little", signed=True)
    return bytes(out)


def reverse_py(fragment: bytes, width: int) -> bytes:
    check_fragment(fragment, width)
    out = bytearray(len(fragment))
    count = len(fragment) // width
    for i in range(count):
        out[(count - 1 - i) * width : (count - i) * width] = fragment[i * width : (i + 1) * width]
    return bytes(out)


def byteswap_py(fragment: bytes, width: int) -> bytes:
    check_fragment(fragment, width)
    out = bytearray(len(fragment))
    for i in range(0, len(fragment), width):
        out[i : i + width] = fragment[i : i + width][::-1]
    return bytes(out)


def lin2lin_py(fragment: bytes, width: int, new_width: int) -> bytes:
    check_fragment(fragment, width)
    check_width(new_width)
    out = bytearray()
    for i in range(0, len(fragment), width):
        val = int.from_bytes(fragment[i : i + width], "little", signed=True)
        if new_width > width:
            val <<= (new_width - width) * 8
        elif new_width < width:
            val >>= (width - new_width) * 8
        out += val.to_bytes(new_width, "little", signed=True)
    return bytes(out)


def getsample_py(fragment: bytes, width: int, index: int) -> int:
    check_fragment(fragment, width)
    if index < 0 or index >= len(fragment) // width:
        raise ValueError("Index out of range")
    return int.from_bytes(fragment[index * width : (index + 1) * width], "little", signed=True)


def max_py(fragment: bytes, width: int) -> int:
    check_fragment(fragment, width)
    best = 0
    for i in range(0, len(fragment), width):
        v = int.from_bytes(fragment[i : i + width], "little", signed=True)
        a = -v if v < 0 else v
        if a > best:
            best = a
    return best


def minmax_py(fragment: bytes, width: int) -> tuple[int, int]:
    check_fragment(fragment, width)
    lo, hi = 0x7FFFFFFF, -0x7FFFFFFF - 1
    for i in range(0, len(fragment), width):
        v = int.from_bytes(fragment[i : i + width], "little", signed=True)
        if v > hi:
            hi = v
        if v < lo:
            lo = v
    return lo, hi


def avg_py(fragment: bytes, width: int) -> int:
    check_fragment(fragment, width)
    count = len(fragment) // width
    if count == 0:
        return 0
    total = 0.0
    for i in range(0, len(fragment), width):
        total += float(int.from_bytes(fragment[i : i + width], "little", signed=True))
    return math.floor(total / count)


def rms_py(fragment: bytes, width: int) -> int:
    check_fragment(fragment, width)
    count = len(fragment) // width
    if count == 0:
        return 0
    total = 0.0
    for i in range(0, len(fragment), width):
        v = float(int.from_bytes(fragment[i : i + width], "little", signed=True))
        total += v * v
    return int(math.sqrt(total / count))


def cross_py(fragment: bytes, width: int) -> int:
    check_fragment(fragment, width)
    ncross = -1
    prev = 17
    for i in range(0, len(fragment), width):
        v = 1 if int.from_bytes(fragment[i : i + width], "little", signed=True) < 0 else 0
        if v != prev:
            ncross += 1
        prev = v
    return ncross


def _unsigned_diff(a: int, b: int) -> int:
    """32-bit unsigned difference ordered by signed comparison."""
    if b < a:
        return ((a & 0xFFFFFFFF) - (b & 0xFFFFFFFF)) & 0xFFFFFFFF
    return ((b & 0xFFFFFFFF) - (a & 0xFFFFFFFF)) & 0xFFFFFFFF


def _peak_walk(fragment: bytes, width: int, want_avg: bool):
    check_fragment(fragment, width)
    if len(fragment) <= width:
        return 0
    prevval = int.from_bytes(fragment[0:width], "little", signed=True)
    prevdiff = 17
    extremevalid = False
    extreme = 0
    nextreme = 0
    total = 0.0
    peak = 0
    for i in range(width, len(fragment), width):
        val = int.from_bytes(fragment[i : i + width], "little", signed=True)
        if val != prevval:
            diff = 1 if val < prevval else 0
            if prevdiff == (1 - diff):
                if extremevalid:
                    d = _unsigned_diff(extreme, prevval)
                    if want_avg:
                        total += float(d)
                        nextreme += 1
                    elif d > peak:
                        peak = d
                extremevalid = True
                extreme = prevval
            prevval = val
            prevdiff = diff
    if want_avg:
        if nextreme == 0:
            return 0
        return int(total / nextreme)
    return peak


def avgpp_py(fragment: bytes, width: int) -> int:
    return _peak_walk(fragment, width, True)


def maxpp_py(fragment: bytes, width: int) -> int:
    return _peak_walk(fragment, width, False)


def _sum2(a: bytes, a_off: int, b: bytes, b_off: int, count: int) -> float:
    total = 0.0
    for i in range(count):
        x = int.from_bytes(a[a_off + i * 2 : a_off + i * 2 + 2], "little", signed=True)
        y = int.from_bytes(b[b_off + i * 2 : b_off + i * 2 + 2], "little", signed=True)
        total += float(x) * float(y)
    return total


def findfactor_py(fragment: bytes, reference: bytes) -> float:
    if len(fragment) % 2 or len(reference) % 2:
        raise ValueError("Strings should be even-sized")
    if len(fragment) != len(reference):
        raise ValueError("Samples should be same size")
    n = len(fragment) // 2
    s_rr = _sum2(reference, 0, reference, 0, n)
    s_ar = _sum2(fragment, 0, reference, 0, n)
    return s_ar / s_rr


def findfit_py(fragment: bytes, reference: bytes) -> tuple[int, float]:
    if len(fragment) % 2 or len(reference) % 2:
        raise ValueError("Strings should be even-sized")
    len1 = len(fragment) // 2
    len2 = len(reference) // 2
    if len1 < len2:
        raise ValueError("First sample should be longer")
    s_rr = _sum2(reference, 0, reference, 0, len2)
    s_aa = _sum2(fragment, 0, fragment, 0, len2)
    s_ar = _sum2(fragment, 0, reference, 0, len2)
    result = (s_rr * s_aa - s_ar * s_ar) / s_aa
    best_result = result
    best_j = 0
    for j in range(1, len1 - len2 + 1):
        a_m1 = float(int.from_bytes(fragment[(j - 1) * 2 : j * 2], "little", signed=True))
        a_lm1 = float(
            int.from_bytes(fragment[(j + len2 - 1) * 2 : (j + len2) * 2], "little", signed=True)
        )
        s_aa = s_aa + a_lm1 * a_lm1 - a_m1 * a_m1
        s_ar = _sum2(fragment, j * 2, reference, 0, len2)
        result = (s_rr * s_aa - s_ar * s_ar) / s_aa
        if result < best_result:
            best_result = result
            best_j = j
    factor = _sum2(fragment, best_j * 2, reference, 0, len2) / s_rr
    return best_j, factor


def findmax_py(fragment: bytes, length: int) -> int:
    if len(fragment) % 2:
        raise ValueError("Strings should be even-sized")
    len1 = len(fragment) // 2
    if length < 0 or len1 < length:
        raise ValueError("Input sample should be longer")
    result = _sum2(fragment, 0, fragment, 0, length)
    best_result = result
    best_j = 0
    for j in range(1, len1 - length + 1):
        a_m1 = float(int.from_bytes(fragment[(j - 1) * 2 : j * 2], "little", signed=True))
        a_lm1 = float(
            int.from_bytes(fragment[(j + length - 1) * 2 : (j + length) * 2], "little", signed=True)
        )
        result = result + a_lm1 * a_lm1 - a_m1 * a_m1
        if result > best_result:
            best_result = result
            best_j = j
    return best_j


SEG_UEND = [0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF]
SEG_AEND = [0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF]
CLIP = 32635


def _search(value: int, table: list[int]) -> int:
    for i in range(8):
        if value <= table[i]:
            return i
    return 8


def _linear2ulaw(pcm: int) -> int:
    mask = 0xFF
    if pcm < 0:
        pcm = -pcm
        mask = 0x7F
    if pcm > CLIP:
        pcm = CLIP
    pcm += 33
    seg = _search(pcm, SEG_UEND)
    if seg >= 8:
        return 0x7F ^ mask
    uval = (seg << 4) | ((pcm >> (seg + 1)) & 0xF)
    return uval ^ mask


def _linear2alaw(pcm: int) -> int:
    mask = 0xD5
    if pcm < 0:
        mask = 0x55
        pcm = -pcm - 1
    seg = _search(pcm, SEG_AEND)
    if seg >= 8:
        return 0x7F ^ mask
    aval = seg << 4
    if seg < 2:
        aval |= (pcm >> 1) & 0xF
    else:
        aval |= (pcm >> seg) & 0xF
    return aval ^ mask


def lin2ulaw_py(fragment: bytes, width: int) -> bytes:
    check_fragment(fragment, width)
    out = bytearray()
    for i in range(0, len(fragment), width):
        out.append(_linear2ulaw(get32(fragment, width, i) >> 18))
    return bytes(out)


def lin2alaw_py(fragment: bytes, width: int) -> bytes:
    check_fragment(fragment, width)
    out = bytearray()
    for i in range(0, len(fragment), width):
        out.append(_linear2alaw(get32(fragment, width, i) >> 19))
    return bytes(out)


# Decode tables transcribed from CPython 3.12.3 Modules/audioop.c
# (Sun Microsystems unrestricted-use notice; see THIRD_PARTY_NOTICES.md).
ULAW2LINEAR16 = [
    -32124,
    -31100,
    -30076,
    -29052,
    -28028,
    -27004,
    -25980,
    -24956,
    -23932,
    -22908,
    -21884,
    -20860,
    -19836,
    -18812,
    -17788,
    -16764,
    -15996,
    -15484,
    -14972,
    -14460,
    -13948,
    -13436,
    -12924,
    -12412,
    -11900,
    -11388,
    -10876,
    -10364,
    -9852,
    -9340,
    -8828,
    -8316,
    -7932,
    -7676,
    -7420,
    -7164,
    -6908,
    -6652,
    -6396,
    -6140,
    -5884,
    -5628,
    -5372,
    -5116,
    -4860,
    -4604,
    -4348,
    -4092,
    -3900,
    -3772,
    -3644,
    -3516,
    -3388,
    -3260,
    -3132,
    -3004,
    -2876,
    -2748,
    -2620,
    -2492,
    -2364,
    -2236,
    -2108,
    -1980,
    -1884,
    -1820,
    -1756,
    -1692,
    -1628,
    -1564,
    -1500,
    -1436,
    -1372,
    -1308,
    -1244,
    -1180,
    -1116,
    -1052,
    -988,
    -924,
    -876,
    -844,
    -812,
    -780,
    -748,
    -716,
    -684,
    -652,
    -620,
    -588,
    -556,
    -524,
    -492,
    -460,
    -428,
    -396,
    -372,
    -356,
    -340,
    -324,
    -308,
    -292,
    -276,
    -260,
    -244,
    -228,
    -212,
    -196,
    -180,
    -164,
    -148,
    -132,
    -120,
    -112,
    -104,
    -96,
    -88,
    -80,
    -72,
    -64,
    -56,
    -48,
    -40,
    -32,
    -24,
    -16,
    -8,
    0,
    32124,
    31100,
    30076,
    29052,
    28028,
    27004,
    25980,
    24956,
    23932,
    22908,
    21884,
    20860,
    19836,
    18812,
    17788,
    16764,
    15996,
    15484,
    14972,
    14460,
    13948,
    13436,
    12924,
    12412,
    11900,
    11388,
    10876,
    10364,
    9852,
    9340,
    8828,
    8316,
    7932,
    7676,
    7420,
    7164,
    6908,
    6652,
    6396,
    6140,
    5884,
    5628,
    5372,
    5116,
    4860,
    4604,
    4348,
    4092,
    3900,
    3772,
    3644,
    3516,
    3388,
    3260,
    3132,
    3004,
    2876,
    2748,
    2620,
    2492,
    2364,
    2236,
    2108,
    1980,
    1884,
    1820,
    1756,
    1692,
    1628,
    1564,
    1500,
    1436,
    1372,
    1308,
    1244,
    1180,
    1116,
    1052,
    988,
    924,
    876,
    844,
    812,
    780,
    748,
    716,
    684,
    652,
    620,
    588,
    556,
    524,
    492,
    460,
    428,
    396,
    372,
    356,
    340,
    324,
    308,
    292,
    276,
    260,
    244,
    228,
    212,
    196,
    180,
    164,
    148,
    132,
    120,
    112,
    104,
    96,
    88,
    80,
    72,
    64,
    56,
    48,
    40,
    32,
    24,
    16,
    8,
    0,
]


ALAW2LINEAR16 = [
    -5504,
    -5248,
    -6016,
    -5760,
    -4480,
    -4224,
    -4992,
    -4736,
    -7552,
    -7296,
    -8064,
    -7808,
    -6528,
    -6272,
    -7040,
    -6784,
    -2752,
    -2624,
    -3008,
    -2880,
    -2240,
    -2112,
    -2496,
    -2368,
    -3776,
    -3648,
    -4032,
    -3904,
    -3264,
    -3136,
    -3520,
    -3392,
    -22016,
    -20992,
    -24064,
    -23040,
    -17920,
    -16896,
    -19968,
    -18944,
    -30208,
    -29184,
    -32256,
    -31232,
    -26112,
    -25088,
    -28160,
    -27136,
    -11008,
    -10496,
    -12032,
    -11520,
    -8960,
    -8448,
    -9984,
    -9472,
    -15104,
    -14592,
    -16128,
    -15616,
    -13056,
    -12544,
    -14080,
    -13568,
    -344,
    -328,
    -376,
    -360,
    -280,
    -264,
    -312,
    -296,
    -472,
    -456,
    -504,
    -488,
    -408,
    -392,
    -440,
    -424,
    -88,
    -72,
    -120,
    -104,
    -24,
    -8,
    -56,
    -40,
    -216,
    -200,
    -248,
    -232,
    -152,
    -136,
    -184,
    -168,
    -1376,
    -1312,
    -1504,
    -1440,
    -1120,
    -1056,
    -1248,
    -1184,
    -1888,
    -1824,
    -2016,
    -1952,
    -1632,
    -1568,
    -1760,
    -1696,
    -688,
    -656,
    -752,
    -720,
    -560,
    -528,
    -624,
    -592,
    -944,
    -912,
    -1008,
    -976,
    -816,
    -784,
    -880,
    -848,
    5504,
    5248,
    6016,
    5760,
    4480,
    4224,
    4992,
    4736,
    7552,
    7296,
    8064,
    7808,
    6528,
    6272,
    7040,
    6784,
    2752,
    2624,
    3008,
    2880,
    2240,
    2112,
    2496,
    2368,
    3776,
    3648,
    4032,
    3904,
    3264,
    3136,
    3520,
    3392,
    22016,
    20992,
    24064,
    23040,
    17920,
    16896,
    19968,
    18944,
    30208,
    29184,
    32256,
    31232,
    26112,
    25088,
    28160,
    27136,
    11008,
    10496,
    12032,
    11520,
    8960,
    8448,
    9984,
    9472,
    15104,
    14592,
    16128,
    15616,
    13056,
    12544,
    14080,
    13568,
    344,
    328,
    376,
    360,
    280,
    264,
    312,
    296,
    472,
    456,
    504,
    488,
    408,
    392,
    440,
    424,
    88,
    72,
    120,
    104,
    24,
    8,
    56,
    40,
    216,
    200,
    248,
    232,
    152,
    136,
    184,
    168,
    1376,
    1312,
    1504,
    1440,
    1120,
    1056,
    1248,
    1184,
    1888,
    1824,
    2016,
    1952,
    1632,
    1568,
    1760,
    1696,
    688,
    656,
    752,
    720,
    560,
    528,
    624,
    592,
    944,
    912,
    1008,
    976,
    816,
    784,
    880,
    848,
]


def ulaw2lin_py(fragment: bytes, width: int) -> bytes:
    check_width(width)
    out = bytearray()
    for code in fragment:
        out += set32(width, ULAW2LINEAR16[code] << 16)
    return bytes(out)


def alaw2lin_py(fragment: bytes, width: int) -> bytes:
    check_width(width)
    out = bytearray()
    for code in fragment:
        out += set32(width, ALAW2LINEAR16[code] << 16)
    return bytes(out)


INDEX_TABLE = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8]
STEPSIZE_TABLE = [
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    16,
    17,
    19,
    21,
    23,
    25,
    28,
    31,
    34,
    37,
    41,
    45,
    50,
    55,
    60,
    66,
    73,
    80,
    88,
    97,
    107,
    118,
    130,
    143,
    157,
    173,
    190,
    209,
    230,
    253,
    279,
    307,
    337,
    371,
    408,
    449,
    494,
    544,
    598,
    658,
    724,
    796,
    876,
    963,
    1060,
    1166,
    1282,
    1411,
    1552,
    1707,
    1878,
    2066,
    2272,
    2499,
    2749,
    3024,
    3327,
    3660,
    4026,
    4428,
    4871,
    5358,
    5894,
    6484,
    7132,
    7845,
    8630,
    9493,
    10442,
    11487,
    12635,
    13899,
    15289,
    16818,
    18500,
    20350,
    22385,
    24623,
    27086,
    29794,
    32767,
]


def lin2adpcm_py(fragment: bytes, width: int, state) -> tuple[bytes, tuple]:
    check_fragment(fragment, width)
    if state is None:
        valpred, index = 0, 0
    else:
        valpred, index = state
        if valpred >= 0x8000 or valpred < -0x8000 or not 0 <= index < 89:
            raise ValueError("bad state")
    step = STEPSIZE_TABLE[index]
    out = bytearray()
    outputbuffer = 0
    bufferstep = True
    for i in range(0, len(fragment), width):
        val = get32(fragment, width, i) >> 16
        if val < valpred:
            diff = valpred - val
            sign = 8
        else:
            diff = val - valpred
            sign = 0
        delta = 0
        vpdiff = step >> 3
        if diff >= step:
            delta = 4
            diff -= step
            vpdiff += step
        step >>= 1
        if diff >= step:
            delta |= 2
            diff -= step
            vpdiff += step
        step >>= 1
        if diff >= step:
            delta |= 1
            vpdiff += step
        if sign:
            valpred -= vpdiff
        else:
            valpred += vpdiff
        if valpred > 32767:
            valpred = 32767
        elif valpred < -32768:
            valpred = -32768
        delta |= sign
        index += INDEX_TABLE[delta]
        if index < 0:
            index = 0
        if index > 88:
            index = 88
        step = STEPSIZE_TABLE[index]
        if bufferstep:
            outputbuffer = (delta << 4) & 0xF0
        else:
            out.append((delta & 0x0F) | outputbuffer)
        bufferstep = not bufferstep
    return bytes(out), (valpred, index)


def adpcm2lin_py(fragment: bytes, width: int, state) -> tuple[bytes, tuple]:
    check_width(width)
    if state is None:
        valpred, index = 0, 0
    else:
        valpred, index = state
        if valpred >= 0x8000 or valpred < -0x8000 or not 0 <= index < 89:
            raise ValueError("bad state")
    step = STEPSIZE_TABLE[index]
    out = bytearray()
    bufferstep = False
    inputbuffer = 0
    for _ in range(len(fragment) * 2):
        if bufferstep:
            delta = inputbuffer & 0xF
        else:
            inputbuffer = fragment[len(out) // (2 * width)]
            delta = (inputbuffer >> 4) & 0xF
        bufferstep = not bufferstep
        index += INDEX_TABLE[delta]
        if index < 0:
            index = 0
        if index > 88:
            index = 88
        sign = delta & 8
        delta &= 7
        vpdiff = step >> 3
        if delta & 4:
            vpdiff += step
        if delta & 2:
            vpdiff += step >> 1
        if delta & 1:
            vpdiff += step >> 2
        if sign:
            valpred -= vpdiff
        else:
            valpred += vpdiff
        if valpred > 32767:
            valpred = 32767
        elif valpred < -32768:
            valpred = -32768
        step = STEPSIZE_TABLE[index]
        out += set32(width, valpred << 16)
    return bytes(out), (valpred, index)


def gcd(a: int, b: int) -> int:
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def ratecv_py(
    fragment: bytes,
    width: int,
    nchannels: int,
    inrate: int,
    outrate: int,
    state,
    weight_a: int = 1,
    weight_b: int = 0,
) -> tuple[bytes, tuple]:
    check_width(width)
    if nchannels < 1:
        raise ValueError("# of channels should be >= 1")
    if weight_a < 1 or weight_b < 0:
        raise ValueError("weightA should be >= 1, weightB should be >= 0")
    if len(fragment) % (width * nchannels) != 0:
        raise ValueError("not a whole number of frames")
    if inrate <= 0 or outrate <= 0:
        raise ValueError("sampling rate not > 0")
    d = gcd(inrate, outrate)
    inrate //= d
    outrate //= d
    d = gcd(weight_a, weight_b)
    weight_a //= d
    weight_b //= d
    if state is None:
        d = -outrate
        prev_i = [0] * nchannels
        cur_i = [0] * nchannels
    else:
        d = state[0]
        if len(state[1]) != nchannels:
            raise ValueError("illegal state argument")
        prev_i = [int(pair[0]) for pair in state[1]]
        cur_i = [int(pair[1]) for pair in state[1]]
    frames = len(fragment) // (width * nchannels)
    out = bytearray()
    fi = 0
    while True:
        while d < 0:
            if fi == frames:
                samps = tuple((prev_i[c], cur_i[c]) for c in range(nchannels))
                return bytes(out), (d, samps)
            for c in range(nchannels):
                prev_i[c] = cur_i[c]
                raw = get32(fragment, width, fi * nchannels * width + c * width)
                cur_i[c] = int(
                    (float(weight_a) * float(raw) + float(weight_b) * float(prev_i[c]))
                    / (float(weight_a) + float(weight_b))
                )
            fi += 1
            d += outrate
        while d >= 0:
            for c in range(nchannels):
                cur_o = int(
                    (float(prev_i[c]) * float(d) + float(cur_i[c]) * float(outrate - d))
                    / float(outrate)
                )
                out += set32(width, cur_o)
            d -= inrate


def tomono_py(fragment: bytes, width: int, lfactor: float, rfactor: float) -> bytes:
    check_fragment(fragment, width)
    if (len(fragment) // width) % 2 != 0:
        raise ValueError("not a whole number of frames")
    lo, hi = MINVALS[width], MAXVALS[width]
    out = bytearray()
    for i in range(0, len(fragment), width * 2):
        left = float(int.from_bytes(fragment[i : i + width], "little", signed=True))
        right = float(int.from_bytes(fragment[i + width : i + width * 2], "little", signed=True))
        out += fbound(left * lfactor + right * rfactor, lo, hi).to_bytes(
            width, "little", signed=True
        )
    return bytes(out)


def tostereo_py(fragment: bytes, width: int, lfactor: float, rfactor: float) -> bytes:
    check_fragment(fragment, width)
    lo, hi = MINVALS[width], MAXVALS[width]
    out = bytearray()
    for i in range(0, len(fragment), width):
        v = float(int.from_bytes(fragment[i : i + width], "little", signed=True))
        out += fbound(v * lfactor, lo, hi).to_bytes(width, "little", signed=True)
        out += fbound(v * rfactor, lo, hi).to_bytes(width, "little", signed=True)
    return bytes(out)


PY_OPS = {
    "add": add_py,
    "bias": lambda f, w: bias_py(f, w, 37),
    "mul": lambda f, w: mul_py(f, w, 0.5),
    "reverse": reverse_py,
    "byteswap": byteswap_py,
    "lin2lin": None,  # dispatched specially
    "getsample": None,
    "max": max_py,
    "minmax": minmax_py,
    "avg": avg_py,
    "rms": rms_py,
    "cross": cross_py,
    "avgpp": avgpp_py,
    "maxpp": maxpp_py,
    "lin2alaw": lin2alaw_py,
    "alaw2lin": alaw2lin_py,
    "lin2ulaw": lin2ulaw_py,
    "ulaw2lin": ulaw2lin_py,
    "tomono": None,
    "tostereo": None,
    "findfactor": findfactor_py,
    "findfit": findfit_py,
    "findmax": findmax_py,
    "lin2adpcm": lin2adpcm_py,
    "adpcm2lin": adpcm2lin_py,
    "ratecv": ratecv_py,
}
