#!/usr/bin/env python3
"""Connect to a running BlendBridge server and explore the scene.

Prerequisites:
  1. Blender is open with the RPC addon running (sidebar -> RPC -> Start Server)
  2. pip install -e ".[dev]" (from repo root)

Usage:
  python examples/01_hello_blender.py
  python examples/01_hello_blender.py --port 5556
"""
import argparse

from blendbridge.client import BlendBridge, RPCError, RPCTimeoutError, RPCConnectionError


def main():
    parser = argparse.ArgumentParser(description="Hello BlendBridge")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    print(f"Connecting to Blender at tcp://{args.host}:{args.port} ...")

    try:
        with BlendBridge(host=args.host, port=args.port, timeout_ms=3000) as client:
            # Ping
            info = client.ping()
            print(f"Connected! Blender {info['blender_version']}")

            # Scene info
            scene = client.scene_info()
            print(f"\nScene has {scene['count']} object(s):")
            for obj in scene["objects"]:
                marker = " (active)" if obj["name"] == scene["active"] else ""
                print(f"  - {obj['name']} [{obj['type']}]{marker}")

            # List handlers
            handlers = client.list_handlers()
            print(f"\n{len(handlers)} registered handler(s):")
            for name, doc in sorted(handlers.items()):
                print(f"  - {name}: {doc}")

            # Clear and confirm
            result = client.clear_scene(keep_camera=True)
            print(f"\nCleared {result['count']} object(s), kept camera: {result['keep_camera']}")

            scene_after = client.scene_info()
            print(f"Scene now has {scene_after['count']} object(s)")

    except RPCConnectionError as e:
        print(f"Could not connect: {e}")
        print("Is the BlendBridge server running?")
    except RPCTimeoutError as e:
        print(f"Timeout: {e}")
    except RPCError as e:
        print(f"RPC error: [{e.error_type}] {e.message}")


if __name__ == "__main__":
    main()
