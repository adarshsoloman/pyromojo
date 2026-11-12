"""Phase 0 Mojo 1.2.0 probe: code points, two-row DP, LCS ratio, timing.

Run with::

    .venv/bin/mojo run libraries/levenshtein/experiments/mojo_dp_probe.mojo
"""

from std.collections import List
from std.testing import assert_equal
from std.time import perf_counter_ns


def codepoints(text: String) -> List[Int]:
    """Materialize the reference unit: one Int per Unicode code point."""
    var out = List[Int](capacity=text.byte_length())
    for cp in text.codepoints():
        out.append(Int(cp))
    return out^


def levenshtein_distance(a: List[Int], b: List[Int]) raises -> Int:
    """Unit-cost Levenshtein with two rolling rows, O(len(a)*len(b))."""
    var n = len(a)
    var m = len(b)
    if n == 0:
        return m
    if m == 0:
        return n

    var prev = List[Int](capacity=m + 1)
    var curr = List[Int](capacity=m + 1)
    for j in range(m + 1):
        prev.append(j)
        curr.append(0)

    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            var substitution = 1
            if a[i - 1] == b[j - 1]:
                substitution = 0
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + substitution)
        var swap = prev^
        prev = curr^
        curr = swap^

    return prev[m]


def lcs_length(a: List[Int], b: List[Int]) raises -> Int:
    """Longest common subsequence length, two rolling rows."""
    var n = len(a)
    var m = len(b)
    if n == 0 or m == 0:
        return 0

    var prev = List[Int](capacity=m + 1)
    var curr = List[Int](capacity=m + 1)
    for _ in range(m + 1):
        prev.append(0)
        curr.append(0)

    for i in range(1, n + 1):
        curr[0] = 0
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        var swap = prev^
        prev = curr^
        curr = swap^

    return prev[m]


def ratio_value(a: List[Int], b: List[Int]) raises -> Float64:
    """Levenshtein.ratio == rapidfuzz Indel normalized similarity."""
    var total = len(a) + len(b)
    if total == 0:
        return 1.0
    var lcs = lcs_length(a, b)
    var indel = total - 2 * lcs
    return 1.0 - Float64(indel) / Float64(total)


def assert_close(actual: Float64, expected: Float64, label: String) raises:
    var delta = actual - expected
    if delta < 0.0:
        delta = -delta
    assert_equal(delta < 1e-12, True, label)


def expected_once() -> List[Tuple[String, String, Int, Float64]]:
    """Reference values captured from Levenshtein 0.27.5."""
    var cases = List[Tuple[String, String, Int, Float64]]()
    cases.append(("", "", 0, 1.0))
    cases.append(("kitten", "sitting", 3, 0.6153846153846154))
    cases.append(("abc", "adc", 1, 0.6666666666666667))
    cases.append(("lewenstein", "levenshtein", 2, 0.8571428571428572))
    cases.append(("ab", "ba", 2, 0.5))
    cases.append(("é", "e", 1, 0.0))
    cases.append(("😀", "", 1, 0.0))
    cases.append(("a😀b", "ab", 1, 0.8))
    cases.append(("naïve", "naive", 1, 0.8))
    return cases^


def run_tests() raises:
    for item in expected_once():
        var left = item[0]
        var right = item[1]
        var expected_distance = item[2]
        var expected_ratio = item[3]
        var a = codepoints(left)
        var b = codepoints(right)
        assert_equal(levenshtein_distance(a, b), expected_distance)
        assert_close(ratio_value(a, b), expected_ratio, left + " / " + right)
    print("tests: ok")


def repeat_text(text: String, count: Int) raises -> String:
    var out = String()
    for _ in range(count):
        out += text
    return out^


def time_pair(left: String, right: String, rounds: Int) raises -> Tuple[Int, Int]:
    var a = codepoints(left)
    var b = codepoints(right)
    var best_distance = -1
    var best_ratio = -1
    for _ in range(rounds):
        var start = perf_counter_ns()
        var distance = levenshtein_distance(a, b)
        var elapsed = perf_counter_ns() - start
        if best_distance < 0 or elapsed < best_distance:
            best_distance = elapsed
        start = perf_counter_ns()
        var ratio = ratio_value(a, b)
        elapsed = perf_counter_ns() - start
        if best_ratio < 0 or elapsed < best_ratio:
            best_ratio = elapsed
        if distance < 0 or ratio < -1.0:
            print("unreachable")
    return (best_distance, best_ratio)


def main() raises:
    run_tests()

    print("== codepoint materialization ==")
    var sample = String("aé😀")
    var cps = codepoints(sample)
    print("byte_length", sample.byte_length())
    print("codepoints", len(cps), cps[0], cps[1], cps[2])
    print("graphemes", len(sample.graphemes()))
    print("slice", sample[codepoint=1:2] == String("é"))
    var nfd = String("e\u0301")
    var family = String("👩‍👩‍👧‍👦")
    print("nfd codepoints/graphemes", len(nfd.codepoints()), len(nfd.graphemes()))
    print("family codepoints/graphemes", len(family.codepoints()), len(family.graphemes()))

    print("== materialization timings (min of 3, ns) ==")
    for size in range(6, 12):
        var text = repeat_text("a", 1 << size)
        var best = -1
        for _ in range(3):
            var start = perf_counter_ns()
            var cps_again = codepoints(text)
            var elapsed = perf_counter_ns() - start
            if best < 0 or elapsed < best:
                best = elapsed
            if len(cps_again) < 0:
                print("unreachable")
        print("n", 1 << size, "codepoints_ns", best)

    print("== DP timings (min of 3, ns) ==")
    var sizes = List[Int](capacity=9)
    for size in range(3, 12):
        sizes.append(1 << size)
    for size in sizes:
        var left = repeat_text("a", size)
        var right = repeat_text("b", size)
        var timings = time_pair(left, right, 3)
        print(
            "n",
            size,
            "distance_ns",
            timings[0],
            "ratio_ns",
            timings[1],
        )

    print("== equal-input timings (min of 3, ns) ==")
    var equal_sizes = List[Int](capacity=4)
    equal_sizes.append(64)
    equal_sizes.append(256)
    equal_sizes.append(1024)
    equal_sizes.append(2048)
    for size in equal_sizes:
        var text = repeat_text("a", size)
        var timings = time_pair(text, text, 3)
        print("n", size, "distance_ns", timings[0], "ratio_ns", timings[1])

    print("probe: ok")
