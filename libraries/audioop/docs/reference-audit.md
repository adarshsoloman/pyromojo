# Reference audit: CPython `audioop` (3.12.3)

Status: Phase 0 investigation only. Every behavioural claim below was either
read from the pinned C source or observed with
`python_reference/probe_audioop.py` (416 cases). Nothing here is inferred from
documentation alone.

## 1. Identity and provenance

| Field | Value |
| --- | --- |
| Module | `audioop` (CPython standard library) |
| Reference version | CPython **3.12.3** |
| Source file | `Modules/audioop.c`, 2003 lines |
| Source SHA-256 | `3ad415f1cafa3dc8118cc63ca4f7089c9ebc325f2fcf741f62eb3771e31f620d` |
| Tarball SHA-256 | `a6b9459f45a6ebbbc1af44f5762623fa355a0c87208ed417628b379d762dddb0` |
| GitHub tag → commit | `v3.12.3` → `f6650f9ad73359051f3e558c2431a109bc016664` |
| Installed build | `/usr/lib/python3.12/lib-dynload/audioop.cpython-312-x86_64-linux-gnu.so` |
| Distribution package | `libpython3.12-stdlib 3.12.3-1ubuntu0.17` |
| Status upstream | deprecated since 3.11 (PEP 594), **removed in 3.13** |

The tarball checksum was compared against the official CPython release SPDX
document, and `Modules/audioop.c` from the tarball is byte-identical to the
file at the GitHub tag. Provenance chain in the file header: the code was
taken from SoX 12.17.7 `g777.c` (the header's `Copyright of g771.c` label is
an upstream inconsistency; both spellings appear). The Sun Microsystems
unrestricted-use notice covers that derived code; the file as a whole ships
in CPython under the PSF-2.0 license. See `licensing-audit.md`.

## 2. Reference build and equivalence proof

Two independent builds were compared:

1. the distribution's `audioop.cpython-312-x86_64-linux-gnu.so`;
2. a pristine build of the pinned `audioop.c` (same compiler flags, module
   init symbol renamed to avoid collision).

```
gcc -shared -fPIC -O2 -I/usr/include/python3.12 -I/tmp/Python-3.12.3/Modules \
    -DPyInit_audioop=PyInit_audioop_pristine \
    /tmp/Python-3.12.3/Modules/audioop.c \
    -o /tmp/audioop_pristine.cpython-312-x86_64-linux-gnu.so
```

`python_reference/verify_reference.py` replayed all 416 probe cases against
both modules:

```
verify_reference: 416 cases, 0 mismatches
  (audioop.cpython-312-x86_64-linux-gnu.so vs audioop_pristine...so)
```

Conclusion: the distribution build **is** the pinned upstream source. All
behaviour recorded below is therefore attributable to CPython 3.12.3 and not
to a distro patch.

## 3. Public surface

26 functions plus one exception type. `error` subclasses `Exception` directly
(never `ValueError`/`TypeError`).

| Function | Signature (positional-only) | Returns |
| --- | --- | --- |
| `add` | `(fragment1, fragment2, width)` | bytes |
| `bias` | `(fragment, width, bias)` | bytes |
| `mul` | `(fragment, width, factor)` | bytes |
| `max` | `(fragment, width)` | int |
| `minmax` | `(fragment, width)` | `(min, max)` |
| `avg` | `(fragment, width)` | int |
| `rms` | `(fragment, width)` | int |
| `cross` | `(fragment, width)` | int |
| `findfactor` | `(fragment, reference)` | float |
| `findfit` | `(fragment, reference)` | `(int, float)` |
| `findmax` | `(fragment, length)` | int |
| `avgpp` | `(fragment, width)` | int |
| `maxpp` | `(fragment, width)` | int |
| `getsample` | `(fragment, width, index)` | int |
| `byteswap` | `(fragment, width)` | bytes |
| `reverse` | `(fragment, width)` | bytes |
| `lin2lin` | `(fragment, width, newwidth)` | bytes |
| `lin2ulaw` | `(fragment, width)` | bytes |
| `ulaw2lin` | `(fragment, width)` | bytes |
| `lin2alaw` | `(fragment, width)` | bytes |
| `alaw2lin` | `(fragment, width)` | bytes |
| `lin2adpcm` | `(fragment, width, state)` | `(bytes, state)` |
| `adpcm2lin` | `(fragment, width, state)` | `(bytes, state)` |
| `ratecv` | `(fragment, width, nchannels, inrate, outrate, state, weightA=1, weightB=0)` | `(bytes, state)` |
| `tomono` | `(fragment, width, lfactor, rfactor)` | bytes |
| `tostereo` | `(fragment, width, lfactor, rfactor)` | bytes |

