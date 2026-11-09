# SPDX-License-Identifier: MIT
"""Actual loopback requests and CLI gates; no external services or browser needed."""
from copy import deepcopy
import http.client
import json
import runpy
import sys
import time

import pytest
from robustband import cli, local_ui
from robustband.workflow import DEMO_CSV, DEFAULT_FAMILY, verify_report
from robustband.segmentation import DEMO_JSONL, verify_segmentation_report
from robustband.scores import DEMO_CSV as SCORES_CSV
from robustband.domains import verify_audit


def request(server, path, payload=None, headers=None, method=None):
    client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    actual = {"X-Robustband-Token": server.token, "Content-Type": "application/json"}
    actual.update(headers or {})
    body = json.dumps(payload).encode() if payload is not None else None
    client.request(method or ("GET" if payload is None else "POST"), path, body, actual)
    response = client.getresponse()
    status, response_headers, data = response.status, dict(response.getheaders()), response.read()
    client.close()
    return status, response_headers, data


def test_page_preview_audit_and_stop_use_the_same_engine(server):
    status, headers, page = request(server, "/")
    assert status == 200 and b"Run example" in page and "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-store"
    status, _, options = request(server, "/api/options")
    assert json.loads(options)["defaults"] == DEFAULT_FAMILY
    payload = {"text": DEMO_CSV, "format": "csv"}
    status, _, body = request(server, "/api/preview", payload)
    assert status == 200 and json.loads(body)["n_items"] == 1
    payload["family"] = deepcopy(DEFAULT_FAMILY)
    status, _, body = request(server, "/api/audit", payload)
    result = json.loads(body)
    assert status == 200 and result["report"]["result"]["exact_band"] == ["-1", "1"]
    assert verify_report(result["report"]) and "&gt;" in result["html"]
    status, _, body = request(server, "/api/stop", {})
    assert status == 200 and json.loads(body)["stopped"]
    # The client can read the acknowledgement before the server thread reaches
    # its finally block. Require the stop flag within a bounded interval.
    deadline = time.monotonic() + 1
    while not server.stop_requested and time.monotonic() < deadline:
        time.sleep(0.001)
    assert server.stop_requested


def test_segmentation_mode_and_lossless_json_export(server):
    payload = {"text": DEMO_JSONL, "mode": "segmentation", "family":
               {"classes": [1], "aggregations": ["pooled", "image_mean"], "empty_classes": ["zero"]}}
    status, _, body = request(server, "/api/preview", payload)
    assert status == 200 and json.loads(body)["n_classes"] == 2
    status, _, body = request(server, "/api/audit", payload)
    result = json.loads(body)
    assert status == 200 and verify_segmentation_report(json.loads(result["json"]))
    assert result["report"]["result"]["exact_band"] == ["-49/51", "1/3"]
    large = [{"sample_id": "huge", "confusion_a": [[2**53+1, 0], [0, 1]], "confusion_b": [[2**53+1, 0], [1, 0]]}]
    payload["text"] = json.dumps(large[0])
    status, _, body = request(server, "/api/audit", payload)
    result = json.loads(body)
    assert status == 200 and json.loads(result["json"])["inputs"][0]["confusion_a"][0][0] == 2**53+1
    assert verify_segmentation_report(json.loads(result["json"]))
    assert request(server, "/api/preview", {"mode": "unknown", "text": DEMO_JSONL})[0] == 400


def test_generic_numeric_domain_http_contract(server):
    payload = {"mode":"scores", "text":SCORES_CSV}
    status, _, body = request(server, "/api/preview", payload)
    assert status == 200 and json.loads(body)["measurement"]["direction"] == "lower"
    status, _, body = request(server, "/api/audit", payload)
    report = json.loads(body)
    assert status == 200 and verify_audit(json.loads(report["json"]))
    assert report["report"]["result"]["exact_band"] == ["-8/3", "1"]
    assert "A &lt; B" in report["html"]


@pytest.mark.parametrize("headers", [
    {"X-Robustband-Token": "wrong"}, {"X-Robustband-Token": ""},
    {"Origin": "https://other.invalid"}, {"Host": "other.invalid"},
])
def test_cross_origin_and_missing_session_are_rejected(server, headers):
    assert request(server, "/api/audit", {"text": DEMO_CSV}, headers)[0] == 403


