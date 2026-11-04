# Contributing to robustband

Thanks for considering a contribution. `robustband` is a small, deliberately boring
library: **zero runtime dependencies**, exact arithmetic where it matters, and a frozen
set of built-in scoring protocols whose reported numbers are reproducible by a third
party. Most of the rules below exist to keep that property intact.

Issues and pull requests are welcome on
<https://github.com/wicalgambles-jpg/robustband>. For security or conduct concerns, email
the maintainer instead of opening a public issue.

---

## 1. Ground rules (hard)

1. **No runtime dependencies, ever.** Everything under `robustband/` imports the standard
   library only. `dependencies = []` in `pyproject.toml` and CI asserts that
   `pip show robustband` reports an empty `Requires:`. Test-only tooling (`pytest`,
   `coverage`) goes in the `dev` extra.
2. **Every source file starts with `# SPDX-License-Identifier: MIT`.** The audit is
   mechanical and checks every tracked Python file.
3. **Tests must be deterministic and offline.** No network, no unseeded randomness, no
   large fixtures, no printed-only assertions. Prefer values you can check by hand (the
   `tests/conftest.py` fixture is designed that way).
4. **100% statement coverage of `robustband` is a gate, not an aspiration.** CI runs
   `coverage run --source=robustband -m pytest` and reports the table; a new branch needs a
   test.
5. **The built-in family and its published readings are frozen.** Changing a built-in
   parser, metric, aggregator, verdict rule, or claim semantic changes reported numbers.
   That is allowed, but it is a **semantic change**: bump the version, regenerate
   `results/`, re-run both verifiers, and update `CHANGELOG.md`. Never edit a published
   reading quietly.
6. **Numeric answers are compared exactly.** Use `Decimal` / `Fraction`; never introduce a
   binary-float threshold in a built-in metric. `9007199254740992 != 9007199254740993`
   must stay true.
7. **`results/tooling_certificate.json` must name the current version.** The verifier
   asserts `cert["robustband_version"] == rb.__version__`; after a version bump you must
   regenerate the artifact (see §5), or verification fails.

---

## 2. Development setup

```bash
git clone https://github.com/wicalgambles-jpg/robustband.git
cd robustband
python -m pip install -e ".[dev]"      # offline machines: --no-build-isolation
```

| task | command |
|---|---|
| tests | `python -m pytest -q` |
| coverage (must be 100% of the package) | `python -m coverage run -m pytest -q && python -m coverage report -m` |
| certificate | `cd demo && python tooling_certificate.py` (~3 min) |
| independent verification | `cd demo && python verify_tooling_certificate.py` (~3 min, exits 2 on mismatch) |
| E negative module | `cd demo && python emodule_bundle.py --dir data_real --better cot --worse plain` |
| robustness readings | `cd demo && python gate1_standing.py` (~3 min) |
| API reference (stdlib only) | `python docs/build_api_docs.py docs/api` |
| runnable usage example | `python examples/band_gate.py` (add `--strict` to exit 1 on a non-identifiable claim) |

Python ≥ 3.9 is supported; CI runs 3.9 / 3.11 / 3.13 on Linux, Windows and macOS.

---

## 3. Adding a parser, metric or aggregator

For a new **domain**, use the separate `AuditDomain` interface described in
[`docs/domains.md`](docs/domains.md). Prefer a domain adapter over adding domain
scorers to the frozen text dictionaries. Add pairing, unit/direction, exact-score
agreement, shared-entry-point and replay-tampering tests. Browser controls and
report sections are described by metadata; external preprocessing dependencies
stay outside `robustband/`.

Register a plain function and add tests; the three dictionaries are the only registry.

| axis | signature | returns |
|---|---|---|
| parse (`robustband/parsers.py`, `PARSE`) | `parse(raw) -> str` | the candidate answer extracted from the raw output |
| metric (`robustband/metrics.py`, `METRIC`) | `metric(cand, gold, meta=None, tol=1e-3) -> int` | `1` correct, `0` incorrect |
| agg (`robustband/aggregate.py`, `AGG`) | `agg(corrects, metas) -> float` | a scalar score from per-item `0/1` values |

Requirements for a new built-in:

* a one-line docstring saying what it does (Chinese or English both fine);
* a test in `tests/` covering **both** outcomes and any degenerate input (empty string,
  missing `meta` key, numeric edge cases);
* a mention in `TUTORIAL.md` §3 if it changes the A-tier family, and in `CHANGELOG.md`;
* if it changes the family size, every place that states `5 × 4 × 4 = 80` (search the
  repository) must be updated in the same pull request.

Adding entries **changes what `build_family()` returns by default**, because it enumerates
whatever is registered. Keep the built-in family at `5 × 4 × 4` unless the change is
intentional and documented.

## 4. Adding a claim type

