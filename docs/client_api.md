# Client API Reference

Complete reference for the `blendbridge.client` package.

## BlendBridge

The main client class. Manages a ZMQ REQ socket connection to a BlendBridge server.

```python
from blendbridge.client import BlendBridge
```

### Constructor

```python
BlendBridge(host: str = "localhost", port: int = 5555, timeout_ms: int = 5000)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | str | `"localhost"` | Server hostname or IP |
| `port` | int | `5555` | Server port |
| `timeout_ms` | int | `5000` | Timeout for send/recv operations in milliseconds |

### Lifecycle

```python
client = BlendBridge(port=5555)
client.connect()     # Opens ZMQ socket, connects to server
# ... use client ...
client.close()       # Closes socket, cleans up resources (idempotent)
```

**Context manager (recommended):**

```python
with BlendBridge(port=5555) as client:
    client.ping()
# Socket closed automatically
```

### call()

```python
client.call(command: str, **params) -> dict
```

Send an RPC command and return the result.

| Parameter | Type | Description |
|-----------|------|-------------|
| `command` | str | Handler name to invoke on the server |
| `**params` | Any | Keyword arguments passed as the request's `params` dict |

**Returns:** The `result` dict from the server response.

**Raises:**
- `RPCError` — server returned an error response
- `RPCTimeoutError` — no response within `timeout_ms`
- `RPCConnectionError` — socket not connected

```python
result = client.call("export_obj", filepath="/tmp/scene.obj", selection_only=False)
# {'file': '/tmp/scene.obj', 'size_bytes': 42856}
```

### Convenience Methods

All return plain `dict` values. All parameters are keyword-only.

#### ping()

```python
client.ping() -> dict
```

Returns: `{"pong": True, "blender_version": "4.5.1"}`

#### scene_info()

```python
client.scene_info() -> dict
```

Returns: `{"objects": [{"name": "Cube", "type": "MESH"}, ...], "count": 3, "active": "Cube"}`

#### clear_scene()

```python
client.clear_scene(*, keep_camera: bool = True) -> dict
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keep_camera` | bool | `True` | If True, camera objects are not removed |

Returns: `{"removed": ["Cube", "Light"], "count": 2, "keep_camera": True}`

#### list_handlers()

```python
client.list_handlers() -> dict
```

Returns: `{"handlers": [{"name": "ping", "doc": "..."}, ...]}`

#### export_obj()

```python
client.export_obj(*, filepath: str = None, selection_only: bool = False) -> dict
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filepath` | str or None | `None` | Output path. Auto-generates a temp path if None. |
| `selection_only` | bool | `False` | Export only selected objects |

Returns: `{"file": "/tmp/blendbridge_xxxx.obj", "size_bytes": 42856}`

#### export_stl()

```python
client.export_stl(*, filepath: str = None, selection_only: bool = False) -> dict
```

Same parameters and return format as `export_obj()`.

#### export_glb()

```python
client.export_glb(*, filepath: str = None) -> dict
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filepath` | str or None | `None` | Output path. Auto-generates a temp path if None. |

Returns: `{"file": "/tmp/blendbridge_xxxx.glb", "size_bytes": 98304}`

#### render()

```python
client.render(
    *,
    filepath: str = None,
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    samples: int = 32,
) -> dict
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filepath` | str or None | `None` | Output PNG path. Auto-generates if None. |
| `resolution_x` | int | `1920` | Render width in pixels |
| `resolution_y` | int | `1080` | Render height in pixels |
| `samples` | int | `32` | Render samples (Cycles and EEVEE) |

Returns: `{"file": "/tmp/blendbridge_xxxx.png"}`

### launch() (classmethod)

```python
BlendBridge.launch(
    blender_path: str = None,
    port: int = 5555,
    host: str = "localhost",
    timeout: float = 30.0,
    headless: bool = True,
    timeout_ms: int = 5000,
) -> BlendBridge
```

Spawn a headless Blender subprocess with the RPC server running and return a connected client.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `blender_path` | str or None | `None` | Path to Blender binary. Falls back to `BLENDER_PATH` env var. |
| `port` | int | `5555` | Port for the spawned server |
| `host` | str | `"localhost"` | Host to connect to |
| `timeout` | float | `30.0` | Seconds to wait for server startup |
| `headless` | bool | `True` | Run Blender without GUI (`--background`) |
| `timeout_ms` | int | `5000` | Per-call timeout for the returned client |

**Returns:** A connected `BlendBridge` instance. The Blender process is terminated when `close()` is called or the context manager exits.

**Raises:** `RPCTimeoutError` if the server doesn't respond within `timeout` seconds.

```python
with BlendBridge.launch(blender_path="/usr/bin/blender") as client:
    client.ping()
    client.call("generate_spring", length=50)
# Blender process terminated, temp script deleted
```

## Exceptions

All exceptions inherit from `BlendBridgeError`.

```python
from blendbridge.client import BlendBridgeError, RPCError, RPCTimeoutError, RPCConnectionError
```

### BlendBridgeError

Base class for all blendbridge exceptions.

```python
class BlendBridgeError(Exception): ...
```

### RPCError

Raised when the server returns a `status: "error"` response.

```python
class RPCError(BlendBridgeError):
    error_type: str    # Exception class name from server (e.g., "ValueError")
    message: str       # Error message from server
    traceback: str     # Server-side traceback (may be empty)
```

```python
try:
    client.call("unknown_command")
except RPCError as e:
    print(e.error_type)   # "NotFoundError"
    print(e.message)      # "No handler registered for 'unknown_command'"
    print(e.traceback)    # ""
```

### RPCTimeoutError

Raised when the server doesn't respond within the configured timeout.

```python
class RPCTimeoutError(BlendBridgeError):
    timeout_ms: int    # The timeout that was exceeded
    command: str       # The command that timed out (may be empty)
```

```python
try:
    client.call("render", samples=4096)  # slow render
except RPCTimeoutError as e:
    print(e.timeout_ms)  # 5000
    print(e.command)     # "render"
```

### RPCConnectionError

Raised when the client cannot establish or use a ZMQ connection.

```python
class RPCConnectionError(BlendBridgeError):
    url: str           # The ZMQ endpoint (e.g., "tcp://localhost:5555")
    reason: str        # Why the connection failed
```

## CLI Reference

The `blendbridge` command provides terminal access to the client.

### Global Options

```bash
blendbridge [--host HOST] [--port PORT] COMMAND
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `localhost` | Server hostname |
| `--port` | `5555` | Server port |

### ping

```bash
blendbridge ping
```

Pings the server and prints the response as JSON.

### call

```bash
blendbridge call COMMAND [--param KEY=VALUE ...] [--json JSON_STRING]
```

| Option | Description |
|--------|-------------|
| `COMMAND` | Handler name to invoke |
| `--param KEY=VALUE` | Repeatable. Values are coerced: `true`/`false` -> bool, integers -> int, floats -> float |
| `--json STRING` | JSON object for params. Takes precedence over `--param` if both given. |

```bash
blendbridge call export_obj --param filepath=/tmp/out.obj --param selection_only=false
blendbridge call render --json '{"resolution_x": 3840, "samples": 128}'
```

Output is always JSON to stdout. Errors go to stderr.

### handlers

```bash
blendbridge handlers
```

Lists all registered handlers with their docstrings.

### launch

```bash
blendbridge launch [--blender PATH] [--timeout SECONDS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--blender` | `BLENDER_PATH` env var | Path to Blender binary |
| `--timeout` | `30` | Seconds to wait for server startup |

Launches a headless Blender with the RPC server and holds until Ctrl+C.
