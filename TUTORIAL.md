# Tutorial — from a leaderboard claim to a certificate

This tutorial takes you from a raw model output to a **certified stability band**, then
shows how to wire `robustband` into a leaderboard or a CI pipeline. Every command runs on
the repository's own frozen data, **offline**, with **zero third-party runtime
dependencies**.

Install first (one command, no dependencies):

For the browser interface and validated paired CSV/JSONL, start with the
[first-use guide](docs/getting_started.md). The Python API below remains available
for custom workflows and larger datasets.

```bash
git clone https://github.com/wicalgambles-jpg/robustband.git
cd robustband
python -m pip install -e .            # add --no-build-isolation on an air-gapped machine
python -m robustband ui               # local browser interface; no code to write
```

For the test suite only you additionally need `pytest` and (for coverage) `coverage`:
`python -m pip install -e ".[dev]"`.

---

## 1. Five-minute first run (synthetic, hand-checkable)

The repository ships a two-item device with known arithmetic: the correct answer is `42`,
the CoT output mentions `7` first and `42` last, the plain output mentions them in the
opposite order.

```python
import robustband as rb

preds = {
    "cot":   {"items": [("the answer is 7 but really 42", "42", {})]},
    "plain": {"items": [("42 no wait 7",                 "42", {})]},
}

family = rb.build_family(parses=["first_num", "last_num"],
                         metrics=["exact_match"], aggs=["micro"])
claim  = rb.RankClaim("cot", "plain")          # the claim: cot beats plain
band   = rb.evaluate(preds, family, claim)

print(band.delta)               # (-1.0, 1.0)
print(band.verdict)             # UNIDENTIFIABLE
print(band.stability_fraction)  # 0.5
print(band.break_set)           # ['first_num|exact_match|micro']
```

Read it as: *if* the answer is extracted as the first number, `plain` wins by 1.0;
*if* it is extracted as the last number, `cot` wins by 1.0. Both extractions are legal
for this family, so the claim's **sign is not identified by the data** — it is decided by
a scoring choice that leaderboards normally leave implicit.

Verdicts: `ROBUST` (holds under every declared protocol), `REFUTED` (no declared
protocol supports it), `UNIDENTIFIABLE` (some support the strict claim and others
do not, including possible ties). A strict sign reversal requires `min < 0 < max`.
Note the asymmetry that matters in practice:
`UNIDENTIFIABLE` requires `min ≤ 0 < max`; `max ≤ 0` is `REFUTED`.

---

## 2. Your own data

One JSONL file **per model** in a directory; the file stem is the model name:

```
preds/
  cot.jsonl
  plain.jsonl
```

Each line is one item:

```json
{"raw": "the answer is 7 but really 42", "gold": "42", "meta": {"class": "arithmetic", "len_bucket": 2}}
```

* `raw` — the model's output, verbatim (do not pre-extract the answer: extraction is one
  of the axes under audit);
* `gold` — the reference answer, as a string;
* `meta` — optional per-item labels. `macro_class` groups by `meta["class"]`,
  `macro_len` by `meta["len_bucket"]`; missing keys degrade to a single `__all__` group.

```python
preds = rb.JSONLAdapter("preds").load()        # -> {"cot": {"items": [...]}, "plain": {...}}
# or build the structure yourself:
preds = {"cot": {"items": [("...", "42", {})]}, "plain": {"items": [("...", "42", {})]}}
```

Items are compared **positionally** for a rank claim, so the two files must list the same
questions in the same order.

---

## 3. Declare the family — deliberately

The band is **conditional on the family you declare**. `rb.build_family()` gives the
default family: `parse (5) × metric (4) × agg (4) = 80` scoring-only configurations
(no re-generation):

| axis | values |
|---|---|
| `parse` | `strict_exact`, `first_num`, `last_num`, `last_line_num`, `boxed` |
| `metric` | `exact_match`, `contains`, `f1_token`, `numeric_tol` |
| `agg` | `micro`, `macro_class`, `macro_len`, `median` |

Two habits keep the result defensible:

```python
# (a) audit over the whole family to find out how fragile the claim is
band = rb.evaluate(preds, rb.build_family(), claim)

# (b) then restrict to the subset you are willing to defend for *this* benchmark
defensible = rb.build_family(parses=["last_line_num", "boxed"],
                             metrics=["exact_match", "numeric_tol"],
                             aggs=["micro", "macro_class"])
band_defensible = rb.evaluate(preds, defensible, claim)
```

