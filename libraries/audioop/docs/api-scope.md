# API scope: audioop v0.1 (frozen)

Scope is frozen for the first release. "In scope" means the Python-compatible
operation set implemented in Mojo and covered by golden vectors plus
differential tests. "Deferred" and "out of scope" entries are deliberate.

## In scope (v0.1)

All 26 reference functions, with reference-compatible signatures at the
Mojo-CLI boundary and the same sample semantics:

- **Arithmetic:** `add`, `bias`, `mul`, `tomono`, `tostereo`.
- **Statistics:** `max`, `minmax`, `avg`, `rms`, `cross`, `avgpp`, `maxpp`.
- **Matching (fixed 16-bit, as in the reference):** `findfactor`, `findfit`,
  `findmax`.
- **Fragments:** `getsample`, `byteswap`, `reverse`, `lin2lin`.
- **Codecs:** `lin2ulaw`, `ulaw2lin`, `lin2alaw`, `alaw2lin`, `lin2adpcm`,
  `adpcm2lin`.
- **Stateful:** `ratecv`.
- **Error type:** `audioop.error`, raised with the reference's message text
  for all validation failures that the port reproduces.

Widths 1, 2, 3 and 4; native byte order only; fragments are opaque byte
buffers; `state` is an optional tuple/`None` exactly as in the reference.

## Frozen compatibility decisions

1. **Native byte order.** No endianness parameter is added in v0.1. On
   little-endian hosts the behaviour is identical to CPython 3.12.3;
   vectors record the generating host's byte order. A future option can add
   explicit endianness without changing the default.
2. **Bytes only.** The Python-compat layer accepts `bytes`/`bytearray`.
   Arbitrary buffer objects (`memoryview`, numpy arrays) are not part of
   v0.1; the framed CLI already transports bytes unambiguously.
3. **Undefined float cases stay undefined.** `mul` with `nan`/`inf` follows a
   documented port policy rather than pretending to match C's undefined
   `(int)NaN`. Tests exclude those combinations from equality assertions.
4. **Error text is part of the contract.** Messages such as
   `Size should be 1, 2, 3 or 4` and `not a whole number of frames` are
   reproduced verbatim; Python-compat tests compare message strings.
5. **Sentinel values are preserved.** Empty `minmax` returns
   `(2147483647, -2147483648)`; empty `cross` returns `-1`; empty
   `findfactor` returns `nan`. These are not "fixed" in the port.
6. **`findfactor`/`findfit`/`findmax` are 16-bit only**, matching the
   reference's narrow signatures. They are not generalised to other widths
   in v0.1.
7. **No additional public API.** Helper functions, a streaming resampler, or
   a Python extension module are not exposed in v0.1.

## Deferred (recorded, not rejected)

- Zero-copy buffer views and a Python C-extension binding.
- Explicit big-endian input/output support.
- Streaming/incremental resampling beyond the reference's state tuple.
- SIMD/batched variants of the sample loops.
- Wider-than-4-byte samples (never present upstream).

## Out of scope (unchanged)

- Reimplementing CPython's `audioop` deprecation policy or module-level
  `DeprecationWarning`.
- Deprecated companions (`sunaudio`, `ossaudiodev`) and unrelated audio I/O.
- Any behaviour absent from the reference (e.g. new codecs, channel
  conversion beyond `tomono`/`tostereo`).

## Interop surface

v0.1 reuses the repository's established **framed Mojo CLI** transport
(`uint32_be length | uint8 opcode | payload`, response `uint8 status |
payload`), as used by the msgpack, Levenshtein and bitarray ports:

- one opcode per reference function, plus a metadata/version opcode;
- payloads carry raw fragment bytes, width, and scalar arguments;
- stateful operations carry the incoming state tuple and return the new one;
- errors carry the exact message text in the response payload.

Python-compat tests call the reference and the CLI on identical inputs and
compare results (and messages) byte-for-byte. Differential testing with a
fixed seed supplements the golden vectors. A native Python extension is
deferred; it is not needed to prove correctness.

## Scope trade-offs

- Implementing all 26 functions (rather than a "core" subset) is justified:
  the functions share the same sample-access and validation machinery, and
  partial coverage would make Python-compat claims misleading.
- Fixed-16-bit matching functions stay fixed-16-bit: generalising them would
  diverge from the reference and break numeric equality.
- Excluding a Python extension keeps the first release reviewable; the CLI is
  sufficient for correctness and performance measurement.

## Open questions for Phase 1 (not blockers)

- Whether the CLI should expose a single binary or one binary per function
  group (decision can follow the bitarray precedent once code exists).
- Whether `mul`'s NaN policy should raise, clamp, or return zeros; the
  reference is undefined, so any documented choice is defensible. Current
  leaning: deterministic zeros for widths 1–3 and `0x80000000` for width 4,
  i.e. reproduce the observed build, and mark it undocumented behaviour.
- Whether to ship a `python_reference/requirements.txt` pin: audioop is stdlib
  and was removed in 3.13, so the pin is a Python **interpreter** range
  (`>=3.11,<3.13`) documented in the reference README rather than a package
  version.
