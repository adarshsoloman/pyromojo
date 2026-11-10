# Levenshtein (Mojo Port)

## Status: NOT STARTED

## Library description

Edit distance and string similarity: Levenshtein distance, ratio-based
similarity, and related operations used in fuzzy matching, spell correction,
and record linkage.

## Original Python package

- Package: `Levenshtein` (formerly python-Levenshtein)
- Pinned reference version and license: recorded in
  `python_reference/requirements.txt` when implementation begins, per
  [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Upstream source is not vendored.

## Planned Mojo implementation

Native distance and similarity routines over byte or code-point sequences, with
an explicit choice of unit (bytes versus Unicode code points) documented up
front. No Python dependency in the measured native path.

## Compatibility objectives

- Match reference distance values for all supported input types.
- Match similarity ratio semantics, including asymmetry where the reference has
  it.
- Handle empty strings, equal strings, and length-mismatch edge cases exactly as
  the reference does.
- Define and document behaviour for non-ASCII input before implementation.

## Testing requirements

- Mojo unit tests for known distance pairs and boundary cases.
- Python compatibility tests against the pinned reference across generated
  input pairs.
- Golden vectors covering ASCII, non-ASCII, empty, and long inputs.
- Explicit tests for any documented deviation.

## Benchmarking requirements

- Inputs of varying length and dissimilarity.
- Three-way comparison: Python reference, native Mojo, Mojo via Python interop.
- Cold compilation and warm execution reported separately.

## Current status

NOT STARTED — placeholder only.
