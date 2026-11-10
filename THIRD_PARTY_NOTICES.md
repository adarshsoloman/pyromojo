# Third-Party Dependency Policy

PyroMojo ports Python libraries. It does not redistribute them by default.
This document defines how third-party code, specifications, and licenses are
handled.

## Reference implementations

- The original Python package is installed as a **pinned external dependency**
  when a port needs reference behaviour.
- Pins are exact versions recorded in the library's own reference dependency
  file (for example, `libraries/<library>/python_reference/requirements.txt`),
  created when that port begins.
- Upstream source code is **not copied into this repository** by default.
  Vendoring requires an explicit written justification, a license review, and
  retention of the upstream license text.
- Test vectors derived from observed upstream behaviour are stored in
  `libraries/<library>/tests/vectors/` and documented as derived data.

## Per-library documentation

Every library must document, in its README or a linked notice:

- The upstream package and the exact pinned version used as reference.
- The upstream license and its terms.
- Any additional transitive dependency used directly by that port.
- Any known compatibility deviations from the reference implementation.

## License compatibility

- Apache License 2.0 is the license for PyroMojo's own code.
- Permissive dependencies (Apache-2.0, MIT, BSD, ISC, PSF) are generally
  acceptable for reference use.
- **Copyleft dependencies** (GPL, LGPL, AGPL, MPL with copyleft obligations, or
  any license with distribution conditions) require an explicit compatibility
  review **before** they are distributed with, linked into, or incorporated
  into PyroMojo.
- A compatibility review must be recorded in the relevant library's
  documentation and reviewed by a maintainer.
- Where a copyleft reference cannot be used safely, the port may rely on a
  published specification or independently produced test vectors instead.

## Attribution

Retain all required copyright and attribution notices for any third-party
material that is included. When in doubt, keep the upstream notice and add an
entry to this file.
