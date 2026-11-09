# Changelog

All notable changes to `robustband` are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.3] - 2026-11-09

- Preserve Unicode NEL, line separator and paragraph separator characters inside
  JSONL strings; only LF/CRLF delimit records. CSV-to-JSONL roundtrips retain them.
- Reject CLI report destinations that would overwrite their input, policy, plan
  or mapping files before writing any report.
- Protect conversion mapping files from output/manifest collisions, including
  explicit overwrite requests.
- Check ranking preview grouping completeness across every sample; correct HTML
  direction labels for nonnegative bands with a zero lower endpoint.
- Preserve JSON number types when importing exact scores: decimal scores stay
  exact, while floating IDs and numeric text/group metadata are rejected.
- Build editable edition instructions using the current version's release notes.
- Record TestAgent-guided local acceptance and explicit platform/usability gaps.
- Finish the authenticated stop acknowledgement before setting the UI exit flag;
  still honor a valid stop request when the reply connection has disconnected.

## [1.0.2] - 2026-11-04

- Fix R48: paired-text audits reject unknown CSV columns and JSONL keys at the
  Python, CLI and local HTTP entry points, with actionable field names.
- Keep explicit column omission in the converter, recorded in its manifest and
  checked by canonical reload; optional class and length grouping fields remain supported.
- Add regression checks for rejection, output protection and explicit conversion.
- Add repeatable fresh-process timing and OS peak resident-memory measurements.
- Organize release acceptance by six software quality characteristics, retaining
  unmeasured human usability and browser/platform limitations as open evidence gaps.
- Rename the public repository to `robustband` and the private development
  repository to `robustband-dev`; update active links and CI artifact versions.
- Preserve the frozen scoring algorithms and previous release evidence.
- Pin the test matrix to Ubuntu 24.04 for Python 3.9 availability; stage CI
  receipts only after successful execution, excluding committed fallback receipts.

## [1.0.1] - 2026-10-22

- Fix FR-01: resource-grid v2 records `bytes_lf` and `sha256_lf` from identical
  normalized bytes; LF and CRLF inputs reproduce the same complete receipt/hash.
- Add a real-input LF/CRLF comparison and a same-length-content-change regression.
- Run the actual `check_quality.py` release gate in every OS/Python CI test job,
  retaining resource/quality receipts and logs.
- Write active release receipts as UTF-8/LF through atomic replacement.
- Document the frozen `exact_match` numeric tolerance and scope historical timing
  figures by their date/environment. Numerical scoring semantics are unchanged.
- Preserve 1.0.0 history and document its resource-replay verification gap.
- Validate both frozen float-sum certificate profiles across Python versions;
  allow only the two named Windows launcher skips on Linux/macOS.

## [1.0.0] - 2026-10-21

- Validated CSV/JSONL conversion for paired text, numeric scores, confusion counts
  and ranking tables, with exact reload checks, explicit omissions and manifests.
- NPZ source protection, void-label handling, archive/header/allocation budgets,
  strict pairing and reference equality; 26 synthetic acceptance scenarios.
- Bounded local HTTP workers, authentication before upload, strict JSON/request
  framing, read timeouts and recovery from saturated or disconnected clients.
- Individual atomic report/output writes preserve existing files on staging errors.
- Consistent browser polish, collapsible adoption stages, keyboard editing,
  standard-data downloads and session controls.
- Windows portable executable requiring no Python installation, with focused and
  generalized launchers; source adapters remain editable in source bundles.
- Actual CUDA/CPU interoperability validation on RTX 4060 Laptop (2/8/64 classes).
- 390 regression tests, full package statement coverage, six browser variants,
  portable acceptance and fresh offline package installs.
- Clean public source history, security/support guidance and explicit evidence
  categories for future user trials.

## [0.9.0] - 2026-10-21

