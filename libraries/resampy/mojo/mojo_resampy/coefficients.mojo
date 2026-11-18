"""Phase 3 / Component C: generic filter-coefficient resource loader.

Resource format (two files, both synthetic in Phase 3):

* ``<name>.json`` — flat JSON metadata (see ``load_filter`` for the schema).
* ``<name>.bin``  — raw little-endian IEEE-754 Float64 coefficient bytes.

Validation is strict and ordered; every failure raises an actionable Error.
No upstream ``kaiser_fast`` / ``kaiser_best`` coefficients are copied here:
Phase 1 ``licensing-audit.md`` §6 left that legal question unresolved. The
loader is generic so a licensed resource can be dropped in later without
changing the numerical kernel.

Explicit little-endian interpretation is enforced by rejecting any metadata
whose ``byte_order`` is not ``"little"``; no host-endian inference is used.
"""

from std.collections import List
from std.io import FileHandle

from mojo_resampy.float_codec import decode_f64le, bytes_to_hex
from mojo_resampy.json_codec import parse_json_object
from mojo_resampy.sha256 import sha256_hex


comptime FILTER_SCHEMA_VERSION: Int = 1
comptime FLOAT64_BYTES: Int = 8
# Resource limits. Bounds are applied BEFORE count * FLOAT64_BYTES so the
# multiplication cannot overflow, and before any file or buffer allocation.
comptime MAX_COEFFICIENT_COUNT: Int = 1_000_000
comptime MAX_RESOURCE_BYTES: Int = MAX_COEFFICIENT_COUNT * FLOAT64_BYTES
comptime MAX_METADATA_BYTES: Int = 64 * 1024


struct FilterMetadata(Copyable, Movable, ImplicitlyCopyable):
    """Parsed and validated coefficient-resource metadata."""

    var schema_version: Int
    var filter_id: String
    var coefficient_count: Int
    var precision: Int
    var rolloff: Float64
    var dtype: String
    var byte_order: String
    var resource_bytes: Int
    var resource_sha256: String

    def __init__(
        out self,
        schema_version: Int,
        filter_id: String,
        coefficient_count: Int,
        precision: Int,
        rolloff: Float64,
        dtype: String,
        byte_order: String,
        resource_bytes: Int,
        resource_sha256: String,
    ):
        self.schema_version = schema_version
        self.filter_id = filter_id
        self.coefficient_count = coefficient_count
        self.precision = precision
        self.rolloff = rolloff
        self.dtype = dtype
        self.byte_order = byte_order
        self.resource_bytes = resource_bytes
        self.resource_sha256 = resource_sha256


struct FilterCoefficients(Copyable, Movable):
    """A validated resource: metadata plus the decoded Float64 coefficients."""

    var metadata: FilterMetadata
    var values: List[Float64]

    def __init__(out self, metadata: FilterMetadata, var values: List[Float64]):
        self.metadata = metadata
        self.values = values^

    def count(self) -> Int:
        return len(self.values)

    def __len__(self) -> Int:
        return len(self.values)

    def __getitem__(self, index: Int) raises -> Float64:
        if index < 0 or index >= len(self.values):
            raise Error(
                "coefficient index " + String(index)
                + " out of range for count " + String(len(self.values))
            )
        return self.values[index]

    def view(self) -> Span[Float64, origin_of(self.values)]:
        return Span(self.values)


def parse_filter_metadata(text: String) raises -> FilterMetadata:
    """Parse and validate a flat coefficient-resource metadata JSON object."""
    var obj = parse_json_object(text)
    var required = List[String]()
    required.append("schema_version")
    required.append("filter_id")
    required.append("coefficient_count")
    required.append("precision")
    required.append("rolloff")
    required.append("dtype")
    required.append("byte_order")
    required.append("resource_bytes")
    required.append("resource_sha256")
    for key in required:
        if not obj.has(key):
            raise Error("coefficient metadata missing required key '" + key + "'")
    for key in obj.keys():
        var known = False
        for r in required:
            if key == r:
                known = True
        if not known:
            raise Error("coefficient metadata has unknown key '" + key + "'")

    var schema_version = obj.get_int("schema_version")
    if schema_version != FILTER_SCHEMA_VERSION:
        raise Error(
            "unsupported coefficient schema_version " + String(schema_version)
            + ", expected " + String(FILTER_SCHEMA_VERSION)
        )
    var dtype = obj.get_string("dtype")
    if dtype != "float64":
        raise Error("coefficient dtype must be 'float64', got '" + dtype + "'")
    var byte_order = obj.get_string("byte_order")
    if byte_order != "little":
        raise Error(
            "coefficient byte_order must be 'little' (explicit LE interpretation), got '"
            + byte_order + "'"
        )
    var filter_id = obj.get_string("filter_id")
    if filter_id.byte_length() == 0:
        raise Error("coefficient filter_id must be non-empty")
    var count = obj.get_int("coefficient_count")
    if count < 0:
        raise Error("coefficient_count must be non-negative, got " + String(count))
    if count > MAX_COEFFICIENT_COUNT:
        raise Error(
            "coefficient_count " + String(count) + " exceeds limit "
            + String(MAX_COEFFICIENT_COUNT)
        )
    var precision = obj.get_int("precision")
    if precision <= 0:
        raise Error("coefficient precision must be positive, got " + String(precision))
    var rolloff = obj.get_float("rolloff")
    if rolloff <= 0.0 or rolloff > 1.0:
        raise Error("coefficient rolloff must be in (0, 1], got " + String(rolloff))
    var resource_bytes = obj.get_int("resource_bytes")
    if resource_bytes < 0 or resource_bytes > MAX_RESOURCE_BYTES:
        raise Error(
            "resource_bytes " + String(resource_bytes) + " is outside [0, "
            + String(MAX_RESOURCE_BYTES) + "]"
        )
    if resource_bytes != count * FLOAT64_BYTES:
        raise Error(
            "resource_bytes " + String(resource_bytes)
            + " does not match coefficient_count " + String(count)
            + " x 8 bytes (expected " + String(count * FLOAT64_BYTES) + ")"
        )
    var digest = obj.get_string("resource_sha256")
    if digest.byte_length() != 64:
        raise Error(
            "resource_sha256 must be 64 lowercase hex characters, got length "
            + String(digest.byte_length())
        )
    for byte in digest.as_bytes():
        if not (
            (byte >= 48 and byte <= 57) or (byte >= 97 and byte <= 102)
        ):
            raise Error("resource_sha256 contains a non-lowercase-hex character")
    return FilterMetadata(
        schema_version,
        filter_id,
        count,
        precision,
        rolloff,
        dtype,
        byte_order,
        resource_bytes,
        digest,
    )


