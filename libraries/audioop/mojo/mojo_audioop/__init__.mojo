"""Native Mojo audioop: sample, arithmetic, statistics and peak layers."""

from mojo_audioop.arithmetic import (
    add,
    bias,
    byteswap,
    lin2lin,
    mul,
    reverse,
)
from mojo_audioop.peak_analysis import (
    avgpp,
    findfactor,
    findfit,
    findmax,
    maxpp,
)
from mojo_audioop.statistics import (
    avg,
    cross,
    getsample,
    max,
    minmax,
    rms,
)
from mojo_audioop.protocol import (
    OP_DECODE_FRAGMENT,
    OP_ECHO,
    OP_ENCODE_FRAGMENT,
    OP_PING,
    STATUS_ERROR,
    STATUS_OK,
    ascii_bytes,
    decode_u32_be,
    read_frame,
    write_frame,
)
from mojo_audioop.samples import (
    MAX_WIDTH,
    MIN_WIDTH,
    decode_fragment,
    decode_sample,
    encode_fragment,
    encode_sample,
    in_sample_range,
    native_is_little_endian,
    sample_count,
    sample_max,
    sample_min,
    validate_fragment,
    validate_value,
    validate_width,
)