### Added
- Fragility-resource prototype (`experiments/resource_grid.py`): scores archived per-item
  outputs under the frozen family (raw output: 80 protocols; recorded scores: metric
  variants x mean/median), with exact rational bands, pair bands, per-protocol leaders and
  the pre-registered gates R-B1..R-B5. `--verify` recomputes the grid from the manifest and
  file hashes. The shipped archive is small, so the scale and flip gates fail by design.

### Fixed
- Windows launchers no longer trust a bare `python` on PATH. A shared detector
  (`_detect_python.cmd`) tries `ROBUSTBAND_PYTHON`, a project `.venv`, `python`, `py -3`
  and the default install folders; a candidate is accepted only if it runs Python 3.9 or
  newer, and a failure prints installation guidance instead of closing the window. This
  matters on machines where the Microsoft Store alias resolves `python` to a placeholder
  that exits with code 9009.
- `check_quality.py` records command paths relative to the repository, so its receipts no
  longer contain the maintainer's local absolute paths; the 0.8.0 receipt is redacted.

### Documentation
- Shared documentation keeps purpose, method, measured results and limits.
- `docs/github_deployment.md` is now release mechanics only, without internal venue or
  readiness assessments. `docs/resource_grid.md` corrects the small-sample explanation:
  each of 10 items is 0.1 of the score, and one protocol choice can span the 0..1 range.

## [0.8.0] - 2026-10-20

### Added
- Ranking audit for more than two models (`python -m robustband matrix`): one long table
  (`sample_id, model, gold, output`), exact per-protocol ranks on one shared sample set,
  pair ranges labelled ahead / behind / ties / flips, and a `verify`-able
  `robustband.matrix_audit/v1` report with a standalone HTML view. Verdicts separate a
  stable ranking (`STABLE`), a stable leader with a moving order (`LEADER-STABLE`) and a
  rule-dependent leader (`SENSITIVE`); `--require-stable` is a CI gate.
- A `/matrix` page in the local app (linked as **Ranking audit** from the comparison and
  adoption pages): upload or drag a long table, preview the shared samples, choose
  protocols and download the readable report or the replay JSON. Its browser smoke
  (`experiments/matrix_browser_smoke.cjs`) runs in CI next to the adoption smoke.

### Changed
- Reports share one visual layer (`report_style`): the app's palette and type scale, a
  brand header, verdict badge, stat strip, witness table, print rules and an inline SVG
  rule-range figure that keeps zero visible for one-sided and all-zero bands. Audit and
  adoption reports both use it; the audit report is now bilingual.
- The generic engine prepares each parse result and item correctness once per family
  instead of once per protocol. On 5,000 items under all 80 protocols, `evaluate` drops
  from 3.0 s to 0.5 s for two models and from 11.0 s to 0.8 s for three models (single
  core, Python 3.13). Aggregated scores, margins and verdicts are unchanged: a regression
  test compares the cached table against a per-protocol reference.
- The local server is threaded, so one slow audit no longer blocks the page's other
  requests. Non-UTF-8 input fails with the byte offset and a "save as UTF-8" repair, CSV
  errors name the line, and every 4 MiB / 5,000-row ceiling points at splitting the file
  or the Python API.
- Release gates read the version from the package: `check_quality.py` records the newest
  frozen scoring-semantics revision (`experiments/scoring_semantics_0.8.0.json` documents
  the caching-only change), `verify_release.py` builds the current version's wheel and now
  checks the ranking CLI and page, and `external_cases.py` writes its version-named record.

### Fixed
- `matrix.html` is declared as package data; previously an installed wheel answered
  `/matrix` with "Unknown local route".
- Dead code and unused imports removed; pyflakes is clean across the repository.

### Documentation
- README states the supported main workflow (paired audit → adoption check → ranking
  audit) and marks the review planner / compiled snapshots as experimental; the edition
  history records 0.8.0.

## [0.7.0] - 2026-10-19

### Added
- Adoption checks with one primary objective and optional guardrails. Each target
  declares its own protocols, exact threshold, strict/inclusive boundary and
  rationale; metrics and units remain separate.
- A guided local decision page for text, segmentation and numeric data, explicit
  wide-column mapping, saved/reusable criteria and source-bound JSON/HTML reports.
