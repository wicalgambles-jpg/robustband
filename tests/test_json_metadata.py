# SPDX-License-Identifier: MIT
"""Exact numeric import must preserve metadata types as well as score values."""
from copy import deepcopy
import json

import pytest
from robustband import convert, decision, scores
from robustband.input_utils import read_table


@pytest.mark.parametrize("column", ["sample_id", "metric", "unit", "group"])
def test_json_numeric_metadata_is_not_coerced_to_text(column):
    row = dict(sample_id="s", score_a="2", score_b="1", metric="accuracy",
               unit="fraction", direction="higher", group="g")
    row[column] = 1.5
    with pytest.raises(ValueError):
        scores.normalize_scores([row])
    with pytest.raises(ValueError):
        scores.load_scores(json.dumps(row), "jsonl")
    with pytest.raises(ValueError):
        convert.convert_table(json.dumps(row), "scores", "jsonl")


@pytest.mark.parametrize("mapped", [False, True])
def test_decision_rejects_numeric_json_group(mapped):
    if mapped:
        row = dict(seed="s", overall_a="2", overall_b="1", human_a="1", human_b="1", cohort=1.5)
        mapping = deepcopy(decision.EXAMPLE_MAPPING)
        mapping["group"] = "cohort"
        plan = decision.EXAMPLE_PLAN
    else:
        row = dict(sample_id="s", score_a="2", score_b="1", metric="mIoU", unit="percent",
                   direction="higher", group=1.5)
        mapping = None
        plan = deepcopy(decision.EXAMPLE_PLAN)
        plan["targets"] = plan["targets"][:1]
    with pytest.raises(ValueError):
        decision.analyze_decision(json.dumps(row), plan, format="jsonl", mapping=mapping)


@pytest.mark.parametrize("a,b,margin", [("9007199254740993.0", "9007199254740992.0", "1"),
    ("1.00000000000000000001", "1.0", "1/100000000000000000000")])
def test_valid_json_number_scores_retain_exact_margin(a, b, margin):
    text = ('{"sample_id":1,"score_a":%s,"score_b":%s,"metric":"count",'
            '"unit":"n","direction":"higher","group":"g"}' % (a, b))
    values = scores.load_scores(text, "jsonl")
    assert values[0]["sample_id"] == "1"
    report = scores.analyze_scores(values)
    assert report["result"]["exact_band"] == [margin, margin]
    assert scores.verify_scores_report(report)
    result = convert.convert_table(text, "scores", "jsonl")
    assert scores.analyze_scores(scores.load_scores(result["text"], "jsonl"))["result"]["exact_band"] == [margin, margin]


def test_decimal_exponent_overflow_is_an_actionable_jsonl_error():
    with pytest.raises(ValueError, match="JSONL line 1"):
        read_table('{"score_a":1e9999999999999999999999999}', "jsonl", exact_decimals=True)
