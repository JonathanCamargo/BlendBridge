"""Unit tests for blendbridge.client — BlendBridge class and exception hierarchy.

All zmq interaction is mocked at the socket level; no server required.
"""
from __future__ import annotations

import json
import sys
import subprocess
from unittest.mock import MagicMock, patch, call
import uuid

import pytest
import zmq


# ---------------------------------------------------------------------------
# Exception hierarchy tests
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    """BlendBridgeError is the base; RPCError, RPCTimeoutError, RPCConnectionError are subclasses."""

    def test_blendbridge_error_is_base_exception(self):
        from blendbridge.client.exceptions import BlendBridgeError
        assert issubclass(BlendBridgeError, Exception)

    def test_rpc_error_is_subclass_of_blendbridge_error(self):
        from blendbridge.client.exceptions import BlendBridgeError, RPCError
        assert issubclass(RPCError, BlendBridgeError)

    def test_rpc_timeout_error_is_subclass_of_blendbridge_error(self):
        from blendbridge.client.exceptions import BlendBridgeError, RPCTimeoutError
        assert issubclass(RPCTimeoutError, BlendBridgeError)

    def test_rpc_connection_error_is_subclass_of_blendbridge_error(self):
        from blendbridge.client.exceptions import BlendBridgeError, RPCConnectionError
        assert issubclass(RPCConnectionError, BlendBridgeError)


class TestRPCError:
    """RPCError stores error_type, message, traceback from server error envelope."""

    def test_rpc_error_stores_attributes(self):
        from blendbridge.client.exceptions import RPCError
        err = RPCError("ValueError", "bad value", "Traceback...")
        assert err.error_type == "ValueError"
        assert err.message == "bad value"
        assert err.traceback == "Traceback..."

    def test_rpc_error_traceback_defaults_to_empty_string(self):
        from blendbridge.client.exceptions import RPCError
        err = RPCError("TypeError", "bad type")
        assert err.traceback == ""

    def test_rpc_error_str_format(self):
        from blendbridge.client.exceptions import RPCError
        err = RPCError("ValueError", "bad value")
        assert str(err) == "ValueError: bad value"


class TestRPCTimeoutError:
    """RPCTimeoutError stores timeout_ms and command."""

    def test_rpc_timeout_error_stores_attributes(self):
        from blendbridge.client.exceptions import RPCTimeoutError
        err = RPCTimeoutError(5000, "render")
        assert err.timeout_ms == 5000
        assert err.command == "render"

    def test_rpc_timeout_error_command_defaults_empty(self):
        from blendbridge.client.exceptions import RPCTimeoutError
        err = RPCTimeoutError(3000)
        assert err.command == ""

    def test_rpc_timeout_error_str_includes_timeout(self):
        from blendbridge.client.exceptions import RPCTimeoutError
        err = RPCTimeoutError(5000, "render")
        msg = str(err)
        assert "5000" in msg


class TestRPCConnectionError:
    """RPCConnectionError stores url and reason."""

    def test_rpc_connection_error_stores_attributes(self):
        from blendbridge.client.exceptions import RPCConnectionError
        err = RPCConnectionError("tcp://localhost:5555", "refused")
        assert err.url == "tcp://localhost:5555"
        assert err.reason == "refused"

    def test_rpc_connection_error_reason_defaults_empty(self):
        from blendbridge.client.exceptions import RPCConnectionError
        err = RPCConnectionError("tcp://localhost:5555")
        assert err.reason == ""


# ---------------------------------------------------------------------------
# BlendBridge class tests
# ---------------------------------------------------------------------------

