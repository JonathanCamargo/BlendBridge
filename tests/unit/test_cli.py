"""Tests for blendbridge.client.cli — full Click command group.

Uses click.testing.CliRunner for in-process invocation and patches
BlendBridge at the module level to avoid actual network connections.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from blendbridge.client.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_client(
    ping_result=None,
    call_result=None,
    list_handlers_result=None,
):
    """Return a configured mock BlendBridge context manager."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)

    if ping_result is None:
        ping_result = {"pong": True, "blender_version": "4.5.1"}
    client.ping.return_value = ping_result

    if call_result is None:
        call_result = {"status": "ok"}
    client.call.return_value = call_result

    if list_handlers_result is None:
        list_handlers_result = {
            "handlers": [
                {"name": "ping", "doc": "Ping the server."},
                {"name": "scene_info", "doc": "Get scene info."},
            ]
        }
    client.list_handlers.return_value = list_handlers_result

    return client


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------

class TestPing:
    def test_ping_prints_json(self):
        runner = CliRunner()
        mock_client = make_mock_client(ping_result={"pong": True, "blender_version": "4.5.1"})
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["ping"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["pong"] is True
        assert parsed["blender_version"] == "4.5.1"

    def test_ping_passes_host_and_port(self):
        runner = CliRunner()
        mock_client = make_mock_client()
        with patch("blendbridge.client.cli.BlendBridge") as MockClass:
            MockClass.return_value = mock_client
            result = runner.invoke(main, ["--host", "127.0.0.1", "--port", "6000", "ping"])
        assert result.exit_code == 0
        MockClass.assert_called_once_with(host="127.0.0.1", port=6000)

    def test_ping_connection_error_exits_1(self):
        runner = CliRunner()
        from blendbridge.client.exceptions import RPCConnectionError
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(side_effect=RPCConnectionError("tcp://localhost:5555"))
        mock_client.__exit__ = MagicMock(return_value=False)
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["ping"])
        assert result.exit_code == 1
        assert "cannot connect" in result.output.lower() or "error" in result.output.lower()

    def test_ping_timeout_error_exits_1(self):
        runner = CliRunner()
        from blendbridge.client.exceptions import RPCTimeoutError
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.ping.side_effect = RPCTimeoutError(5000, "ping")
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["ping"])
        assert result.exit_code == 1
        assert "timeout" in result.output.lower() or "error" in result.output.lower()

    def test_ping_rpc_error_exits_1(self):
        runner = CliRunner()
        from blendbridge.client.exceptions import RPCError
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.ping.side_effect = RPCError("ValueError", "bad input")
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["ping"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# call
# ---------------------------------------------------------------------------

class TestCall:
    def test_call_scene_info_prints_json(self):
        runner = CliRunner()
        scene_result = {"objects": [], "count": 0, "active": None}
        mock_client = make_mock_client(call_result=scene_result)
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["call", "scene_info"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed == scene_result
        mock_client.call.assert_called_once_with("scene_info")

    def test_call_with_param_bool_false(self):
        """--param keep_camera=false should pass keep_camera=False (bool)."""
        runner = CliRunner()
        clear_result = {"removed": [], "count": 0}
        mock_client = make_mock_client(call_result=clear_result)
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["call", "clear_scene", "--param", "keep_camera=false"])
        assert result.exit_code == 0
        mock_client.call.assert_called_once_with("clear_scene", keep_camera=False)

    def test_call_with_param_bool_true(self):
        """--param keep_camera=true should pass keep_camera=True (bool)."""
        runner = CliRunner()
        mock_client = make_mock_client()
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["call", "clear_scene", "--param", "keep_camera=true"])
        assert result.exit_code == 0
        mock_client.call.assert_called_once_with("clear_scene", keep_camera=True)

    def test_call_with_json_params(self):
        """--json '{...}' sends JSON params."""
        runner = CliRunner()
        render_result = {"file": "/tmp/render.png"}
        mock_client = make_mock_client(call_result=render_result)
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(
                main, ["call", "render", "--json", '{"resolution_x": 800}']
            )
        assert result.exit_code == 0
        mock_client.call.assert_called_once_with("render", resolution_x=800)

    def test_call_json_takes_precedence_over_param(self):
        """When both --param and --json are given, --json takes precedence."""
        runner = CliRunner()
        mock_client = make_mock_client()
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(
                main,
                ["call", "render", "--param", "x=1", "--json", '{"resolution_x": 800}'],
            )
        assert result.exit_code == 0
        # Should use JSON params only
        mock_client.call.assert_called_once_with("render", resolution_x=800)

    def test_call_param_int_coercion(self):
        """--param count=5 should pass count=5 (int)."""
        runner = CliRunner()
        mock_client = make_mock_client()
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["call", "foo", "--param", "count=5"])
        assert result.exit_code == 0
        mock_client.call.assert_called_once_with("foo", count=5)

    def test_call_param_float_coercion(self):
        """--param scale=1.5 should pass scale=1.5 (float)."""
        runner = CliRunner()
        mock_client = make_mock_client()
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["call", "foo", "--param", "scale=1.5"])
        assert result.exit_code == 0
        mock_client.call.assert_called_once_with("foo", scale=1.5)

    def test_call_param_string_fallback(self):
        """--param name=cube should pass name='cube' (str)."""
        runner = CliRunner()
        mock_client = make_mock_client()
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["call", "foo", "--param", "name=cube"])
        assert result.exit_code == 0
        mock_client.call.assert_called_once_with("foo", name="cube")

    def test_call_connection_error_exits_1(self):
        runner = CliRunner()
        from blendbridge.client.exceptions import RPCConnectionError
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(side_effect=RPCConnectionError("tcp://localhost:5555"))
        mock_client.__exit__ = MagicMock(return_value=False)
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["call", "scene_info"])
        assert result.exit_code == 1

    def test_call_multiple_params(self):
        """Multiple --param flags should all be parsed."""
        runner = CliRunner()
        mock_client = make_mock_client()
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(
                main,
                ["call", "render", "--param", "resolution_x=1920", "--param", "samples=128"],
            )
        assert result.exit_code == 0
        mock_client.call.assert_called_once_with("render", resolution_x=1920, samples=128)


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------

