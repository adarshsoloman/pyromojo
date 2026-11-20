"""Resampy representation layer and Phase 4 resampling kernel.

Representation, comparison, codec and verification utilities are exported
alongside ``resample`` and ``output_length``.
"""

from mojo_resampy.signal import Signal
from mojo_resampy.output import OutputBuffer
from mojo_resampy.float_codec import (
    base64_decode_bytes,
    base64_encode_bytes,
    bits_to_float64,
    bytes_to_hex,
    decode_f64le,
    encode_f64le,
    float64_to_bits,
    hex_to_bytes,
)
from mojo_resampy.sha256 import sha256_hex, sha256_hex_of_f64le
from mojo_resampy.json_codec import (
    JSON_BOOL,
    JSON_FLOAT,
    JSON_INT,
    JSON_NULL,
    JSON_STRING,
    JsonObject,
    JsonValue,
    parse_json_object,
)
from mojo_resampy.coefficients import (
    FILTER_SCHEMA_VERSION,
    FilterCoefficients,
    FilterMetadata,
    describe_filter,
    load_filter,
    parse_filter_metadata,
    validate_filter_resource,
)
from mojo_resampy.numerical_compare import ComparisonResult, compare_arrays
from mojo_resampy.golden_vector import (
    GOLDEN_SCHEMA_VERSION,
    GoldenVector,
    parse_golden_vector,
    serialize_golden_vector,
)
from mojo_resampy.resample import resample, output_length
from mojo_resampy.protocol import (
    MAX_FRAME_BYTES,
    OP_COMPARE,
    OP_ECHO,
    OP_F64_DECODE,
    OP_F64_ENCODE,
    OP_FILTER_LOAD,
    OP_GOLDEN_PARSE,
    OP_GOLDEN_SERIALIZE,
    OP_OUTPUT_ALLOC,
    OP_OUTPUT_SET,
    OP_PING,
    OP_RESAMPLE,
    OP_SHA256,
    OP_SIGNAL_INFO,
    STATUS_ERROR,
    STATUS_OK,
    append_u32_be,
    ascii_bytes,
    decode_u32_be,
    read_frame,
    write_frame,
)
