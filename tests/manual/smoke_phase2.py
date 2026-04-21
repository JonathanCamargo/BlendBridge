"""Phase 2 integration smoke test — run inside Blender.

Usage:
    blender --background --python tests/manual/smoke_phase2.py

Starts the RPC server on the main thread, then from the SAME process
opens a zmq.REQ client that sends JSON commands and validates responses.
Exits 0 if all checks pass, nonzero on any failure.

This is NOT a pytest file — it runs under Blender's embedded Python.

Timer ticking: In blender --background mode, bpy.app.timers callbacks do
NOT auto-fire on a loop. We directly call server._poll() in a manual spin
loop after each client.send(). This exercises the full recv->dispatch->send
path inside a background Blender without relying on Blender's event loop.

Port 15557: Non-default to avoid clashing with any user server already
running on 5555.
"""
import sys
import json
import time
import os
import traceback

# Make the repo root importable when run via blender --background --python
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import bpy
import zmq

# Trigger addon registration (handlers, operators, preferences, etc.).
# In real Blender this happens via Preferences > Add-ons; in --background
# mode we call it directly to mimic the enable-addon flow.
from addon import register, unregister
register()

# Import server after registration so handlers are already loaded.
from addon import server

PORT = 15557  # non-default to avoid clash with a user's live server on 5555
PASSED = 0
FAILED = 0


def check(name, response, expected_status="ok"):
    """Assert response has expected status; print PASS/FAIL; update counters."""
    global PASSED, FAILED
    status = response.get("status")
    if status != expected_status:
        print(f"  FAIL [{name}] expected status={expected_status!r}, got {status!r}: {response}")
        FAILED += 1
        return False
    print(f"  PASS [{name}]")
    PASSED += 1
    return True


def call(client, command, params=None):
    """Send a command and spin server._poll() until the reply arrives.

    In --background mode bpy.app.timers do not run automatically. We call
    server._poll() directly (it is a plain function registered as a timer).
    200 ticks * 10 ms = 2 s max wait per command.
    """
    msg = {"id": command, "command": command}
    if params:
        msg["params"] = params
    client.send(json.dumps(msg).encode())
    for _ in range(200):
        server._poll()
        try:
            raw = client.recv(flags=zmq.NOBLOCK)
            return json.loads(raw)
        except zmq.Again:
            time.sleep(0.01)
    raise TimeoutError(f"No response for {command!r} after 2 s of polling")


