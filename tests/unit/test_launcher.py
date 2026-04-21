"""Unit tests for blendbridge.client.launcher and BlendBridge.launch() classmethod.

All subprocess and socket interactions are mocked — no real Blender process is spawned.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from unittest.mock import MagicMock, patch, call, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_process():
    """Return a MagicMock simulating a subprocess.Popen instance."""
    proc = MagicMock()
    proc.pid = 12345
    proc.returncode = None
    return proc


def _make_connected_client(host="localhost", port=5555, timeout_ms=5000):
    """Return a BlendBridge instance with a mocked socket (no real ZMQ)."""
    from blendbridge.client.client import BlendBridge
    with patch("zmq.Context") as mock_ctx_cls:
        mock_ctx = MagicMock()
        mock_socket = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.socket.return_value = mock_socket
        mock_socket.recv_json.return_value = {"status": "ok", "id": "x", "result": {}}
        client = BlendBridge(host=host, port=port, timeout_ms=timeout_ms)
        client.connect()
        client._socket = mock_socket
        return client, mock_socket


# ---------------------------------------------------------------------------
# Startup script content tests
# ---------------------------------------------------------------------------

class TestGenerateStartupScript:
    """_generate_startup_script() returns a Python script string with correct content."""

    def test_startup_script_imports_handlers(self):
        from blendbridge.client.launcher import _generate_startup_script
        script = _generate_startup_script(port=5555)
        assert "import addon.handlers" in script

    def test_startup_script_calls_start_server_with_port(self):
        from blendbridge.client.launcher import _generate_startup_script
        script = _generate_startup_script(port=7777)
        assert "start_server" in script
        assert "7777" in script

    def test_startup_script_imports_server_module(self):
        from blendbridge.client.launcher import _generate_startup_script
        script = _generate_startup_script(port=5555)
        assert "server" in script

    def test_startup_script_has_poll_loop(self):
        from blendbridge.client.launcher import _generate_startup_script
        script = _generate_startup_script(port=5555)
        assert "_poll()" in script

    def test_startup_script_port_injected_correctly(self):
        from blendbridge.client.launcher import _generate_startup_script
        script_5555 = _generate_startup_script(port=5555)
        script_9999 = _generate_startup_script(port=9999)
        assert "5555" in script_5555
        assert "9999" in script_9999
        # Cross-check: wrong port not in wrong script
        assert "9999" not in script_5555
        assert "5555" not in script_9999


# ---------------------------------------------------------------------------
# launcher.launch() low-level function tests
# ---------------------------------------------------------------------------

class TestLaunchFunction:
    """launcher.launch() manages process and temp script creation."""

    def test_launch_raises_rpc_connection_error_when_no_blender_path(self, monkeypatch):
        """launch() raises RPCConnectionError when blender_path is None and BLENDER_PATH unset."""
        from blendbridge.client.launcher import launch
        from blendbridge.client.exceptions import RPCConnectionError
        monkeypatch.delenv("BLENDER_PATH", raising=False)
        with pytest.raises(RPCConnectionError):
            launch()

    def test_launch_uses_env_var_when_param_is_none(self, monkeypatch, tmp_path):
        """launch() reads BLENDER_PATH env var when blender_path param is None."""
        from blendbridge.client.launcher import launch
        fake_blender = str(tmp_path / "blender.exe")
        monkeypatch.setenv("BLENDER_PATH", fake_blender)

        mock_proc = _make_mock_process()
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            process, script_path = launch(blender_path=None, port=5555)
            assert mock_popen.called
            cmd = mock_popen.call_args[0][0]
            assert cmd[0] == fake_blender
        # Cleanup
        if script_path.exists():
            script_path.unlink()

    def test_launch_uses_explicit_blender_path(self, monkeypatch, tmp_path):
        """launch() uses provided blender_path over env var."""
        from blendbridge.client.launcher import launch
        fake_blender = str(tmp_path / "explicit_blender")
        env_blender = str(tmp_path / "env_blender")
        monkeypatch.setenv("BLENDER_PATH", env_blender)

        mock_proc = _make_mock_process()
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            process, script_path = launch(blender_path=fake_blender, port=5555)
            cmd = mock_popen.call_args[0][0]
            assert cmd[0] == fake_blender
        if script_path.exists():
            script_path.unlink()

    def test_launch_spawns_with_background_and_python_flags(self, tmp_path, monkeypatch):
        """launch() calls Popen with --background --python <script_path>."""
        from blendbridge.client.launcher import launch
        fake_blender = str(tmp_path / "blender")
        monkeypatch.setenv("BLENDER_PATH", fake_blender)

        mock_proc = _make_mock_process()
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            process, script_path = launch(port=5555)
            cmd = mock_popen.call_args[0][0]
            assert "--background" in cmd
            assert "--python" in cmd
            # The script path should follow --python
            python_idx = cmd.index("--python")
            assert cmd[python_idx + 1] == str(script_path)
        if script_path.exists():
            script_path.unlink()

    def test_launch_writes_temp_script_with_py_suffix(self, tmp_path, monkeypatch):
        """launch() writes startup script to a .py temp file."""
        from blendbridge.client.launcher import launch
        fake_blender = str(tmp_path / "blender")
        monkeypatch.setenv("BLENDER_PATH", fake_blender)

        mock_proc = _make_mock_process()
        with patch("subprocess.Popen", return_value=mock_proc):
            process, script_path = launch(port=5555)
            assert script_path.suffix == ".py"
            assert script_path.exists()
        # Cleanup
        if script_path.exists():
            script_path.unlink()

    def test_launch_returns_popen_instance_and_script_path(self, tmp_path, monkeypatch):
        """launch() returns a (Popen, Path) tuple."""
        from blendbridge.client.launcher import launch
        fake_blender = str(tmp_path / "blender")
        monkeypatch.setenv("BLENDER_PATH", fake_blender)

        mock_proc = _make_mock_process()
        with patch("subprocess.Popen", return_value=mock_proc):
            result = launch(port=5555)
            process, script_path = result
            assert process is mock_proc
            assert isinstance(script_path, pathlib.Path)
        if script_path.exists():
            script_path.unlink()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only flag test")
    def test_launch_uses_create_no_window_flag_on_windows(self, tmp_path, monkeypatch):
        """On Windows, launch() passes CREATE_NO_WINDOW to Popen."""
        from blendbridge.client.launcher import launch
        fake_blender = str(tmp_path / "blender.exe")
        monkeypatch.setenv("BLENDER_PATH", fake_blender)

        mock_proc = _make_mock_process()
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            process, script_path = launch(port=5555)
            kwargs = mock_popen.call_args[1]
            assert kwargs.get("creationflags") == subprocess.CREATE_NO_WINDOW
        if script_path.exists():
            script_path.unlink()


# ---------------------------------------------------------------------------
# BlendBridge.launch() classmethod tests
# ---------------------------------------------------------------------------

class TestBlendBridgeLaunchClassmethod:
    """BlendBridge.launch() returns a connected client with _process set."""

    def _setup_launch(self, monkeypatch, ping_side_effect=None, blender_path="/fake/blender"):
        """Patch launcher and ZMQ so launch() runs without real processes or sockets."""
        from blendbridge.client import BlendBridge

        mock_proc = _make_mock_process()
        fake_script = pathlib.Path("/tmp/fake_startup.py")

        # Patch the low-level launch function
        mock_launch = MagicMock(return_value=(mock_proc, fake_script))
        monkeypatch.setattr(
            "blendbridge.client.launcher.launch",
            mock_launch,
        )

        # Patch ZMQ context and socket
        mock_socket = MagicMock()
        if ping_side_effect is not None:
            mock_socket.recv_json.side_effect = ping_side_effect
        else:
            mock_socket.recv_json.return_value = {"status": "ok", "id": "x", "result": {"pong": True}}

        return mock_proc, fake_script, mock_launch, mock_socket

    def test_launch_classmethod_exists(self):
        from blendbridge.client.client import BlendBridge
        assert hasattr(BlendBridge, "launch")
        assert callable(BlendBridge.launch)

    def test_launch_returns_blendbridge_instance(self, monkeypatch):
        from blendbridge.client.client import BlendBridge
        from blendbridge.client.exceptions import RPCTimeoutError

        mock_proc = _make_mock_process()
        fake_script = pathlib.Path("/tmp/fake_startup.py")

        with patch("blendbridge.client.launcher.launch", return_value=(mock_proc, fake_script)):
            with patch("zmq.Context") as mock_ctx_cls:
                mock_ctx = MagicMock()
                mock_socket = MagicMock()
                mock_ctx_cls.return_value = mock_ctx
                mock_ctx.socket.return_value = mock_socket
                mock_socket.recv_json.return_value = {
                    "status": "ok", "id": "x", "result": {"pong": True}
                }

                client = BlendBridge.launch(blender_path="/fake/blender", port=5555, timeout=5.0)
                assert isinstance(client, BlendBridge)

    def test_launch_sets_process_attribute(self, monkeypatch):
        from blendbridge.client.client import BlendBridge

        mock_proc = _make_mock_process()
        fake_script = pathlib.Path("/tmp/fake_startup.py")

        with patch("blendbridge.client.launcher.launch", return_value=(mock_proc, fake_script)):
            with patch("zmq.Context") as mock_ctx_cls:
                mock_ctx = MagicMock()
                mock_socket = MagicMock()
                mock_ctx_cls.return_value = mock_ctx
                mock_ctx.socket.return_value = mock_socket
                mock_socket.recv_json.return_value = {
                    "status": "ok", "id": "x", "result": {"pong": True}
                }

                client = BlendBridge.launch(blender_path="/fake/blender", port=5555, timeout=5.0)
                assert client._process is mock_proc

    def test_launch_sets_script_path_attribute(self, monkeypatch):
        from blendbridge.client.client import BlendBridge

        mock_proc = _make_mock_process()
        fake_script = pathlib.Path("/tmp/fake_startup.py")

        with patch("blendbridge.client.launcher.launch", return_value=(mock_proc, fake_script)):
            with patch("zmq.Context") as mock_ctx_cls:
                mock_ctx = MagicMock()
                mock_socket = MagicMock()
                mock_ctx_cls.return_value = mock_ctx
                mock_ctx.socket.return_value = mock_socket
                mock_socket.recv_json.return_value = {
                    "status": "ok", "id": "x", "result": {"pong": True}
                }

                client = BlendBridge.launch(blender_path="/fake/blender", port=5555, timeout=5.0)
                assert client._script_path == fake_script

    def test_launch_polls_ping_until_success(self, monkeypatch):
        """launch() retries ping on failure and returns when ping succeeds."""
        from blendbridge.client.client import BlendBridge
        import zmq

        mock_proc = _make_mock_process()
        fake_script = pathlib.Path("/tmp/fake_startup.py")

        # First call: zmq.Again (timeout) — second call: success
        ping_responses = [zmq.Again(), {"status": "ok", "id": "x", "result": {"pong": True}}]

        with patch("blendbridge.client.launcher.launch", return_value=(mock_proc, fake_script)):
            with patch("zmq.Context") as mock_ctx_cls:
                mock_ctx = MagicMock()
                mock_socket = MagicMock()
                mock_ctx_cls.return_value = mock_ctx
                mock_ctx.socket.return_value = mock_socket
                mock_socket.recv_json.side_effect = ping_responses

                with patch("time.sleep"):  # avoid actual sleep
                    client = BlendBridge.launch(
                        blender_path="/fake/blender", port=5555, timeout=5.0
                    )
                assert isinstance(client, BlendBridge)

    def test_launch_raises_rpc_timeout_error_if_ping_never_succeeds(self, monkeypatch):
        """launch() raises RPCTimeoutError if ping never succeeds within timeout."""
        from blendbridge.client.client import BlendBridge
        from blendbridge.client.exceptions import RPCTimeoutError
        import zmq

        mock_proc = _make_mock_process()
        fake_script = pathlib.Path("/tmp/fake_startup.py")

        with patch("blendbridge.client.launcher.launch", return_value=(mock_proc, fake_script)):
            with patch("zmq.Context") as mock_ctx_cls:
                mock_ctx = MagicMock()
                mock_socket = MagicMock()
                mock_ctx_cls.return_value = mock_ctx
                mock_ctx.socket.return_value = mock_socket
                # Always fail with timeout
                mock_socket.recv_json.side_effect = zmq.Again()

                with patch("time.sleep"):
                    with patch("time.monotonic", side_effect=[0.0, 0.0, 0.3]):
                        # monotonic: deadline check (0.0 < 0.0+0.1 timeout), second check past deadline
                        with pytest.raises(RPCTimeoutError):
                            BlendBridge.launch(
                                blender_path="/fake/blender", port=5555, timeout=0.1
                            )

    def test_launch_calls_launcher_with_correct_args(self, monkeypatch):
        """BlendBridge.launch() passes blender_path, port, host, timeout to launcher.launch()."""
        from blendbridge.client.client import BlendBridge

        mock_proc = _make_mock_process()
        fake_script = pathlib.Path("/tmp/fake_startup.py")

        with patch("blendbridge.client.launcher.launch", return_value=(mock_proc, fake_script)) as mock_launch:
            with patch("zmq.Context") as mock_ctx_cls:
                mock_ctx = MagicMock()
                mock_socket = MagicMock()
                mock_ctx_cls.return_value = mock_ctx
                mock_ctx.socket.return_value = mock_socket
                mock_socket.recv_json.return_value = {
                    "status": "ok", "id": "x", "result": {"pong": True}
                }

                BlendBridge.launch(
                    blender_path="/my/blender", port=9999, host="remotehost", timeout=15.0
                )
                mock_launch.assert_called_once_with(
                    blender_path="/my/blender",
                    port=9999,
                    host="remotehost",
                    timeout=15.0,
                    headless=True,
                )


# ---------------------------------------------------------------------------
# close() with process cleanup tests
# ---------------------------------------------------------------------------

class TestBlendBridgeCloseWithProcess:
    """close() terminates spawned Blender process and cleans up temp script."""

    def _make_launched_client(self):
        """Return a BlendBridge with mocked _process and _script_path."""
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        # Mock the socket to avoid real ZMQ
        mock_socket = MagicMock()
        client._socket = mock_socket
        # Simulate a launched client
        mock_proc = _make_mock_process()
        client._process = mock_proc
        fake_script = MagicMock(spec=pathlib.Path)
        client._script_path = fake_script
        return client, mock_proc, fake_script

    def test_close_terminates_process(self):
        from blendbridge.client.client import BlendBridge
        client, mock_proc, fake_script = self._make_launched_client()
        client.close()
        mock_proc.terminate.assert_called_once()

    def test_close_waits_for_process(self):
        from blendbridge.client.client import BlendBridge
        client, mock_proc, fake_script = self._make_launched_client()
        client.close()
        mock_proc.wait.assert_called_once()

    def test_close_clears_process_attribute(self):
        from blendbridge.client.client import BlendBridge
        client, mock_proc, fake_script = self._make_launched_client()
        client.close()
        assert client._process is None

    def test_close_removes_script_file(self):
        from blendbridge.client.client import BlendBridge
        client, mock_proc, fake_script = self._make_launched_client()
        client.close()
        fake_script.unlink.assert_called_once()

    def test_close_clears_script_path_attribute(self):
        from blendbridge.client.client import BlendBridge
        client, mock_proc, fake_script = self._make_launched_client()
        client.close()
        assert client._script_path is None

    def test_close_without_process_does_not_raise(self):
        """close() on a non-launched client (no _process) is idempotent."""
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        # No _process set — should not raise
        client.close()

    def test_exit_calls_close(self):
        """__exit__ ultimately calls close(), which terminates process."""
        from blendbridge.client.client import BlendBridge
        client, mock_proc, fake_script = self._make_launched_client()
        client.__exit__(None, None, None)
        mock_proc.terminate.assert_called_once()

    def test_close_tolerates_script_unlink_oserror(self):
        """close() does not re-raise OSError from script unlink."""
        from blendbridge.client.client import BlendBridge
        client, mock_proc, fake_script = self._make_launched_client()
        fake_script.unlink.side_effect = OSError("permission denied")
        # Should NOT raise
        client.close()
        assert client._script_path is None


# ---------------------------------------------------------------------------
# Ping convenience method tests
# ---------------------------------------------------------------------------

class TestBlendBridgePing:
    """BlendBridge.ping() sends a 'ping' command and returns the result."""

    def test_ping_calls_call_with_ping_command(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        client.call = MagicMock(return_value={"pong": True})
        result = client.ping()
        client.call.assert_called_once_with("ping")

    def test_ping_returns_result(self):
        from blendbridge.client.client import BlendBridge
        client = BlendBridge()
        client.call = MagicMock(return_value={"pong": True})
        result = client.ping()
        assert result == {"pong": True}