- Frozen numeric criteria bind metric names, units and preferred directions.
  Selected targets require identical sample ID sets and group labels.
- `decision-template` and `decision --require-pass` commands, an example CI gate,
  target endpoint explanations and objective-tradeoff reporting.
- Deterministic threshold, import and replay checks; browser trials; an independent
  pilot protocol with proposed acceptance targets and a research experiment plan.

### Preserved
- The original scoring functions, default 80-protocol library family, professional
  text-only profile, generalized adapter registry and prior immutable releases.

## [0.6.1] - 2026-10-19

### Changed
- Lead the local interface with the comparison's purpose, data-kind cards and a
  one-click example. Put algorithm controls and exact diagnostics behind details.
- Explain verdicts in plain language, label example versus uploaded data, show
  the endpoint rules and provide a direct transition to the user's own file.
- Add drag-and-drop, matching templates, file preparation guidance and actionable
  error messages. Keep professional/generalized profiles and exact replay intact.

### Added
- `WELCOME.html`: a standalone example page generated from the real UI and exact
  synthetic reports. It requires no Python/server/network for the saved examples;
  instructions explain how to start the local app for new calculations.
- Browser checks for the first-use flow, keyboard help, drag-and-drop, no-install
  examples, preview restrictions and setup instructions.
- Scoring implementations and numerical readings remain unchanged; current
  version-bound reports and certificates are regenerated for 0.6.1.

## [0.6.0] - 2026-10-13

### Added
- Professional and generalized profiles, separate Windows launchers and an
  editable general-domain adapter demonstrating algorithms, exact parameters
  and source-bound replay. Preserve the 0.5.0 AI evaluation baseline.
- Explicit domain adapters and a shared exact audit engine; schema-based replay
  dispatch and common `domains`, `run`, domain `demo` and `template` commands.
- Segmentation confusion-count audits with fixed class targets, count/image/group
  aggregation, explicit empty-class policies and per-class diagnostics.
- Recorded scalar audits with lossless decimal ingestion, explicit metric/unit/
  direction, mean/median/group policies and oriented margins for lower-is-better
  measurements. Percent score differences display in percentage points.
- An optional NumPy preprocessing helper for strictly paired cached prediction/
  label arrays. No runtime dependency is added to the package.
- Domain-driven browser controls, templates, preview columns and report sections;
  exact JSON exports preserve integer counts above the JavaScript safe range.

### Changed
- Text, confusion and scalar workflows reuse exact decisions, source-bound
  envelopes, HTML export and transport. Displayed decimals/plots are rounded;
  exact rational values determine all verdicts and remain in replay JSON.
- Separate measurement targets instead of mixing overall and rare-class scores
  in one band. Source-bound artifacts are regenerated for this version; the frozen
  text scoring sources, default 80 protocols and historical numerical readings
  remain unchanged. Local domain trials are not independent user evidence.

## [0.5.0] - 2026-10-13

### Added
- A local English/Chinese browser interface: run a hand-checkable example, upload
  paired CSV/JSONL, preview records, declare policies and inspect exact results.
- Installed `robustband` and `python -m robustband` commands for `ui`, `demo`,
  `template`, `audit` and `verify`; a Windows source-folder launcher.
- Shared paired-input validation: required fields, unique sample IDs, explicit
  group labels and bounded interactive uploads. Empty model outputs are retained.
- Self-contained replay JSON and escaped offline HTML summaries, with exact
  endpoints, endpoint protocols, full policy scores, ties and all-zero diagnostics.
- Optional offline browser smoke checks covering real uploads, exports, desktop/
  narrow layout, language switching and result invalidation.

### Changed
- Put the first-use workflow before implementation details in the README. Add
  concrete terminal and AI-assisted instructions, input examples and report scope.
- Replace local-drive hyperlinks in the mathematical follow-up with named local
  provenance notes. The software's proofs are self-contained.
- Extend distribution checks to the installed command entry points, UI asset
  and replay workflow. Runtime dependencies remain empty; the frozen library
  scoring sources, default 80-policy family and historical readings are unchanged.
