# First use: a local audit from your records to a report

Open `WELCOME.html` in your browser to explore the examples without installation.
To calculate results from your own files, use the Windows portable ZIP or Python
3.9 or later. The portable folder contains its own runtime: extract the entire ZIP,
then double-click `start_generalized.cmd` or `start_professional.cmd`. Keep the
`_internal` folder beside the executable. Its executable is unsigned. For editable
domain adapters and the optional NumPy NPZ converter, use the source edition.
The browser interface, command line and library
use the same registered domain adapters and exact rational audit engine. There are no
third-party runtime dependencies, model downloads or accounts required by this tool.

## Import your own files

Drop one paired table or two single-model result files into the local app.
CSV, TSV, JSON, JSONL/NDJSON, Excel XLSX and official MMLU-Pro result ZIPs are
supported. Recognized data is validated and analyzed automatically; review the
source names, sample count, subject, rules and warnings before saving the complete
result bundle. See the [file import guide](file_import.md) for required columns,
strict pairing, Excel limitations and the MMLU-Pro missing-prediction policy.

## Compare more than two models (optional)

The browser app has a ranking page: open **Ranking audit** in the header (or `/matrix`
after the session fragment) to preview a long table, choose protocols and download the
report. The same check is available from the command line with one long table (one row per
sample and model):

```bash
python -m robustband matrix models.csv --parse strict_exact first_num last_num \
  --metric exact_match --agg micro --output ranking
python -m robustband verify ranking/report.json
```

Every model must contain exactly the same `sample_id` set with the same `gold`; the
verifier recomputes every rank and pair. `STABLE` means the whole order is identical under
all declared protocols, `LEADER-STABLE` means the leader is stable while the rest moves,
and `SENSITIVE` means the leader itself depends on the protocol. Each pair is labelled
ahead / behind / ties / flips with its exact range. Limits: 5,000 measurement rows and 8
models per audit.

## 1. Start with the example

After extracting the source bundle, double-click `WELCOME.html`. Choose a card:
**AI answers**, **Segmentation results**, **Numeric metrics**, or the editable
**Custom algorithms** example when included. Click **Run example**.

The standalone preview uses exact saved reports from the actual Python engine.
It runs without Python or a server and makes no network requests. Its settings
are fixed; **Use my own data** opens instructions for starting the local app.

### Open the local app for your own files

From the source directory:

```bash
python -m robustband ui
```

On Windows, double-click `start_robustband.cmd` in that directory. The launcher
finds Python 3.9 or newer itself, checking `ROBUSTBAND_PYTHON`, a `.venv` in the
source folder, `python` on PATH, the `py` launcher and the default install
folders in that order; if none runs, it prints installation guidance and keeps
the window open. Set `ROBUSTBAND_PYTHON` to the full path of an interpreter to
force one. From an installed wheel, `robustband ui` also works.
The page opens in your browser and supports English/Chinese. Use **Stop** on the
page or Ctrl+C in the terminal to close its local server. If automatic opening
fails, copy the complete printed URL, including the fragment after `#`.

```bash
# Install a downloaded wheel offline, outside the source checkout:
python -m pip install --no-index --no-deps robustband-1.0.3-py3-none-any.whl
python -m robustband ui
```

The service binds to `127.0.0.1` on an available port and does not expose a file
browser or remote upload service. Files you select are processed on this machine.
This is a local research interface; public hosting needs a separately designed service.

### Export a standard file

In **Adoption check**, load your paired file, explicitly map custom numeric columns
when needed, and select **Check data and set criteria**. The completed input stage
collapses. **Export standard data and manifest** downloads canonical JSONL and a
hash manifest after reloading and comparing all recognized values. Expand either
stage to edit it; edited criteria invalidate the previous result.

The CLI exposes the same conversion:

```bash
python -m robustband convert paired.csv --domain scores --output paired-standard.jsonl
python -m robustband convert wide.csv --domain scores --mapping mapping.json --output paired-standard.jsonl
```

