# SPDX-License-Identifier: MIT
"""Build both editable editions from one committed, reviewed Git source tree."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robustband import __version__
from robustband.storage import write_json_atomic


def main():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    committed = subprocess.check_output(["git", "show", "HEAD:robustband/__init__.py"], cwd=ROOT).decode("utf-8")
    assert '__version__ = "%s"' % __version__ in committed, "Commit the version before building editions"
    assert not subprocess.check_output(["git", "diff", "HEAD", "--"], cwd=ROOT), "Commit tracked changes first"
    archive = subprocess.check_output(["git", "archive", "--format=zip", "HEAD"], cwd=ROOT)
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    for edition in ("professional", "generalized"):
        name = "robustband-%s-%s" % (__version__, edition)
        folder = destination / name
        if folder.exists():
            raise FileExistsError("Edition already exists: %s. Keep it or move it before rebuilding." % folder)
        with tempfile.TemporaryDirectory(prefix="edition-", dir=destination) as stage:
            staging = Path(stage) / name
            staging.mkdir()
            with zipfile.ZipFile(io.BytesIO(archive)) as source:
                for member in source.infolist():
                    target = (staging / member.filename).resolve()
                    assert target.is_relative_to(staging.resolve()), member.filename
                source.extractall(staging)
            command = [sys.executable, "-S", "submission/build_welcome.py", "--edition", edition]
            if edition == "generalized":
                command.append("--include-lab")
            subprocess.run(command, cwd=staging, check=True)
            subprocess.run([sys.executable, "-S", "docs/build_api_docs.py", "docs/api"], cwd=staging, check=True)
            shutil.copyfile(staging / ("start_%s.cmd" % edition), staging / "start_robustband.cmd")
            changed = ["WELCOME.html", "start_robustband.cmd"]
            for launcher in staging.glob("*.cmd"):
                launcher.write_bytes(launcher.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
                changed.append(launcher.name)
            (staging / "README-FIRST.txt").write_bytes((
                "robustband %s - %s\n\nOpen WELCOME.html for an offline example.\n"
                "Double-click start_robustband.cmd to start this edition (Python 3.9+).\n"
                "Use start_professional.cmd or start_generalized.cmd to switch profiles.\n"
                "The two editions share the same exact scoring code.\n"
                "See docs/release_1.0.2.md for acceptance evidence and limitations.\n" % (__version__, edition)
            ).encode("utf-8"))
            manifest = {"schema": "robustband.edition_bundle/v1", "version": __version__,
                        "edition": edition, "source_commit": commit,
                        "profile_changes_sha256": {name: hashlib.sha256((staging / name).read_bytes()).hexdigest()
                                                   for name in sorted(set(changed))},
                        "generated_extras": ["README-FIRST.txt", "BUNDLE.json", "docs/api/"],
                        "scope": "Shared exact source; profile-specific preview/default launcher and CRLF Windows launchers."}
            write_json_atomic(staging / "BUNDLE.json", manifest)
            # The generated docs import the package; exclude bytecode from delivery.
            for cache in staging.rglob("__pycache__"):
                assert cache.resolve().is_relative_to(staging.resolve())
                shutil.rmtree(cache)
            staging.rename(folder)
        zipped = Path(shutil.make_archive(str(destination / name), "zip", destination, name))
        print(json.dumps({"edition": edition, "archive": zipped.name, "source_commit": commit,
                          "sha256": hashlib.sha256(zipped.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
