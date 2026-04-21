"""BlendBridge client — connects to a running BlendBridge server over ZMQ REQ/REP.

This module is intentionally free of any bpy or Blender-only imports so it
can be used from any external Python process without a Blender installation.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import zmq

from .exceptions import RPCConnectionError, RPCError, RPCTimeoutError


class BlendBridge:
    """ZMQ REQ client for a BlendBridge server.

    Usage (context manager — recommended)::

        with BlendBridge(host="localhost", port=5555) as rpc:
            result = rpc.call("list_handlers")

    Usage (manual lifecycle)::

        rpc = BlendBridge()
        rpc.connect()
        try:
            result = rpc.call("ping")
        finally:
            rpc.close()

    Parameters
    ----------
    host:
        Hostname or IP of the BlendBridge server. Default ``"localhost"``.
    port:
        TCP port the server is bound to. Default ``5555``.
    timeout_ms:
        Send and receive timeout in milliseconds. Default ``5000``.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5555,
        timeout_ms: int = 5000,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self._ctx: zmq.Context | None = None
        self._socket: zmq.Socket | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> "BlendBridge":
        """Open a ZMQ REQ socket and connect to the server.

        Returns
        -------
        BlendBridge
            *self*, so callers can chain: ``rpc = BlendBridge().connect()``.

        Raises
        ------
        RPCConnectionError
            If the ZMQ connection attempt raises a :class:`zmq.ZMQError`.
        """
        url = f"tcp://{self.host}:{self.port}"
        try:
            self._ctx = zmq.Context()
            self._socket = self._ctx.socket(zmq.REQ)
            self._socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
            self._socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
            self._socket.connect(url)
        except zmq.ZMQError as exc:
            raise RPCConnectionError(url, str(exc)) from exc
        return self

    @classmethod
    def launch(
        cls,
        blender_path: str | None = None,
        port: int = 5555,
        host: str = "localhost",
        timeout: float = 30.0,
        headless: bool = True,
        timeout_ms: int = 5000,
    ) -> "BlendBridge":
        """Launch a headless Blender subprocess and return a connected client.

        Starts Blender with ``--background --python <startup_script>``, where
        the startup script imports handlers and starts the RPC server.  Then
        polls ``ping()`` until the server responds or ``timeout`` seconds have
        elapsed.

        Parameters
        ----------
        blender_path:
            Path to the Blender executable. Falls back to the ``BLENDER_PATH``
            environment variable if ``None``. Raises :class:`RPCConnectionError`
            when neither is available.
        port:
            TCP port the RPC server will listen on. Default ``5555``.
        host:
            Hostname to connect to after launch. Default ``"localhost"``.
        timeout:
            Maximum seconds to wait for Blender to start and respond to ping.
            Default ``30.0``.
        headless:
            When ``True`` (default) passes ``--background`` to Blender.
        timeout_ms:
            ZMQ send/receive timeout in milliseconds for each individual call.
            Default ``5000``.

        Returns
        -------
        BlendBridge
            A connected client instance with :attr:`_process` and
            :attr:`_script_path` set for cleanup via :meth:`close`.

        Raises
        ------
        RPCConnectionError
            When no Blender executable is available.
        RPCTimeoutError
            When the server does not respond within ``timeout`` seconds.
        """
        import time

        from .launcher import launch as _launch_process

        process, script_path = _launch_process(
            blender_path=blender_path,
            port=port,
            host=host,
            timeout=timeout,
            headless=headless,
        )

        client = cls(host=host, port=port, timeout_ms=timeout_ms)
        client._process = process
        client._script_path = script_path
        client.connect()

        # LAUN-03: poll ping until server responds
        deadline = time.monotonic() + timeout
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            try:
                client.ping()
                return client
            except Exception as exc:
                last_err = exc
                time.sleep(0.2)

        # Timeout — clean up before raising
        client.close()
        raise RPCTimeoutError(
            timeout_ms=int(timeout * 1000),
            command="launch/ping",
        )

    def close(self) -> None:
        """Close the ZMQ socket and terminate any spawned Blender subprocess.

        Idempotent — safe to call multiple times or when not connected.
        The ZMQ context is *not* destroyed here to match the server-side
        pattern (RESEARCH.md Pitfall 6) and to allow context reuse.

        If this client was created via :meth:`launch`, also terminates the
        Blender subprocess and deletes the temporary startup script (LAUN-04).
        """
        if self._socket is not None:
            self._socket.close(linger=0)
            self._socket = None
        # Terminate spawned subprocess (LAUN-04)
        if getattr(self, "_process", None) is not None:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None
        # Clean up temp startup script
        if getattr(self, "_script_path", None) is not None:
            try:
                self._script_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._script_path = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "BlendBridge":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # RPC call
    # ------------------------------------------------------------------

    def call(self, command: str, **params: Any) -> dict:
        """Send an RPC request and return the result dict.

        Parameters
        ----------
        command:
            Handler name registered on the server (e.g. ``"list_handlers"``).
        **params:
            Keyword arguments forwarded as the ``params`` dict in the request.

        Returns
        -------
        dict
            The ``result`` value from the server's success envelope.

        Raises
        ------
        RPCTimeoutError
            When :data:`zmq.Again` is raised (send buffer full or no response
            within ``timeout_ms``).
        RPCError
            When the server returns an error envelope
            (``{"status": "error", ...}``).
        """
        msg = {
            "command": command,
            "id": uuid4().hex,
            "params": params,
        }
        try:
            self._socket.send_json(msg)
            response = self._socket.recv_json()
        except zmq.Again:
            raise RPCTimeoutError(self.timeout_ms, command)

        if response.get("status") == "ok":
            return response["result"]

        # status == "error"
        error = response.get("error", {})
        raise RPCError(
            error.get("type", "UnknownError"),
            error.get("message", ""),
            error.get("traceback", ""),
        )

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def ping(self) -> dict:
        """Ping the server. Returns ``{"pong": True, "blender_version": "..."}``.

        Raises
        ------
        RPCTimeoutError
            If the server does not respond within ``timeout_ms``.
        RPCError
            If the server returns an error envelope.
        """
        return self.call("ping")

    def scene_info(self) -> dict:
        """Get scene object summary.

        Returns
        -------
        dict
            ``{"objects": list, "count": int, "active": str | None}``
        """
        return self.call("scene_info")

    def clear_scene(self, *, keep_camera: bool = True) -> dict:
        """Remove mesh objects from the scene.

        Parameters
        ----------
        keep_camera:
            When ``True`` (default) camera objects are preserved.

        Returns
        -------
        dict
            ``{"removed": list, "count": int, "keep_camera": bool}``
        """
        return self.call("clear_scene", keep_camera=keep_camera)

    def list_handlers(self) -> dict:
        """List all registered handler names with docstrings.

        Returns
        -------
        dict
            ``{"handlers": [{"name": str, "doc": str}, ...]}``
        """
        return self.call("list_handlers")

    def export_obj(
        self,
        *,
        filepath: str | None = None,
        selection_only: bool = False,
    ) -> dict:
        """Export the scene (or selection) to an OBJ file.

        Parameters
        ----------
        filepath:
            Destination path on the Blender host. If ``None`` a temp path is
            chosen by the server handler.
        selection_only:
            When ``True`` only selected objects are exported.

        Returns
        -------
        dict
            ``{"file": str, "size_bytes": int}``
        """
        return self.call("export_obj", filepath=filepath, selection_only=selection_only)

    def export_stl(
        self,
        *,
        filepath: str | None = None,
        selection_only: bool = False,
    ) -> dict:
        """Export the scene (or selection) to an STL file.

        Parameters
        ----------
        filepath:
            Destination path on the Blender host. If ``None`` a temp path is
            chosen by the server handler.
        selection_only:
            When ``True`` only selected objects are exported.

        Returns
        -------
        dict
            ``{"file": str, "size_bytes": int}``
        """
        return self.call("export_stl", filepath=filepath, selection_only=selection_only)

    def export_glb(self, *, filepath: str | None = None) -> dict:
        """Export the scene to a GLB file.

        Parameters
        ----------
        filepath:
            Destination path on the Blender host. If ``None`` a temp path is
            chosen by the server handler.

        Returns
        -------
        dict
            ``{"file": str, "size_bytes": int}``
        """
        return self.call("export_glb", filepath=filepath)

    def render(
        self,
        *,
        filepath: str | None = None,
        resolution_x: int = 1920,
        resolution_y: int = 1080,
        samples: int = 32,
    ) -> dict:
        """Render the scene to a PNG image.

        Parameters
        ----------
        filepath:
            Output path on the Blender host. If ``None`` a temp path is used.
        resolution_x:
            Horizontal resolution in pixels. Default ``1920``.
        resolution_y:
            Vertical resolution in pixels. Default ``1080``.
        samples:
            Cycles sample count. Default ``32``.

        Returns
        -------
        dict
            ``{"file": str}``
        """
        return self.call(
            "render",
            filepath=filepath,
            resolution_x=resolution_x,
            resolution_y=resolution_y,
            samples=samples,
        )
