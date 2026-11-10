import mojo.importer
import interop

result = interop.factorial(5)

print("Python calling native Mojo")
print("Factorial of 5:", result)
