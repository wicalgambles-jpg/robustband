# SPDX-License-Identifier: MIT
"""Build distributions and install both into fresh isolated environments offline.

The sdist is unpacked and rebuilt; the checkout is never used as an import path.
Build tooling is required on the development machine, not at library runtime.
Version numbers are read from the package, so a release only bumps that string.
"""
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from robustband import __version__ as VERSION  # noqa: E402
from robustband.storage import write_json_atomic

SMOKE = r'''
import importlib.metadata as md
import json
from pathlib import Path
import subprocess
import sys
import robustband as rb
from robustband.workflow import DEMO_CSV, load_paired, analyze, verify_report
from robustband.domains import domain_options, audit_domain, verify_audit
from robustband.compiled import CompiledScores
from robustband.import_service import analyze_import
import base64
import io
import zipfile
from robustband.review import ReviewProblem, Target
assert rb.__version__ == "__VERSION__"
assert len(rb.build_family()) == 80
assert not [r for r in (md.requires("robustband") or []) if "extra ==" not in r]
preds = {"A":{"items":[("2", "2", {})]},"B":{"items":[("3", "2", {})]}}
family = rb.build_family(parses=["last_num"], metrics=["exact_match"], aggs=["micro"])
claim = rb.RankClaim("A", "B")
assert rb.evaluate(preds, family, claim).delta == (1,1)
assert CompiledScores(preds, family).evaluate(claim).to_dict() == rb.evaluate(preds, family, claim).to_dict()
p = ReviewProblem(("a", "b"), ((-1,1),(-1,1)), (Target("micro", ("1/2","1/2")),))
plan = p.plan_refined("1/10")
assert plan["n_reviews"] == 2 and p.verify_lower_bound(plan["lower_bound_certificate"])
row = {"target":"2","messages":[{"role":"user","content":"1+1"},{"role":"assistant","content":"2"}],
 "sample_score":{"sample_id":0,"sample_metadata":{},"score":{"prediction":"2","value":{"acc":1}}}}
Path("sample.jsonl").write_text(json.dumps(row), encoding="utf8")
adapter = rb.EvalScopeAdapter({"A":"sample.jsonl"})
assert adapter.records()["A"][0]["scores"]["acc"] == 1
assert adapter.load()["A"]["items"][0][:2] == ("2","2")
assert not any(m in __import__("sys").modules for m in ("numpy","scipy","torch","datasets"))
report = analyze(load_paired(DEMO_CSV))
assert report["result"]["exact_band"] == ["-1", "1"] and verify_report(report)
assert len(domain_options()) == 3
assert [d["id"] for d in domain_options("professional")] == ["text"]
for option in domain_options():
    native = audit_domain(option["id"], option["example"], option["example_format"])
    assert verify_audit(native)
for filename, data in (("paired.csv", DEMO_CSV), ("paired.json", json.dumps([{"sample_id":"s","prompt":"p","gold":"42","output_a":"42","output_b":"7"}]))):
    imported=analyze_import({"files":[{"name":filename,"data":base64.b64encode(data.encode()).decode()}]},"generalized")
    assert verify_audit(imported["report"])
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(imported["bundle_base64"]))) as archive:
        assert archive.read("report.json").decode()==imported["json"]
assets = Path(rb.__file__).parent
assert "Run example" in (assets / "ui.html").read_text(encoding="utf-8")
assert (assets / "decision.html").is_file()
assert (assets / "matrix.html").is_file()
from robustband.decision import analyze_decision, verify_decision, EXAMPLE, EXAMPLE_PLAN, EXAMPLE_MAPPING
adoption = analyze_decision(EXAMPLE, EXAMPLE_PLAN, mapping=EXAMPLE_MAPPING)
assert adoption["result"]["status"] == "FAIL" and adoption["result"]["target_tradeoff"]
assert verify_decision(adoption)
from robustband.convert import convert_table
converted = convert_table(EXAMPLE, 'scores', mapping=EXAMPLE_MAPPING)
assert converted['manifest']['roundtrip_verified'] and converted['manifest']['n_records'] == 6
Path('wide.csv').write_text(EXAMPLE, encoding='utf-8')
Path('mapping.json').write_text(json.dumps(EXAMPLE_MAPPING), encoding='utf-8')
subprocess.run([sys.executable, '-I', '-m', 'robustband', 'convert', 'wide.csv', '--domain', 'scores',
 '--mapping', 'mapping.json', '--output', 'standard.jsonl'], check=True, capture_output=True)
assert json.loads(Path('standard.jsonl.manifest.json').read_text(encoding='utf-8'))['roundtrip_verified']
subprocess.run([sys.executable, "-I", "-m", "robustband", "demo", "--output", "installed-demo"], check=True, capture_output=True)
subprocess.run([sys.executable, "-I", "-m", "robustband", "verify", "installed-demo/report.json"], check=True, capture_output=True)
subprocess.run([sys.executable, "-I", "-m", "robustband", "--edition", "professional", "demo", "--output", "professional-demo"], check=True, capture_output=True)
subprocess.run([sys.executable, "-I", "-m", "robustband", "--edition", "professional", "verify", "professional-demo/report.json"], check=True, capture_output=True)
for domain in ("segmentation", "scores"):
    subprocess.run([sys.executable, "-I", "-m", "robustband", "demo", "--domain", domain, "--output", domain], check=True, capture_output=True)
    subprocess.run([sys.executable, "-I", "-m", "robustband", "verify", domain+"/report.json"], check=True, capture_output=True)
Path("ranking.csv").write_text("sample_id,model,gold,output\nq1,a,42,42\nq1,b,42,7\n", encoding="utf8")
subprocess.run([sys.executable, "-I", "-m", "robustband", "matrix", "ranking.csv", "--output", "ranking-out"], check=True, capture_output=True)
subprocess.run([sys.executable, "-I", "-m", "robustband", "verify", "ranking-out/report.json"], check=True, capture_output=True)
entry = Path(sys.executable).with_name("robustband.exe" if sys.platform == "win32" else "robustband")
assert subprocess.check_output([str(entry), "--version"], text=True).strip() == rb.__version__
print(json.dumps({"version":rb.__version__,"import_path":rb.__file__,"runtime_requirements":[],
 "default_configs":80,"raw_cache_equal":True,"review_proof_verified":True,"adapter_import_verified":True,
 "workflow_replay_verified":True,"ui_assets_installed":True,"ranking_audit_verified":True,
 "module_and_console_entrypoints_verified":True,"validated_conversion_verified":True,
 "file_import_and_bundle_verified":True,"domain_adapters_replayed":["text","segmentation","scores"],"professional_profile_verified":True}))
'''.replace("__VERSION__", VERSION)


