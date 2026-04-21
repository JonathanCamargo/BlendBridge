"""SRV-03: server lifecycle + _poll contract. SRV-04: malformed JSON. SRV-05: bind error."""
from __future__ import annotations
import json
from unittest.mock import MagicMock
import pytest

import zmq

# The addon.server module imports bpy — conftest stubs it.
server = pytest.importorskip("addon.server")


@pytest.fixture(autouse=True)
def _reset_server_state(monkeypatch):
    # Force-clean the module-level server state between tests.
    monkeypatch.setattr(server, "_socket", None, raising=False)
    monkeypatch.setattr(server, "_ctx", None, raising=False)
    monkeypatch.setattr(server, "_bound_port", None, raising=False)
    yield


def test_is_running_false_when_no_socket():
    assert server.is_running() is False


def test_get_port_none_when_no_socket():
    assert server.get_port() is None


def test_start_server_binds_socket_and_registers_timer(monkeypatch):
    fake_sock = MagicMock()
    fake_ctx = MagicMock()
    fake_ctx.socket.return_value = fake_sock
    monkeypatch.setattr(zmq.Context, "instance", staticmethod(lambda: fake_ctx))

    fake_timers = MagicMock()
    fake_timers.is_registered.return_value = False
    monkeypatch.setattr(server.bpy.app, "timers", fake_timers, raising=False)

    server.start_server(host="*", port=5555)

    fake_sock.bind.assert_called_once_with("tcp://*:5555")
    fake_timers.register.assert_called_once()
    assert server.is_running() is True
    assert server.get_port() == 5555


def test_start_server_bind_error_surfaces_zmq_error(monkeypatch):
    fake_sock = MagicMock()
    fake_sock.bind.side_effect = zmq.ZMQError(zmq.EADDRINUSE, "Address already in use")
    fake_ctx = MagicMock()
    fake_ctx.socket.return_value = fake_sock
    monkeypatch.setattr(zmq.Context, "instance", staticmethod(lambda: fake_ctx))
    monkeypatch.setattr(server.bpy.app, "timers", MagicMock(), raising=False)

    with pytest.raises(zmq.ZMQError):
        server.start_server(host="*", port=5555)
    assert server.is_running() is False


def test_stop_server_closes_socket_and_unregisters_timer(monkeypatch):
    fake_sock = MagicMock()
    fake_timers = MagicMock()
    fake_timers.is_registered.return_value = True
    monkeypatch.setattr(server, "_socket", fake_sock, raising=False)
    monkeypatch.setattr(server, "_bound_port", 5555, raising=False)
    monkeypatch.setattr(server.bpy.app, "timers", fake_timers, raising=False)

    server.stop_server()

    fake_sock.close.assert_called_once()
    fake_timers.unregister.assert_called_once()
    assert server.is_running() is False
    assert server.get_port() is None


def test_poll_returns_float_when_no_message(monkeypatch):
    fake_sock = MagicMock()
    fake_sock.recv.side_effect = zmq.Again()
    monkeypatch.setattr(server, "_socket", fake_sock, raising=False)
    result = server._poll()
    assert isinstance(result, float)
    assert result == server.POLL_INTERVAL


def test_poll_dispatches_valid_message_and_sends_response(monkeypatch):
    from addon import registry
    registry._HANDLERS.clear()
    registry.register_handler("ping", lambda: {"pong": True})

    fake_sock = MagicMock()
    fake_sock.recv.return_value = json.dumps({"id": "1", "command": "ping"}).encode()
    monkeypatch.setattr(server, "_socket", fake_sock, raising=False)

    result = server._poll()

    fake_sock.send_json.assert_called_once()
    sent = fake_sock.send_json.call_args[0][0]
    assert sent["status"] == "ok"
    assert sent["result"] == {"pong": True}
    assert isinstance(result, float)


def test_poll_malformed_json_sends_error_envelope(monkeypatch):
    fake_sock = MagicMock()
    fake_sock.recv.return_value = b"not json at all"
    monkeypatch.setattr(server, "_socket", fake_sock, raising=False)

    result = server._poll()

    fake_sock.send_json.assert_called_once()
    sent = fake_sock.send_json.call_args[0][0]
    assert sent["status"] == "error"
    assert sent["error"]["type"] == "JSONDecodeError"
    assert isinstance(result, float)


def test_poll_handler_exception_still_sends_response(monkeypatch):
    from addon import registry
    registry._HANDLERS.clear()
    def broken():
        raise RuntimeError("kaboom")
    registry.register_handler("broken", broken)

    fake_sock = MagicMock()
    fake_sock.recv.return_value = json.dumps({"id": "1", "command": "broken"}).encode()
    monkeypatch.setattr(server, "_socket", fake_sock, raising=False)

    result = server._poll()

    fake_sock.send_json.assert_called_once()
    sent = fake_sock.send_json.call_args[0][0]
    assert sent["status"] == "error"
    assert sent["error"]["type"] == "RuntimeError"
    assert isinstance(result, float)


def test_poll_returns_float_when_socket_is_none(monkeypatch):
    monkeypatch.setattr(server, "_socket", None, raising=False)
    assert isinstance(server._poll(), float)
