
import time
import statistics
import mojo.importer
import interop


def python_checksum(seed, iterations):
    state = seed

    for _ in range(iterations):
        state = (state * 48271) % 2147483647

    return state


def measure(fn, *args, warmups=3, samples=15):
    for _ in range(warmups):
        fn(*args)

    timings = []

    for _ in range(samples):
        start = time.perf_counter_ns()
        result = fn(*args)
        elapsed = time.perf_counter_ns() - start
        timings.append(elapsed / 1_000_000)

    return result, statistics.median(timings)


seed = 12345
workloads = [100_000, 500_000, 1_000_000, 2_000_000]

print("\nPYROMOJO RECURRENCE BENCHMARK")
print("=" * 65)

for iterations in workloads:
    python_result, python_ms = measure(
        python_checksum, seed, iterations
    )

    mojo_result, mojo_ms = measure(
        interop.prng_checksum, seed, iterations
    )

    assert python_result == mojo_result

    print(f"\nIterations:      {iterations:,}")
    print(f"Python median:   {python_ms:.4f} ms")
    print(f"Mojo median:     {mojo_ms:.4f} ms")
    print(f"Speedup:         {python_ms / mojo_ms:.2f}x")
    print("Correctness:     PASSED")

print("\nAll workload checks passed.")
