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

## audioop (native Mojo port)

- Reference: CPython 3.12.3 `audioop` (stdlib module, PSF-2.0). The module was
  removed in Python 3.13; the pinned 3.12 interpreter is local tooling only
  (`libraries/audioop/python_reference/.venv`, git-ignored) and no upstream
  source is vendored.
- The u-law/A-law routines and their decode tables in the reference derive
  from SoX 12.17.7 `g777.c`/`g771.c` and carry the following embedded notice,
  which is retained here for the tables transcribed into
  `libraries/audioop/mojo/mojo_audioop/g711.mojo`:

  > This source code is a product of Sun Microsystems, Inc. and is provided
  > for unrestricted use. Users may copy or modify this source code without
  > charge.
  >
  > SUN SOURCE CODE IS PROVIDED AS IS WITH NO WARRANTIES OF ANY KIND
  > INCLUDING THE WARRANTIES OF DESIGN, MERCHANTIBILITY AND FITNESS FOR A
  > PARTICULAR PURPOSE, OR ARISING FROM A COURSE OF DEALING, USAGE OR TRADE
  > PRACTICE.
  >
  > Sun Microsystems, Inc., 2550 Garcia Avenue, Mountain View, California
  > 94043.

- The ADPCM step-size and index tables in
  `libraries/audioop/mojo/mojo_audioop/adpcm.mojo` are standard IMA/DVI
  constants taken from the published specification and cross-checked against
  the reference implementation.
- The Mojo implementation itself is independent; numerical test vectors in
  `libraries/audioop/tests/vectors/` are derived data recorded from observed
  reference behaviour.