- New UI/CLI workflows start with the explicitly selected two-policy example
  family. Policy applicability remains a user decision.

## [0.4.1] - 2026-10-13

### Changed
- Rewrite the project landing page around software functionality, appropriate
  usage, related work and specific evidence limits. Remove internal evaluation
  labels, prestige classifications and publication targets from the landing page.
- Apply neutral wording to the related-work document and record the shared
  documentation convention in the contributor guide.
- Update package metadata, version-bound verification paths and review artifacts
  for the documentation patch. The default 80 scoring protocols and numerical
  readings are unchanged; earlier 0.4.0 experiment reports retain their provenance.

## [0.4.0] (2026-10-12)

### GitHub deployment (2026-10-13)
- Authenticated private repository access and deployment branch/PR are established.
  The README-only initialization history is connected to the verified research history.
- Executed remote CI passes all nine OS/Python jobs and Linux wheel/source
  installation verification. CI archives verified distributions and offline API docs.
- Documentation distinguishes deployment evidence from independent user adoption.

### Added
- Strict `EvalScopeAdapter` for paired review JSONL, preserving raw predictions
  and exact recorded scores while rejecting identity/context/schema drift.
- Offline integration audits of pinned GSM8K and IFEval ten-pair public samples;
  both exact strict-comparison bands are [-1/10, 0]. No new inference, independent
  IFEval grading, external adoption or human-review savings is claimed.
- Local wheel/source packaging checks and an evidence index.

- Shared-price review `ReviewProblem.plan_refined`: shared target-price guidance,
  exact integer surrogate bounds and independently checkable rational lower-bound
  certificates. Float guidance does not determine feasibility or proof validity.
- `lower_bound_certificate` / `verify_lower_bound`: optimizer-free weak-duality
  checks with problem/target/domain identity and reviewed values bound into artifacts.
- A frozen 60-case development / 210-case held-out-plus-regression comparison.
  On 48 fresh dense cases, certified minima increase 38 to 46; search nodes fall
  75.45%, planning time falls 15.59%, and review count falls 0.455%. Root certificates
  prove 38 minima without search. All 48 counts match external numerical optimization.
  Grouped and tiny planning are slower; actual human-review savings are unmeasured.
- Experimental `review` module: exact finite-record completion bounds under explicit
  per-item domains and linear targets, unit-cost width planning, target-conflict
  certificates, and rejection of out-of-domain reviews.
- Experimental `compiled.CompiledScores`: immutable item-scoring snapshots that reuse
  parsing/metrics while recomputing aggregators on each paired bootstrap sample.
- Frozen exploratory comparison protocols, reproducible results, a review template,
  and a primary-source novelty audit. Candidate integration is not a methodology novelty claim.
- `ReviewProblem.plan_optimized`: exact integer scaling, feasible packing portfolio,
  bounded one-for-two exchanges, pooled-target lower bounds and grouped search with
  a deterministic node budget. Reports a valid optimality gap on cutoff; review
  count never exceeds legacy greedy under the same objective.
- Frozen development/held-out optimization comparison and optional HiGHS cross-check.
  Held-out dense cases: 23/36 use fewer reviews; 29/36 certified minima versus 1/36
  legacy; 33/36 match the external solver. Grouped planning is 7.97x faster locally
  with equal counts. Dense search is 3.01x slower; real review counts remain unchanged.

### Changed
- Version 0.4.0 includes the earlier experimental cache/review features below.
  Scoring semantics and the frozen default family of 80 protocols are unchanged.
  Version-bound artifacts are regenerated and independently verified.
- Current candidate: 106 tests, 100% statement coverage (815/815).
  Historical experiment reports retain their frozen provenance and timing logs.

- The research example defaults to `--planner refined`, with explicit `optimized`
  and `legacy` options and a configurable pricing budget. The experiment records its public source identities.
