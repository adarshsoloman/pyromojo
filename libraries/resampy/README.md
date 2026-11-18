# resampy (Mojo Port)

## Status: PHASE 3 COMPLETE — representation layer only (no resampling algorithm)

Phase 3 provides the native Mojo Float64 representation and verification
infrastructure: signal/output buffers, a synthetic coefficient resource loader
with SHA-256 integrity, a strict minimal JSON/Base64 codec, a numerical
comparator with an explicit non-finite policy, a versioned golden-vector
protocol, and a minimal framed CLI. **There is no resampling implementation, no
`resample`, and no upstream filter coefficient data** (licensing review pending).
All tests are synthetic. See [representation design](docs/representation-design.md)
and the Phase 1/2 audits in `docs/`.

Build and test with `--fp-mode contract=off`; run
`.venv/bin/python libraries/resampy/tests/run_phase3_tests.py` from the repo root.

## Library description

High-quality audio resampling: band-limited interpolation for changing the
sample rate of a signal, with selectable filter characteristics.

## Original Python package

- Package: `resampy`
- Pinned reference version and license: recorded in
  `python_reference/requirements.txt` when implementation begins, per
  [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Upstream source is not vendored.

## Planned Mojo implementation

Native band-limited resampling over sample buffers, with documented filter
design, phase handling, and edge/padding treatment. Numerical tolerance against
the reference will be defined explicitly rather than assumed to be exact.

## Compatibility objectives

- Match reference output within a documented tolerance for supported rates.
- Match output length and boundary handling for whole-buffer resampling.
- Match behaviour for mono and multi-channel input as supported.
- Document any excluded filter modes or parameters.

## Testing requirements

- Mojo unit tests for rate ratios, signal lengths, and boundary handling.
- Python compatibility tests against the pinned reference with an explicit
  numerical tolerance.
- Golden vectors for representative rates and signals, including silence and
  impulses.

## Benchmarking requirements

- Short and long signals, upsampling and downsampling, mono and multi-channel.
- Three-way comparison: Python reference, native Mojo, Mojo via Python interop.
- Cold compilation and warm execution reported separately.

## Current status

PHASE 3 COMPLETE — representation layer only. Resampling, upstream filter
integration, and compatibility-tolerance calibration are deferred to Phase 4+.
