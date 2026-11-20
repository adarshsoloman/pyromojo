# Roadmap

Status: Msgpack, Levenshtein, Bitarray, and Audioop v0.1 are complete and
released, with CLI/test runners and curated benchmark reports. Resampy's native
implementation, parity evidence, and benchmarks are complete, but its release
is blocked on production coefficient-table licensing clarity. Dates are
intentionally omitted; phases are completed when their exit criteria are met.

## Phase 1: Repository foundation

**Goal:** A maintainable, reproducible project skeleton.

- [x] Directory structure for libraries, shared infrastructure, scripts, docs.
- [x] Root documentation, license, third-party policy, and editor/CI ignores.
- [x] Python project configuration (test and lint tooling).
- [x] Placeholder CI workflows with toolchain steps marked for later setup.
- [x] Verify the locally installed Mojo toolchain and record its version.
- [x] Add test vector JSON schema and the first shared generator interface.

**Exit criteria:** Clean scaffold reviewed, configuration validated, and the
toolchain documented.

## Phase 2: Msgpack v0.1

**Goal:** The first complete port, exercising the entire workflow.

Scope: integer, float, string, binary, array, map, extension, and timestamp
encoding; decoding; nested structures; invalid-input handling.

Progress: the full v0.1 type set — integers, floats, strings, binary, arrays,
maps, extensions, and timestamps — plus top-level nil/bool, the audited
batch CLI, repository test runners, and the three-way benchmark suite with
a curated release report are complete
([results](../libraries/msgpack/PHASE7_RESULTS.md)).

- [x] Pin the reference `msgpack` version and document its license.
- [x] Define the v0.1 compatibility surface and known deviations.
- [x] Add golden vectors covering all supported types and nesting.
- [x] Implement native Mojo encoding and decoding.
- [x] Add Mojo unit tests and Python compatibility tests.
- [x] Add repository test and compatibility runners (`run_all_tests.py`,
  `check_compatibility.py`).
- [x] Add cold-compilation and warm-execution benchmarks with a curated
  release report (`docs/benchmarks/releases/msgpack-v0.1.md`).

**Exit criteria:** All vector and compatibility tests pass; benchmark report is
reproducible from a clean checkout.

## Phase 3: First five verified ports

**Goal:** Demonstrate the process generalises beyond one library.

Candidates: `levenshtein`, `audioop`, `bitarray`, `resampy`.

- [x] Establish a per-library checklist derived from the Msgpack work.
- [x] Port four libraries to the same verification standard.
- [x] Publish per-library compatibility and limitation notes for released ports.
- [x] Publish comparable benchmark reports using the shared methodology.
- [ ] Clear production coefficient licensing and release Resampy.

**Exit criteria:** Five ports with green test suites, shared vectors, and
documented benchmarks. Resampy's implementation and evidence satisfy the
technical bar; its release remains blocked pending licensing clearance.

## Phase 4: Expand toward 20 libraries

**Goal:** Broad, sustainable coverage.

- [ ] Prioritise libraries by user value, licensing clarity, and tractability.
- [ ] Recruit and onboard maintainers per library.
- [ ] Keep review and CI load manageable as the library count grows.
- [ ] Track coverage, compatibility, and maintenance status in one index.

**Exit criteria:** At least 20 independently maintained and verified ports.

## Phase 5: Performance analysis and ecosystem contributions

**Goal:** Turn measurements into knowledge and upstream value.

- [ ] Publish cross-library performance analysis with methodology and caveats.
- [ ] Identify patterns where native Mojo materially changes cost profiles.
- [ ] Contribute findings, bug reports, and tooling back to relevant projects.
- [ ] Evaluate whether shared infrastructure should be published as reusable
      packages.

**Exit criteria:** Published analysis and documented ecosystem contributions.
