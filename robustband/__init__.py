# SPDX-License-Identifier: MIT
"""robustband：已归档模型输出的计分协议审计与结论稳健带。
接口：evaluate(preds, family, claim) -> Band；证书见 certificate.emit。
"""
__version__ = "1.0.3"

from .parsers import PARSE
from .metrics import METRIC
from .aggregate import AGG
from .claim import RankClaim, ScoreClaim
from .core import Perturbation, build_family, score_table, evaluate, Band
from . import certificate
from . import rational
from . import matrix
from .adapter import BenchmarkAdapter, JSONLAdapter, InMemoryAdapter
from .evalscope import EvalScopeAdapter

__all__ = [
    "PARSE", "METRIC", "AGG",
    "RankClaim", "ScoreClaim",
    "Perturbation", "build_family", "score_table", "evaluate", "Band",
    "certificate", "rational", "matrix",
    "BenchmarkAdapter", "JSONLAdapter", "InMemoryAdapter",
    "EvalScopeAdapter",
]