Claims live in `robustband/claim.py` and must expose:

```python
class MyClaim:
    kind = "my-kind"                 # short identifier used in certificates
    def __init__(...): self.name = ...   # human-readable, used in repro blocks
    def holds(self, table): ...      # table = {model: score} -> bool
    def margin(self, table): ...     # signed effect size; positive means "supports"
```

The engine treats `margin > 0` as support and `margin <= 0` as a break, so the sign
convention is part of the contract. Add unit tests for both a supporting and a violating
table, and make sure `rb.certificate.emit(...)` produces a sensible witness for it.

---

## 5. Changing anything that affects the published artifacts

```bash
# 1) version bump (pyproject.toml, robustband/__init__.py, README.md header + Citation, CHANGELOG.md)
# 2) regenerate every artifact
cd demo
python tooling_certificate.py
python emodule_bundle.py --dir data_real --better cot --worse plain
python gate1_standing.py
# 3) re-verify: both must pass
python verify_tooling_certificate.py      # [VERIFY PASS], exit 0
python verify_certificate.py              # [VERIFY PASS], exit 0
# 4) tests + coverage
cd .. && python -m pytest -q && python -m coverage run -m pytest -q && python -m coverage report -m
```

Then update `CHANGELOG.md` with what changed, **why the reported numbers are unchanged or
how they changed**, and commit the regenerated `results/` files together with the code.

---

## 6. Pull-request checklist

- [ ] `python -m pytest -q` passes; coverage of `robustband` is still 100%
- [ ] new/changed source files carry the SPDX line
- [ ] no new runtime dependency (`dependencies = []` untouched)
- [ ] `CHANGELOG.md` updated under an "Unreleased" or new version heading
- [ ] if a published reading could change: artifacts regenerated **and** both verifiers pass
- [ ] documentation updated (`README.md`, `TUTORIAL.md` and the resource note if the
      family or the headline numbers moved)
- [ ] no secrets, no large binaries, no generated caches in the diff

## 7. Release steps (maintainer)

1. bump the version in the four places listed in §5 and add the `CHANGELOG.md` entry;
2. regenerate and re-verify the artifacts (§5) and run the full test/coverage chain;
3. `git commit`, then `git tag -a vX.Y.Z -m "..."` and push the branch **and** the tag;
4. create the GitHub release from the tag (Zenodo mints a DOI for tagged releases);
5. build the submission archive with `git archive --format=tar.gz --prefix=robustband-X.Y.Z/ -o robustband-X.Y.Z-src.tar.gz HEAD`
   (no `.git`, no caches) and confirm it with `tar -tzf ... | grep -E "\.git/|__pycache__"`.

Semantic versioning: `MAJOR` for a change in scoring semantics or the frozen family,
`MINOR` for new features/registries, `PATCH` for docs, tests and non-semantic fixes.

---

## 8. Reporting a bug

Please include: the exact version (`python -c "import robustband; print(robustband.__version__)"`),
Python version and OS, the smallest data snippet that shows the problem (two or three JSONL
lines are usually enough), the command you ran, what you expected, and what you got
(full traceback). If a band looks wrong, include `band.delta`, `band.verdict` and
`band.margins` — that pins the issue to a protocol.

## 9. Style

Shared documentation should help readers install, use and evaluate the software.
Describe functionality, relevant prior work, measured results and specific limits
in neutral language. Keep publication goals and prestige classifications out of
the project landing page. Avoid internal evaluation labels, unsupported comparisons
and subjective self-assessments. Retain accurate attribution and material evidence
limitations when editing presentation.

PEP 8, four-space indent, ~100-column lines, small modules with a docstring explaining
*why* the module exists. Chinese or English comments/docstrings are both acceptable in this
repository; user-facing strings (README, TUTORIAL, CHANGELOG, error messages) are English.
Type hints are not required, but keep public functions' argument shapes documented — the
axes are consumed as `(cand, gold, meta)` and `(corrects, metas)` tuples, and changing those
shapes is a breaking change.

## 10. License

By contributing you agree that your contribution is licensed under the MIT License
(see [`LICENSE`](LICENSE)) and that it can be redistributed as part of the project and of
any released source archive.

Maintainer: Zengzhao Gao (Harbin Engineering University) — wicalgambles@gmail.com —
ORCID [0009-0007-9138-4642](https://orcid.org/0009-0007-9138-4642).

## 11. Release acceptance

For each release, review functionality, reliability, usability, efficiency,
maintainability and portability. Record executed checks separately from pending
or unavailable evidence. Automated browser flows do not establish unfamiliar-human
usability. Run `submission/check_quality.py`, distribution/converter/portable checks
where supported, and `experiments/measure_resources.py`; link versioned receipts
and describe the measured workload and environment. This project checklist is not
external standards certification.