Notable API facts:

- There is **no endianness parameter**. All 16/24/32-bit reads and writes use
  native byte order; `byteswap` exists to convert fragments.
- There is **no `min` function**; `minmax` returns both extremes and `max`
  returns the maximum absolute value.
- `findfactor`, `findfit`, and `findmax` are **fixed at 16-bit** and take no
  `width` argument, even though every other function is width-polymorphic.
- `state` is a tuple in the reference (`None` on first call).

## 4. Sample representation

Widths 1–4 map to signed two's-complement samples of 8/16/24/32 bits, stored
in native byte order at `index * width`. The reference keeps:

```
maxvals = {0, 0x7F, 0x7FFF, 0x7FFFFF, 0x7FFFFFFF}
minvals = {0, -0x80, -0x8000, -0x800000, -0x7FFFFFFF-1}
masks   = {0, 0xFF, 0xFFFF, 0xFFFFFF, 0xFFFFFFFF}
```

Validation order (observed, and confirmed against the source):

1. width check → `Size should be 1, 2, 3 or 4`;
2. frame alignment → `not a whole number of frames`;
3. function-specific checks (length equality, index range, state shape…).

`getsample` rejects negative indices as well as indices past the last sample
(`Index out of range`); the probe suite records both cases.

## 5. Behaviour inventory

### Arithmetic transforms

| Op | Rule (from source + probes) |
| --- | --- |
| `add` | Samplewise `a + b`. Widths 1–3 use C `int` then clamp; width 4 promotes to `double` before clamping, avoiding signed-overflow UB. Equal fragment lengths required (`Lengths should be the same`). |
| `bias` | `(sample + bias) & mask` reinterpreted as signed — **wraps**, never clamps. |
| `mul` | `fbound(sample * factor)` per sample: clamp to `[minval, maxval]`, then `floor`, then truncate. `-3 * 0.5 == -2`. |
| `tomono` | `l*L + r*R` per frame through the same `fbound`. |
| `tostereo` | `l*sample` and `r*sample` through `fbound`, interleaved. |

### Statistics

| Op | Rule |
| --- | --- |
| `max` | Maximum absolute value; absolute value computed in unsigned 32-bit, so `-2147483648` yields `2147483648`. |
| `minmax` | Minimum and maximum signed values. Empty input returns the sentinels `(2147483647, -2147483648)`. |
| `avg` | Integer division truncating toward zero (`avg([-1,0]) == 0`). Empty → `0`. |
| `rms` | `int(floor(sqrt(sum(s²)/n)))`, computed in `double`. Empty → `0`. |
| `avgpp` | Average absolute difference between successive samples; empty → `0`; a single sample → `0`. |
| `maxpp` | Maximum absolute successive difference; empty → `0`. |
| `cross` | Counts sign changes between successive samples, biased by an initial `-1`. Empty → `-1`; all-non-negative input → `0`; `[1,-1,1,-1]` → `3`. |

### Matching (16-bit only)

- `findfactor(fragment, reference)` → `sum(a*r) / sum(r²)`; requires equal
  byte lengths and even lengths (`Samples should be same size`,
  `Strings should be even-sized`). Empty/empty → `nan`.
- `findfit(fragment, reference)` → `(offset, factor)` minimising residual
  energy; requires `len(fragment) >= len(reference)` (`First sample should be
  longer`); does **not** require equal lengths. Empty/empty → `(0, nan)`.
- `findmax(fragment, length)` → index of the `length`-sample window with
  maximum energy; `length` is in **samples** (fixed 16-bit), and
  `length > len(fragment)/2` raises `Input sample should be longer`.
