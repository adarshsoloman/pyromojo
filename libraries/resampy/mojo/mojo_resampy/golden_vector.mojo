"""Phase 3 / Component E: versioned golden-vector protocol.

Format: JSON metadata + Base64-encoded LITTLE-ENDIAN Float64 payloads.

Schema v1 is a FLAT JSON object (no nested objects) so the strict
``json_codec`` reader is sufficient. Exact key set and types are enforced;
every payload is validated for encoding, element count and SHA-256 integrity.

The integrity hash covers the concatenation of the raw little-endian input
bytes followed by the raw little-endian expected bytes (i.e. the exact bits
that must round-trip), not the Base64 text and not the JSON document.

All data in Phase 3 is SYNTHETIC. Synthetic vectors carry
``reference.library == "synthetic"`` and must never be described as Resampy
compatibility vectors. The Phase 2 upstream calibration corpus is deliberately
not integrated here (see ``licensing-audit.md`` §6 and Phase 2 §14).
"""

from std.collections import List

from mojo_resampy.float_codec import (
    base64_decode_bytes,
    base64_encode_bytes,
    decode_f64le,
    encode_f64le,
)
from mojo_resampy.json_codec import JsonObject, parse_json_object
from mojo_resampy.sha256 import sha256_hex


comptime GOLDEN_SCHEMA_VERSION: Int = 1
# Bounds on decoded payload elements. Guards the element-count * 8 byte
# calculation against overflow and caps in-memory vector sizes.
comptime MAX_VECTOR_ELEMENTS: Int = 1_000_000


struct GoldenVector(Copyable, Movable):
    """A parsed, validated golden-vector case."""

    var schema_version: Int
    var case_id: String
    var description: String
    var reference_library: String
    var reference_version: String
    var reference_commit: String
    var python_version: String
    var numpy_version: String
    var numba_version: String
    var input_dtype: String
    var output_dtype: String
    var byte_order: String
    var sr_orig: Int
    var sr_new: Int
    var filter_id: String
    var input_count: Int
    var expected_count: Int
    var payload_element_count: Int
    var payload_sha256: String
    var atol: Float64
    var rtol: Float64
    var input_values: List[Float64]
    var expected_values: List[Float64]

    def __init__(
        out self,
        schema_version: Int,
        case_id: String,
        description: String,
        reference_library: String,
        reference_version: String,
        reference_commit: String,
        python_version: String,
        numpy_version: String,
        numba_version: String,
        input_dtype: String,
        output_dtype: String,
        byte_order: String,
        sr_orig: Int,
        sr_new: Int,
        filter_id: String,
        input_count: Int,
        expected_count: Int,
        payload_element_count: Int,
        payload_sha256: String,
        atol: Float64,
        rtol: Float64,
        var input_values: List[Float64],
        var expected_values: List[Float64],
    ):
        self.schema_version = schema_version
        self.case_id = case_id
        self.description = description
        self.reference_library = reference_library
        self.reference_version = reference_version
        self.reference_commit = reference_commit
        self.python_version = python_version
        self.numpy_version = numpy_version
        self.numba_version = numba_version
        self.input_dtype = input_dtype
        self.output_dtype = output_dtype
        self.byte_order = byte_order
        self.sr_orig = sr_orig
        self.sr_new = sr_new
        self.filter_id = filter_id
        self.input_count = input_count
        self.expected_count = expected_count
        self.payload_element_count = payload_element_count
        self.payload_sha256 = payload_sha256
        self.atol = atol
        self.rtol = rtol
        self.input_values = input_values^
        self.expected_values = expected_values^