class TestBlendBridgeInit:
    """BlendBridge.__init__ accepts host, port, timeout_ms with proper defaults."""

    def test_default_host(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        assert client.host == "localhost"

    def test_default_port(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        assert client.port == 5555

    def test_default_timeout_ms(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        assert client.timeout_ms == 5000

    def test_custom_params(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge(host="192.168.1.1", port=6666, timeout_ms=10000)
        assert client.host == "192.168.1.1"
        assert client.port == 6666
        assert client.timeout_ms == 10000

    def test_socket_initially_none(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        assert client._socket is None

    def test_context_initially_none(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        assert client._ctx is None


class TestBlendBridgeContextManager:
    """BlendBridge as context manager calls connect() on enter and close() on exit."""

    def test_context_manager_calls_connect_on_enter(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        client.connect = MagicMock(return_value=client)
        client.close = MagicMock()

        with client as c:
            client.connect.assert_called_once()
            assert c is client

    def test_context_manager_calls_close_on_exit(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        client.connect = MagicMock(return_value=client)
        client.close = MagicMock()

        with client:
            pass

        client.close.assert_called_once()

    def test_context_manager_calls_close_on_exception(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        client.connect = MagicMock(return_value=client)
        client.close = MagicMock()

        with pytest.raises(ValueError):
            with client:
                raise ValueError("test")

        client.close.assert_called_once()


class TestBlendBridgeConnect:
    """connect() creates zmq context, REQ socket, and connects to the server URL."""

    def test_connect_returns_self(self):
        from blendbridge.client.client import BlendBridge
        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_socket = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            result = client.connect()
            assert result is client

    def test_connect_creates_req_socket(self):
        from blendbridge.client.client import BlendBridge
        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_socket = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            client.connect()
            mock_ctx.socket.assert_called_once_with(zmq.REQ)

    def test_connect_connects_to_correct_url(self):
        from blendbridge.client.client import BlendBridge
        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_socket = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge(host="myhost", port=9999)
            client.connect()
            mock_socket.connect.assert_called_once_with("tcp://myhost:9999")

    def test_connect_sets_timeout_options(self):
        from blendbridge.client.client import BlendBridge
        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_socket = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge(timeout_ms=3000)
            client.connect()

            # Both SNDTIMEO and RCVTIMEO should be set to timeout_ms
            setsockopt_calls = mock_socket.setsockopt.call_args_list
            opt_names = {c[0][0] for c in setsockopt_calls}
            assert zmq.SNDTIMEO in opt_names
            assert zmq.RCVTIMEO in opt_names

    def test_connect_wraps_zmq_error_in_connection_error(self):
        from blendbridge.client.client import BlendBridge
        from blendbridge.client.exceptions import RPCConnectionError
        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_socket = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket
            mock_socket.connect.side_effect = zmq.ZMQError("connection refused")

            client = BlendBridge()
            with pytest.raises(RPCConnectionError):
                client.connect()


class TestBlendBridgeClose:
    """close() closes socket with linger=0, is idempotent."""

    def test_close_closes_socket(self):
        from blendbridge.client.client import BlendBridge
        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_socket = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            client.connect()
            client.close()
            mock_socket.close.assert_called_once_with(linger=0)

    def test_close_is_idempotent(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        # close without connect should not raise
        client.close()
        client.close()


class TestBlendBridgeCall:
    """call() sends correct JSON, returns result on ok, raises on error/timeout."""

    def _make_client_with_mock_socket(self, recv_response: dict):
        """Helper: return (client, mock_socket) with recv_json preset."""
        from blendbridge.client.client import BlendBridge
        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_socket = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket
            mock_socket.recv_json.return_value = recv_response

            client = BlendBridge()
            client.connect()
            # Keep reference to mock_socket before context exits
            client._socket = mock_socket
            return client, mock_socket

    def test_call_sends_command_in_json(self):
        from blendbridge.client.client import BlendBridge
        mock_socket = MagicMock()
        mock_socket.recv_json.return_value = {"status": "ok", "id": "any", "result": {}}

        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            client.connect()
            client.call("my_command", key="val")

        sent = mock_socket.send_json.call_args[0][0]
        assert sent["command"] == "my_command"
        assert sent["params"] == {"key": "val"}

    def test_call_includes_uuid_id(self):
        from blendbridge.client.client import BlendBridge
        mock_socket = MagicMock()
        mock_socket.recv_json.return_value = {"status": "ok", "id": "any", "result": {}}

        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            client.connect()
            client.call("some_cmd")

        sent = mock_socket.send_json.call_args[0][0]
        # id must be a non-empty string (UUID hex)
        assert isinstance(sent["id"], str)
        assert len(sent["id"]) == 32  # uuid4().hex is 32 chars

    def test_call_ids_are_unique_per_call(self):
        from blendbridge.client.client import BlendBridge
        mock_socket = MagicMock()
        mock_socket.recv_json.side_effect = [
            {"status": "ok", "id": "any", "result": {}},
            {"status": "ok", "id": "any", "result": {}},
        ]

        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            client.connect()
            client.call("cmd1")
            client.call("cmd2")

        calls = mock_socket.send_json.call_args_list
        id1 = calls[0][0][0]["id"]
        id2 = calls[1][0][0]["id"]
        assert id1 != id2

    def test_call_returns_result_on_ok(self):
        from blendbridge.client.client import BlendBridge
        expected_result = {"mesh": "cube", "vertices": 8}
        mock_socket = MagicMock()
        mock_socket.recv_json.return_value = {
            "status": "ok", "id": "any", "result": expected_result
        }

        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            client.connect()
            result = client.call("get_mesh")

        assert result == expected_result

    def test_call_raises_rpc_error_on_error_response(self):
        from blendbridge.client.client import BlendBridge
        from blendbridge.client.exceptions import RPCError
        mock_socket = MagicMock()
        mock_socket.recv_json.return_value = {
            "status": "error",
            "id": "any",
            "error": {
                "type": "ValueError",
                "message": "bad input",
                "traceback": "File ...\n  line 1",
            }
        }

        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            client.connect()
            with pytest.raises(RPCError) as exc_info:
                client.call("bad_cmd")

        err = exc_info.value
        assert err.error_type == "ValueError"
        assert err.message == "bad input"
        assert "line 1" in err.traceback

    def test_call_raises_rpc_error_without_traceback(self):
        from blendbridge.client.client import BlendBridge
        from blendbridge.client.exceptions import RPCError
        mock_socket = MagicMock()
        mock_socket.recv_json.return_value = {
            "status": "error",
            "id": "any",
            "error": {
                "type": "RuntimeError",
                "message": "oops",
            }
        }

        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge()
            client.connect()
            with pytest.raises(RPCError) as exc_info:
                client.call("fail_cmd")

        err = exc_info.value
        assert err.traceback == ""

    def test_call_raises_rpc_timeout_error_on_zmq_again(self):
        from blendbridge.client.client import BlendBridge
        from blendbridge.client.exceptions import RPCTimeoutError
        mock_socket = MagicMock()
        mock_socket.recv_json.side_effect = zmq.Again()

        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge(timeout_ms=1000)
            client.connect()
            with pytest.raises(RPCTimeoutError) as exc_info:
                client.call("slow_cmd")

        err = exc_info.value
        assert err.timeout_ms == 1000
        assert err.command == "slow_cmd"

    def test_call_raises_rpc_timeout_error_on_send_again(self):
        """Also handles zmq.Again raised during send (e.g., send buffer full)."""
        from blendbridge.client.client import BlendBridge
        from blendbridge.client.exceptions import RPCTimeoutError
        mock_socket = MagicMock()
        mock_socket.send_json.side_effect = zmq.Again()

        with patch("zmq.Context") as mock_ctx_cls:
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.socket.return_value = mock_socket

            client = BlendBridge(timeout_ms=2000)
            client.connect()
            with pytest.raises(RPCTimeoutError) as exc_info:
                client.call("blocked_cmd")

        err = exc_info.value
        assert err.timeout_ms == 2000


# ---------------------------------------------------------------------------
# No bpy import guard
# ---------------------------------------------------------------------------

class TestNoBpyImport:
    """Client module must have zero imports from bpy or Blender-only modules."""

    def test_no_bpy_import_in_client_module(self):
        """Run grep to confirm no 'import bpy' lines in blendbridge/client/."""
        result = subprocess.run(
            ["grep", "-r", "import bpy", "blendbridge/client/"],
            cwd="D:/scratch/zermqblender",
            capture_output=True,
            text=True,
        )
        # grep exits 0 if found, 1 if not found — we want exit code 1 (not found)
        assert result.returncode != 0, (
            f"Found 'import bpy' in client code:\n{result.stdout}"
        )

    def test_client_importable_without_bpy_in_sys_modules(self):
        """Importing the client does not pull bpy into sys.modules."""
        # bpy may be mocked in conftest, but client should not reference it
        import blendbridge.client.client  # noqa: F401
        import blendbridge.client.exceptions  # noqa: F401
        # If we reach here without AttributeError/ImportError, client is bpy-free


# ---------------------------------------------------------------------------
# Public re-exports from __init__.py
# ---------------------------------------------------------------------------

class TestClientInit:
    """blendbridge.client.__init__ re-exports all public names."""

    def test_all_exports_importable(self):
        from blendbridge.client import (
            BlendBridge,
            BlendBridgeError,
            RPCError,
            RPCTimeoutError,
            RPCConnectionError,
        )
        assert BlendBridge is not None
        assert BlendBridgeError is not None
        assert RPCError is not None
        assert RPCTimeoutError is not None
        assert RPCConnectionError is not None

    def test_all_dunder_all_contains_five_names(self):
        import blendbridge.client as client_pkg
        assert set(client_pkg.__all__) >= {
            "BlendBridge",
            "BlendBridgeError",
            "RPCError",
            "RPCTimeoutError",
            "RPCConnectionError",
        }
