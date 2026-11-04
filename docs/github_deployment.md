# Release and deployment mechanics

This page describes how a maintainer builds, verifies and publishes a release. Running
these commands does not publish anything; pushing a tag and changing repository visibility
are separate maintainer actions.

## What a release contains

| artifact | produced by | checked by |
|---|---|---|
| wheel and source distribution | `python -m build --no-isolation` | `submission/verify_release.py` |
| no-install preview `WELCOME.html` | `submission/build_welcome.py --include-lab` | rebuilt and compared inside `verify_release.py` |
| offline API reference | `docs/build_api_docs.py docs/api` | CI artifact |
| version-bound receipts under `results/` | `check_quality.py`, the two browser smokes, `external_cases.py`, `resource_grid.py` | each script has a `--verify` mode |

A release is the commit that carries the version, the tag `vX.Y.Z`, and every receipt
regenerated from that commit.

## Build and verify locally

```bash
python -m pip install "setuptools>=77" build
python submission/check_quality.py        # tests, 100% coverage, matrix CLI, artifact verifiers, SPDX, frozen scoring
python submission/verify_release.py       # wheel + sdist, fresh offline installs, sdist rebuild, welcome rebuild
python docs/build_api_docs.py docs/api    # standard-library API reference
```

Browser checks need Node 22 and an installed Chromium:

```bash
node experiments/decision_browser_smoke.cjs
node experiments/decision_browser_smoke.cjs --professional
node experiments/matrix_browser_smoke.cjs
```

Both checks resolve an interpreter themselves: `python` on PATH, then `py -3` (or
`python3` on other platforms). Set `ROBUSTBAND_PYTHON` to force one, for example when
`python` on PATH is a placeholder that cannot start.

`verify_release.py` unpacks the sdist, rebuilds a wheel from it, installs both into fresh
virtual environments with `--no-index`, and runs the same smoke assertions in each. The
building machine needs build tools; the library itself has no runtime dependencies.

## Continuous integration

`.github/workflows/ci.yml` runs these jobs:

| job | platforms | what it proves |
|---|---|---|
| `test` | Ubuntu / Windows / macOS × Python 3.9, 3.11, 3.13 | complete `check_quality.py` gate: tests, 100% coverage, resource-grid replay, real-input LF/CRLF comparison, certificates, source identities and external/review proof replay |
| `ui` | Ubuntu, Node 22 + Chromium | both adoption pages and the ranking page in a real browser |
| `distribution` | Ubuntu | builds the distributions, verifies fresh offline installs, rebuilds the preview and the API reference |
| `converters` | Ubuntu / Windows | optional NumPy NPZ conversion acceptance cases |
| `portable` | Windows | builds a standalone folder and exercises both editions with system-only PATH |

GPU validation is executed separately on named local hardware with
`python experiments/validate_gpu.py`; public pull requests do not run on a
maintainer's GPU machine. The versioned receipt binds that run to source hashes.

`.github/workflows/pages.yml` builds the API reference and runs only when the repository
variable `ENABLE_GITHUB_PAGES` is `true` and Pages is enabled with source **GitHub
Actions** (public repositories on the free plan support this).

## Publishing checklist

1. Bump the version in `pyproject.toml`, `robustband/__init__.py`, `README.md` and
   `CHANGELOG.md`.
2. Regenerate every version-bound receipt and both distributions (commands above) and
   confirm each `--verify` passes.
3. Commit, tag `vX.Y.Z`, and push the branch and the tag.
4. Create the release from the tag with the wheel, the sdist and `WELCOME.html`, then
   attach the receipts you want to distribute.
5. Optionally enable Pages as described above.

For the Windows portable artifact, install PyInstaller and run
`python submission/build_portable.py`, then `python submission/verify_portable.py`.
Publish the ZIP only after that acceptance check. Editable source editions remain
separate from the bundled core executable.

After committing the reviewed release tree, `python submission/build_editions.py`
builds the professional and generalized source ZIPs from that exact Git commit.
Each `BUNDLE.json` identifies the source commit and hashes the profile-specific
files. Both editions use the same scoring implementation.

The first public 1.0.0 release used a newly initialized `robustband-public`
repository containing reviewed files, without importing earlier development Git
history. Since 1.0.2, that public repository is named `robustband`; the original
development repository is named `robustband-dev` and remains private. Review all source
and distribution members before publishing; in particular exclude internal
preparation materials, credentials, local source paths and private datasets.

## Historical record

`results/github_ci_2026-10-13.json` records a specific CI run and its source commit. It is
evidence for that commit only; it does not establish external adoption or independent
scientific review.
