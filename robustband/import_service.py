# SPDX-License-Identifier: MIT
"""Local file import, analysis and a portable result bundle; no filesystem writes."""
import base64
from hashlib import sha256
from html import escape
import io
import json
from pathlib import Path
import zipfile

from . import __version__
from .domains import audit_domain
from .matrix import analyze_matrix, load_long
from .report import render_html

MAX_ENCODED_FILE = 32 * 1024 * 1024


def analyze_import(payload, edition):
    from .importers import import_files
    sources = payload.get("files")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 2:
        raise ValueError("Choose one paired table or two model-result files.")
    files = []
    for source in sources:
        if (not isinstance(source, dict) or set(source) != {"name", "data"}
                or not isinstance(source["name"], str) or not isinstance(source["data"], str)
                or len(source["data"]) > MAX_ENCODED_FILE):
            raise ValueError("Each file needs a name and base64 data, at most 24 MiB before encoding.")
        try:
            raw = base64.b64decode(source["data"], validate=True)
        except ValueError as exc:
            raise ValueError("Invalid base64 file data.") from exc
        files.append({"name": source["name"], "data": raw})
    result = import_files(files, payload.get("category"), edition, payload.get("domain", "text"))
    if result["mode"] == "matrix":
        report = analyze_matrix(load_long(result["text"], "jsonl")[2], result["family"])
    else:
        report = audit_domain(result["mode"], result["text"], "jsonl", result["family"],
                              result["model_a"], result["model_b"])
    replay = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    manifest = dict(result["manifest"], software_version=__version__,
                    report_json_sha256=sha256(replay.encode("utf-8")).hexdigest(),
                    normalized_jsonl_sha256=sha256(result["text"].encode("utf-8")).hexdigest(),
                    importer_source_sha256_lf={name: sha256(Path(__file__).with_name(name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                              for name in ("importers.py", "import_service.py")})
    provenance = json.dumps(manifest, ensure_ascii=False, indent=2)
    html = render_html(report).replace("</body>", "<section style='padding:24px;max-width:1100px;margin:auto'>"
        "<h2>导入说明 / Import details</h2><p>结果基于下列来源、范围和转换规则。 / "
        "Results use the sources, scope and conversion rules below.</p><pre style='white-space:pre-wrap;overflow-wrap:anywhere'>"
        + escape(provenance) + "</pre></section></body>")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in (("report.json", replay), ("report.html", html),
                              ("paired.jsonl", result["text"]), ("import_manifest.json", provenance + "\n")):
            archive.writestr(name, content.encode("utf-8"))
    return {**result, "manifest": manifest, "report": report, "html": html, "json": replay,
            "bundle_base64": base64.b64encode(buffer.getvalue()).decode("ascii")}
