"""Blender launcher — spawns a headless Blender subprocess with the RPC server running.

This module is intentionally free of any bpy or Blender-only imports so it
can be used from any external Python process without a Blender installation.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

from .exceptions import RPCConnectionError


# ---------------------------------------------------------------------------
# Startup script generation
# ---------------------------------------------------------------------------

_STARTUP_SCRIPT_TEMPLATE = """\
import addon.handlers  # noqa: F401  -- side-effect import registers all handlers
from addon import server
import time

server.start_server(port={port})
print("blendbridge: server started on port {port}")

# In --background mode, bpy.app.timers callbacks don't auto-fire.
# Poll manually in a loop (same pattern as smoke_phase2.py).
try:
    while True:
        server._poll()
        time.sleep(0.01)
except KeyboardInterrupt:
    server.stop_server()
"""


def _generate_startup_script(port: int) -> str:
    """Return the text of a Python script that starts the RPC server in Blender.

    The script runs inside Blender's embedded Python interpreter. It:

    1. Imports ``addon.handlers`` (triggers ``@rpc_handler`` registration via side-effect).
    2. Calls ``addon.server.start_server(port=port)``.
    3. Runs a blocking poll loop because ``bpy.app.timers`` callbacks do not
       auto-fire in ``--background`` mode (RESEARCH.md Pitfall / Phase 2 decision).

    Parameters
    ----------
    port:
        The TCP port the RPC server should bind to.

    Returns
    -------
    str
        Python source code suitable for writing to a ``.py`` file.
    """
    return _STARTUP_SCRIPT_TEMPLATE.format(port=port)


# ---------------------------------------------------------------------------
# Process launch
# ---------------------------------------------------------------------------

def launch(
    blender_path: str | None = None,
    port: int = 5555,
    host: str = "localhost",
    timeout: float = 30.0,
    headless: bool = True,
) -> tuple[subprocess.Popen, pathlib.Path]:
    """Spawn a Blender process running the RPC server and return the process handle.

    Parameters
    ----------
    blender_path:
        Path to the Blender executable. If ``None``, the ``BLENDER_PATH``
        environment variable is used. Raises :class:`RPCConnectionError` if
        neither is provided.
    port:
        TCP port for the RPC server. Default ``5555``.
    host:
        Hostname for the RPC server (informational only; startup script uses
        ``"*"`` to bind all interfaces). Default ``"localhost"``.
    timeout:
        How long (seconds) the caller will wait for the server to respond.
        Not enforced here — passed for caller convenience. Default ``30.0``.
    headless:
        If ``True`` (default), passes ``--background`` to Blender so it runs
        without opening a GUI window.

    Returns
    -------
    tuple[subprocess.Popen, pathlib.Path]
        ``(process, script_path)`` — the spawned process and the path to the
        temporary startup script. The caller is responsible for eventually
        cleaning up both (typically via ``BlendBridge.close()``).

    Raises
    ------
    RPCConnectionError
        When no Blender executable path is available.
    """
    import os

    # --- 1. Resolve blender path ---
    resolved_path = blender_path or os.environ.get("BLENDER_PATH")
    if not resolved_path:
        raise RPCConnectionError(
            url="",
            reason=(
                "No Blender executable found. Provide blender_path= or set "
                "the BLENDER_PATH environment variable."
            ),
        )

    blender_exe = pathlib.Path(resolved_path)

    # --- 2. Write startup script to temp file ---
    script_text = _generate_startup_script(port=port)
    tmp_file = tempfile.NamedTemporaryFile(
        suffix=".py",
        mode="w",
        delete=False,
        encoding="utf-8",
    )
    try:
        tmp_file.write(script_text)
        tmp_file.flush()
        script_path = pathlib.Path(tmp_file.name)
    finally:
        tmp_file.close()

    # --- 3. Build command ---
    cmd = [str(blender_exe)]
    if headless:
        cmd.append("--background")
    cmd.extend(["--python", str(script_path)])

    # --- 4. Platform-specific subprocess flags ---
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    # --- 5. Spawn process ---
    process = subprocess.Popen(cmd, **kwargs)

    return process, script_path