def _required_keys() -> List[String]:
    var keys = List[String]()
    keys.append("schema_version")
    keys.append("case_id")
    keys.append("description")
    keys.append("reference_library")
    keys.append("reference_version")
    keys.append("reference_commit")
    keys.append("python_version")
    keys.append("numpy_version")
    keys.append("numba_version")
    keys.append("input_dtype")
    keys.append("output_dtype")
    keys.append("byte_order")
    keys.append("sr_orig")
    keys.append("sr_new")
    keys.append("filter_id")
    keys.append("input_count")
    keys.append("expected_count")
    keys.append("input_encoding")
    keys.append("expected_encoding")
    keys.append("input_data")
    keys.append("expected_data")
    keys.append("payload_element_count")
    keys.append("payload_sha256")
    keys.append("atol")
    keys.append("rtol")
    return keys^


def _provenance_keys() -> List[String]:
    var keys = List[String]()
    keys.append("case_id")
    keys.append("description")
    keys.append("reference_library")
    keys.append("reference_version")
    keys.append("reference_commit")
    keys.append("python_version")
    keys.append("numpy_version")
    keys.append("numba_version")
    keys.append("filter_id")
    return keys^


def _check_keys(obj: JsonObject) raises:
    var required = _required_keys()
    for key in required:
        if not obj.has(key):
            raise Error("golden vector missing required key '" + key + "'")
    for key in obj.keys():
        var known = False
        for r in required:
            if key == r:
                known = True
        if not known:
            raise Error("golden vector has unknown key '" + key + "'")


def _decode_payload(b64: String, expected_count: Int, label: String) raises -> List[Float64]:
    if expected_count < 0 or expected_count > MAX_VECTOR_ELEMENTS:
        raise Error(
            label + "_count " + String(expected_count)
            + " is outside [0, " + String(MAX_VECTOR_ELEMENTS) + "]"
        )
    var raw = base64_decode_bytes(b64)
    if len(raw) != expected_count * 8:
        raise Error(
            label + " payload byte length " + String(len(raw))
            + " does not match " + label + "_count " + String(expected_count)
            + " x 8 bytes"
        )
    var values = decode_f64le(Span(raw))
    if len(values) != expected_count:
        raise Error(label + " decoded element count mismatch")
    return values^


def _require_nonempty(obj: JsonObject, key: String) raises -> String:
    var value = obj.get_string(key)
    if value.byte_length() == 0:
        raise Error("golden vector field '" + key + "' must not be empty")
    return value


