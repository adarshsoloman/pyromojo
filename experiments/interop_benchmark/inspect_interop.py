import mojo.importer
import interop

print("MODULE:", interop)
print("MODULE FILE:", getattr(interop, "__file__", None))
print("MODULE SPEC:", interop.__spec__)

print("\nFUNCTION:", interop.sum_squares_batch)

for n, repeats in [
    (10, 1),
    (100_000, 20),
    (1_000_000, 20),
]:
    result = interop.sum_squares_batch(n, repeats)
    print(f"n={n:,}, repeats={repeats}, result={result}")