Unknown columns require an explicit `--allow-extra-columns`; the manifest lists
omitted fields. Units are never guessed or rescaled. Existing outputs require
`--overwrite`, and the input file cannot be an output. See
[the conversion guide](conversion.md) for NPZ caches and void-label handling.

## 2. Run the hand-checkable example

On the **AI answers** card, click **Run example**. The reference is `42`; output A says `7` then `42`, and
output B says `42` then `7`. First-number extraction supports B; last-number
extraction supports A. With exact match and equal item weights, the exact band
is `[-1, 1]`, with one supporting protocol out of two: `UNIDENTIFIABLE`.

These are explicitly selected example policies. Neither this two-policy family
nor the library's 80-policy default is an endorsement for your own benchmark.
Confirm scientifically appropriate policies before interpreting a result.

## 3. Import your paired records

Click **Use my own data**, choose **AI answers**, then **Download a template**. Replace the sample row and choose your file, or drag it onto the upload area.
One row contains both outputs for the same question:

```csv
sample_id,prompt,gold,output_a,output_b,class,len_bucket
question-1,What is 6 times 7?,42,the answer is 42,the answer is 7,arithmetic,short
```

CSV quoting supports commas and multiline outputs. Keep the model outputs verbatim.
UTF-8 is required; a byte order mark is accepted. Only the five required fields and
optional `class,len_bucket` are accepted by text audits. Correct misspelled fields
or explicitly remove extra columns through the converter; review its omission manifest.
Paired JSONL uses the same fields:

```json
{"sample_id":"question-1","prompt":"What is 6 times 7?","gold":"42","output_a":"the answer is 42","output_b":"the answer is 7","class":"arithmetic","len_bucket":"short"}
```

- Required: `sample_id`, `prompt`, `gold`, `output_a`, `output_b`.
- IDs must be unique, nonempty strings or integers; integer IDs normalize to strings.
- `prompt`, `gold` and outputs are strings; prompt and reference must be nonempty.
- Empty model outputs remain actual observations and are reported as diagnostics.
- Optional `class` and `len_bucket` are explicit user-provided group labels.
  Group labels normalize to strings. A selected macro aggregator requires its
  field on every record; missing labels
  are rejected rather than silently converted to one group.
- The interface and CLI accept at most 4 MiB and 5,000 paired records per audit.
  Larger/custom workloads can use the existing Python API.

This paired format is different from the legacy one-file-per-model JSONL format.
For existing files, align by stable IDs and check equal questions/references before
combining them. Do not truncate or take an intersection to hide mismatched samples.
Existing EvalScope users can use the [strict adapter](external_cases.md).

The preview shows the first five records and empty-output counts. Correct any
reported duplicate ID or field error, then provide names for the two output columns.

## 4. Confirm protocols and interpret the audit

Open **Review or change rules and parameters** to select answer extraction, item correctness and aggregation. Every checked
combination is part of the declared family; the page shows its size before running.
Group aggregators become available only after their required labels are present.

- `ROBUST`: every declared policy supports A strictly better under the declared direction.
- `REFUTED`: no declared policy supports that strict claim. A tie does not prove B wins.
- `UNIDENTIFIABLE`: some policies support the claim and others do not. A strict
  reversal occurs only when the band has a negative and a positive endpoint.

The endpoint protocols and full results remain available. All-zero item scorers
are flagged for inspection. The support fraction counts selected protocols;
it is neither a probability nor a confidence level. Changing inputs, model names
or policies invalidates the displayed result until the audit runs again.

The interface audits strict paired preference claims. Score-threshold claims,
resampling, logged IFEval scoring and experimental review planning remain in
their existing Python APIs/examples; they are not inferred from this form.

## Other measurement domains

