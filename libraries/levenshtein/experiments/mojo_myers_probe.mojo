"""Phase 0 probe: is 64-bit Myers bit-parallel distance feasible in Mojo?

Only strings up to 64 ASCII code points are exercised here. The purpose is to
prove the algorithm and bit operations work in Mojo 1.2.0, not to ship it.

Run with::

    .venv/bin/mojo run libraries/levenshtein/experiments/mojo_myers_probe.mojo
"""

from std.collections import List
from std.testing import assert_equal
from std.time import perf_counter_ns


def myers_distance_64(left: String, right: String) raises -> Int:
    var n = len(left.codepoints())
    var m = len(right.codepoints())
    if n > 64 or m > 64:
        raise Error("probe supports at most 64 code points")
    if n == 0:
        return m
    if m == 0:
        return n

    var peq = List[UInt64](capacity=128)
    for _ in range(128):
        peq.append(0)
    var bit = UInt64(1)
    for cp in left.codepoints():
        var code = Int(cp)
        if code < 0 or code > 127:
            raise Error("probe supports ASCII only")
        peq[code] = peq[code] | bit
        bit = bit << 1

    # Shifts by the full bit width are target-dependent, so guard n == 64.
    var vp = UInt64.MAX
    if n < 64:
        vp = (UInt64(1) << UInt64(n)) - 1
    var vn = UInt64(0)
    var distance = n
    var mask = UInt64(1) << UInt64(n - 1)

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
        hp = (hp << 1) | 1
        hn = hn << 1
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


def repeat_text(text: String, count: Int) raises -> String:
    var out = String()
    for _ in range(count):
        out += text
    return out^


def main() raises:
    var cases = List[Tuple[String, String, Int]]()
    cases.append(("", "", 0))
    cases.append(("", "abc", 3))
    cases.append(("abc", "", 3))
    cases.append(("kitten", "sitting", 3))
    cases.append(("abc", "adc", 1))
    cases.append(("lewenstein", "levenshtein", 2))
    cases.append(("spam", "park", 3))
    cases.append(("aaaaaaaa", "aaa", 5))
    cases.append(("the quick brown fox", "the quick brown cat", 3))

    for item in cases:
        var expected = item[2]
        var actual = myers_distance_64(item[0], item[1])
        assert_equal(actual, expected)
        assert_equal(actual, dp_distance(item[0], item[1]))

    var rng_state = UInt64(20260101)
    var mismatches = 0
    for _ in range(200):
        rng_state = rng_state * UInt64(6364136223846793005) + UInt64(1442695040888963407)
        var len_left = Int(rng_state % UInt64(65))
        rng_state = rng_state * UInt64(6364136223846793005) + UInt64(1442695040888963407)
        var len_right = Int(rng_state % UInt64(65))
        var left_bytes = List[UInt8](capacity=len_left)
        var right_bytes = List[UInt8](capacity=len_right)
        for _ in range(len_left):
            rng_state = rng_state * UInt64(6364136223846793005) + UInt64(1442695040888963407)
            left_bytes.append(UInt8(Int(rng_state % UInt64(26)) + 97))
        for _ in range(len_right):
            rng_state = rng_state * UInt64(6364136223846793005) + UInt64(1442695040888963407)
            right_bytes.append(UInt8(Int(rng_state % UInt64(26)) + 97))
        var left = String(from_utf8=Span(left_bytes))
        var right = String(from_utf8=Span(right_bytes))
        if myers_distance_64(left, right) != dp_distance(left, right):
            mismatches += 1
    assert_equal(mismatches, 0)
    print("myers checks: ok")

    print("== Myers 64 vs DP timings (min of 5, ns) ==")
    var timing_sizes = List[Int](capacity=3)
    timing_sizes.append(16)
    timing_sizes.append(32)
    timing_sizes.append(64)
    for size in timing_sizes:
        var left = repeat_text("a", size)
        var right = repeat_text("b", size)
        var best_myers = -1
        var best_dp = -1
        for _ in range(5):
            var start = perf_counter_ns()
            var value = myers_distance_64(left, right)
            var elapsed = perf_counter_ns() - start
            if best_myers < 0 or elapsed < best_myers:
                best_myers = elapsed
            start = perf_counter_ns()
            var dp_value = dp_distance(left, right)
            elapsed = perf_counter_ns() - start
            if best_dp < 0 or elapsed < best_dp:
                best_dp = elapsed
            if value != dp_value:
                raise Error("timing value mismatch")
        print("n", size, "myers_ns", best_myers, "dp_ns", best_dp)
    print("probe: ok")
