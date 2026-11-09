# SPDX-License-Identifier: MIT
"""Standalone ranking reports: shared visuals, pairwise flipping and rank ranges."""
from fractions import Fraction

from .report_style import badge, page, safe, table

VERDICT_TONE = {"STABLE": ("ok", "名次稳健 / stable order"),
                "LEADER-STABLE": ("warn", "第一名稳定、其余随规则变化 / stable leader, moving rest"),
                "SENSITIVE": ("warn", "第一名随规则改变 / rule-sensitive leader")}


def render_matrix(report):
    """Present one ranking audit without collapsing it into a single order."""
    result, models = report["result"], report["models"]
    tone, tone_label = VERDICT_TONE.get(result["verdict"], ("neutral", result["verdict"]))
    body = ("<div class='rh'><span class='mark'>r</span><span class='brand'>robustband</span>"
            "<span class='ver'>v" + safe(report["software_version"]) + "</span>"
            "<span class='kicker'>排名审计 / ranking audit</span></div>")
    body += "<h1>名次会不会因为评分规则而改变？ / Does the order survive the rules?</h1>"
    body += ("<div class='hero'>" + badge(tone_label, tone) +
             "<p class='lede'>" + safe(result["explanation"]) + "</p>" +
             "<p class='small muted'>模型 / Models: " + safe(", ".join(models)) + "</p></div>")
    body += ("<div class='stats'>"
             "<div class='stat'><b>" + safe(result["n_models"]) + "</b><span>模型 / Models</span></div>"
             "<div class='stat'><b>" + safe(result["n_items"]) + "</b><span>共享样本 / Shared samples</span></div>"
             "<div class='stat'><b>" + safe(result["n_protocols"]) + "</b><span>评分协议 / Protocols</span></div>"
             "<div class='stat'><b>" + safe(result["flipping_pairs"]) + "</b><span>翻转的两两比较 / Flipping pairs</span></div>"
             "<div class='stat'><b>" + safe(result["n_reaching_first"]) + "</b><span>曾排第一的模型 / Reach first</span></div></div>")
    rows = [[model, result["rank_floor"][model], result["rank_ceiling"][model],
             result["first_place_counts"][model], result["n_protocols"]] for model in models]
    body += ("<h2>名次范围 / Rank range</h2>" +
             table(["模型 / Model", "最好名次 / Best", "最差名次 / Worst",
                    "第一名协议数 / First-place protocols", "协议总数 / Protocols"], rows))
    body += "<h2>两两比较 / Pairwise comparisons</h2>"
    lookup = {frozenset((row["model_a"], row["model_b"])): row for row in report["pairs"]}

    def pair_cell(model, other):
        if model == other:
            return "—"
        row = lookup[frozenset((model, other))]
        # Pairs are built in input order, so ``model_a`` is the earlier column and the
        # stored band is already oriented as "earlier minus later".
        lo, hi = (Fraction(value) for value in row["exact_band"])
        if lo < 0 < hi:
            label = "翻转 / flips "
        elif hi == 0:
            label = "含并列 / ties "
        elif lo >= 0:
            label = "领先 / ahead "
        else:
            label = "落后 / behind "
        return label + "[" + str(lo) + ", " + str(hi) + "]"

    pair_table = [[model] + [pair_cell(model, other) for other in models] for model in models]
    body += table(["模型 / Model"] + models, pair_table,
                  caption="区间 = 列顺序在前者 − 后者（定向差值）。 / Range = earlier column minus later column, oriented.")
    ranking = [[row["protocol"]] + [str(row["ranks"][model]) for model in models] for row in report["protocols"]]
    body += ("<h2>逐条协议的名次 / Ranking per protocol</h2>" +
             table(["协议 / Protocol"] + models, ranking))
    body += ("<h2>范围与诊断 / Scope and diagnostics</h2><div class='scope'><ul>" +
             "".join("<li>" + safe(n) + "</li>" for n in report["warnings"] + report["limits"]) +
             "</ul></div>")
    body += ("<h2>可复算 / Reproduction</h2><p class='small'>版本 / Version: " +
             safe(report["software_version"]) + " · 输入 SHA256 / input: <code>" +
             safe(report["input_sha256"]) + "</code></p>")
    body += ("<p class='small'>用同一版本执行 <code>python -m robustband verify report.json</code> "
             "可复算全部名次与两两区间。 / Recompute every rank and pair with "
             "<code>python -m robustband verify report.json</code>.</p>")
    body += ("<footer><p>robustband · MIT · 零运行时依赖 / zero runtime dependencies</p>"
             "<p>名次结论以声明的协议与提供的记录为条件 / The order is conditional on the declared protocols and supplied records.</p></footer>")
    return page("robustband ranking audit · " + str(result["verdict"]), body, lang="zh")
