# Roadmap

Status: initial scaffolding. Dates are intentionally omitted; phases are
completed when their exit criteria are met.

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

Progress: the integer codec and its cross-language tests are complete
([results](../libraries/msgpack/PHASE2_RESULTS.md)). The remaining type families
are still in progress.

- [x] Pin the reference `msgpack` version and document its license.
- [x] Define the v0.1 compatibility surface and known deviations.
- [x] Add golden vectors covering all supported types and nesting.
- [ ] Implement native Mojo encoding and decoding.
- [ ] Add Mojo unit tests and Python compatibility tests.
- [ ] Add cold-compilation and warm-execution benchmarks.

**Exit criteria:** All vector and compatibility tests pass; benchmark report is
reproducible from a clean checkout.

## Phase 3: First five verified ports

**Goal:** Demonstrate the process generalises beyond one library.

Candidates: `levenshtein`, `audioop`, `bitarray`, `resampy`.

- [ ] Establish a per-library checklist derived from the Msgpack work.
- [ ] Port each library to the same verification standard.
- [ ] Publish per-library compatibility and limitation notes.
- [ ] Publish comparable benchmark reports using the shared methodology.

**Exit criteria:** Five ports with green test suites, shared vectors, and
documented benchmarks.

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
