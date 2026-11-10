import mojo.importer
import interop

import statistics
import time


def python_sum_squares_batch(n: int, repeats: int) -> int:
    total = 0

    for r in range(repeats):
        for i in range(n):
            value = i + r
            total += value * value

    return total


def measure(function, args, warmups=2, repeats=9):
    for _ in range(warmups):
        function(*args)

    timings = []

    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = function(*args)
        elapsed = time.perf_counter_ns() - start

        timings.append(elapsed)

    return statistics.median(timings), result


def main():
    n = 100_000
    repeats = 20

    args = (n, repeats)

    expected = python_sum_squares_batch(*args)

    mojo_result = interop.sum_squares_batch(*args)

    assert expected == mojo_result, "Output mismatch!"

    python_time, _ = measure(
        python_sum_squares_batch, args
    )

    mojo_time, _ = measure(
        interop.sum_squares_batch, args
    )

    speedup = python_time / mojo_time

    print("\nPyroMojo - Batched Benchmark")
    print("=" * 55)
    print(f"Input size:       {n:,}")
    print(f"Repetitions:      {repeats}")
    print(f"Total iterations: {n * repeats:,}")
    print(f"Verified result:  {mojo_result:,}")
    print("-" * 55)
    print(f"Python median:    {python_time / 1e6:.4f} ms")
    print(f"Mojo median:      {mojo_time / 1e6:.4f} ms")
    print(f"Speedup:          {speedup:.2f}x")
    print("=" * 55)
    print("Output verification: PASSED")
    print("Compilation time: excluded")


if __name__ == "__main__":
    main()
