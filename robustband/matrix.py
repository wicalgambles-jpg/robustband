# SPDX-License-Identifier: MIT
"""Ranking audits for more than two archived result sets.

A paired audit answers "does A beat B under every declared rule?". Real leaderboards
ask a second question: "does the *order* survive the rules?". This module reads one
long table (one row per sample and model), scores every model under every declared
protocol, ranks the models per protocol and reports which pairs flip and which models
reach first place under some rule.

Input (CSV or JSONL): ``sample_id, model, gold, output`` plus optional ``prompt``,
``class`` and ``len_bucket``. Every model must cover exactly the same sample ids with
the same reference answer, so a ranking is always computed on one shared sample.
"""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path

from . import __version__
from .aggregate import AGG
from .audit_engine import LIMITS, exact
from .core import build_family
from .input_utils import MAX_BYTES, MAX_ROWS, read_table
from .metrics import METRIC
from .parsers import PARSE
from .rational import item_correct_and_certain, score_frac

REQUIRED = ("sample_id", "model", "gold", "output")
GROUPS = {"macro_class": "class", "macro_len": "len_bucket"}
MAX_MODELS = 8
DEFAULT_FAMILY = {"parses": ["first_num", "last_num"], "metrics": ["exact_match"], "aggs": ["micro"]}
SCHEMA = "robustband.matrix_audit/v1"
DEMO_CSV = ("sample_id,model,gold,output\n"
            "q1,cot,42,the answer is 7 but really 42\n"
            "q1,plain,42,42 no wait 7\n"
            "q1,exact,42,42\n")
EXPLANATIONS = {
    "STABLE": "Every declared protocol produces the same ranking of these models.",
    "LEADER-STABLE": "The first place is stable; the order below it depends on the declared protocol.",
    "SENSITIVE": "Which model leads depends on the declared protocol.",
}


def _normalize(rows):
    """Validate the long table and return (models, samples, rows)."""
    normalized, seen, models, sample_order = [], set(), [], []
    for number, row in enumerate(rows, 1):
        if number > MAX_ROWS:
            raise ValueError("Use at most %d measurement rows per ranking audit; split the file or use the Python API."
                             % MAX_ROWS)
        if not isinstance(row, dict) or not set(REQUIRED) <= row.keys():
            raise ValueError("Record %d needs fields: %s." % (number, ", ".join(REQUIRED)))
        sample = row["sample_id"]
        if type(sample) not in (str, int) or not str(sample).strip():
            raise ValueError("Record %d needs a nonempty sample_id." % number)
        sample = str(sample)
        model = row["model"]
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Record %d needs a nonempty model name." % number)
        model = model.strip()
        gold = row["gold"]
        if not isinstance(gold, str) or not gold.strip():
            raise ValueError("Record %d: gold must be a nonempty string." % number)
        output = row["output"]
        if not isinstance(output, str):
            raise ValueError("Record %d: output must be a string." % number)
        key = (sample, model)
        if key in seen:
            raise ValueError("Record %d repeats sample %s for model %s." % (number, sample, model))
        seen.add(key)
        record = {"sample_id": sample, "model": model, "gold": gold, "output": output}
        for column in ("prompt",) + tuple(GROUPS.values()):
            value = row.get(column, "")
            if type(value) not in (str, int):
                raise ValueError("Record %d: %s must be a string or integer." % (number, column))
            record[column] = str(value)
        if model not in models:
            models.append(model)
        if sample not in sample_order:
            sample_order.append(sample)
        normalized.append(record)
    if not normalized:
        raise ValueError("The input has no measurement rows.")
    if len(models) < 2:
        raise ValueError("A ranking audit needs at least two models.")
    if len(models) > MAX_MODELS:
        raise ValueError("Use at most %d models per ranking audit; split the comparison." % MAX_MODELS)
    by_sample = {sample: {} for sample in sample_order}
    for record in normalized:
        by_sample[record["sample_id"]][record["model"]] = record
    for sample in sample_order:
        present = by_sample[sample]
        if len(present) != len(models):
            missing = [model for model in models if model not in present]
            raise ValueError("Sample %s is missing models: %s. Every model must cover the same samples."
                             % (sample, ", ".join(missing)))
        golds = {present[model]["gold"] for model in models}
        if len(golds) != 1:
            raise ValueError("Sample %s has different reference answers across models." % sample)
        for column in GROUPS.values():
            values = {present[model][column] for model in models}
            if len(values) != 1:
                raise ValueError("Sample %s has inconsistent %s labels across models." % (sample, column))
    return models, sample_order, normalized, by_sample


def load_long(text, format="csv"):
    """Read the long measurement table; preserve outputs and reject ambiguous rows."""
    return _normalize(read_table(text, format, REQUIRED, MAX_BYTES, MAX_ROWS))


def preview_matrix(rows):
    models, samples, normalized, by_sample = _normalize(rows)
    return {"n_models": len(models), "n_items": len(samples), "models": models,
            "empty_outputs": {model: sum(not by_sample[sample][model]["output"].strip() for sample in samples)
                              for model in models},
            "group_fields_complete": {column: all(row[column].strip() for row in normalized)
                                      for column in GROUPS.values()}}


def _protocols(settings):
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


def _ranks(scores, models):
    """Competition ranking: equal scores share the best rank they could occupy."""
    return {model: 1 + sum(1 for other in models if scores[other] > scores[model]) for model in models}


