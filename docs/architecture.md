# Architecture

How BlendBridge works under the hood.

## Overview

BlendBridge is a dual-package system:

1. **Client** (`blendbridge/`) — a normal pip package. Runs in any Python 3.10+ environment. Speaks ZMQ REQ.
2. **Server** (`addon/`) — a Blender addon. Runs inside Blender's embedded Python. Speaks ZMQ REP.

The two share zero code. The only contract between them is the JSON protocol over ZMQ.

## Protocol

Every exchange follows ZMQ REQ/REP: client sends one message, server sends one response. No streaming, no subscriptions.

### Request

```json
{
  "command": "export_obj",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "params": {
    "filepath": "/tmp/scene.obj",
    "selection_only": false
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Handler name to invoke |
| `id` | string | UUID for correlation (echoed in response) |
| `params` | object | Keyword arguments passed to the handler |

### Success Response

```json
{
  "status": "ok",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "result": {
    "file": "/tmp/scene.obj",
    "size_bytes": 42856
  }
}
```

### Error Response

```json
{
  "status": "error",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "error": {
    "type": "ValueError",
    "message": "coils must be > 0",
    "traceback": "Traceback (most recent call last):\n  ..."
  }
}
```

The server never crashes on bad input. Malformed JSON, missing fields, unknown commands, and handler exceptions all produce structured error responses.

## Server Side

### Threading Model

Blender's `bpy` API is not thread-safe. All API calls must happen on the main thread. BlendBridge uses Blender's official main-thread callback mechanism:

```
bpy.app.timers.register(_poll, persistent=True)
```

`_poll()` runs every 50ms on the main thread. It does a non-blocking ZMQ recv, dispatches to the handler, sends the response, and returns. The UI stays responsive because `zmq.NOBLOCK` returns immediately if no message is waiting.

### REP State Machine

ZMQ REP sockets enforce a strict recv-send-recv-send alternation. Every successful `recv()` must be followed by exactly one `send()` before the next `recv()`. The server guarantees this on every code path — JSON parse errors, dispatch failures, and handler exceptions all send a response before returning.

### Request Lifecycle

```
_poll() tick (every 50ms)
  │
  ├─ sock.recv(NOBLOCK) ─── zmq.Again ──► return (no message)
  │
  ├─ json.loads(raw) ─── JSONDecodeError ──► send error envelope
  │
  ├─ router.dispatch(message)
  │    │
  │    ├─ validate message shape (dict with "command" key)
  │    ├─ registry.get_handler(command)
  │    ├─ handler(**params)
  │    └─ return {status: ok, result: ...}
  │         or {status: error, error: ...}
  │
  └─ sock.send_json(response)
```

### Component Responsibilities

| Module | Role | Depends on bpy? |
|--------|------|-----------------|
| `server.py` | Socket lifecycle, timer registration, poll loop | Yes |
| `router.py` | Message validation, handler dispatch, error envelopes | No |
| `registry.py` | `@rpc_handler` decorator, handler storage/lookup | No |
| `handlers/` | Built-in command implementations | Yes |
| `ops.py` | Blender operators (start/stop buttons) | Yes |
| `panel.py` | Sidebar UI (status, controls) | Yes |
| `preferences.py` | Addon settings (host, port, autostart) | Yes |

`router.py` and `registry.py` are deliberately bpy-free so they can be unit-tested without Blender.

### Handler Registration

Handlers are registered via the `@rpc_handler` decorator at import time:

```python
from addon.registry import rpc_handler

@rpc_handler("my_command")
def my_command(param1: str) -> dict:
    ...
```

The decorator adds the function to a module-level dict in `registry.py` and returns it unchanged (no wrapper). `addon/handlers/__init__.py` imports all handler modules as a side effect, populating the registry when the addon loads.

## Client Side

### Connection

`BlendBridge` creates a ZMQ REQ socket and connects to `tcp://{host}:{port}`. Connection is eager — it happens in `connect()` (or `__init__` via context manager), not on first `call()`.

### call()

```python
def call(self, command: str, **params) -> dict:
    request = {"command": command, "id": str(uuid4()), "params": params}
    self._socket.send_json(request)
    response = self._socket.recv_json()
    # check status, raise RPCError/RPCTimeoutError if needed
    return response["result"]
```

Timeout is set via `zmq.SNDTIMEO` and `zmq.RCVTIMEO` socket options. If the server doesn't respond within `timeout_ms`, ZMQ raises `zmq.Again` which the client translates to `RPCTimeoutError`.

### Convenience Methods

Each built-in handler has a corresponding method on `BlendBridge` that delegates to `call()`:

```python
def export_obj(self, *, filepath=None, selection_only=False):
    return self.call("export_obj", filepath=filepath, selection_only=selection_only)
```

All parameters are keyword-only. Return values are plain dicts matching the server's JSON response.

### Launcher

`BlendBridge.launch()` automates the "start Blender with the server" workflow:

1. Generate a Python startup script that imports handlers and starts the server
2. Spawn `blender --background --python <script>` via `subprocess.Popen`
3. Create a `BlendBridge` client and poll `ping()` until the server responds
4. Return the connected client
5. On `close()` / `__exit__`, terminate the Blender subprocess and delete the temp script

The startup script includes a manual `_poll()` loop because `bpy.app.timers` callbacks don't fire automatically in `--background` mode.

## Separation of Concerns

```
pip install blendbridge          Blender: Install Addon from zip
        │                                │
        ▼                                ▼
blendbridge/client/              addon/
  - Pure Python 3.10+              - Runs in Blender's Python 3.11
  - ZMQ REQ socket                 - ZMQ REP socket
  - No bpy imports (enforced)      - Full bpy access
  - Installed via pip              - Installed via Blender UI
```

The client and addon have zero shared code or imports. This is intentional:

- Blender's embedded Python is difficult to `pip install` into
- Blender's Python version may differ from the client's
- The JSON protocol is the only contract, making it language-agnostic
