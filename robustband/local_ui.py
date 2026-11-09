# SPDX-License-Identifier: MIT
"""Session-scoped local browser UI; fixed routes and no filesystem API."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as _ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import webbrowser

from . import __version__
from .parsers import PARSE
from .metrics import METRIC
from .aggregate import AGG
from .workflow import DEFAULT_FAMILY, DEMO_CSV, MAX_BYTES
from .report import render_html
from .segmentation import DEMO_JSONL
from .domains import domain_options, get_domain, preview_domain, audit_domain
from .decision import analyze_decision, preview_decision, inspect_columns, validate_plan, EXAMPLE, EXAMPLE_MAPPING, EXAMPLE_PLAN
from .matrix import (DEMO_CSV as MATRIX_DEMO_CSV, DEFAULT_FAMILY as MATRIX_FAMILY, MAX_MODELS as MATRIX_MAX_MODELS,
                     analyze_matrix, load_long as load_matrix, preview_matrix)
from .input_utils import MAX_ROWS, _json_object, _json_constant, _json_depth
from .convert import convert_table

MAX_REQUEST_BYTES = MAX_BYTES * 2 + 8192
READ_TIMEOUT = 10
MAX_CONNECTIONS = 8
MAX_IMPORT_REQUEST_BYTES = 72 * 1024 * 1024


class ThreadingHTTPServer(_ThreadingHTTPServer):
    """Bound accepted workers; excess connections receive an explicit retry."""
    request_queue_size = 16

    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            body = b'{"error":"Local server is busy; retry shortly."}'
            response = (b'HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\n'
                        b'Cache-Control: no-store\r\nConnection: close\r\nRetry-After: 1\r\nContent-Length: '+
                        str(len(body)).encode()+b'\r\n\r\n'+body)
            try:
                # Drain one bounded packet so Windows can deliver the reply
                # without resetting a socket with unread request headers.
                request.settimeout(0.05)
                request.recv(8192)
                request.sendall(response)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class _Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(READ_TIMEOUT)

    def log_message(self, format, *args):
        """Keep model outputs and URLs out of request logs."""

    def _send(self, status, content, type="application/json; charset=utf-8"):
        data = content.encode("utf-8") if isinstance(content, str) else json.dumps(content, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        for name, value in (("Content-Type", type), ("Content-Length", str(len(data))),
                            ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                            ("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'; base-uri 'none'")):
            self.send_header(name, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _host_ok(self):
        return self.headers.get("Host") == "127.0.0.1:%d" % self.server.server_port

    def do_GET(self):
        if not self._host_ok():
            self._send(403, {"error": "Invalid local host."})
        elif self.path == "/":
            self._send(200, Path(__file__).with_name("ui.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/options":
            self._send(200, {"version": __version__, "parses": list(PARSE), "metrics": list(METRIC),
                             "aggs": list(AGG), "defaults": DEFAULT_FAMILY, "example": DEMO_CSV,
                             "segmentation_example": DEMO_JSONL, "matrix_example": MATRIX_DEMO_CSV,
                             "matrix_defaults": MATRIX_FAMILY, "matrix_max_models": MATRIX_MAX_MODELS,
                             "matrix_max_rows": MAX_ROWS,
                             "max_bytes": MAX_BYTES, "domains": domain_options(self.server.edition), "edition": self.server.edition})
        elif self.path == "/decision":
            self._send(200, Path(__file__).with_name("decision.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        elif self.path == "/matrix":
            self._send(200, Path(__file__).with_name("matrix.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/decision/example":
            if self.server.edition == "professional":
                target = {k: v for k, v in EXAMPLE_PLAN["targets"][0].items() if k not in ("metric", "unit", "direction")}
                target.update(family=DEFAULT_FAMILY, threshold="0", reason="Inspect the explicitly selected answer scoring rules.")
                plan = dict(EXAMPLE_PLAN, domain="text", targets=[target], rationale="Synthetic paired-answer example.")
                self._send(200, {"text": DEMO_CSV, "format": "csv", "mapping": None, "plan": plan})
            else:
                self._send(200, {"text": EXAMPLE, "format": "csv", "mapping": EXAMPLE_MAPPING, "plan": EXAMPLE_PLAN})
        else:
            self._send(404, {"error": "Unknown local route."})

    def do_POST(self):
        origin = "http://127.0.0.1:%d" % self.server.server_port
        token = self.headers.get("X-Robustband-Token", "").encode("utf-8")
        if (not self._host_ok() or self.headers.get("Origin", origin) != origin or
                not secrets.compare_digest(token, self.server.token.encode("utf-8"))):
            self._send(403, {"error": "Open the launch URL for this local session."})
            # Authentication is complete. Drain at most one small packet to
            # deliver the rejection on Windows without waiting for an upload.
            try:
                self.connection.settimeout(0.05)
                self.rfile.read1(8192)
            except OSError:
                pass
            return
        if self.path == "/api/import":
            if not self.server.import_slot.acquire(blocking=False):
                self._send(503, {"error": "Another file import is running; retry shortly."})
                try:
                    self.connection.settimeout(0.05)
                    self.rfile.read1(8192)
                except OSError:
                    pass
                return
            try:
                self._post_body(MAX_IMPORT_REQUEST_BYTES)
            finally:
                self.server.import_slot.release()
        else:
            self._post_body(MAX_REQUEST_BYTES)

    def _post_body(self, maximum):
        try:
            if len(self.headers.get_all('Content-Length', [])) != 1 or self.headers.get('Transfer-Encoding'):
                raise ValueError('Send one Content-Length header without Transfer-Encoding.')
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= maximum:
                raise ValueError("Request is empty or exceeds the local upload limit.")
            self.connection.settimeout(READ_TIMEOUT)
            body = self.rfile.read(length)
        except (ValueError, OSError) as exc:
            self._send(400, {"error": str(exc)})
            return
        if self.path == "/api/stop":
            try:
                self._send(200, {"stopped": True})
            finally:
                # The UI loop may exit the process as soon as this flag is set.
                self.server.stop_requested = True
            return
        if self.path not in ("/api/import", "/api/preview", "/api/audit", "/api/convert", "/api/matrix/preview", "/api/matrix/audit",
                             "/api/decision/columns", "/api/decision/preview", "/api/decision/audit", "/api/decision/plan"):
            self._send(404, {"error": "Unknown local route."})
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Send JSON with Content-Type application/json.")
            decoded = body.decode('utf-8')
            _json_depth(decoded)
            payload = json.loads(decoded, object_pairs_hook=_json_object, parse_constant=_json_constant)
            if not isinstance(payload, dict):
                raise ValueError("Request must be a JSON object.")
            if self.path == "/api/import":
                from .import_service import analyze_import
                self._send(200, analyze_import(payload, self.server.edition))
                return
            if self.path == '/api/convert':
                self._send(200, convert_table(payload.get('text',''), payload.get('domain','text'),
                    payload.get('format','csv'), payload.get('output_format','csv'), payload.get('mapping'),
                    self.server.edition, payload.get('allow_extra',False)))
                return
            if self.path.startswith("/api/matrix/"):
                self._matrix(payload)
                return
            if self.path.startswith("/api/decision/"):
                self._decision(payload)
                return
            mode = payload.get("mode", "text")
            get_domain(mode, self.server.edition)
            if self.path == "/api/preview":
                self._send(200, preview_domain(mode, payload.get("text", ""), payload.get("format")))
            else:
                report = audit_domain(mode, payload.get("text", ""), payload.get("format"),
                                      payload.get("family"), payload.get("model_a", "A"), payload.get("model_b", "B"))
                self._send(200, {"report": report, "html": render_html(report),
                                 "json": json.dumps(report, ensure_ascii=False, indent=2) + "\n"})
        except (ValueError, RecursionError) as exc:
            self._send(400, {"error": str(exc)})

    def _matrix(self, payload):
        rows = load_matrix(payload.get("text", ""), payload.get("format", "csv"))[2]
        if self.path.endswith("/preview"):
            self._send(200, preview_matrix(rows))
            return
        report = analyze_matrix(rows, payload.get("family"), payload.get("models"))
        self._send(200, {"report": report, "html": render_html(report),
                         "json": json.dumps(report, ensure_ascii=False, indent=2) + "\n"})

    def _decision(self, payload):
        if self.path.endswith("/plan"):
            self._send(200, validate_plan(payload.get("plan"), self.server.edition))
        elif self.path.endswith("/columns"):
            self._send(200, inspect_columns(payload.get("text", ""), payload.get("format", "csv")))
        elif self.path.endswith("/preview"):
            self._send(200, preview_decision(payload.get("text", ""), payload.get("domain", "scores"),
                payload.get("format", "csv"), payload.get("mapping"), self.server.edition))
        else:
            report = analyze_decision(payload.get("text", ""), payload.get("plan"), payload.get("format", "csv"),
                payload.get("mapping"), payload.get("model_a", "A"), payload.get("model_b", "B"), self.server.edition)
            self._send(200, {"report": report, "html": render_html(report), "json": json.dumps(report, ensure_ascii=False, indent=2)+"\n"})


def create_server(port=0, edition="generalized"):
    """Bind only loopback; the operating system chooses an available default port."""
    domain_options(edition)
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    server.daemon_threads = True
    server.edition = edition
    server.timeout = 0.5
    server.token = secrets.token_urlsafe(32)
    server.stop_requested = False
    server.import_slot = threading.BoundedSemaphore(1)
    return server


def run_ui(port=0, open_browser=True, edition="generalized"):
    """Run until the page's Stop button or a console interrupt, then close the socket."""
    server = create_server(port, edition)
    url = "http://127.0.0.1:%d/#%s" % (server.server_port, server.token)
    print("robustband local UI: " + url, flush=True)
    print("Data stays on this machine. Stop from the page or press Ctrl+C.", flush=True)
    try:
        if open_browser:
            webbrowser.open(url)
        while not server.stop_requested:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