def _read_file(path: String, max_bytes: Int) raises -> List[UInt8]:
    """Read at most ``max_bytes + 1`` bytes so an oversized file is rejected
    before it can be fully allocated. The extra byte detects over-limit files.
    """
    try:
        var handle = FileHandle(path, "r")
        var data = handle.read_bytes(size=max_bytes + 1)
        handle.close()
        if len(data) > max_bytes:
            raise Error(
                "resource file '" + path + "' exceeds the " + String(max_bytes) + "-byte limit"
            )
        return data^
    except error:
        raise Error("cannot read resource file '" + path + "': " + String(error))


def validate_filter_resource(
    metadata_text: String, payload: Span[UInt8, _]
) raises -> FilterCoefficients:
    """Validate metadata + raw coefficient bytes held in memory.

    Checks metadata schema, explicit little-endian dtype, byte length,
    element count and SHA-256 integrity before decoding any value.
    """
    var metadata = parse_filter_metadata(metadata_text)
    if len(payload) > MAX_RESOURCE_BYTES:
        raise Error(
            "coefficient payload " + String(len(payload))
            + " bytes exceeds limit " + String(MAX_RESOURCE_BYTES)
        )
    if len(payload) != metadata.resource_bytes:
        raise Error(
            "truncated or oversized coefficient resource: expected "
            + String(metadata.resource_bytes) + " bytes, got " + String(len(payload))
        )
    var actual = sha256_hex(Span(payload))
    if actual != metadata.resource_sha256:
        raise Error(
            "coefficient integrity failure: sha256 " + actual
            + " does not match metadata " + metadata.resource_sha256
        )
    var values = decode_f64le(Span(payload))
    if len(values) != metadata.coefficient_count:
        raise Error(
            "decoded coefficient count " + String(len(values))
            + " does not match metadata " + String(metadata.coefficient_count)
        )
    return FilterCoefficients(metadata, values^)


def load_filter(metadata_path: String, resource_path: String) raises -> FilterCoefficients:
    """Load and fully validate a coefficient resource from two files."""
    var metadata_bytes = _read_file(metadata_path, MAX_METADATA_BYTES)
    var metadata_text = String(from_utf8=Span(metadata_bytes))
    var payload = _read_file(resource_path, MAX_RESOURCE_BYTES)
    return validate_filter_resource(metadata_text, Span(payload))


def describe_filter(resource: FilterCoefficients) raises -> String:
    """Human-readable one-line summary for CLI responses and tests."""
    return (
        "filter_id=" + resource.metadata.filter_id
        + ";count=" + String(resource.metadata.coefficient_count)
        + ";precision=" + String(resource.metadata.precision)
        + ";rolloff=" + String(resource.metadata.rolloff)
        + ";dtype=" + resource.metadata.dtype
        + ";byte_order=" + resource.metadata.byte_order
        + ";resource_bytes=" + String(resource.metadata.resource_bytes)
        + ";sha256=" + resource.metadata.resource_sha256
        + ";first_bits=" + bytes_to_hex(Span(_first_bytes(resource)))
    )


def _first_bytes(resource: FilterCoefficients) -> List[UInt8]:
    from mojo_resampy.float_codec import encode_f64le
    var out = List[UInt8]()
    if len(resource.values) > 0:
        var one = List[Float64](capacity=1)
        one.append(resource.values[0])
        return encode_f64le(Span(one))
    return out^
