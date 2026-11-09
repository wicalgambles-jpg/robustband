# robustband 1.0.3 — local acceptance

Date: 2026-11-09. This release is prepared and tested locally using the user's
TestAgent 0.2.1 workflow. The AI testing role is part of development; its checks
do not constitute independent third-party or unfamiliar-human acceptance.

## Changes

- Drag one paired table or two single-model files into the local app for automatic
  validation and analysis. Import accepts CSV, TSV, JSON, JSONL/NDJSON, Excel XLSX
  and the official MMLU-Pro result ZIP layout. Complete-subject selection, strict
  pairing, missing-prediction policy and source omissions are visible. Download
  a ZIP containing the report, normalized input and import manifest. See the
  [file import guide](file_import.md) for schemas and limits.
- XLSX imports preserve ordinary rich text while excluding phonetic hints from
  cell values. Formulas and unsafe archive/XML layouts are rejected.
- Changing comparison settings hides the earlier import bundle. A new import
  clears the prior result before validation, including the first of two archives.
- JSONL treats LF/CRLF as record boundaries. Valid U+0085, U+2028 and U+2029
  characters inside strings survive ingestion, HTTP audits and CSV conversion.
- CLI audits check output paths before writing. `report.json` and `report.html`
  cannot replace the input table or an input policy, adoption plan or mapping.
- CLI conversion protects its mapping file even when `--overwrite` is requested.
  Select a separate destination to keep the conversion inputs available.
- Ranking preview diagnostics check grouping labels across every sample, including
  later samples with missing labels.
- Ranking HTML labels the hand-checkable nonnegative pair band `[0, 1]` as ahead,
  consistent with the browser; the interval still records the possibility of a tie.
- Exact-score JSON import uses decimal numbers without coercing numeric IDs,
  metric names, units or group labels into accepted strings. Large and tiny valid
  decimal score margins retain their exact values.
- A valid stop request sends its acknowledgement before allowing the UI process
  to exit, including the standalone executable. Disconnected clients still stop
  the session. The initially observed connection-reset failure is retained in
  the local TestAgent evidence.

Scoring parsers, metrics, aggregators, claims and exact arithmetic remain frozen.
Version-bound external/resource receipts are regenerated from the current source;
previous numbered release evidence remains available in history.

## Six quality characteristics

| Characteristic | Acceptance method | Limit |
|---|---|---|
| Functionality | Existing regression suite, hand-checkable Unicode examples, roundtrip/replay, CLI and actual HTTP paths | Declared protocols and supplied data |
| Reliability | Red/green defect regressions; input/config protection; malformed input, tamper and HTTP recovery tests | Individual file writes are atomic; a multi-file export is not a database transaction |
| Usability | Automatic import, source/scope warnings, seven automated browser flows and mobile-width checks | Unfamiliar-human completion/time remains unmeasured |
| Efficiency | Three fresh processes per default-protocol workload; OS peak resident memory; black-box workload ceiling 256 MiB | Synthetic 5,000 pairs or 500 × 8 model rows; not a worst-case bound |
| Maintainability | 100% package statement coverage, SPDX, frozen-source hashes and reviewed test oracles | Statement coverage does not measure assertion strength |
| Portability | Local Python 3.9/3.12/3.13, CRLF/LF, Unicode paths, wheel/sdist installs, Windows portable and optional CUDA preparation | Current Linux/macOS runs and Firefox/Safari not executed in this local-only release |

The TestAgent runner records actual commands, exit codes, fingerprints, logs and
JUnit outcomes in a new evidence directory. Failing reproductions are retained
alongside post-fix runs. A successful command is interpreted using the tool's
native test counts and assertions.

```bash
python submission/check_quality.py
python -S experiments/measure_resources.py
python experiments/validate_converters.py
python submission/verify_release.py
python submission/build_portable.py
python submission/verify_portable.py
```

The exact audit uses CPU arithmetic. Optional GPU validation compares actual CUDA
argmax/count preparation and NPZ conversion with CPU references; it is not an
inference-speed benchmark. Browser automation covers Chromium-based local flows.

No repository upload or remote CI execution is part of this release task.

## Executed local results

- Complete quality gate: 520 tests, zero failures/errors/skips; 2769/2769 package
  statements covered. Frozen scoring source identities match the existing record.
- Python 3.9: 520 tests passed. Python 3.13: the complete quality gate above.
- Seven Edge 148 browser variants: 122 checks, zero script exceptions, including
  actual file drops, result-bundle replay, sequential archive pairing, a complete
  official subject, mobile width, mismatched-cohort rejection, and agreement
  between browser and exported HTML for a zero-endpoint ranking band. The offline
  WELCOME page also passed its six preview checks.
- NPZ converter: 26 cases. Actual RTX 4060 CUDA preparation: three class-count
  cases. Standalone Windows acceptance: 27 checks, plus 20 fresh stop sessions.
- Fresh offline wheel and source-distribution installs pass outside the checkout.

The first final Python 3.9 run exposed a test synchronization race: the client
could read the stop acknowledgement before the server thread set its stop flag.
The test now requires that flag within one second, while separate tests still
require acknowledgement-before-exit ordering. The failed run is retained.

Three fresh-process measurements per workload on this Windows machine found:

| Workload | Load, audit and replay | Maximum observed peak RSS |
|---|---|---|
| 5,000 text pairs | 0.152–0.153 s | 28.9 MiB |
| 5,000 score pairs | 0.123–0.125 s | 26.8 MiB |
| 500 samples × eight models | 0.088–0.090 s | 25.3 MiB |

These measurements include input preparation in OS peak RSS and exclude process
startup from timing. They do not establish a worst-case resource bound.

## Official archived evaluation data

A protocol fixed before accuracy calculation selects the complete 410-item
computer-science subject from the official
[MMLU-Pro archived results](https://github.com/TIGER-AI-Lab/MMLU-Pro/tree/f418b116db00b065c2aea046518d8fcf74d39872/eval_results).
Meta-Llama-3-8B and Meta-Llama-3-8B-Instruct have identical IDs, questions, options
and reference answers on that subject. No records are dropped or joined silently.

Under the explicit rule “valid archived prediction letter equals the reference;
missing or out-of-range predictions count as incorrect,” independent integer
counts give 134/410 and 173/410. The exact A-minus-B margin is `-39/410`.
Text audit, numeric-score audit, ranking, adoption criteria, CSV/JSONL conversion,
CLI export/replay and tamper rejection agree with this independent oracle.
An initially considered 70B archive has a different subject cohort and is rejected.

The base archive has 39 missing predictions and one prediction outside its five
options; the instruct archive has 22 missing predictions. All are retained as
incorrect. This differs from the upstream script's random fallback for missing
predictions, so these are deterministic archive-audit results, not claimed official
leaderboard accuracies. Full generated answers and original ZIPs are retained in
the separate local evidence directory; the test uses archived extracted letters.

The built Windows executable also imported the two original ZIPs through its
actual HTTP interface with system-only PATH: 410 items, counts 134 and 173,
exact band `[-39/410, -39/410]`, and verified result-bundle replay. One local run
took 2.68 seconds for the import request and peaked at 158.1 MiB server RSS.
This is a single measured archive workload, not a general memory or latency bound.
