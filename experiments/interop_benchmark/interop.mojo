from std.python import PythonObject
from std.python.bindings import PythonModuleBuilder
from std.os import abort


@export
def PyInit_interop() abi("C") -> PythonObject:
    try:
        var module = PythonModuleBuilder("interop")

        module.def_function[prng_checksum](
            "prng_checksum",
            docstring="Compute an iterative modular recurrence using Mojo",
        )

        return module.finalize()

    except e:
        abort(String("Failed to initialize Mojo module: ", e))


def prng_checksum(
    seed_obj: PythonObject,
    iterations_obj: PythonObject
) raises -> PythonObject:
    var state = Int(py=seed_obj)
    var iterations = Int(py=iterations_obj)

    for i in range(iterations):
        state = (state * 48271) % 2147483647

    return state