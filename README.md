# robustband — see whether scoring rules change your comparison

**Maintainer:** Zengzhao Gao (Harbin Engineering University, China) — wicalgambles@gmail.com
· ORCID [0009-0007-9138-4642](https://orcid.org/0009-0007-9138-4642)
· **License:** MIT · **Version:** 1.0.3 · **Zero runtime dependencies** · Python ≥ 3.9

**1.0.3:** drag in evaluation files for automatic import and analysis. Editable
source editions and a Windows portable bundle are available from
[Releases](https://github.com/wicalgambles-jpg/robustband/releases).
See the [acceptance notes](docs/release_1.0.3.md) for executed checks and limits.

`robustband` compares two sets of results on the same samples across scoring
rules you choose. It shows **who leads, the margin range, and whether the conclusion
changes with the rule**. Use it for archived AI answers, segmentation counts or
recorded metrics such as latency and accuracy.

**中文速览**：把同一批样本的两组已有结果放在一起，看看谁领先、领先多少，以及换一种
评分方式是否会改变结论。支持 AI 答案、分割计数和已有数值指标。

**Main workflow / 主线**：paired audit（两组比较）→ adoption check（采用条件）→
ranking audit（多模型名次）。**Experimental / 实验区**（不属于主线，证据为合成或冻结
样本）：human-review planning（`robustband.review`）、compiled-score snapshots
（`robustband.compiled`）与 [docs/review_mechanism.md](docs/review_mechanism.md) 中的
研究问题。

## Try an example without installing anything

Download and extract a source bundle, then **open [WELCOME.html](WELCOME.html)**
in your browser. Choose a data card and click **Run example**. It shows an exact,
precomputed example using the same interface as the app, with no Python, account,
server or network request needed for that preview.

## Compare your own results

**Windows, no Python installation:** download the **Windows portable ZIP** from
[Releases](https://github.com/wicalgambles-jpg/robustband/releases/latest),
extract the entire folder, and double-click `start_generalized.cmd` or
`start_professional.cmd`. Keep `_internal` beside the executable. Source bundles
remain available for editable adapters and optional NPZ preprocessing.

1. With Python ≥ 3.9 installed, double-click `start_professional.cmd` for AI text
   evaluation, or `start_generalized.cmd` for domain measurements and editable
   modules. You can also run `python -m robustband ui` from the source folder.
2. Drop one paired file or two single-model files onto the page. CSV, TSV, JSON,
   JSONL/NDJSON, Excel XLSX and official MMLU-Pro result ZIPs are supported.
   Recognized inputs are validated and analyzed automatically.
3. Check the sample count, source details, subject and scoring rules. Save the
   complete result bundle, or change rules and recalculate the comparison.
   See the [file import guide](docs/file_import.md) for schemas and limits.

Results lead with a plain-language conclusion and show which rules produced the
two endpoints. Example data is labeled; file errors explain the next repair step.
The interface supports English and Chinese and processes your files locally.

The text entry points start with the example's **two explicitly selected protocols**
(`first_num` / `last_num`, `exact_match`, `micro`). Select policies appropriate to
your own task. The library's default family remains **80 configurations**.
Both outputs belong to the same record in the new paired format; duplicate IDs,
missing fields, unknown extra fields and incomplete selected group labels are rejected.
For intentional extra columns, use the [explicit conversion workflow](docs/file_import.md#input-contract-change)
and inspect its omission manifest before auditing.

For terminal use and AI-assisted automation:

```bash
python -m robustband demo --output audit-demo
python -m robustband verify audit-demo/report.json
python -m robustband template paired.csv
python -m robustband audit paired.csv --output audit-results
```

Follow the [first-use guide](docs/getting_started.md) for input examples, installation,
protocol selection, report sharing and the AI-assistant instructions. These entry
points audit archived paired outputs; they do not generate model responses or labels.

## Check a candidate against adoption criteria

Click **Adoption check** in the local app to declare one primary benefit and
optional guardrails. Import paired results, map your numeric columns if needed,
set exact thresholds, save the criteria and inspect separate target evidence.
A primary gain alongside a failing guardrail is reported as an objective tradeoff.

```bash
python -m robustband decision-template audit-demo/decision-input
python -m robustband decision audit-demo/decision-input/paired.csv --plan audit-demo/decision-input/plan.json --mapping audit-demo/decision-input/mapping.json --output audit-results/decision --require-pass
python -m robustband verify audit-results/decision/report.json
```

The synthetic example fails its declared guardrail, so `--require-pass` returns
1. See [the decision workflow](docs/decision_workflow.md) for units, boundary rules,
input alignment, criteria reuse and the CI example. Protocol ranges describe
supplied data and selected rules; they are not confidence intervals.

## Rank more than two models

A paired audit answers "does A beat B?"; a leaderboard asks whether the *order* survives
the rules. The ranking audit reads one long table (`sample_id, model, gold, output`, plus
optional `prompt`, `class` and `len_bucket`), scores every model under every declared
protocol and ranks them per protocol:

```bash
python -m robustband matrix models.csv --parse strict_exact first_num last_num \
  --metric exact_match --agg micro --output ranking
python -m robustband verify ranking/report.json
python -m robustband matrix models.csv --output ranking --require-stable   # gate
```

Each model must cover exactly the same sample ids with the same reference answer; a
missing row, a different `gold` or a conflicting group label is rejected. One audit reads
at most 5,000 measurement rows and 8 models. The report separates three outcomes:
`STABLE` (identical ranking under every protocol), `LEADER-STABLE` (the leader is stable,
the order below it moves) and `SENSITIVE` (which model leads depends on the protocol). It
lists every pair as ahead / behind / ties / flips with its exact range, and each model's
best and worst rank. The same check is in the local app: **Ranking audit** in the header
opens the `/matrix` page, which previews the table, lets you pick protocols and downloads
the readable report or the replay JSON.

## Two editions

| Edition | Start | Purpose |
| --- | --- | --- |
| Professional | `python -m robustband ui --edition professional` or `start_professional.cmd` | Original AI text evaluation and exact scoring workflows |
| Generalized | `start_generalized.cmd` or `python -m robustband ui --edition generalized` | Domain adapters, algorithm choices and parameters |

Both use the same exact core. The professional profile provides the original
text evaluator; the generalized source launcher also includes an editable
measurement lab with aggregation algorithms, trimming parameters and a strict
advantage threshold. See [edition operations and adaptation](docs/editions.md).
The original 0.5.0 release is retained as an archived baseline.

## Domain applications

Version 1.0.3 provides three adapters through the same browser, report and replay
workflow. Choose a data card, download its template and declare the target:

| Domain | Input | What is audited |
| --- | --- | --- |
| Text answers | Paired CSV/JSONL with raw outputs and references | Extraction, correctness and aggregation choices |
| Segmentation | Paired integer confusion matrices in JSONL | Class target, count/image/group aggregation and undefined class handling |
| Recorded metrics | Paired decimal scores in CSV/JSONL | Mean/median/group choices for one explicit metric, unit and direction |

```bash
python -m robustband domains
python -m robustband demo --domain scores --output audit-demo/scores
python -m robustband template counts.jsonl --domain segmentation
python -m robustband segment counts.jsonl --classes 1 --output audit-results
```

Lower-is-better measurements, such as latency or error, use oriented margins:
positive always supports the declared preference for A. Overall mIoU and a rare
class, or accuracy and latency, are separate targets with separate reports.
See [domain inputs and extension contracts](docs/domains.md) for formats,
preprocessing and adding a trusted adapter. Browser controls and common report
sections are generated from module descriptors. This extension preserves the
original text scoring library's default 80 protocols.

## The problem

Leaderboards report a single number per model per benchmark. That number is produced
by a pipeline of declared scoring choices — how the answer is extracted from the
model's raw output (`parse`), how a candidate is judged correct (`metric`), and how
per-item correctness is aggregated (`agg`). Different choices can give
different numbers, and can reverse the *order* of two models. The reported score is
therefore a **point sample** of a **band**.

`robustband` makes that band explicit and certifiable.

## The idea

Freeze an explicit family of scoring protocols

```
ℋ = parse × metric × agg
  parse  ∈ {strict_exact, first_num, last_num, last_line_num, boxed}      (5)
  metric ∈ {exact_match, contains, f1_token, numeric_tol}                 (4)
  agg    ∈ {micro, macro_class, macro_len, median}                        (4)
```

⟹ **80 configurations** (the default scoring family: no generation).
Whether each configuration is defensible for a particular benchmark must be assessed
before interpreting the resulting band.

For a claim `K` (a rank claim `A > B`, or a score claim `A > τ`), evaluate the claim's
**margin** under every configuration. Then:

| output | meaning |
|---|---|
| `delta = (min margin, max margin)` | the **band** of the effect across legal protocols |
| `verdict = UNIDENTIFIABLE` | `min ≤ 0 < max`: some configurations support a strict claim and others do not |
| `stability_fraction` | fraction of the enumerated protocols under which the claim holds; not a probability over protocols |
| `break_set` | configurations where the strict claim fails, including ties |
| `certificate` | conditional witness certificate and counterexamples when applicable |

**Replication rule:** repeating the *same* items leaves the band unchanged. This is
an algebraic check on the aggregation code. New independent items can change the band.

## Install

```bash
python -m pip install -e .        # editable, from the repo root
# Or install the downloaded release wheel offline:
python -m pip install --no-index --no-deps robustband-1.0.3-py3-none-any.whl
```

After installation, `robustband ui` and `python -m robustband ui` are equivalent.
Source-checkout use of `python -m robustband` requires no installation. A PyPI
publication is not currently part of the installation instructions.

**Zero runtime dependencies.** Pure standard library (`re`, `statistics`, `itertools`,
`dataclasses`, `json`, `pathlib`, `fractions`). Python ≥ 3.9.
For the test suite only: `pip install -e ".[dev]"`.

> **Offline / air-gapped install.** The build backend is `setuptools` (PEP 621). By default
> pip builds in an isolated environment and fetches `setuptools` from the index; on a machine
> with a restricted network, add `--no-build-isolation` to use the already-installed
> setuptools (≥ 77, which PEP 639 license expressions require):
> ```bash
> pip install -e . --no-build-isolation    # uses the local setuptools; fully offline
> ```
> Runtime audits and report replay use no network services. Build isolation can
> download development build tools; installing a supplied wheel with the command
> above avoids that build step.

## Quickstart

```python
import robustband as rb

# preds = {model: {"items": [(raw_output, gold, meta), ...]}}
preds = {
    "cot":   {"items": [("the answer is 7 but really 42", "42", {})]},
    "plain": {"items": [("42 no wait 7",                 "42", {})]},
}

family = rb.build_family()                    # the default 80-config scoring family
claim  = rb.RankClaim("cot", "plain")         # the claim: cot beats plain

band = rb.evaluate(preds, family, claim)
print(band.verdict)              # UNIDENTIFIABLE
print(band.delta)               # (-1.0, 1.0)  -> the band contains 0
print(band.stability_fraction)  # 0.6 (full 80-config family)

cert = rb.certificate.emit(preds, family, claim, band)
print(cert["type"])             # impossibility_certificate
print(cert["witness_negative"]) # a protocol under which cot LOSES
```

### Exact rational band (certified endpoints)

```python
from fractions import Fraction
cot_items, plain_items = preds["cot"]["items"], preds["plain"]["items"]

r = rb.rational.rational_band(cot_items, plain_items, family)
print(r["lo"], r["hi"])                     # -1  1   (Fractions, not floats)
print(float(r["lo"]))                       # -1.0 (matches engine.delta to <=1e-12)

base, reps = rb.rational.duplication_invariance(cot_items, plain_items, ks=(1, 2, 4, 8))
print(all(x["same"] for x in reps))         # True -> endpoints bit-identical under data x k
```

The endpoints agree with the float engine (`≤1e-12`) and are **invariant under item
replication**. Numeric comparisons use exact finite decimal arithmetic. The frozen
`exact_match` rule accepts normalized text equality or a numeric difference of at
most `1e-9`; `numeric_tol` uses its declared tolerance (default `1e-3`). Reported
`Fraction` endpoints aggregate exactly. See [metric semantics](docs/metric_semantics.md).

## The certificate (four bound layers)

`demo/tooling_certificate.py` emits a single machine-readable JSON artifact
(`results/tooling_certificate.json`, schema `robustband.tooling_certificate/v3`) that
binds four layers:

| layer | content |
|---|---|
| **L1** positive band | the δ-band, verdict, witnesses (C′ instrument output) |
| **L2** negative module (E) | impossibility certificate + minimal counterexample + strongest counterexample + decision hooks D1/D2/D3 |
| **L3** robustness | full-scale score band + paired bootstrap (`P(UNIDENTIFIABLE)`, `P(sign-flip)`) + leave-one-axis subfamilies |
| **L4** certified endpoints | exact-`Fraction` band over the built-in metrics, duplication invariance |

The certificate is **recomputed from hashed input files** (V-source, V0–V8) by
`demo/verify_tooling_certificate.py`, which does **not** trust the artifact's own numbers —
it checks every layer, including the 1319-item score band. The main score band is also
checked with a separate reference implementation; bootstrap checks still share the engine.
Input hashes normalize CRLF to LF so the same text verifies on Windows and Unix.
Schema v3 records the floating summation profile: Python 3.9/3.11 use the
sequential snapshot `results/tooling_certificate_sequential.json`; Python 3.12+
uses the compensated snapshot `results/tooling_certificate.json`. The verifier
detects the sum behavior and strictly replays the corresponding frozen artifact.
Near-zero bootstrap margins differ between these profiles; see
[the 1.0.3 evidence](docs/release_1.0.3.md). Exact rational endpoints are checked
separately.
The repository ships the frozen model outputs for rescoring; it does not currently pin
the model revision and full generation environment needed to reproduce those outputs.
Dataset and model attribution is recorded in `THIRD_PARTY_NOTICES.md`.

```bash
cd demo
python tooling_certificate.py          # writes the runtime's matching certificate
python verify_tooling_certificate.py   # re-derives V-source and V0..V8; prints [VERIFY PASS] (exit 0)
```

## Tests

```bash
python -m pytest          # deterministic synthetic fixtures and numerical edge cases
```

The suite covers the engine (family size, δ-band, verdicts), the exact-rational band
(endpoints, `Fraction` exactness, duplication invariance), the E negative module
(impossibility / minimal counterexample / `emit`), the adapters (in-memory, JSONL), and
the edge branches (blank-only parses, `\boxed{}` extraction and fallback, numerically
equal strings, empty-side F1, macro aggregation without a meta key, empty margins,
empty family rejection).

**Release checks.** See the [1.0.3 evaluation](docs/release_1.0.3.md) and
version-bound receipts in `results/` for executed test and coverage totals. These include paired-input
validation, report replay, command exits, ranking audits and actual local HTTP requests. Two
automated browser checks drive the app in headless Chromium (Node ≥ 22): one for the
[adoption flow](experiments/decision_browser_smoke.cjs) and one for the
[ranking page](experiments/matrix_browser_smoke.cjs). They write receipts under `results/`
and run in CI on Linux; they are not independent user evidence. Review planning and compiled
scoring remain experimental APIs.

```bash
python -m coverage run -m pytest && python -m coverage report -m --fail-under=100
```

## Documentation and examples

| what | where |
|---|---|
| browser interface, paired input and terminal/AI workflows | [`docs/getting_started.md`](docs/getting_started.md) |
| step-by-step tutorial (synthetic → your data → certificate → CI gate) | [`TUTORIAL.md`](TUTORIAL.md) |
| runnable CI-gate example (`--strict` exits 1 on a non-identifiable claim) | [`examples/band_gate.py`](examples/band_gate.py) |
| offline API reference (stdlib builder; included in CI distribution artifacts) | [`docs/build_api_docs.py`](docs/build_api_docs.py); open the generated `docs/api/index.html` |
| how to contribute (invariants, coverage gate, release steps) | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| reproducible numerical examples | `demo/` + `results/` (see *Reproduce*) |

Parsers, metrics and aggregators are registered in three dictionaries (`rb.PARSE`,
`rb.METRIC`, `rb.AGG`); `rb.build_family()` enumerates whatever is registered, so pass
explicit axis lists whenever you report numbers — see [`TUTORIAL.md`](TUTORIAL.md) §8.

## Scope and related work

`robustband` audits benchmarking claims over explicitly declared scoring protocols.
Specification curve analysis and item-level harness-sensitivity studies examine
related questions. The [related-work review](docs/review_mechanism.md) records
their objectives and how they connect to this implementation.

The package combines exact numeric judgments, claim witnesses, cached resampling,
strict paired-record import and finite-record review certificates. Select scoring
policies and target weights appropriate to your application before interpreting
the reported band. Degenerate all-zero scorers are diagnostics of the selected
policy; they do not validate a benchmark or establish a useful model comparison.

The [GitHub CI](https://github.com/wicalgambles-jpg/robustband/actions)
checks nine OS/Python combinations and isolated distribution installs.
[Deployment and release instructions](docs/github_deployment.md) describe the
downloadable artifacts and offline documentation. Independent user outcomes and
human-review domain coverage have not yet been measured.

## Experimental mechanisms (not part of the main workflow)

These capabilities are reported as research results with synthetic or frozen evidence. They
are not needed for the paired, adoption or ranking audits above, no external adoption is
claimed for them, and the review planner has no measured human-label saving on real data.

- **Fragility resource prototype** (`experiments/resource_grid.py`): scores an archive of
  per-item outputs under the protocol family and records per-model bands, pair bands and
  per-protocol leaders, with `--verify`. The archive shipped here is small, so the scale and
  ranking-flip gates **fail by design**; [the resource note](docs/resource_grid.md) records
  the measured numbers and what a grid at publication scale requires.

The [related-work and mechanism documentation](docs/review_mechanism.md) explain
two candidate capabilities built on established algorithms:

- `robustband.review`: separate linear target weights from item-scoring ambiguity,
  plan unit-cost reviews with an exact residual-width guarantee, and identify target
  conflicts that further item review cannot reconcile. Default domains allow every
  binary-score difference; narrower candidate domains are explicitly conditional.
- `robustband.compiled.CompiledScores`: snapshot parsing and item scores once,
  then reuse them for paired resampling with the existing aggregators. The archived
  2026-10-12 measurement (Python 3.13.14, Windows 11) took 0.85 s including compilation
  versus 170.28 s for repeated raw-text scoring on 2,000 resamples, with every
  serialized Band field identical. Timings and speedup depend on the environment;
  rerun `python experiments/compiled_benchmark.py` for a local measurement.

The first review experiment has modest gains: 6.95 versus 7.01 reviews for greedy
on 100 synthetic cases. The follow-up `ReviewProblem.plan_optimized` uses exact
integer arithmetic, retained-item packing, bounded exchanges, surrogate bounds
and grouped search. On a frozen held-out seed, it reduces reviews on 23/36 larger
synthetic problems (23.22 to 22.50 on average), certifies minima on 29/36 versus
1/36 for the legacy planner, and is 7.97x faster on 12 grouped problems with equal
review counts. Dense search takes 3.01x longer than legacy greedy in that run.
The real 24-pair record still has no review-count gain. These are matched-objective
software improvements, not a new-mathematics or human-label accuracy claim.

The [shared-price review follow-up](docs/shared_price_review.md) implements
`plan_refined` with shared target prices and standalone exact lower-bound proofs.
On 48 fresh held-out dense cases it certifies 46 minima versus 38 for the prior
integer planner, visits 75.45% fewer search states, and takes 15.59% less planning
time. It further reduces reviews on 4 cases (0.455% overall). Root certificates
prove 38 of those minima without search, and checking those proofs is 24.26x faster
than replanning on that subset. Grouped and tiny-case planning are slower due to
proof construction. Real review counts remain 24 / conditional 5. These ideas
have prior foundations in duality and optimization certificates.

```bash
python examples/review_budget.py                     # conservative default: 24 reviews
python examples/review_budget.py --domain candidate  # conditional plan: 5 reviews
python -S experiments/review_dual_benchmark.py --verify results/review_dual_held_out_public_1.0.0.json
```

Historical timing logs are retained unchanged. The earlier V1 optimization
report binds its own source hashes and must be verified at frozen commit
`be19c67`, not with the later shared-price implementation. The refined proof
report above remains verifiable in this candidate because its bound sources
are unchanged. See the submission evidence index for provenance and replay.

## External toolkit integration

`EvalScopeAdapter` imports review JSONL with strict sample-ID and input-context
alignment. Two pinned ten-pair public samples add GSM8K answer scoring and
IFEval recorded prompt-score auditing. Both declared strict comparisons give
exact bands [-1/10, 0]; these are useful negative integration cases, not broad
model rankings or external adoption evidence.

See [the offline tutorial and limitations](docs/external_cases.md) and
[the release and deployment mechanics](docs/github_deployment.md).

```bash
python -S experiments/external_cases.py --verify results/external_cases_1.0.3.json
```

Historical integration and timing reports retain their source hashes.
Verify the 0.4.0/0.4.1 integration artifacts at their respective tags; current
commands verify the 1.0.3 artifact with the same numerical readings.

## Reproduce the headline readings

```bash
cd demo
python gate1_standing.py        # Gate-1 robustness: full-scale band + bootstrap + leave-one
python tooling_certificate.py && python verify_tooling_certificate.py
```

## Citation

```bibtex
@software{robustband2026,
  title  = {robustband: the score you report is a band, not a point},
  author = {Gao, Zengzhao},
  year   = {2026},
  version = {1.0.3},
  note   = {Instrument for certified stability bands of benchmarking claims},
  url    = {https://github.com/wicalgambles-jpg/robustband}
}
```

## License

MIT — see [`LICENSE`](LICENSE).
