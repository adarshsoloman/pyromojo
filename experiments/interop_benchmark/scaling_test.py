import mojo.importer
import interop
import time

sizes = [
    1_000,
    10_000,
    100_000,
    1_000_000,
    10_000_000,
]

repeats = 10

for n in sizes:
    start = time.perf_counter()

    result = interop.sum_squares_batch(n, repeats)

    elapsed = time.perf_counter() - start

    print(
        f"N={n:>10,} | "
        f"Time={elapsed * 1000:>12.6f} ms | "
        f"Result={result}"
    )
