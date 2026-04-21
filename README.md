# BlendBridge

> Turn any running Blender instance into a geometry/render microservice over ZeroMQ.

[![CI](https://github.com/jcl00/blendbridge/actions/workflows/test.yml/badge.svg)](https://github.com/jcl00/blendbridge/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`blendbridge` lets any Python process call into a running Blender instance over ZeroMQ with sub-millisecond overhead. Optimization loops, ML pipelines, CI/CD systems, and simulation workflows can treat Blender as a callable service — no GUI interaction required.

## Two Pieces, One System

| | Blender Addon (server) | Python Client |
|---|---|---|
| **What** | Runs inside Blender, listens for commands | Runs in your Python environment, sends commands |
| **Install** | Addon zip in Blender | `pip install blendbridge` |
| **Needs** | Blender 4.x (pyzmq auto-installed) | Python 3.10+ (pyzmq installed via pip) |
| **When** | Always — this is the server | Only when calling Blender from external code |

## Quickstart

### 1. Install the Addon (server side)

```bash
# Build the addon zip
python scripts/build_addon_zip.py
```

Then in Blender: **Edit -> Preferences -> Add-ons -> Install** -> select `dist/blendbridge_addon_v0.1.0.zip`.

The addon automatically installs `pyzmq` into Blender's Python on first enable. No manual dependency step needed.

Start the server: Open the **3D Viewport sidebar (N) -> RPC tab -> Start Server**.

### 2. Install the Client (caller side)

Only needed if you want to call Blender from an external Python process or CLI.

```bash
pip install -e ".[dev]"
```

This installs the `blendbridge` package and its dependencies (`pyzmq>=25`, `click>=8`) into your Python environment.

### 3. Talk to Blender

```python
from blendbridge.client import BlendBridge

with BlendBridge(port=5555) as b:
    print(b.ping())           # {'pong': True, 'blender_version': '4.5.1'}
    print(b.scene_info())     # {'objects': [...], 'count': 3, 'active': 'Cube'}
    b.export_glb("/tmp/scene.glb")
```

Or from the CLI:

```bash
blendbridge ping
blendbridge call scene_info
blendbridge call export_obj --param filepath=/tmp/scene.obj
```

Or launch your own headless Blender (no GUI needed):

```python
with BlendBridge.launch(blender_path="/path/to/blender") as b:
    result = b.call("generate_spring", length=50, coils=8)
```

## Why ZeroMQ?

| | ZMQ REQ/REP | HTTP/REST |
|---|---|---|
| Per-call overhead | ~0.1ms | ~1-5ms |
| Connection setup | Bind once | Handshake per request (or keep-alive) |
| Blender integration | Non-blocking poll in `bpy.app.timers` | Needs a web server thread |
| Optimization loops (10k+ calls) | Native fit | Unnecessary overhead |

The protocol is JSON over ZMQ. Today we ship a Python client; anything with a ZMQ binding can speak the protocol directly.

## Architecture

```
┌──────────────────────────┐       ZMQ REQ/REP        ┌──────────────────────────┐
│  Your Python Process     │  ◄── JSON messages ──►   │  Blender 4.x             │
│                          │      tcp://host:5555      │                          │
│  from blendbridge.client │                           │  addon/                  │
│  import BlendBridge      │                           │  ├─ server.py            │
│                          │                           │  │  bpy.app.timers poll  │
│  # or from CLI:          │                           │  │  zmq.NOBLOCK recv     │
│  # blendbridge ping      │                           │  ├─ router.py            │
│                          │                           │  │  dispatch(message)     │
│  BlendBridge             │                           │  ├─ registry.py          │
│  ├─ call(cmd, **params)  │                           │  │  @rpc_handler("name") │
│  ├─ ping()               │   ┌──────────────────┐   │  └─ handlers/            │
│  ├─ scene_info()         │   │  JSON Protocol   │   │     ├─ scene.py          │
│  ├─ export_obj/stl/glb() │   │                  │   │     ├─ export.py         │
│  ├─ render()             │   │  Request:        │   │     └─ render.py         │
│  └─ launch()             │   │  {command, id,   │   │                          │
│                          │   │   params}         │   │  contrib/               │
│  Exceptions:             │   │                  │   │  └─ spring_generator/   │
│  ├─ RPCError             │   │  Response:       │   │                          │
│  ├─ RPCTimeoutError      │   │  {status, id,   │   └──────────────────────────┘
│  └─ RPCConnectionError   │   │   result|error}  │
│                          │   └──────────────────┘
└──────────────────────────┘
```

**Threading model:** Blender's `bpy` API is not thread-safe. The server polls ZMQ with `zmq.NOBLOCK` on a 50ms `bpy.app.timers` callback — all handler execution happens on Blender's main thread. The UI stays responsive.

## Client API

### BlendBridge

```python
from blendbridge.client import BlendBridge

# Context manager (recommended)
with BlendBridge(host="localhost", port=5555, timeout_ms=5000) as client:
    result = client.call("any_command", key="value")

# Manual lifecycle
client = BlendBridge(port=5555)
client.connect()
try:
    client.ping()
finally:
    client.close()
```

### Convenience Methods

```python
client.ping()                                    # -> {'pong': True, 'blender_version': '4.5.1'}
client.scene_info()                              # -> {'objects': [...], 'count': N, 'active': '...'}
client.clear_scene(keep_camera=True)             # -> {'removed': [...], 'count': N}
client.list_handlers()                           # -> {'handlers': [{'name': '...', 'doc': '...'}, ...]}
client.export_obj(filepath="/tmp/out.obj")       # -> {'file': '/tmp/out.obj', 'size_bytes': N}
client.export_stl(filepath="/tmp/out.stl")       # -> {'file': '/tmp/out.stl', 'size_bytes': N}
client.export_glb(filepath="/tmp/out.glb")       # -> {'file': '/tmp/out.glb', 'size_bytes': N}
client.render(resolution_x=1920, samples=64)     # -> {'file': '/tmp/render.png'}
```

### Launcher

```python
with BlendBridge.launch(
    blender_path="/path/to/blender",  # or set BLENDER_PATH env var
    port=5555,
    timeout=30.0,
) as client:
    client.ping()
    # Blender process terminates automatically on exit
```

### Exceptions

```python
from blendbridge.client import RPCError, RPCTimeoutError, RPCConnectionError

try:
    client.call("bad_command")
except RPCError as e:
    print(e.error_type, e.message, e.traceback)
except RPCTimeoutError as e:
    print(f"No response within {e.timeout_ms}ms for '{e.command}'")
except RPCConnectionError as e:
    print(f"Cannot connect to {e.url}: {e.reason}")
```

See [docs/client_api.md](docs/client_api.md) for the full reference.

## CLI

```bash
blendbridge ping                                        # ping a running server
blendbridge call scene_info                             # call any command
blendbridge call export_obj --param filepath=/tmp/a.obj # with parameters
blendbridge call render --json '{"samples": 128}'       # or pass JSON
blendbridge handlers                                    # list registered handlers
blendbridge launch --blender /path/to/blender           # launch headless Blender

# Global options
blendbridge --host 192.168.1.10 --port 5556 ping
```

## Writing Custom Handlers

```python
# my_handlers.py
from addon.registry import rpc_handler

@rpc_handler("my_operation")
def my_operation(param1: str, param2: int = 10) -> dict:
    """Does something useful with the Blender scene."""
    import bpy
    # ... your Blender logic here ...
    return {"result": "done", "param1": param1}
```

See [docs/writing_handlers.md](docs/writing_handlers.md) for the full guide.

## Project Layout

```
blendbridge/            Pip-installable client package
  client/
    __init__.py         Public API: BlendBridge, exceptions
    client.py           BlendBridge class (ZMQ REQ, call, convenience methods)
    launcher.py         Blender subprocess management
    cli.py              Click CLI: ping, call, handlers, launch
    exceptions.py       BlendBridgeError, RPCError, RPCTimeoutError, RPCConnectionError
addon/                  Blender addon (ships as zip, not part of pip package)
  __init__.py           Auto-installs pyzmq on first enable
  server.py             ZMQ REP socket + bpy.app.timers poll loop
  router.py             Message dispatch (command -> handler)
  registry.py           @rpc_handler decorator + handler registry
  handlers/             Built-in handlers (scene, export, render)
  ops.py                Blender operators (start/stop server)
  panel.py              Sidebar UI panel (status, controls, handler list)
  preferences.py        Addon preferences (host, port, autostart)
contrib/                Domain-specific handlers (spring generator)
scripts/                Build and install helpers
examples/               Usage examples
tests/unit/             151 unit tests (pytest)
docs/                   Documentation
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BLENDER_PATH` | (none) | Path to Blender binary, used by launcher and CLI |
| `BLENDBRIDGE_HOST` | `localhost` | Default host for client connections |
| `BLENDBRIDGE_PORT` | `5555` | Default port for client connections |

## Documentation

- [Installation Guide](docs/installation.md) — detailed setup for addon and client
- [Architecture](docs/architecture.md) — protocol, threading model, component design
- [Writing Handlers](docs/writing_handlers.md) — add your own RPC commands
- [Client API Reference](docs/client_api.md) — full BlendBridge class and CLI docs
- [Headless Mode](docs/headless_mode.md) — CI/CD, optimization loops, Docker

## License

MIT