`contains` and `strict_exact` are *legal* protocols, not necessarily *good* ones for a
free-form arithmetic benchmark. Report both numbers and say which family you consider
defensible — the tool will not make that judgement for you.

---

## 4. Read the band on real data

The repository ships 24 paired GSM8K items (Qwen2.5-0.5B-Instruct, CoT vs. plain
prompting). Run the shipped example:

```bash
python examples/band_gate.py
```

```
claim      : cot>plain
configs    : 80
delta      : (-0.041667, +0.065000)
verdict    : UNIDENTIFIABLE
stability  : 0.3125
breaks     : 55/80
certificate: impossibility_certificate
  supports : last_line_num|exact_match|macro_class (+0.065000)
  opposes  : last_line_num|exact_match|macro_len (-0.041667)
```

What this says:

* the claim **holds** under `last_line_num|exact_match|macro_class` (+13/200) and
  **reverses** under `last_line_num|exact_match|macro_len` (−1/24) — both strict;
* `stability_fraction = 0.3125` means the claim holds under 25 of the 80 declared
  protocols. It is a fraction over the declared family, **not** a probability;
* 55/80 protocols break the strict claim (including ties).

**The trap this tool exists to catch.** Under the default protocol of many harnesses —
`strict_exact|exact_match|micro` — both arms score `0.0`, so the margin is `0.0`: a
point-estimate leaderboard would report "tie", while the truth is "the sign depends on a
legal scoring choice". A single number cannot express that.

Purely for scale: on the shipped 1319-item single-model file the score band over the same
80 configurations is `[0.000, 0.472]` (width ≈ `0.4716`).

---

## 5. Emit the certificate

```python
cert = rb.certificate.emit(preds, family, claim, band)
# -> impossibility_certificate (when min <= 0 < max), with:
#      witness_positive / witness_negative : the configs that support / oppose
#      strict_sign_flip                    : True only when the sign truly reverses
#      stability_fraction, delta           : the numbers above

mce = rb.certificate.minimal_counterexample(preds, family, claim, band)
# -> the flipping protocol with the smallest |margin|, plus the score table under it and
#    a "repro" block (parse/metric/agg/claim) so a third party can replay the flip
```

`emit` never asserts a strict reversal unless `lo < 0 < hi`; a claim that only ever ties
is reported as `REFUTED`, not as "reversed". Keep the emitted JSON next to the
leaderboard revision it audits — that is the artifact a reviewer or a reader can replay.

---

## 6. Exact rational endpoints

Floating point is not the argument you want to have with a reviewer:

```python
from fractions import Fraction

cot_items   = preds["cot"]["items"]
plain_items = preds["plain"]["items"]

r = rb.rational.rational_band(cot_items, plain_items, family)
print(r["lo"], r["hi"])          # -1/24 13/200   (Fraction, bit-exact)
print(float(r["lo"]))            # -0.041666666666666664
print(r["n_certain"], r["n_configs"])   # 80 80   (all built-in decisions are exact)

base, reps = rb.rational.duplication_invariance(cot_items, plain_items, ks=(1, 2, 4, 8))
print(all(x["same"] for x in reps))     # True -> endpoints unchanged under item x k
```

Two honesty notes that the tests enforce and this tutorial repeats:

* numeric answers are compared as **exact finite decimals** (no binary-float thresholds),
  so `1,000` equals `1000` and `9007199254740992` does **not** equal `9007199254740993`;
* **duplication invariance is an algebraic self-check on the aggregation code, not
  evidence about new data.** Replicating the same items cannot change the band; *adding
  independent items can*. A sign flip that survives new items is a stronger statement and
  must be shown with new items, not with copies.

---

## 7. Gate a leaderboard in CI

`examples/band_gate.py` is a complete, runnable gate. The core is five lines:

```python
band = rb.evaluate(preds, rb.build_family(), claim)
if band.verdict == "UNIDENTIFIABLE":
    cert = rb.certificate.emit(preds, rb.build_family(), claim, band)
    print("claim is not identifiable:", cert["witness_positive"], cert["witness_negative"])
    raise SystemExit(1)          # fail the build / block the leaderboard update
```