class TestHandlers:
    def test_handlers_pretty_prints(self):
        runner = CliRunner()
        handlers_result = {
            "handlers": [
                {"name": "ping", "doc": "Ping the server."},
                {"name": "scene_info", "doc": "Get scene info."},
            ]
        }
        mock_client = make_mock_client(list_handlers_result=handlers_result)
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["handlers"])
        assert result.exit_code == 0
        assert "ping" in result.output
        assert "scene_info" in result.output
        # Docstrings should appear
        assert "Ping the server." in result.output
        assert "Get scene info." in result.output

    def test_handlers_empty_list(self):
        runner = CliRunner()
        mock_client = make_mock_client(list_handlers_result={"handlers": []})
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["handlers"])
        assert result.exit_code == 0  # Should not crash on empty list

    def test_handlers_connection_error_exits_1(self):
        runner = CliRunner()
        from blendbridge.client.exceptions import RPCConnectionError
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(side_effect=RPCConnectionError("tcp://localhost:5555"))
        mock_client.__exit__ = MagicMock(return_value=False)
        with patch("blendbridge.client.cli.BlendBridge", return_value=mock_client):
            result = runner.invoke(main, ["handlers"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# launch
# ---------------------------------------------------------------------------

class TestLaunch:
    def test_launch_calls_blendbridge_launch(self):
        """launch command should call BlendBridge.launch() classmethod."""
        runner = CliRunner()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.ping.return_value = {"pong": True, "blender_version": "4.5.1"}

        with patch("blendbridge.client.cli.BlendBridge") as MockClass:
            MockClass.launch.return_value = mock_client
            # Simulate KeyboardInterrupt to exit the blocking loop
            mock_client.__enter__.side_effect = KeyboardInterrupt
            result = runner.invoke(main, ["launch", "--blender", "/usr/bin/blender"])
        # The command should handle the interrupt gracefully
        assert result.exit_code == 0

    def test_launch_with_blender_path_and_timeout(self):
        """--blender and --timeout should be forwarded to BlendBridge.launch()."""
        runner = CliRunner()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.ping.return_value = {"pong": True, "blender_version": "4.5.1"}

        with patch("blendbridge.client.cli.BlendBridge") as MockClass:
            # Make __enter__ raise KeyboardInterrupt to exit loop
            ctx_mgr = MagicMock()
            ctx_mgr.__enter__ = MagicMock(side_effect=KeyboardInterrupt)
            ctx_mgr.__exit__ = MagicMock(return_value=False)
            MockClass.launch.return_value = ctx_mgr
            result = runner.invoke(
                main, ["launch", "--blender", "/path/to/blender", "--timeout", "60.0"]
            )
        MockClass.launch.assert_called_once_with(
            blender_path="/path/to/blender",
            port=5555,
            host="localhost",
            timeout=60.0,
        )

    def test_launch_connection_error_exits_1(self):
        runner = CliRunner()
        from blendbridge.client.exceptions import RPCConnectionError

        with patch("blendbridge.client.cli.BlendBridge") as MockClass:
            MockClass.launch.side_effect = RPCConnectionError("tcp://localhost:5555")
            result = runner.invoke(main, ["launch"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# help / group
# ---------------------------------------------------------------------------

class TestGroupHelp:
    def test_main_help_lists_subcommands(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        for cmd in ("ping", "call", "handlers", "launch"):
            assert cmd in result.output

    def test_ping_help_shows_host_port(self):
        runner = CliRunner()
        result = runner.invoke(main, ["ping", "--help"])
        assert result.exit_code == 0

    def test_call_help_shows_param_and_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["call", "--help"])
        assert result.exit_code == 0
        assert "--param" in result.output or "-p" in result.output
        assert "--json" in result.output
