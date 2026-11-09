# SPDX-License-Identifier: MIT
"""Actual local imports enforce authentication, budgets and replayable bundles."""
import base64
from hashlib import sha256
import io
import json
from unittest.mock import Mock
import zipfile

import pytest
from robustband import import_service, local_ui, workflow
from test_local_ui_cli import request


def payload(name="paired.csv", data=workflow.DEMO_CSV):
    return {"files": [{"name": name, "data": base64.b64encode(data.encode("utf-8")).decode("ascii")}]}


def test_actual_import_returns_analysis_and_complete_bundle(server):
    status, _, body = request(server, "/api/import", payload("<script>.csv"))
    result = json.loads(body)
    assert status == 200 and result["mode"] == "text"
    assert result["report"]["result"]["exact_band"] == ["-1", "1"]
    assert workflow.verify_report(json.loads(result["json"]))
    assert "&lt;script&gt;.csv" in result["html"] and "<script>.csv" not in result["html"]
    assert result["manifest"]["report_json_sha256"] == sha256(result["json"].encode()).hexdigest()
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(result["bundle_base64"]))) as archive:
        assert set(archive.namelist()) == {"report.json", "report.html", "paired.jsonl", "import_manifest.json"}
        assert archive.read("report.json").decode() == result["json"]
        assert archive.read("paired.jsonl").decode() == result["text"]


@pytest.mark.parametrize("value", [{}, {"files": []}, {"files": [{"name": "x"}]},
    {"files": [False]}, {"files": [{"name": "x", "data": 0}]},
    {"files": [{"name": "x.csv", "data": "%%%"}]}])
def test_invalid_import_is_actionable_and_slot_recovers(server, value):
    assert request(server, "/api/import", value)[0] == 400
    assert request(server, "/api/import", payload())[0] == 200


def test_import_specific_size_limit_and_encoded_file_limit(server, monkeypatch):
    monkeypatch.setattr(import_service, "MAX_ENCODED_FILE", 2)
    status, _, body = request(server, "/api/import", payload())
    assert status == 400 and "24 MiB" in json.loads(body)["error"]
    monkeypatch.setattr(local_ui, "MAX_IMPORT_REQUEST_BYTES", 2)
    status, _, body = request(server, "/api/import", headers={"Content-Length": "3"}, method="POST")
    assert status == 400 and "upload limit" in json.loads(body)["error"]


def test_import_slot_is_after_authentication_and_releases(server):
    assert request(server, "/api/import", payload(), {"X-Robustband-Token": "wrong"})[0] == 403
    assert server.import_slot.acquire(False)
    try:
        assert request(server, "/api/import", {})[0] == 503
    finally:
        server.import_slot.release()
    assert request(server, "/api/import", payload())[0] == 200


def test_import_busy_disconnected_upload_is_bounded():
    handler = object.__new__(local_ui._Handler)
    handler.path = "/api/import"
    handler.server = Mock(server_port=123, token="token")
    handler.server.import_slot.acquire.return_value = False
    handler.headers = {"Host": "127.0.0.1:123", "X-Robustband-Token": "token"}
    handler._send = Mock()
    handler.connection = Mock()
    handler.rfile = Mock()
    handler.rfile.read1.side_effect = TimeoutError("not uploading")
    handler.do_POST()
    assert handler._send.call_args.args[0] == 503
    handler.rfile.read1.assert_called_once_with(8192)


def test_matrix_import_produces_ranking_and_standard_replay(server):
    value = payload("ranking.tsv", "sample_id\tmodel\tgold\toutput\nq1,A,42,42\n".replace(",", "\t") + "q1\tB\t42\t7\n")
    status, _, body = request(server, "/api/import", value)
    assert status == 200
    result = json.loads(body)
    assert result["mode"] == "matrix" and result["report"]["result"]["n_models"] == 2
