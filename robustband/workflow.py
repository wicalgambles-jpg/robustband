# SPDX-License-Identifier: MIT
"""Validated paired inputs and exact, replayable audits for every user entry point."""
from .audit_engine import assemble, validate_names, STRICT_RANK_EXPLANATIONS as EXPLANATIONS, LIMITS
from .input_utils import MAX_BYTES, MAX_ROWS, read_table
from .core import build_family
from .parsers import PARSE
from .metrics import METRIC
from .aggregate import AGG
from .rational import item_correct_and_certain, score_frac

REQUIRED = ("sample_id", "prompt", "gold", "output_a", "output_b")
GROUPS = {"macro_class": "class", "macro_len": "len_bucket"}
DEFAULT_FAMILY = {"parses": ["first_num", "last_num"],
                  "metrics": ["exact_match"], "aggs": ["micro"]}
DEMO_CSV = ('sample_id,prompt,gold,output_a,output_b\n'
            'example-1,What is 6 times 7?,42,the answer is 7 but really 42,the answer is 42 but really 7\n')
def _normalize(rows, allow_extra=False):
    normalized, seen = [], set()
    for number, row in enumerate(rows, 1):
        if number > MAX_ROWS:
            raise ValueError("Use at most %d paired records per audit; split the file or use the Python API." % MAX_ROWS)
        if not isinstance(row, dict) or not set(REQUIRED) <= row.keys():
            raise ValueError("Record %d needs fields: %s." % (number, ", ".join(REQUIRED)))
        extra = set(row) - set(REQUIRED) - set(GROUPS.values())
        if extra and not allow_extra:
            raise ValueError("Record %d has unrecognized fields: %s. Remove them, correct the column names, "
                             "or use convert --allow-extra-columns to record omitted columns in a manifest."
                             % (number, ", ".join(sorted(map(str, extra)))))
        identity = row["sample_id"]
        if type(identity) not in (str, int) or not str(identity).strip():
            raise ValueError("Record %d needs a nonempty string or integer sample_id." % number)
        identity = str(identity)
        if identity in seen:
            raise ValueError("Record %d has duplicate sample_id: %s." % (number, identity))
        seen.add(identity)
        result = {"sample_id": identity}
        for key in REQUIRED[1:]:
            value = row[key]
            if not isinstance(value, str) or (key in ("prompt", "gold") and not value.strip()):
                raise ValueError("Record %d: %s must be %sstring." %
                                 (number, key, "a nonempty " if key in ("prompt", "gold") else "a "))
            result[key] = value
        for key in GROUPS.values():
            value = row.get(key, "")
            if type(value) not in (str, int):
                raise ValueError("Record %d: %s must be a string or integer." % (number, key))
            result[key] = str(value)
        normalized.append(result)
    if not normalized:
        raise ValueError("The input has no paired records. Start with the example template.")
    return normalized


def load_paired(text, format="csv", *, allow_extra=False):
    """Read one paired table; preserve outputs and reject ambiguous schemas."""
    return _normalize(read_table(text, format, REQUIRED, MAX_BYTES, MAX_ROWS), allow_extra)


def _family(settings):
    if not isinstance(settings, dict) or set(settings) != set(DEFAULT_FAMILY):
        raise ValueError("Declare parses, metrics and aggs in the protocol family.")
    for key, registry in (("parses", PARSE), ("metrics", METRIC), ("aggs", AGG)):
        values = settings[key]
        if (not isinstance(values, list) or not values or
                any(not isinstance(v, str) or v not in registry for v in values)):
            raise ValueError("Choose at least one supported option for " + key + ".")
        if len(set(values)) != len(values):
            raise ValueError("Duplicate protocol option in " + key + ".")
    return build_family(**settings)


def preview(rows):
    """Return structural diagnostics before the user chooses a scoring family."""
    rows = _normalize(rows)
    return {"n_items": len(rows), "records": rows[:5],
            "group_fields_complete": {key: all(r[key].strip() for r in rows) for key in GROUPS.values()},
            "empty_outputs": {key: sum(not r[key].strip() for r in rows) for key in ("output_a", "output_b")}}


def analyze(rows, family=None, model_a="A", model_b="B"):
    """Use the library's exact item scorers/aggregators, caching each score vector."""
    rows = _normalize(rows)
    validate_names(model_a, model_b)
    settings = DEFAULT_FAMILY if family is None else family
    protocols = _family(settings)
    settings = {key: list(value) for key, value in settings.items()}
    for agg in settings["aggs"]:
        if agg in GROUPS and any(not r[GROUPS[agg]].strip() for r in rows):
            raise ValueError("%s requires a nonempty %s field on every record." % (agg, GROUPS[agg]))
    metas = [{k: row[k] for k in GROUPS.values()} for row in rows]
    items = {side: [(row[side], row["gold"], meta) for row, meta in zip(rows, metas)]
             for side in ("output_a", "output_b")}
    pairs = dict.fromkeys((h.parse, h.metric) for h in protocols)
    scores = {(side, pair): item_correct_and_certain(items[side], *pair)[0]
              for side in items for pair in pairs}
    configurations = []
    for h in protocols:
        pair = (h.parse, h.metric)
        a, b = (score_frac(scores[(side, pair)], metas, h.agg) for side in items)
        margin = a - b
        configurations.append({"protocol": str(h), "score_a": str(a), "score_b": str(b),
                               "margin": str(margin), "supports": margin > 0,
                               "all_zero": not any(any(scores[(side, pair)]) for side in items)})
    warnings = []
    zero_count = sum(c["all_zero"] for c in configurations)
    if zero_count:
        warnings.append("%d protocols score every output zero on both sides; inspect their suitability." % zero_count)
    empty = preview(rows)["empty_outputs"]
    if any(empty.values()):
        warnings.append("Empty model outputs are retained: A=%d, B=%d." % tuple(empty.values()))
    sources = ("workflow.py", "core.py", "parsers.py", "metrics.py", "aggregate.py", "rational.py", "input_utils.py")
    return assemble("robustband.audit/v1", rows, settings, model_a, model_b,
                    configurations, sources, warnings, list(LIMITS), EXPLANATIONS)


def verify_report(report):
    """Recompute all fields, including input/source bindings; require matching version."""
    if not isinstance(report, dict) or report.get("schema") != "robustband.audit/v1":
        raise ValueError("Unsupported audit report schema.")
    try:
        actual = analyze(report["inputs"], report["family"],
                         report["claim"]["model_a"], report["claim"]["model_b"])
    except (KeyError, TypeError) as exc:
        raise ValueError("Incomplete audit report.") from exc
    if actual != report:
        raise ValueError("Report mismatch: use the recorded software version and unchanged inputs/protocols.")
    return True
