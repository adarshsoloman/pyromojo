# audioop (Mojo Port)

## Status: NOT STARTED

## Library description

Legacy operations on raw audio samples: sample-width conversion, channel
conversion, gain, bias, clipping, RMS, peak, and related transforms. The module
was part of the Python standard library and was removed in Python 3.13 under
PEP 594, so a native implementation is useful for code maintaining that
behaviour.

## Original Python package

- Reference: the CPython `audioop` standard library module, or a pinned
  maintained backport where the target interpreter no longer ships it.
- Reference version, source distribution, and license: recorded in
  `python_reference/requirements.txt` when implementation begins, per
  [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Upstream source is not vendored.

## Planned Mojo implementation

Native sample-buffer transforms over 8-, 16-, 24-, and 32-bit integer samples,
with explicit endianness and signedness handling. The API shape and supported
subset will be documented before coding.

## Compatibility objectives

- Match reference results for supported sample widths and operations.
- Preserve saturating and wrapping behaviour exactly where the reference
  distinguishes them.
- Handle empty buffers, odd buffer lengths, and fragment counts as the
  reference does.
- Document any operation intentionally excluded from the port.

## Testing requirements

- Mojo unit tests for each supported operation and sample width.
- Python compatibility tests against the reference implementation.
- Golden vectors including boundary amplitudes, silence, and malformed buffer
  lengths.

## Benchmarking requirements

- Short and long buffers, mono and multi-channel.
- Three-way comparison: Python reference, native Mojo, Mojo via Python interop.
- Cold compilation and warm execution reported separately.

## Current status

NOT STARTED — placeholder only.
