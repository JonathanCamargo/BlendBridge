# Headless Mode

Running Blender without a GUI for scripting, CI/CD, and automated workflows.

## Overview

blendbridge's launcher spawns Blender in `--background` mode (no GUI) with the RPC server running. This is ideal for:

- **Optimization loops:** scipy/ML calling Blender thousands of times
- **CI/CD pipelines:** Automated geometry generation and rendering
- **Batch processing:** Export hundreds of scene variations
- **Testing:** Integration tests against a real Blender binary

## Quick Start

### From Python

```python
from blendbridge.client import BlendBridge

with BlendBridge.launch(blender_path="/path/to/blender") as client:
    info = client.ping()
    print(info["blender_version"])

    for i in range(100):
        client.clear_scene()
        result = client.call("create_something", seed=i)
        client.export_glb(filepath=f"/tmp/output_{i}.glb")
```

### From CLI

```bash
# Start headless Blender and keep it running
blendbridge launch --blender /path/to/blender

# In another terminal:
blendbridge ping
blendbridge call scene_info
```

## How launch() Works

1. **Generate startup script** — a temporary Python file that:
   - Imports all registered handlers (`from addon.handlers import *`)
   - Calls `start_server(port=N)` to bind the ZMQ socket
   - Runs a manual `_poll()` loop (because `bpy.app.timers` don't fire in `--background` mode)

2. **Spawn Blender** — runs:
   ```
   /path/to/blender --background --python /tmp/blendbridge_startup_XXXX.py
   ```
   On Windows, uses `CREATE_NO_WINDOW` to suppress the console window.

3. **Poll for readiness** — the client repeatedly calls `ping()` until the server responds or the timeout is reached.

4. **Return connected client** — the `BlendBridge` instance is ready to use.

5. **Cleanup on exit** — `close()` terminates the Blender subprocess and deletes the temp startup script.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BLENDER_PATH` | Default Blender binary path. Used by `launch()` and `blendbridge launch` when no explicit path is given. |
| `BLENDER_RPC_PORT` | Default port (currently used by convention; launcher accepts `port` parameter) |
| `BLENDER_RPC_HOST` | Default host (currently used by convention; launcher accepts `host` parameter) |

## Custom Startup Scripts

For advanced setups, you can write your own startup script instead of using the auto-generated one:

```python
# my_startup.py
import sys
sys.path.insert(0, "/path/to/my/project")

# Import custom handlers
from addon.handlers import *
import my_custom_handlers  # registers via @rpc_handler

# Start server
from addon.server import start_server, _poll
start_server(host="*", port=5555)

# Manual poll loop (required in --background mode)
while True:
    _poll()
```

Then launch Blender directly:

```bash
/path/to/blender --background --python my_startup.py
```

And connect from your client:

```python
with BlendBridge(port=5555) as client:
    client.ping()
```

## CI/CD Integration

### GitHub Actions Example

```yaml
jobs:
  geometry-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Blender
        run: |
          sudo snap install blender --classic

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          python scripts/install_zmq_blender.py

      - name: Run geometry tests
        run: |
          python -c "
          from blendbridge.client import BlendBridge
          with BlendBridge.launch(blender_path='blender') as client:
              assert client.ping()['pong'] is True
              info = client.scene_info()
              print(f'Scene has {info[\"count\"]} objects')
          "
```

### Docker

```dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y blender python3-pip
RUN pip install blendbridge
RUN python3 scripts/install_zmq_blender.py

ENV BLENDER_PATH=/usr/bin/blender

CMD ["python3", "my_pipeline.py"]
```

## Optimization Loop Example

The primary use case for headless mode — calling Blender thousands of times from an optimizer:

```python
from blendbridge.client import BlendBridge
from scipy.optimize import minimize

def objective(params):
    length, coils, thickness = params
    result = client.call(
        "generate_spring",
        length=float(length),
        coils=int(coils),
        thickness=float(thickness),
    )
    # Your fitness function here
    return compute_fitness(result)

with BlendBridge.launch(blender_path="/path/to/blender") as client:
    # Single persistent connection for all iterations
    result = minimize(
        objective,
        x0=[50, 8, 2.0],
        method="Nelder-Mead",
        options={"maxiter": 1000},
    )
    print(f"Optimal: length={result.x[0]}, coils={result.x[1]}, thickness={result.x[2]}")
```

Key points:
- One `BlendBridge` connection for the entire optimization (not per-call)
- Blender stays running between calls — no startup overhead per iteration
- ZMQ REQ/REP adds ~0.1ms per call, making Blender the bottleneck (not transport)

## Troubleshooting

### Server doesn't start (timeout on launch)

Check that:
1. `blender_path` points to a working Blender binary
2. pyzmq is installed in Blender's Python (`python scripts/install_zmq_blender.py`)
3. The addon is functional (try starting the server from Blender's GUI first)
4. The port isn't already in use

### "bpy.app.timers callbacks don't fire"

This is expected in `--background` mode. The launcher's startup script includes a manual `_poll()` loop to work around this. If you're writing a custom startup script, you must include this loop yourself.

### Blender process lingers after crash

If your Python script crashes without calling `close()`, the Blender subprocess may keep running. Use a context manager (`with BlendBridge.launch(...) as client:`) to guarantee cleanup, or kill orphaned processes manually:

```bash
# Linux/macOS
pkill -f "blender.*background"

# Windows
taskkill /F /IM blender.exe
```