```yaml
# .github/workflows/leaderboard.yml (your repository)
- run: python -m pip install git+https://github.com/wicalgambles-jpg/robustband.git
- run: python scripts/band_gate.py --strict
```

Run it against the repository's own data and it exits **1 by design** — that is the
demonstration: the canonical `cot > plain` claim on these 24 items is not identifiable,
and the job says so before a leaderboard reports an order.

---

## 8. Extend it

Parsers, metrics and aggregators are plain functions registered in three dictionaries:

```python
def p_after_equals(raw):                      # parse: raw -> candidate string
    return (raw or "").split("=")[-1].strip()

def m_substring(cand, gold, meta=None, tol=1e-3):   # metric: (cand, gold, meta) -> 0/1
    return int(str(gold).strip() != "" and str(gold).strip() in str(cand))

def a_top1(corrects, metas):                  # agg: (list[int], list[dict]) -> float
    return float(corrects[0]) if corrects else 0.0

rb.PARSE["after_equals"] = p_after_equals
rb.METRIC["substring"]   = m_substring
rb.AGG["top1"]           = a_top1

family = rb.build_family(parses=["after_equals", "boxed"],
                         metrics=["substring", "exact_match"],
                         aggs=["top1", "micro"])
```

Two cautions:

* `rb.build_family()` with **no arguments** enumerates whatever is currently registered,
  so a custom entry changes the "80-configuration" default. Pass explicit lists whenever
  you report numbers, or your band will not match the published one.
* the built-in family and its reported readings are **frozen** (see
  [`CHANGELOG.md`](CHANGELOG.md) and the certification artifacts under `results/`).
  Changing a built-in parser/metric/aggregator is a semantic change: bump the version,
  regenerate `results/`, and re-run the verifier.

---

## 9. Reproduce the shipped certificate

```bash
cd demo
python tooling_certificate.py           # ~3 min: writes ../results/tooling_certificate.json
python verify_tooling_certificate.py    # ~3 min: re-derives V-source, V0..V8 -> [VERIFY PASS]
python gate1_standing.py                # ~3 min: full-scale band, bootstrap, leave-one-axis
```

The verifier deliberately **does not trust** the certificate's own numbers: it re-hashes
the four input files and recomputes every layer, including a separate reference
implementation of the 1319-item score band. Exit code `0` means `[VERIFY PASS]`; a
mismatch exits `2`.

---

## 10. FAQ and pitfalls

**My band is `[0, 0]` and the verdict is `REFUTED`, but the model is clearly better.**
The default protocol may be collapsing your answers (both arms scoring `0`). Print
`band.margins`, or evaluate the claim on a defensible subset — the band tells you *which*
protocol kills the claim via `break_set`.

**The band contains 0 and I still believe the claim.**
Then say *under which protocols* you claim it, and show that the flipping protocols are
not defensible for your benchmark. That is a legitimate scientific answer; an unexplained
point estimate is not.

**`ValueError: family must contain at least one configuration`.**
You passed an empty family (e.g. `rb.build_family(parses=[])`).

**`ValueError: nonzero tol_eps is unsupported`.** `evaluate(..., tol_eps=...)` is
deliberately unimplemented — express the tolerance in the claim
(`ScoreClaim(model, threshold)`) instead of loosening the engine.

**How large a family should I report?** Report the full family *and* your defensible
subset. The first is the fragility audit; the second is your scientific claim.

**Where do the numbers in `results/` come from?** `demo/tooling_certificate.py`
(certificate), `demo/emodule_bundle.py` (E negative module), `demo/gate1_standing.py`
(robustness). The frozen model outputs that can be rescored are in `demo/data/`; the
repository does **not** pin the model revision or the generation environment, so it
reproduces the *scoring*, not the *generation*.

---

## File map

| path | what it is |
|---|---|
| `robustband/` | the library (9 modules, zero runtime dependencies) |
| `tests/` | 38 deterministic tests, 100% statement coverage of the package |
| `examples/band_gate.py` | runnable CI-gate example (report / `--strict`) |
| `demo/` | reproduction scripts: certificate, verifier, Gate-1 robustness, E module |
| `results/` | the frozen artifacts (certificate JSON, bundle, robustness readings) |
| `docs/build_api_docs.py` | builds this API reference with the standard library only |
| `TUTORIAL.md` | this file |
