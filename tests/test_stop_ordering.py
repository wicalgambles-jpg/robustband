# SPDX-License-Identifier: MIT
"""A valid stop request must finish its acknowledgement before allowing exit."""
import http.client

import pytest
from robustband import local_ui
from test_local_ui_cli import request


def test_stop_response_is_sent_before_stop_flag(server, monkeypatch):
    original = local_ui._Handler._send
    observed = []

    def check(handler, status, content, *args):
        if handler.path == "/api/stop":
            observed.append(handler.server.stop_requested)
        return original(handler, status, content, *args)

    monkeypatch.setattr(local_ui._Handler, "_send", check)
    status, _, body = request(server, "/api/stop", {})
    assert status == 200 and b'"stopped": true' in body
    assert observed == [False]


def test_valid_stop_still_stops_if_reply_connection_is_gone(server, monkeypatch):
    original = local_ui._Handler._send

    def fail(handler, status, content, *args):
        if handler.path == "/api/stop":
            raise BrokenPipeError("client disconnected")
        return original(handler, status, content, *args)

    monkeypatch.setattr(local_ui._Handler, "_send", fail)
    monkeypatch.setattr(server, "handle_error", lambda *args: None)
    with pytest.raises((http.client.RemoteDisconnected, ConnectionResetError)):
        request(server, "/api/stop", {})
    assert server.stop_requested