def parse_golden_vector(text: String) raises -> GoldenVector:
    """Parse + fully validate one golden-vector JSON document."""
    var obj = parse_json_object(text)
    _check_keys(obj)

    var schema_version = obj.get_int("schema_version")
    if schema_version != GOLDEN_SCHEMA_VERSION:
        raise Error(
            "unsupported golden vector schema_version " + String(schema_version)
            + ", expected " + String(GOLDEN_SCHEMA_VERSION)
        )
    if obj.get_string("input_encoding") != "base64":
        raise Error("input_encoding must be 'base64'")
    if obj.get_string("expected_encoding") != "base64":
        raise Error("expected_encoding must be 'base64'")
    if obj.get_string("byte_order") != "little":
        raise Error("byte_order must be 'little' (explicit LE interpretation)")
    if obj.get_string("input_dtype") != "float64":
        raise Error("input_dtype must be 'float64'")
    if obj.get_string("output_dtype") != "float64":
        raise Error("output_dtype must be 'float64'")

    # Metadata validity is checked independently of payload integrity: a
    # matching hash must never make inconsistent metadata acceptable.
    var sr_orig = obj.get_int("sr_orig")
    var sr_new = obj.get_int("sr_new")
    if sr_orig <= 0:
        raise Error("sr_orig must be positive, got " + String(sr_orig))
    if sr_new <= 0:
        raise Error("sr_new must be positive, got " + String(sr_new))
    for key in _provenance_keys():
        _ = _require_nonempty(obj, key)

    var input_count = obj.get_int("input_count")
    var expected_count = obj.get_int("expected_count")
    if input_count < 0 or expected_count < 0:
        raise Error("element counts must be non-negative")
    var payload_element_count = obj.get_int("payload_element_count")
    if payload_element_count != input_count + expected_count:
        raise Error(
            "payload_element_count " + String(payload_element_count)
            + " does not equal input_count + expected_count ("
            + String(input_count + expected_count) + ")"
        )
    if payload_element_count > MAX_VECTOR_ELEMENTS:
        raise Error(
            "payload_element_count " + String(payload_element_count)
            + " exceeds limit " + String(MAX_VECTOR_ELEMENTS)
        )

    var input_values = _decode_payload(obj.get_string("input_data"), input_count, "input")
    var expected_values = _decode_payload(obj.get_string("expected_data"), expected_count, "expected")

    var combined = List[UInt8](capacity=(input_count + expected_count) * 8)
    for byte in encode_f64le(Span(input_values)):
        combined.append(byte)
    for byte in encode_f64le(Span(expected_values)):
        combined.append(byte)
    var actual_digest = sha256_hex(Span(combined))
    var declared = obj.get_string("payload_sha256")
    if actual_digest != declared:
        raise Error(
            "golden vector integrity failure: sha256 " + actual_digest
            + " does not match declared " + declared
        )

    var atol = obj.get_float("atol")
    var rtol = obj.get_float("rtol")
    if atol < 0.0 or rtol < 0.0:
        raise Error("golden vector tolerances must be non-negative")

    return GoldenVector(
        schema_version,
        obj.get_string("case_id"),
        obj.get_string("description"),
        obj.get_string("reference_library"),
        obj.get_string("reference_version"),
        obj.get_string("reference_commit"),
        obj.get_string("python_version"),
        obj.get_string("numpy_version"),
        obj.get_string("numba_version"),
        obj.get_string("input_dtype"),
        obj.get_string("output_dtype"),
        obj.get_string("byte_order"),
        sr_orig,
        sr_new,
        obj.get_string("filter_id"),
        input_count,
        expected_count,
        payload_element_count,
        declared,
        atol,
        rtol,
        input_values^,
        expected_values^,
    )


def serialize_golden_vector(gv: GoldenVector) raises -> String:
    """Serialize a case to canonical schema-v1 JSON (recomputes the hash)."""
    var input_bytes = encode_f64le(Span(gv.input_values))
    var expected_bytes = encode_f64le(Span(gv.expected_values))
    var combined = List[UInt8](capacity=len(input_bytes) + len(expected_bytes))
    for byte in input_bytes:
        combined.append(byte)
    for byte in expected_bytes:
        combined.append(byte)
    var digest = sha256_hex(Span(combined))

    var obj = JsonObject()
    obj.set_int("schema_version", gv.schema_version)
    obj.set_string("case_id", gv.case_id)
    obj.set_string("description", gv.description)
    obj.set_string("reference_library", gv.reference_library)
    obj.set_string("reference_version", gv.reference_version)
    obj.set_string("reference_commit", gv.reference_commit)
    obj.set_string("python_version", gv.python_version)
    obj.set_string("numpy_version", gv.numpy_version)
    obj.set_string("numba_version", gv.numba_version)
    obj.set_string("input_dtype", gv.input_dtype)
    obj.set_string("output_dtype", gv.output_dtype)
    obj.set_string("byte_order", gv.byte_order)
    obj.set_int("sr_orig", gv.sr_orig)
    obj.set_int("sr_new", gv.sr_new)
    obj.set_string("filter_id", gv.filter_id)
    obj.set_int("input_count", len(gv.input_values))
    obj.set_int("expected_count", len(gv.expected_values))
    obj.set_string("input_encoding", "base64")
    obj.set_string("expected_encoding", "base64")
    obj.set_string("input_data", base64_encode_bytes(Span(input_bytes)))
    obj.set_string("expected_data", base64_encode_bytes(Span(expected_bytes)))
    obj.set_int("payload_element_count", len(gv.input_values) + len(gv.expected_values))
    obj.set_string("payload_sha256", digest)
    obj.set_float("atol", gv.atol)
    obj.set_float("rtol", gv.rtol)
    return obj.serialize()
