# SPDX-License-Identifier: MIT
"""Transport preserves Unicode text and CLI exports preserve their own inputs."""
import json

import pytest
from robustband import cli, convert, decision, workflow
from test_local_ui_cli import request


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
def test_jsonl_unicode_separators_are_content_not_record_boundaries(separator, server):
    row = dict(sample_id="q1", prompt="Question" + separator + "continued",
               gold="42", output_a="42", output_b="7")
    text = json.dumps(row, ensure_ascii=False) + "\r\n"
    loaded = workflow.load_paired(text, "jsonl")
    assert loaded[0]["prompt"] == row["prompt"]
    report = workflow.analyze(loaded)
    assert report["result"]["exact_band"] == ["1", "1"]
    assert workflow.verify_report(report)
    csv_text = "sample_id,prompt,gold,output_a,output_b\nq1," + row["prompt"] + ",42,42,7\n"
    converted = convert.convert_table(csv_text)
    assert json.loads(converted["text"])["prompt"] == row["prompt"]
    status, _, body = request(server, "/api/audit", {"text": text, "format": "jsonl"})
    assert status == 200 and json.loads(body)["report"]["result"]["exact_band"] == ["1", "1"]


@pytest.mark.parametrize("name", ["report.json", "report.html"])
def test_cli_audit_cannot_overwrite_its_input(name, tmp_path, capsys):
    row = dict(sample_id="q1", prompt="Question", gold="42", output_a="42", output_b="7")
    source = tmp_path / name
    original = (json.dumps(row) + "\n").encode("utf-8")
    source.write_bytes(original)
    assert cli.main(["audit", str(source), "--format", "jsonl", "--output", str(tmp_path)]) == 2
    assert "source file" in capsys.readouterr().err
    assert source.read_bytes() == original
    assert not (tmp_path / ("report.html" if name == "report.json" else "report.json")).exists()


@pytest.mark.parametrize("sidecar", [False, True])
def test_cli_conversion_preserves_mapping_source_even_with_overwrite(sidecar, tmp_path, capsys):
    source = tmp_path / "paired.csv"
    source.write_text(decision.EXAMPLE, encoding="utf-8")
    target = tmp_path / "converted.jsonl"
    manifest = target.with_name(target.name + ".manifest.json")
    mapping = manifest if sidecar else target
    original = json.dumps(decision.EXAMPLE_MAPPING).encode("utf-8")
    mapping.write_bytes(original)
    assert cli.main(["convert", str(source), "--domain", "scores", "--mapping", str(mapping),
                     "--output", str(target), "--overwrite"]) == 2
    assert "source file" in capsys.readouterr().err
    assert mapping.read_bytes() == original
    assert not (target if sidecar else manifest).exists()
