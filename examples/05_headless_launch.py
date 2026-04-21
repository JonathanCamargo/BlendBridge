#!/usr/bin/env python3
"""Launch a headless Blender instance and interact with it programmatically.

No GUI needed — this script spawns its own Blender process, uses it,
and shuts it down automatically.

Prerequisites:
  1. pip install -e ".[dev]" (from repo root)
  2. pyzmq installed in Blender's Python (python scripts/install_zmq_blender.py)
  3. BLENDER_PATH env var set, or pass --blender

Usage:
  python examples/03_headless_launch.py --blender /path/to/blender
  BLENDER_PATH=/path/to/blender python examples/03_headless_launch.py
"""
import argparse

from blendbridge.client import BlendBridge, RPCTimeoutError


def main():
    parser = argparse.ArgumentParser(description="Headless Blender demo")
    parser.add_argument("--blender", default=None, help="Path to Blender binary")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    print("Launching headless Blender ...")

    try:
        with BlendBridge.launch(
            blender_path=args.blender,
            port=args.port,
            timeout=30.0,
        ) as client:
            info = client.ping()
            print(f"Blender {info['blender_version']} is running (headless)\n")

            # Check the default scene
            scene = client.scene_info()
            print(f"Default scene: {scene['count']} object(s)")
            for obj in scene["objects"]:
                print(f"  - {obj['name']} [{obj['type']}]")

            # Clear it
            client.clear_scene(keep_camera=True)
            print("\nScene cleared.")

            # Export the empty scene (demonstrates the full round trip)
            result = client.export_glb()
            print(f"Exported empty scene: {result['file']} ({result['size_bytes']} bytes)")

            print("\nDone! Blender will shut down automatically.")

    except RPCTimeoutError:
        print("Failed to start Blender within 30 seconds.")
        print("Check that BLENDER_PATH is set or pass --blender /path/to/blender")


if __name__ == "__main__":
    main()
