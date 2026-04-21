"""BlendBridge ZMQ REP server.

Owns the ZMQ socket lifecycle and the main-thread polling loop.

Threading model: `bpy.app.timers.register(_poll, persistent=True)`
schedules `_poll` on Blender's main thread every POLL_INTERVAL seconds.
`_poll` does a non-blocking recv, dispatches via `router.dispatch`, and
sends the response. No worker thread. No locks. `bpy` is not thread-safe
and handlers run via the timer callback which is guaranteed main-thread.

REP state machine: ZMQ REP requires exactly one send per recv. Every
branch in `_poll` that successfully recv's MUST send exactly once before
returning, or the next recv raises
`zmq.ZMQError: Operation cannot be accomplished in current state`.

SRV-03 / SRV-04 / SRV-05 all live in this file.
"""
from __future__ import annotations
import json
import logging
import traceback
from typing import Optional

import bpy
import zmq

from .router import dispatch

log = logging.getLogger("blendbridge.server")

POLL_INTERVAL: float = 0.05  # 50 ms per SRV-03

# Module-level server state. Unit tests monkeypatch these directly.
_ctx: Optional[zmq.Context] = None
_socket: Optional[zmq.Socket] = None
_bound_port: Optional[int] = None


def is_running() -> bool:
    """True if the server socket is currently bound."""
    return _socket is not None


def get_port() -> Optional[int]:
    """Return the port the server is bound to, or None."""
    return _bound_port


def start_server(host: str = "*", port: int = 5555) -> None:
    """Bind a ZMQ REP socket and register the main-thread poll timer.

    Raises:
        zmq.ZMQError: If the bind fails (e.g. port already in use).
            Caller (the start_server operator) is expected to catch
            this and self.report({'ERROR'}, ...) so the user sees it
            in Blender's info bar. This is SRV-05.
    """
    global _ctx, _socket, _bound_port
    if _socket is not None:
        log.warning("blendbridge: server already running on port %s", _bound_port)
        return

    _ctx = zmq.Context.instance()
    sock = _ctx.socket(zmq.REP)
    try:
        sock.bind(f"tcp://{host}:{port}")
    except zmq.ZMQError as e:
        # SRV-05: surface bind errors visibly, clean up, re-raise.
        log.error("blendbridge: bind failed on tcp://%s:%s — %s", host, port, e)
        try:
            sock.close(linger=0)
        except Exception:
            pass
        _ctx = None
        raise

    _socket = sock
    _bound_port = port
    if not bpy.app.timers.is_registered(_poll):
        bpy.app.timers.register(_poll, persistent=True)
    log.info("blendbridge: server listening on tcp://%s:%s", host, port)


def stop_server() -> None:
    """Unregister the poll timer and close the socket.

    Safe to call when the server is already stopped.
    Does NOT call zmq.Context.term — the process-wide singleton is
    left alone so subsequent start_server calls work without deadlock
    (see RESEARCH.md Pitfall 6).
    """
    global _ctx, _socket, _bound_port
    try:
        if bpy.app.timers.is_registered(_poll):
            bpy.app.timers.unregister(_poll)
    except Exception as e:
        log.warning("blendbridge: timer unregister failed: %s", e)

    if _socket is not None:
        try:
            _socket.close(linger=0)
        except Exception as e:
            log.warning("blendbridge: socket close failed: %s", e)
    _socket = None
    _ctx = None
    _bound_port = None
    log.info("blendbridge: server stopped")


def _poll() -> float:
    """Main-thread poll tick.

    Critical contract: MUST return a float on every code path.
    Returning None (implicit or explicit) would unregister the timer
    silently — this is RESEARCH.md Pitfall 3.

    REP state machine: every successful recv MUST be followed by
    exactly one send_json. Every exception branch after recv emits
    an error envelope before returning.
    """
    sock = _socket  # snapshot for type-checkers; also protects against stop mid-tick
    if sock is None:
        return POLL_INTERVAL  # server stopped — keep returning float until timer is unregistered

    # Step 1: non-blocking recv
    try:
        raw = sock.recv(flags=zmq.NOBLOCK)
    except zmq.Again:
        return POLL_INTERVAL  # no message waiting — normal idle tick
    except zmq.ZMQError as e:
        log.error("blendbridge: recv error: %s", e)
        return POLL_INTERVAL  # socket in bad state; next tick retries

    # Step 2: JSON parse
    try:
        message = json.loads(raw)
    except json.JSONDecodeError as e:
        # SRV-04: malformed JSON must NOT crash — send an error envelope so
        # the REP state machine advances to "ready for recv".
        _safe_send(sock, {
            "status": "error",
            "id": "",
            "error": {
                "type": "JSONDecodeError",
                "message": str(e),
                "traceback": "",
            },
        })
        return POLL_INTERVAL

    # Step 3: dispatch (router is defensive; this wrap is belt-and-suspenders
    # so REP state is never stuck even if router itself has a bug)
    try:
        response = dispatch(message)
    except Exception as e:
        response = {
            "status": "error",
            "id": message.get("id", "") if isinstance(message, dict) else "",
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
        }

    # Step 4: send — every successful recv must reach exactly one send
    _safe_send(sock, response)
    return POLL_INTERVAL


def _safe_send(sock, payload: dict) -> None:
    """Send a dict response, logging (not raising) on send failure."""
    try:
        sock.send_json(payload)
    except zmq.ZMQError as e:
        log.error("blendbridge: send_json failed: %s", e)