def command(args, cwd):
    process = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if process.returncode:
        raise RuntimeError(process.stdout[-4000:] + process.stderr[-4000:])
    return process.stdout


def smoke(wheel, location):
    env = location / "env"
    venv.EnvBuilder(with_pip=True).create(env)
    python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    command([str(python), "-I", "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], location)
    info = json.loads(command([str(python), "-I", "-c", SMOKE], location))
    assert Path(info["import_path"]).resolve().is_relative_to(env.resolve())
    return {key: value for key, value in info.items() if key != "import_path"}


def main():
    command([sys.executable, "-m", "build", "--no-isolation"], ROOT)
    wheel = ROOT / ("dist/robustband-%s-py3-none-any.whl" % VERSION)
    sdist = ROOT / ("dist/robustband-%s.tar.gz" % VERSION)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for required in ("robustband/evalscope.py", "robustband/ui.html", "robustband/decision.html",
                         "robustband/matrix.html", "robustband/matrix.py", "robustband/report_style.py",
                         "robustband/importers.py", "robustband/import_service.py"):
            assert required in names, required
        assert not any("__pycache__" in path or path.endswith(".pyc") for path in names)
    source_members = []
    with tempfile.TemporaryDirectory(prefix="robustband-distribution-check-") as tmp:
        base = Path(tmp).resolve()
        wheel_check = smoke(wheel, base)
        extract_root = base / "sdist"
        extract_root.mkdir()
        with tarfile.open(sdist, "r:gz") as archive:
            source_members = archive.getnames()
            assert all(not ("/.git/" in path or "__pycache__" in path or path.endswith((".pyc", ".sty")))
                       for path in source_members)
            for member in archive.getmembers():
                target = (extract_root / member.name).resolve()
                assert target.is_relative_to(extract_root.resolve()) and (member.isfile() or member.isdir())
            try:
                archive.extractall(extract_root, filter="data")
            except TypeError:                       # Python without the tarfile filter parameter
                archive.extractall(extract_root)
        source = extract_root / ("robustband-%s" % VERSION)
        assert (source / "examples/data/evalscope/manifest.json").exists()
        assert (source / "demo/data/Qwen0.5B_cot.jsonl").exists()
        assert (source / "WELCOME.html").exists()
        command([sys.executable, "-S", "submission/build_welcome.py", "build/verified-welcome.html", "--include-lab"], source)
        assert (source / "build/verified-welcome.html").read_text(encoding="utf-8") == (source / "WELCOME.html").read_text(encoding="utf-8")
        command([sys.executable, "-m", "build", "--wheel", "--no-isolation"], source)
        rebuild_location = base / "rebuilt-check"
        rebuild_location.mkdir()
        sdist_check = smoke(source / "dist" / wheel.name, rebuild_location)
        command([str((rebuild_location / "env") / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")),
                 "-S", "experiments/external_cases.py", "--verify", "results/external_cases_%s.json" % VERSION], source)
        command([sys.executable, "-S", "experiments/review_dual_benchmark.py", "--verify",
                 "results/review_dual_held_out_public_1.0.0.json"], source)
        command([sys.executable, "-S", "experiments/resource_grid.py", "--verify",
                 "results/resource_grid_%s.json" % VERSION], source)
        command([sys.executable, "-S", "experiments/check_resource_portability.py"], source)
    report = {"schema": "robustband.distribution_check/v1", "version": VERSION,
              "platform": platform.platform(), "python": platform.python_version(),
              "wheel": {"filename": wheel.name, "sha256": sha256(wheel.read_bytes()).hexdigest(),
                        "bytes": wheel.stat().st_size, "fresh_offline_install": wheel_check},
              "sdist": {"filename": sdist.name, "sha256": sha256(sdist.read_bytes()).hexdigest(),
                        "bytes": sdist.stat().st_size, "members": len(source_members),
                        "rebuilt_wheel_fresh_offline_install": sdist_check,
                        "external_cases_offline_replayed": True, "review_root_proofs_replayed": True,
                        "resource_grid_offline_replayed": True, "lf_crlf_resource_replayed": True},
              "scope": "Build and fresh offline installs on the reported platform, isolated from checkout; no package publication"}
    write_json_atomic(ROOT / "results" / ("distribution_check_%s.json" % VERSION), report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