- Math transfer tests total 79, with 100% statement coverage (748/748).
- The earlier review-budget example defaulted to the optimized planner; `--planner
  legacy` reproduces the first prototype. Search and exchange budgets are configurable.
- The earlier review-budget stage had 72 tests and 100% statement coverage (619/619).
- Certificate generation, verification and Gate-1 bootstrap loops use compiled snapshots.
  A 2,000-resample equivalence benchmark checks every serialized Band field against
  the existing raw-text scorer. No scoring registry or released protocol semantic is changed.
- Corrected the quickstart's full-family stability proportion and the statement about
  externally observed decision changes.
- Replaying Gate-1 also fixes two stale single-axis artifact verdicts from the pre-0.3.0
  zero-boundary rule: metric-only and aggregation-only results are `REFUTED` under
  the already-released strict-claim semantics. Margins and bootstrap readings are unchanged.

## [0.3.1] — 2026-10-08

### Added
- `tests/test_edges.py` — edge-branch tests: blank-only parses, `\boxed{}` extraction and
  fallback to last-number, numerically equal but textually different answers, empty-side
  F1, macro aggregation without a meta key, certificates with empty margins, empty-sample
  exact rationals, empty-family rejection, the adapter base class, and blank-line skipping
  in the JSONL adapter.
- `coverage` in the `dev` extra plus `[tool.coverage]` configuration; CI now measures and
  reports coverage on every platform and Python version.

### Notes
- **No library code change.** Test count 28 → 38; `robustband` statement coverage
  **96% → 100% (298/298)**.
- Every reported band, verdict, certificate value and the frozen protocol pre-registration
  is unchanged; `demo/verify_tooling_certificate.py` still prints `[VERIFY PASS]`.

## [0.3.0] — 2026-10-01

### Fixed
- Numeric answer comparison now uses exact decimal rational values; large distinct integers
  no longer collapse to the same binary float.
- A strict rank claim tied under every configuration is `REFUTED`, and a tie-versus-win
  certificate no longer claims a strict sign reversal.
- The v2 tooling certificate binds all four input files by SHA-256. Its verifier checks
  the 1319-item score band, every leave-one result, the duplication rows, and the final
  `overall` decision. Hashes normalize CRLF to LF across platforms. The full-scale
  output file is included with the repository.
- Reworded replication and bootstrap conclusions to distinguish repeated observations
  from new independent items. All 80 built-in configurations now have exact item decisions.

## [0.2.0] — 2026-10-01

### Added
- `robustband.rational` — **exact-rational certified band**:
  - `rational_band(better_items, worse_items, family=None)` → `{rows, lo, hi, lo_c, hi_c, n_certain, n_configs}`
    with `Fraction` endpoints (bit-exact), a **borderline fence** (`CERTAIN` / `BORDERLINE`
    per configuration), and a **strict envelope** over the `CERTAIN` subset.
  - `duplication_invariance(...)` — item-replication certificate (endpoints bit-identical
    under `k`-fold replication ⟹ the band is not a finite-sample artifact).
  - `score_frac(...)`, `item_correct_and_certain(...)`, `frac_to_json(...)`.
- Both `certificate` and `rational` are exported from the top-level package.

### Changed
- The float `delta` reported by `core.evaluate` is guaranteed to agree with the exact
  rational endpoint to `≤1e-12` (added as a frozen certificate contract).

## [0.1.0] — 2026-10-01

### Added
- Core engine: `Perturbation`, `build_family`, `score_table`, `evaluate`, `Band`.
- A-tier scoring family `ℋ` = `parse(5) × metric(4) × agg(4)` = **80 configurations**.
- Claims: `RankClaim` (`A > B`) and `ScoreClaim` (`A > τ`).
- Verdicts: `UNIDENTIFIABLE` / `ROBUST` / `FRAGILE` / `REFUTED`.
- E negative module (`certificate`): `impossibility_certificate`,
  `minimal_counterexample`, `emit`.
- Adapters: `BenchmarkAdapter`, `JSONLAdapter`, `InMemoryAdapter`.
- **Zero runtime dependencies** (standard library only).
