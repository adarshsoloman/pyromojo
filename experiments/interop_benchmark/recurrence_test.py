import time
import mojo.importer
import interop


def python_checksum(seed, iterations):
    state = seed

    for _ in range(iterations):
        state = (state * 48271) % 2147483647

    return state


seed = 12345
sizes = [1_000, 10_000, 100_000, 1_000_000, 2_000_000]

print("\nMOJO RECURRENCE TEST")
print("=" * 55)

for n in sizes:
    expected = python_checksum(seed, n)

    start = time.perf_counter_ns()
    actual = interop.prng_checksum(seed, n)
    mojo_time = time.perf_counter_ns() - start

    assert actual == expected, f"Mismatch at {n:,} iterations"

    print(
        f"N={n:>10,} | "
        f"Mojo={mojo_time / 1e6:>10.4f} ms | "
        f"Result={actual}"
    )

print("\nOutput verification: PASSED")
