# Installation Guide

blendbridge has two parts: a **Blender addon** (the server) and a **Python client** (for calling Blender from external code). Install the addon first — the client is only needed if you're calling Blender from outside.

## Prerequisites

- **Addon:** Blender 4.x (4.0 or newer). pyzmq is auto-installed on first enable.
- **Client:** Python 3.10+ with pip. pyzmq and click are installed automatically via pip.

## 1. Build and Install the Addon (server)

### Build the zip

```bash
git clone https://github.com/jcl00/blendbridge.git
cd blendbridge
python scripts/build_addon_zip.py
```

Output: `dist/blendbridge_addon_v0.1.0.zip`

### Install in Blender

1. Open Blender 4.x
2. Edit -> Preferences -> Add-ons
3. Click "Install..." (top right)
4. Select `dist/blendbridge_addon_v0.1.0.zip`
5. Enable "BlendBridge" in the addon list

On first enable, the addon automatically installs `pyzmq` into Blender's Python. You'll see a message in Blender's console. No manual dependency step needed.

### If auto-install fails

If Blender's Python can't pip install (network restrictions, permissions), use the manual script:

```bash
python scripts/install_zmq_blender.py                            # auto-detect Blender
python scripts/install_zmq_blender.py --blender /path/to/blender # explicit path
python scripts/install_zmq_blender.py --dry-run                  # preview only
```

The script searches common install locations:

| Platform | Locations searched |
|----------|-------------------|
| Linux | `/usr/bin/blender`, `/usr/local/bin/blender`, `/opt/blender/blender`, `/snap/bin/blender`, `~/.local/bin/blender` |
| macOS | `/Applications/Blender.app/Contents/MacOS/Blender`, `~/Applications/...` |
| Windows | `C:\Program Files\Blender Foundation\Blender 4.X\blender.exe` (4.0-4.3) |

Then re-enable the addon.

## 2. Install the Client (optional — external Python only)

Only needed if you want to call Blender from an external Python process or use the `blendbridge` CLI.

```bash
pip install -e ".[dev]"
```

This installs `blendbridge` and its dependencies (`pyzmq>=25`, `click>=8`) into your Python environment.

Verify:

```bash
blendbridge --version
# blendbridge 0.1.0
```

### Configure (optional)

In addon preferences (expand the addon entry):

| Setting | Default | Description |
|---------|---------|-------------|
| Host | `*` | Bind address (`*` = all interfaces, `127.0.0.1` = localhost only) |
| Port | `5555` | ZMQ port |
| Autostart | Off | Start server automatically when Blender opens |

## 5. Start the Server

**From the sidebar panel:**
- Open the 3D Viewport
- Press N to open the sidebar
- Click the "RPC" tab
- Click "Start Server"
- Status shows "RUNNING" with the port number

**From Blender's Python console:**

```python
from addon.server import start_server
start_server(host="*", port=5555)
```

**Autostart:** Enable "Autostart" in addon preferences. The server will start automatically whenever Blender opens or loads a file.

## 6. Smoke Test

With the server running in Blender:

```bash
blendbridge ping
# {"pong": true, "blender_version": "4.5.1"}
```

Or from Python:

```python
from blendbridge.client import BlendBridge

with BlendBridge() as client:
    print(client.ping())
```

## Troubleshooting

### "Connection refused" or timeout

- Is the server running? Check the sidebar panel in Blender.
- Is the port correct? Default is 5555.
- Is a firewall blocking the port?

### "Address already in use" on server start

Another process (or a previous Blender instance) is using port 5555. Either close that process or change the port in addon preferences.

### pyzmq import error in Blender

The `install_zmq_blender.py` script may not have found the right Python. Run:

```bash
/path/to/blender --background --python-expr "import zmq; print(zmq.__version__)"
```

If this errors, reinstall pyzmq manually into Blender's Python (see step 2).

### Addon doesn't appear after install

- Make sure you're on Blender 4.x (the addon requires `blender >= (4, 0, 0)`)
- Try refreshing: Edit -> Preferences -> Add-ons -> Refresh
- Check Blender's console (Window -> Toggle System Console on Windows) for error messages