Select the **Segmentation results** card to upload paired integer matrices. Choose
one class target (all classes or explicit indices), count/image/group aggregation
and the undefined-class convention. The example has a pooled versus equal-image
reversal. With class 1 selected, its exact band is `[-49/51, 1/3]`.

Select the **Numeric metrics** card for existing measurements such as latency,
error or accuracy. Every record declares `metric,unit,direction`, with
`direction=higher` or `lower`. The latency example compares mean and median and
has exact oriented margins `[-8/3, 1]` ms. A positive margin always favors A;
for latency, the claim is A's value **lower** than B's.

Download the selected domain's template, replace the synthetic records, and use
the same preview, audit and export controls. Keep distinct metrics and objectives
in separate audits. See [domain formats and modular extensions](domains.md) for
precise definitions and optional raw-array preparation.

```bash
python -m robustband demo --domain segmentation --output audit-demo/segmentation
python -m robustband demo --domain scores --output audit-demo/scores
python -m robustband scores metrics.csv --aggregations mean median --output audit-results
python -m robustband run counts.jsonl --domain segmentation --output audit-results
```

The generic `run` command accepts `--policy policies.json`, containing a JSON
object with that domain's family settings. `python -m robustband domains` lists
registered formats and defaults. The existing text `audit` command remains valid.

## 5. Export and recompute

**Save readable report** produces a standalone readable table, without including
the input records. Domain diagnostics and aggregate measurements remain visible. **Save full replay data** includes your canonical
input records, the selected policies, exact scores, witnesses and source hashes.
Check its contents before sharing data with other people.

```bash
python -m robustband verify report.json
```

Recomputation requires the recorded software version and unchanged scoring sources.
It detects mismatched inputs, policies, results and hashes. This is a consistency
check, not a digital signature or independent scientific/human verification.

## Terminal and automation

```bash
python -m robustband demo --output audit-demo
python -m robustband verify audit-demo/report.json
python -m robustband template paired.csv
python -m robustband audit paired.csv --model-a "Model A" --model-b "Model B" --output audit-results

# Explicitly declare your family:
python -m robustband audit paired.csv --parses last_num boxed --metrics exact_match numeric_tol --aggs micro --output audit-results

# JSONL input:
python -m robustband audit paired.jsonl --format jsonl --output audit-results

# Use as an automated gate; non-ROBUST valid audits return 1:
python -m robustband audit paired.csv --output audit-results --require-robust
```

Exit codes: `0` successful operation; `1` a valid non-ROBUST strict gate;
`2` invalid inputs or an execution error. Every completed audit exports both
`report.html` and `report.json`. `python -m robustband --help` lists all commands.

## Optional AI-assistant instructions

You can give a coding assistant these instructions:

> Work in the robustband source directory with Python 3.9 or later. Run
> `python -m robustband demo --output audit-demo` and recompute its JSON using
> `python -m robustband verify audit-demo/report.json`. Inspect my input schema
> and propose a mapping to the paired CSV template. Verify unique sample IDs and
> matching question/reference contexts before combining model files. Ask me to
> confirm the scoring family for my actual task. Run the audit command with that
> explicit family, export HTML/JSON and show the exact band, endpoint protocols
> and limitations. Preserve empty outputs and report mismatches as errors.

The software works without an AI assistant. The assistant can automate the same
commands; task-appropriate policies and trusted human judgments still need evidence.

## Verification performed by the project

Package tests include strict input validation, exact result agreement with the
existing rational engine, report tampering/escaping, command exits and actual
loopback HTTP requests. An optional development-only Chromium test checks the
real page, uploads, exports, responsive layout and language switching:

```bash
node experiments/ui_browser_smoke.cjs
```

That check needs Node >=22 and an installed Chromium browser; set
`ROBUSTBAND_BROWSER_PATH` if needed. Neither is an additional Python runtime
dependency. These automated results do not establish independent user adoption.

For primary-benefit and guardrail conditions, use the [adoption workflow](decision_workflow.md).