- All three ignore any width convention: input length must be even, samples
  are read as native 16-bit.

### Fragment transforms

- `getsample` → signed sample at `index`; out of range → `Index out of range`.
- `byteswap` → swaps byte order within each width-sized sample.
- `reverse` → reverses the order of samples, preserving each sample's bytes.
- `lin2lin` → re-quantises by shifting into a 32-bit domain and back:
  widening shifts left (`<< (newwidth-width)*8`), narrowing shifts right
  arithmetically (truncating toward negative infinity), then the low
  `newwidth` bytes are stored.

### Codecs

- `lin2ulaw` / `ulaw2lin` — Sun/SoX u-law. Encoding shifts samples to a
  14-bit domain, clips at `CLIP`, adds `BIAS>>2 = 33`, selects a segment via
  `seg_uend`, and XORs with `0x7F` / `0xFF` according to sign. Decoding uses a
  256-entry table.
- `lin2alaw` / `alaw2lin` — A-law, 13-bit domain, even-bit inversion mask
  `0xD5`/`0x55`, segment search via `seg_aend`, XOR masks. Decoding uses a
  256-entry table.
- `lin2adpcm` — Intel/DVI 4-bit ADPCM. State is `(valpred, index)`; the
  89-entry `stepsizeTable` and 16-entry `indexTable` drive the predictor.
  Two samples are packed per output byte; a trailing odd sample is dropped
  (`len//(width*2)` output bytes). `state=None` starts at `(0, 0)`.
- `adpcm2lin` — reverses the above; output is `nibbles * width` bytes.
- `ratecv` — rational resampler. Rates and weights are reduced by their GCD;
  samples are promoted to a 32-bit domain, interpolated with
  `weightA`/`weightB` history, and written back. State is
  `(d, (prev, cur) per channel)`. Output length is an upper bound:
  `ceil(len/inrate) * outrate` frames; the returned slice is trimmed.

### Error type

`audioop.error` derives directly from `Exception`. The probe suite records
46 exceptions across 19 distinct messages, including the reference's
TypeErrors for wrong argument types (`state must be a tuple or None`,
`ratecv(): illegal state argument`, `lin2adpcm(): illegal state argument`).

## 6. Reference quirks that a port must preserve

These are observed, not hypothetical:

1. Empty `minmax` → `(2147483647, -2147483648)`.
2. Empty `cross` → `-1`; the counter starts at `-1` regardless of input.
3. `findfactor(b"", b"")` → `nan`; `findfit(b"", b"")` → `(0, nan)`.
   No exception is raised.
4. `mul(fragment, w, nan)` and non-finite factors reach C's
   `(int)NaN`/`(int)Inf`; the reference documents no behaviour. On this build
   width 1–3 produce zero samples and width 4 produces `0x80000000` per
   sample. Treated as **undefined**; the port must define a policy and the
   Python-compat layer must not claim nan parity.
5. `bias` wraps: `bias(0x7FFF, 2, 1) == 0x8000` (i.e. `-32768`), while `add`
   clamps.
6. `mul` rounds with `floor` after clamping, not round-half-even:
   `3 * 0.5 == 1`, `-3 * 0.5 == -2`.
7. An odd sample count is silently dropped by `lin2adpcm`; odd byte counts
   are accepted by `adpcm2lin` (each nibble is independent).
8. `ratecv` output length is an over-allocation trimmed to the real count;
   the returned bytes are not zero-padded.
9. Widths are validated before frame alignment, so a bad width masks a
   ragged fragment error.
10. `findmax` takes `length` in samples, while its guard is expressed in
    samples after `len >> 1`; a 4-byte fragment with `length=4` therefore
    raises even though both are numerically equal in bytes.

## 7. Determinism

- No randomness, no environment dependence, no locale dependence.
- The only platform dependence is **native byte order** (and C `int` being
  32-bit, `int16_t`/`int32_t` being two's-complement). The recorded vectors
  carry `host.byte_order` so a big-endian host can be detected and handled.
- Floating-point results (`rms`, `findfactor`, `findfit`, `ratecv`) follow
  IEEE-754 doubles; the port must use `Float64` and the same operation order
  where the tests require bit-identical integers.