def test_unknown_routes_and_host(server):
    assert request(server, "/", headers={"Host": "other.invalid"})[0] == 403
    assert request(server, "/../private-file")[0] == 404
    assert request(server, "/api/unknown", {})[0] == 404


def test_incomplete_upload_times_out_without_blocking_later_requests(server, monkeypatch):
    monkeypatch.setattr(local_ui, "READ_TIMEOUT", 0.05)
    status, _, body = request(server, "/api/audit", headers={"Content-Length": "4"}, method="POST")
    assert status == 400 and "timed out" in json.loads(body)["error"]
    assert request(server, "/api/options")[0] == 200


@pytest.mark.parametrize("payload,headers,match", [
    ({}, {}, "CSV header"), ([], {}, "JSON object"),
    ({"text": DEMO_CSV}, {"Content-Type": "text/plain"}, "Content-Type"),
    ({"text": DEMO_CSV}, {"Content-Length": "bad"}, "invalid literal"),
    ({"text": DEMO_CSV}, {"Content-Length": "0"}, "upload limit"),
    ({"text": DEMO_CSV}, {"Content-Length": str(local_ui.MAX_REQUEST_BYTES + 1)}, "upload limit"),
    ({"text": DEMO_CSV, "family": {}}, {}, "Declare"),
])
def test_input_errors_are_actionable_http_responses(server, payload, headers, match):
    # Rejected length headers are answered before reading a body. Sending extra
    # unread bytes can make Windows reset the connection before the response.
    status, _, body = request(server, "/api/audit", None if "Content-Length" in headers else payload, headers, method="POST")
    assert status == 400 and match in json.loads(body)["error"]


def test_cli_example_template_audit_replay_and_exit_codes(tmp_path, capsys):
    csv = tmp_path / "paired.csv"
    assert cli.main(["template", str(csv)]) == 0
    assert csv.read_text(encoding="utf-8") == DEMO_CSV
    assert cli.main(["demo", "--output", str(tmp_path / "demo")]) == 0
    output = tmp_path / "audit"
    assert cli.main(["audit", str(csv), "--output", str(output), "--require-robust"]) == 1
    assert cli.main(["verify", str(output / "report.json")]) == 0
    assert cli.main(["audit", str(csv), "--parses", "last_num", "--output", str(output), "--require-robust"]) == 0
    assert "VERIFY PASS" in capsys.readouterr().out
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    report["result"]["exact_band"] = ["0", "0"]
    (output / "report.json").write_text(json.dumps(report), encoding="utf-8")
    assert cli.main(["verify", str(output / "report.json")]) == 2
    assert cli.main(["audit", str(tmp_path / "missing.csv")]) == 2
    assert "Error:" in capsys.readouterr().err


def test_ui_command_validates_ports_and_closes_on_interrupt(monkeypatch, capsys):
    assert cli.main(["ui", "--port", "65536"]) == 2
    opened = []
    class FakeServer:
        server_port = 12345
        token = "session"
        stop_requested = False
        closed = False
        def handle_request(self):
            raise KeyboardInterrupt
        def server_close(self):
            self.closed = True
    fake = FakeServer()
    monkeypatch.setattr(local_ui, "create_server", lambda port, edition="generalized": fake)
    monkeypatch.setattr(local_ui.webbrowser, "open", opened.append)
    assert cli.main(["ui"]) == 0 and fake.closed
    assert opened == ["http://127.0.0.1:12345/#session"]
    assert cli.main(["ui", "--no-browser"]) == 0 and len(opened) == 1
    fake.stop_requested = True
    assert local_ui.run_ui(open_browser=False) == 0
    assert "Data stays on this machine" in capsys.readouterr().out


def test_cli_checks_input_size_before_loading(tmp_path, monkeypatch, capsys):
    path = tmp_path / "oversized.csv"
    path.write_text(DEMO_CSV, encoding="utf-8")
    monkeypatch.setattr(cli, "MAX_BYTES", 1)
    assert cli.main(["audit", str(path)]) == 2
    assert "exceeds 4 MiB" in capsys.readouterr().err


def test_module_help_is_an_installed_entrypoint(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["robustband", "--help"])
    with pytest.raises(SystemExit) as exit:
        runpy.run_module("robustband.__main__", run_name="__main__")
    assert exit.value.code == 0
