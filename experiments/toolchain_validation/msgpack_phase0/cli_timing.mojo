"""Phase 0 probe: CLI argv and monotonic timing for the CLI benchmark harness."""

from std.sys import argv
from std.time import perf_counter_ns


def checksum(rounds: Int) -> UInt64:
    var acc: UInt64 = 0
    for i in range(rounds):
        acc = acc + UInt64(i) * 3
    return acc


def main() raises:
    var args = argv()
    print("argc:", len(args))
    for i in range(len(args)):
        print("argv[" + String(i) + "]:", String(args[i]))

    var rounds: Int = 1_000_000
    var start = perf_counter_ns()
    var result = checksum(rounds)
    var elapsed = perf_counter_ns() - start

    assert result > 0
    assert elapsed > 0
    print("checksum:", result)
    print("elapsed_ns:", elapsed)
    print("ns_per_round:", elapsed // rounds)
    print("cli_timing: PASS")
