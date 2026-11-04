# robustband 1.0.2 acceptance

This maintenance release addresses R48 from the 1.0.1 black-box review and tracks
evidence under functionality, reliability, usability, efficiency, maintainability
and portability. This is a project acceptance framework, not a claim of external
standards certification.

## Input contract change

Paired-text audit input accepts `sample_id,prompt,gold,output_a,output_b` and optional
`class,len_bucket`. An unknown field now stops the audit before a report is written.
The error identifies the record and unexpected field names. CSV, JSONL, Python
preview/audit and local HTTP preview/audit use the same validation.

For an intentional extra column, first inspect it, then explicitly convert:

```bash
python -m robustband convert input.csv --domain text --to jsonl --allow-extra-columns --output paired.jsonl
python -m robustband audit paired.jsonl --format jsonl --output audit-results
```

The adjacent `paired.jsonl.manifest.json` records `omitted_columns`. Check that list
before using the converted input. This is an intentional compatibility change for
tables with extra columns; supported scoring rules and exact endpoints are unchanged.

## Acceptance evidence

The release uses these reproducible checks. Executed totals are recorded in the
versioned receipts; commands alone do not establish a pass.

| Characteristic | Check and evidence |
|---|---|
| Functionality | Full regression suite; canonical conversion and report replay; R48 CSV/JSONL, CLI, Python and HTTP checks |
| Reliability | Unknown fields rejected; explicit omissions traceable; existing malformed input, tamper, atomic write and HTTP isolation checks |
| Usability | Actionable errors; offline examples and automated browser flows; unfamiliar-human completion rate remains unmeasured |
| Efficiency | `python -S experiments/measure_resources.py`: three fresh processes per workload, OS peak resident memory and load/audit/replay timing |
| Maintainability | Full package statement coverage, source hashes, SPDX, unchanged frozen scoring sources and synchronized versions |
| Portability | OS/Python CI matrix, LF/CRLF replay, offline wheel/sdist installs and Windows portable acceptance |

```bash
python -S experiments/external_cases.py
python -S experiments/resource_grid.py
python submission/check_quality.py
python -S experiments/measure_resources.py
python submission/verify_release.py
```

Resource measurements use synthetic default-protocol inputs: 5,000 text pairs,
5,000 score pairs and 500 samples across eight models (4,000 long-table rows).
Peak memory is the OS high-water mark of each fresh worker, including interpreter,
imports and input preparation up to measurement. Timing includes input loading,
audit and replay, excluding process startup. These are measured workloads, not
worst-case guarantees. See `results/resource_measurement_1.0.2.json`.

The floating-sum certificate profiles introduced before this release remain in use:
Python 3.9/3.11 replay the sequential artifact; Python 3.12+ replay the compensated
artifact. See [1.0.1](release_1.0.1.md) for the numerical details.

## Local results (2026-11-04)

On Windows 11 / Python 3.13, the complete quality gate passed 402 tests with
2318/2318 package statements covered. Six automated browser variants passed
104 checks on Edge 148 with zero script exceptions. The NPZ converter passed
26 acceptance cases; the standalone Windows package passed nine checks with
Python absent from PATH. Wheel and sdist rebuilt-wheel installations passed in
fresh offline environments outside the checkout.

Actual CUDA argmax/counts, NPZ conversion and exact CPU reference comparison passed
for 2, 8 and 64 classes on an NVIDIA GeForce RTX 4060 Laptop GPU. This validates
the optional data preparation path; the exact audit itself runs on the CPU.

| Synthetic workload | Load + audit + replay, three runs | OS peak resident memory |
|---|---|---|
| 5,000 text pairs | 0.152–0.153 s | 28.4–29.0 MiB |
| 5,000 score pairs | 0.123 s | 26.2–26.6 MiB |
| 500 samples × 8 models | 0.088–0.089 s | 24.9–25.3 MiB |

Timing is specific to this machine and workload. It is not a speedup comparison
against the previous review, whose measurement scope differed.

## Repository names and evidence limits

The first remote run passed 13 of 14 jobs; Ubuntu 26.04 could not install Python
3.9, so that job never executed the tests. The regression matrix now pins Ubuntu
24.04 while UI, converter and distribution jobs keep `ubuntu-latest`. CI archives
fresh receipts only after successful checks; committed local receipts are not
substituted when environment setup fails.

The public repository is now `wicalgambles-jpg/robustband`; the original development
history remains in private `wicalgambles-jpg/robustband-dev`. The rename preserves
each repository's history and visibility. New public changes use the already
reviewed public source tree. Historical receipts retain their original provenance.

Automated browser checks are not unfamiliar-human trials. Firefox/Safari user flows
and physical Linux/macOS machines are not covered by the local Windows checks;
hosted CI provides separate OS coverage. This release does not add real-world
adoption evidence or change the research conclusions in the resource-grid report.