def _pair(name_a, name_b, margins):
    lo, hi = min(margins), max(margins)
    supports = sum(margin > 0 for margin in margins)
    verdict = "ROBUST" if lo > 0 else "REFUTED" if hi <= 0 else "UNIDENTIFIABLE"
    return {"model_a": name_a, "model_b": name_b, "exact_band": [exact(lo), exact(hi)],
            "verdict": verdict, "support_count": supports, "n_protocols": len(margins),
            "tie_count": sum(margin == 0 for margin in margins),
            "reverse_count": sum(margin < 0 for margin in margins),
            "flips": lo < 0 < hi}


def analyze_matrix(rows, family=None, models=None):
    """Score every model under every protocol, then rank and compare all pairs."""
    all_models, samples, normalized, by_sample = _normalize(rows)
    selected = all_models if models is None else list(models)
    if len(selected) < 2 or len(set(selected)) != len(selected) or any(model not in all_models for model in selected):
        raise ValueError("Choose at least two distinct models present in the input.")
    settings = DEFAULT_FAMILY if family is None else family
    protocols = _protocols(settings)
    settings = {key: list(value) for key, value in settings.items()}
    metas = {sample: {column: by_sample[sample][selected[0]][column] for column in GROUPS.values()}
             for sample in samples}
    for agg in settings["aggs"]:
        if agg in GROUPS and any(not metas[sample][GROUPS[agg]].strip() for sample in samples):
            raise ValueError("%s requires a nonempty %s field on every record." % (agg, GROUPS[agg]))
    items = {model: [(by_sample[sample][model]["output"], by_sample[sample][model]["gold"], metas[sample])
                     for sample in samples] for model in selected}
    meta_list = [metas[sample] for sample in samples]
    pairs = dict.fromkeys((protocol.parse, protocol.metric) for protocol in protocols)
    corrects = {(model, pair): item_correct_and_certain(items[model], *pair)[0]
                for model in selected for pair in pairs}

    protocol_rows, warnings = [], []
    rank_vectors, leader_sets = set(), set()
    first_place = {model: 0 for model in selected}
    for protocol in protocols:
        pair = (protocol.parse, protocol.metric)
        scores = {model: score_frac(corrects[(model, pair)], meta_list, protocol.agg) for model in selected}
        ranks = _ranks(scores, selected)
        rank_vectors.add(tuple(ranks[model] for model in selected))
        leader_sets.add(frozenset(model for model in selected if ranks[model] == 1))
        for model in selected:
            if ranks[model] == 1:
                first_place[model] += 1
        if all(score == 0 for score in scores.values()):
            warnings.append("%s scores every model zero; inspect its suitability." % protocol)
        protocol_rows.append({"protocol": str(protocol), "exact_scores": {m: exact(scores[m]) for m in selected},
                              "ranks": ranks})
    pair_rows = []
    for index, name_a in enumerate(selected):
        for name_b in selected[index + 1:]:
            margins = [Fraction(protocol["exact_scores"][name_a]) - Fraction(protocol["exact_scores"][name_b])
                       for protocol in protocol_rows]
            pair_rows.append(_pair(name_a, name_b, margins))
    if len(rank_vectors) == 1:
        verdict = "STABLE"
    elif len(leader_sets) == 1:
        verdict = "LEADER-STABLE"
    else:
        verdict = "SENSITIVE"
    reach_first = [model for model in selected if first_place[model]]
    empty = {model: sum(not by_sample[sample][model]["output"].strip() for sample in samples)
             for model in selected}
    for model in selected:
        if empty[model]:
            warnings.append("Model %s has %d empty outputs; they stay in the audit." % (model, empty[model]))
    if len(pair_rows) > 1 and any(row["flips"] for row in pair_rows):
        flips = sum(row["flips"] for row in pair_rows)
        warnings.append("%d of %d model pairs reverse direction under some declared protocol." % (flips, len(pair_rows)))
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    root = Path(__file__).parent
    sources = ("matrix.py", "core.py", "parsers.py", "metrics.py", "aggregate.py", "rational.py", "input_utils.py")
    return {"schema": SCHEMA, "software_version": __version__,
            "claim": {"kind": "ranking", "models": [m for m in selected]},
            "family": settings, "models": [m for m in selected], "inputs": normalized,
            "input_sha256": sha256(encoded).hexdigest(),
            "source_sha256_lf": {name: sha256((root / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                 for name in dict.fromkeys((*sources, "audit_engine.py"))},
            "result": {"n_models": len(selected), "n_items": len(samples), "n_protocols": len(protocols),
                       "verdict": verdict, "explanation": EXPLANATIONS[verdict],
                       "n_reaching_first": len(reach_first), "models_reaching_first": reach_first,
                       "first_place_counts": first_place,
                       "rank_floor": {m: min(row["ranks"][m] for row in protocol_rows) for m in selected},
                       "rank_ceiling": {m: max(row["ranks"][m] for row in protocol_rows) for m in selected},
                       "flipping_pairs": sum(row["flips"] for row in pair_rows)},
            "protocols": protocol_rows, "pairs": pair_rows, "warnings": warnings,
            "limits": list(LIMITS) + [
                "Rankings are computed on one shared sample; a model missing any sample is rejected.",
                "Equal scores share the best rank they could occupy (competition ranking).",
                "Order sensitivity is conditional on the declared protocols and supplied records."]}


def verify_matrix_report(report):
    """Recompute every field from the recorded inputs and protocols."""
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        raise ValueError("Unsupported ranking audit schema.")
    try:
        actual = analyze_matrix(report["inputs"], report["family"], report["models"])
    except (KeyError, TypeError) as exc:
        raise ValueError("Incomplete ranking audit report.") from exc
    if actual != report:
        raise ValueError("Report mismatch: use the recorded software version and unchanged inputs/protocols.")
    return True
