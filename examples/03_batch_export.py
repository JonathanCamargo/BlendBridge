#!/usr/bin/env python3
"""Export the current Blender scene in multiple formats.

Demonstrates convenience methods for OBJ, STL, and GLB export,
plus the raw call() API for custom parameters.

Prerequisites:
  1. Blender is open with some objects and the RPC server running
  2. pip install -e ".[dev]" (from repo root)

Usage:
  python examples/02_batch_export.py
  python examples/02_batch_export.py --output-dir /tmp/exports
"""
import argparse
import os
from pathlib import Path

from blendbridge.client import BlendBridge


def main():
    parser = argparse.ArgumentParser(description="Batch export Blender scene")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--output-dir", default=None, help="Directory for exported files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd() / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    with BlendBridge(host=args.host, port=args.port) as client:
        scene = client.scene_info()
        print(f"Exporting scene with {scene['count']} object(s)\n")

        # Export in all three formats
        formats = {
            "OBJ": lambda p: client.export_obj(filepath=str(p)),
            "STL": lambda p: client.export_stl(filepath=str(p)),
            "GLB": lambda p: client.export_glb(filepath=str(p)),
        }

        for fmt, export_fn in formats.items():
            ext = fmt.lower()
            filepath = output_dir / f"scene.{ext}"
            result = export_fn(filepath)
            size_kb = result["size_bytes"] / 1024
            print(f"  {fmt}: {result['file']} ({size_kb:.1f} KB)")

        # Render a preview
        render_path = output_dir / "preview.png"
        print(f"\nRendering preview at 960x540 ...")
        result = client.render(
            filepath=str(render_path),
            resolution_x=960,
            resolution_y=540,
            samples=16,
        )
        print(f"  PNG: {result['file']}")

        print(f"\nAll exports saved to: {output_dir}")


if __name__ == "__main__":
    main()
