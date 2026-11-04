# SPDX-License-Identifier: MIT
"""R48: every audit entry point rejects silent column loss."""
import json

import pytest
from robustband import cli, convert, workflow
from test_local_ui_cli import request


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_unknown_columns_rejected_and_explicit_conversion_traced(format, tmp_path, capsys):
    row = dict(sample_id="q1", prompt="Q?", gold="42", output_a="42", output_b="7",
               output_c="private content", extra="notes", **{"class": "math", "len_bucket": "short"})
    text = (",".join(row) + "\n" + ",".join(row.values()) + "\n"
            if format == "csv" else json.dumps(row) + "\n")
    for operation in (lambda: workflow.load_paired(text, format),
                      lambda: workflow.analyze([row]), lambda: workflow.preview([row])):
        with pytest.raises(ValueError, match="unrecognized fields: extra, output_c"):
            operation()
    source = tmp_path / ("input." + format)
    source.write_text(text, encoding="utf-8")
    output = tmp_path / "report.json"
    assert cli.main(["audit", str(source), "--format", format, "--output", str(output)]) == 2
    assert not output.exists()
    assert "--allow-extra-columns" in capsys.readouterr().err
    with pytest.raises(ValueError, match="omitted"):
        convert.convert_table(text, "text", format)
    result = convert.convert_table(text, "text", format, allow_extra=True)
    assert result["manifest"]["omitted_columns"] == ["extra", "output_c"]
    assert result["manifest"]["roundtrip_verified"]
    assert "private content" not in result["text"]
    canonical = workflow.load_paired(result["text"], "jsonl")
    assert canonical[0]["class"] == "math" and canonical[0]["len_bucket"] == "short"
    assert workflow.verify_report(workflow.analyze(canonical))
    target = tmp_path / "converted.jsonl"
    assert cli.main(["convert", str(source), "--domain", "text", "--allow-extra-columns", "--output", str(target)]) == 0
    assert json.loads(target.with_name(target.name + ".manifest.json").read_text(encoding="utf-8"))["omitted_columns"] == ["extra", "output_c"]


def test_http_unknown_columns_error_and_explicit_conversion(server):
    text = workflow.DEMO_CSV.replace("output_b\n", "output_b,extra\n").rstrip() + ",note\n"
    for path in ("/api/preview", "/api/audit"):
        status, _, body = request(server, path, {"text": text, "format": "csv"})
        assert status == 400
        assert "unrecognized fields: extra" in json.loads(body)["error"]
    status, _, body = request(server, "/api/convert", {"text": text, "domain": "text", "allow_extra": True})
    assert status == 200
    assert json.loads(body)["manifest"]["omitted_columns"] == ["extra"]