try:
    # ------------------------------------------------------------------ #
    # 1. Start server                                                      #
    # ------------------------------------------------------------------ #
    server.start_server(host="127.0.0.1", port=PORT)
    assert server.is_running(), "Server should be running after start_server()"
    assert server.get_port() == PORT, f"Expected port {PORT}, got {server.get_port()}"
    print(f"Server started on port {PORT}")

    # ------------------------------------------------------------------ #
    # 2. Create REQ client (same process)                                  #
    # ------------------------------------------------------------------ #
    ctx = zmq.Context.instance()
    client = ctx.socket(zmq.REQ)
    client.setsockopt(zmq.RCVTIMEO, 5000)
    client.setsockopt(zmq.SNDTIMEO, 5000)
    client.connect(f"tcp://127.0.0.1:{PORT}")

    # ------------------------------------------------------------------ #
    # HAND-01: ping                                                        #
    # ------------------------------------------------------------------ #
    resp = call(client, "ping")
    if check("ping", resp):
        r = resp["result"]
        assert r.get("pong") is True, f"pong should be True, got {r.get('pong')!r}"
        assert isinstance(r.get("blender_version"), str), (
            f"blender_version should be str, got {type(r.get('blender_version'))}"
        )
        print(f"    Blender version: {r['blender_version']}")

    # ------------------------------------------------------------------ #
    # HAND-02: scene_info                                                  #
    # ------------------------------------------------------------------ #
    resp = call(client, "scene_info")
    if check("scene_info", resp):
        r = resp["result"]
        assert "objects" in r and "count" in r, f"Missing keys in scene_info: {list(r.keys())}"
        print(f"    Objects: {r['count']}")

    # ------------------------------------------------------------------ #
    # HAND-04: list_handlers                                               #
    # ------------------------------------------------------------------ #
    resp = call(client, "list_handlers")
    if check("list_handlers", resp):
        r = resp["result"]
        expected = {"ping", "scene_info", "clear_scene", "list_handlers",
                    "export_obj", "export_stl", "export_glb", "render"}
        actual = set(r.keys())
        missing = expected - actual
        assert not missing, f"Missing handlers: {missing}"
        print(f"    Handlers: {sorted(r.keys())}")

    # ------------------------------------------------------------------ #
    # Add a fresh cube so export tests always have geometry                #
    # ------------------------------------------------------------------ #
    bpy.ops.mesh.primitive_cube_add()
    print("    Added primitive cube for export tests")

    # ------------------------------------------------------------------ #
    # HAND-03: clear_scene                                                 #
    # ------------------------------------------------------------------ #
    resp = call(client, "clear_scene", {"keep_camera": True})
    if check("clear_scene", resp):
        r = resp["result"]
        assert "removed" in r and "count" in r, f"Missing keys in clear_scene: {list(r.keys())}"
        print(f"    Removed {r['count']} objects")

    # Add another cube for export tests (clear_scene removed the previous one).
    bpy.ops.mesh.primitive_cube_add()
    print("    Added primitive cube after clear_scene for export tests")

    # ------------------------------------------------------------------ #
    # HAND-05: export_obj (auto temp path)                                 #
    # ------------------------------------------------------------------ #
    resp = call(client, "export_obj")
    if check("export_obj", resp):
        r = resp["result"]
        assert "file" in r and "size_bytes" in r, f"Missing keys: {list(r.keys())}"
        print(f"    OBJ file: {r['file']} ({r['size_bytes']} bytes)")

    # ------------------------------------------------------------------ #
    # HAND-06: export_stl                                                  #
    # ------------------------------------------------------------------ #
    resp = call(client, "export_stl")
    if check("export_stl", resp):
        r = resp["result"]
        assert "file" in r and "size_bytes" in r, f"Missing keys: {list(r.keys())}"
        print(f"    STL file: {r['file']} ({r['size_bytes']} bytes)")

    # ------------------------------------------------------------------ #
    # HAND-07: export_glb                                                  #
    # ------------------------------------------------------------------ #
    resp = call(client, "export_glb")
    if check("export_glb", resp):
        r = resp["result"]
        assert "file" in r and "size_bytes" in r, f"Missing keys: {list(r.keys())}"
        print(f"    GLB file: {r['file']} ({r['size_bytes']} bytes)")

    # ------------------------------------------------------------------ #
    # HAND-08: render (small resolution + low samples for speed)           #
    # ------------------------------------------------------------------ #
    resp = call(client, "render", {"resolution_x": 64, "resolution_y": 64, "samples": 1})
    if check("render", resp):
        r = resp["result"]
        assert "file" in r, f"Missing 'file' key in render result: {list(r.keys())}"
        assert os.path.exists(r["file"]), f"Render output file not found: {r['file']}"
        print(f"    Render: {r['file']}")

    # ------------------------------------------------------------------ #
    # SRV-04: malformed JSON                                               #
    # ------------------------------------------------------------------ #
    client.send(b"this is not json at all {{{{")
    malformed_resp = {"status": "timeout"}
    for _ in range(100):
        server._poll()
        try:
            raw = client.recv(flags=zmq.NOBLOCK)
            malformed_resp = json.loads(raw)
            break
        except zmq.Again:
            time.sleep(0.01)
    if check("malformed_json", malformed_resp, expected_status="error"):
        assert malformed_resp["error"]["type"] == "JSONDecodeError", (
            f"Expected JSONDecodeError, got {malformed_resp['error']['type']!r}"
        )
        print("    Malformed JSON handled correctly")

    # ------------------------------------------------------------------ #
    # SRV-04 / SRV-02: unknown command                                     #
    # ------------------------------------------------------------------ #
    resp = call(client, "nonexistent_command_xyz_smoke")
    if check("unknown_command", resp, expected_status="error"):
        assert resp["error"]["type"] == "NotFound", (
            f"Expected NotFound, got {resp['error']['type']!r}"
        )
        print("    Unknown command handled correctly")

    # ------------------------------------------------------------------ #
    # Cleanup                                                              #
    # ------------------------------------------------------------------ #
    client.close()
    server.stop_server()
    assert not server.is_running(), "Server should be stopped after stop_server()"
    print("Server stopped cleanly")

    # ------------------------------------------------------------------ #
    # Summary                                                              #
    # ------------------------------------------------------------------ #
    print(f"\n{'=' * 60}")
    print(f"Results: {PASSED} passed, {FAILED} failed")
    print(f"{'=' * 60}")

    if FAILED > 0:
        sys.exit(1)

except Exception as e:
    traceback.print_exc()
    print(f"\nFATAL: {e}")
    try:
        server.stop_server()
    except Exception:
        pass
    sys.exit(2)

finally:
    try:
        unregister()
    except Exception:
        pass
