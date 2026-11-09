# SPDX-License-Identifier: MIT
"""Preview completeness and oriented HTML labels use all supplied evidence."""
import json

import pytest
from robustband import matrix
from robustband.matrix_report import render_matrix
from test_local_ui_cli import request


def rows():
    return [dict(sample_id=sample, model=model, gold="42", output="42",
                 **{"class": "math" if sample == "q1" else "",
                    "len_bucket": "short" if sample == "q1" else ""})
            for sample in ("q1", "q2") for model in ("A", "B")]


@pytest.mark.parametrize("column,agg", [("class", "macro_class"), ("len_bucket", "macro_len")])
def test_preview_completeness_covers_later_samples(column, agg):
    values = rows()
    with pytest.raises(ValueError, match="requires a nonempty"):
        matrix.analyze_matrix(values, {"parses": ["first_num"], "metrics": ["exact_match"], "aggs": [agg]})
    assert matrix.preview_matrix(values)["group_fields_complete"][column] is False
    for row in values:
        row[column] = "complete"
    assert matrix.preview_matrix(values)["group_fields_complete"][column] is True


def test_nonnegative_pair_band_is_never_labeled_behind():
    values = [dict(sample_id="q1", model="A", gold="42", output="42"),
              dict(sample_id="q1", model="B", gold="42", output="42 then 7")]
    report = matrix.analyze_matrix(values)
    # First-number extraction ties; last-number extraction favors A.
    assert report["pairs"][0]["exact_band"] == ["0", "1"]
    assert matrix.verify_matrix_report(report)
    html = render_matrix(report)
    assert "领先 / ahead [0, 1]" in html
    assert "落后 / behind [0, 1]" not in html


def test_http_matrix_preview_reports_incomplete_later_groups(server):
    text = "".join(json.dumps(row) + "\n" for row in rows())
    status, _, body = request(server, "/api/matrix/preview", {"text": text, "format": "jsonl"})
    assert status == 200
    assert json.loads(body)["group_fields_complete"] == {"class": False, "len_bucket": False}
