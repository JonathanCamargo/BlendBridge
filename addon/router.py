"""BlendBridge message router.

Pure-function dispatch. Takes a parsed JSON message dict, looks up the
handler in the registry, calls it, and returns either a success or error
envelope. Never raises — every exception path becomes a structured dict
response so the ZMQ REP socket can always send exactly one response per
request (REP state-machine requirement).

Bpy-free: this module must stay importable in plain Python so it can
be unit-tested in tests/unit/test_router.py without a running Blender.
Do NOT add any `import bpy` here.
"""
from __future__ import annotations
import traceback
from typing import Any

from .registry import get_handler


def _error(msg_id: str, err_type: str, message: str, tb: str = "") -> dict:
    """Build a protocol-spec error envelope."""
    return {
        "status": "error",
        "id": msg_id,
        "error": {
            "type": err_type,
            "message": message,
            "traceback": tb,
        },
    }


def dispatch(message: Any) -> dict:
    """Route a parsed JSON message to its handler.

    Returns a dict — always. Never raises. Every failure mode produces
    a protocol-spec error envelope with `status`, `id`, and `error`
    (with `type`, `message`, and optional `traceback`).

    Error taxonomy:
      - TypeError: message is not a dict
      - ValueError: message dict has no "command" field
      - NotFound: command name is not registered
      - <handler exception class>: handler raised — traceback included
    """
    # Phase 1: input shape check
    if not isinstance(message, dict):
        return _error("", "TypeError", "Message must be a JSON object")

    msg_id = message.get("id", "")
    if not isinstance(msg_id, str):
        msg_id = str(msg_id)

    # Phase 2: command field check
    command = message.get("command")
    if command is None:
        return _error(msg_id, "ValueError", "Missing 'command' field")

    # Phase 3: handler lookup
    handler = get_handler(command)
    if handler is None:
        return _error(msg_id, "NotFound", f"No handler registered: {command}")

    # Phase 4: handler invocation with catch-all
    params = message.get("params") or {}
    if not isinstance(params, dict):
        return _error(msg_id, "TypeError", "'params' must be an object if present")

    try:
        result = handler(**params)
    except Exception as e:
        return _error(
            msg_id,
            type(e).__name__,
            str(e),
            traceback.format_exc(),
        )

    return {"status": "ok", "id": msg_id, "result": result}
