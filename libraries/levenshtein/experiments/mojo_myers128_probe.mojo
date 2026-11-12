"""Phase 0 probe: 128-bit Myers distance in Mojo, n <= 128."""

from std.collections import List
from std.testing import assert_equal
from std.time import perf_counter_ns


def myers_distance_128(left: String, right: String) raises -> Int:
    var n = len(left.codepoints())
    var m = len(right.codepoints())
    if n > 128 or m > 128:
        raise Error("probe supports at most 128 code points")
    if n == 0:
        return m
    if m == 0:
        return n

    var peq = List[UInt128](capacity=128)
    for _ in range(128):
        peq.append(0)
    var bit = UInt128(1)
    for cp in left.codepoints():
        var code = Int(cp)
        if code < 0 or code > 127:
            raise Error("probe supports ASCII only")
        peq[code] = peq[code] | bit
        bit = bit << UInt128(1)

    # Shifts by the full bit width are target-dependent, so guard n == 128.
    var vp = UInt128.MAX
    if n < 128:
        vp = (UInt128(1) << UInt128(n)) - 1
    var vn = UInt128(0)
    var distance = n
    var mask = UInt128(1) << UInt128(n - 1)

    for cp in right.codepoints():
        var code = Int(cp)
        if code < 0 or code > 127:
            raise Error("probe supports ASCII only")
        var pm = peq[code]
        var x = pm
        var d0 = (((x & vp) + vp) ^ vp) | x | vn
        var hp = vn | ~(d0 | vp)
        var hn = d0 & vp
        if hp & mask != 0:
            distance += 1
        if hn & mask != 0:
            distance -= 1
        hp = (hp << UInt128(1)) | 1
        hn = hn << UInt128(1)
        vp = hn | ~(d0 | hp)
        vn = hp & d0

    return distance


def dp_distance(left: String, right: String) raises -> Int:
    var a = List[Int](capacity=left.byte_length())
    var b = List[Int](capacity=right.byte_length())
    for cp in left.codepoints():
        a.append(Int(cp))
    for cp in right.codepoints():
        b.append(Int(cp))
    var prev = List[Int](capacity=len(b) + 1)
    var curr = List[Int](capacity=len(b) + 1)
    for j in range(len(b) + 1):
        prev.append(j)
        curr.append(0)
    for i in range(1, len(a) + 1):
        curr[0] = i
        for j in range(1, len(b) + 1):
            var sub = 1
            if a[i - 1] == b[j - 1]:
                sub = 0
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + sub)
        var swap = prev^
        prev = curr^
        curr = swap^
    return prev[len(b)]


def make_ascii(rng_state: UInt64, length: Int) raises -> Tuple[String, UInt64]:
    var raw = List[UInt8](capacity=length)
    var state = rng_state
    for _ in range(length):
        state = state * UInt64(6364136223846793005) + UInt64(1442695040888963407)
        raw.append(UInt8(Int(state % UInt64(26)) + 97))
    return (String(from_utf8=Span(raw)), state)


def main() raises:
    var seed = UInt64(20260101)
    for size in range(0, 129):
        var pair = make_ascii(seed, size)
        seed = pair[1]
        var pair2 = make_ascii(seed, size)
        seed = pair2[1]
        assert_equal(myers_distance_128(pair[0], pair2[0]), dp_distance(pair[0], pair2[0]))
    print("myers128 checks (n=0..128): ok")

    print("== Myers128 vs DP timings (min of 5, ns) ==")
    var timing_sizes = List[Int](capacity=3)
    timing_sizes.append(64)
    timing_sizes.append(96)
    timing_sizes.append(128)
    for size in timing_sizes:
        var pair = make_ascii(seed, size)
        seed = pair[1]
        var pair2 = make_ascii(seed, size)
        seed = pair2[1]
        var best_myers = -1
        var best_dp = -1
        for _ in range(5):
            var start = perf_counter_ns()
            var value = myers_distance_128(pair[0], pair2[0])
            var elapsed = perf_counter_ns() - start
            if best_myers < 0 or elapsed < best_myers:
                best_myers = elapsed
            start = perf_counter_ns()
            var dp_value = dp_distance(pair[0], pair2[0])
            elapsed = perf_counter_ns() - start
            if best_dp < 0 or elapsed < best_dp:
                best_dp = elapsed
            if value != dp_value:
                raise Error("timing mismatch")
        print("n", size, "myers128_ns", best_myers, "dp_ns", best_dp)
    print("probe: ok")
