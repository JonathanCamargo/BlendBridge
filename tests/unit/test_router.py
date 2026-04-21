"""SRV-02: dispatch contract + error envelope shape. SRV-04: handler exception."""
from __future__ import annotations
import pytest

registry = pytest.importorskip("addon.registry")
router = pytest.importorskip("addon.router")


def setup_function():
    registry._HANDLERS.clear()


def test_dispatch_ok_envelope_for_known_command():
    registry.register_handler("ping", lambda: {"pong": True})
    resp = router.dispatch({"id": "abc", "command": "ping", "params": {}})
    assert resp == {"status": "ok", "id": "abc", "result": {"pong": True}}


def test_dispatch_ok_with_kwargs():
    registry.register_handler("echo", lambda value=None: {"echoed": value})
    resp = router.dispatch({"id": "1", "command": "echo", "params": {"value": 42}})
    assert resp["status"] == "ok"
    assert resp["result"] == {"echoed": 42}


def test_dispatch_unknown_command_returns_error_envelope():
    resp = router.dispatch({"id": "x", "command": "nonexistent"})
    assert resp["status"] == "error"
    assert resp["id"] == "x"
    assert resp["error"]["type"] == "NotFound"
    assert "nonexistent" in resp["error"]["message"]


def test_dispatch_missing_command_field():
    resp = router.dispatch({"id": "x"})
    assert resp["status"] == "error"
    assert resp["error"]["type"] == "ValueError"
    assert "command" in resp["error"]["message"].lower()


def test_dispatch_non_dict_message():
    resp = router.dispatch("not a dict")
    assert resp["status"] == "error"
    assert resp["error"]["type"] == "TypeError"


def test_dispatch_handler_exception_captured_with_traceback():
    def broken():
        raise ValueError("boom")
    registry.register_handler("broken", broken)
    resp = router.dispatch({"id": "x", "command": "broken"})
    assert resp["status"] == "error"
    assert resp["error"]["type"] == "ValueError"
    assert resp["error"]["message"] == "boom"
    assert "Traceback" in resp["error"]["traceback"]


def test_dispatch_omits_id_gracefully_when_missing():
    registry.register_handler("ping", lambda: {"pong": True})
    resp = router.dispatch({"command": "ping"})
    assert resp["status"] == "ok"
    assert resp["id"] == ""
