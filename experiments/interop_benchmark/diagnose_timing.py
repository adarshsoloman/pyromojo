import mojo.importer
import interop
import time


def python_reference(n, repeats):
    total = 0
    for r in range(repeats):
        for i in range(n):
            value = i + r
            total += value * value
    return total


def main():
    n = 100_000
    repeats = 20
    calls = 10

    expected = [
        python_reference(n + j, repeats)
        for j in range(calls)
    ]

    start = time.perf_counter_ns()

    results = [
        interop.sum_squares_batch(n + j, repeats)
        for j in range(calls)
    ]

    elapsed = time.perf_counter_ns() - start

    assert results == expected, "Output mismatch!"

    print("\nMOJO TIMING DIAGNOSTIC")
    print("=" * 45)
    print(f"Calls:              {calls}")
    print(f"Iterations/call:    {n * repeats:,}")
    print(f"Total iterations:   {n * repeats * calls:,}")
    print(f"Total elapsed:      {elapsed:,} ns")
    print(f"Total elapsed:      {elapsed / 1e6:.4f} ms")
    print(f"Average per call:   {elapsed / calls / 1e6:.4f} ms")
    print("Output verification: PASSED")


if __name__ == "__main__":
    main()
