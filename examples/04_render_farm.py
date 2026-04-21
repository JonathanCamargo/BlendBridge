#!/usr/bin/env python3
"""Render the same scene at multiple resolutions and sample counts.

Demonstrates using a single persistent connection to batch render
with varying parameters — useful for quality/performance comparisons.

Prerequisites:
  1. Blender is open with a scene you want to render, RPC server running
  2. pip install -e ".[dev]" (from repo root)

Usage:
  python examples/04_render_farm.py
  python examples/04_render_farm.py --output-dir /tmp/renders
"""
import argparse
import time
from pathlib import Path

from blendbridge.client import BlendBridge


RENDER_CONFIGS = [
    {"name": "thumbnail", "resolution_x": 480, "resolution_y": 270, "samples": 8},
    {"name": "preview", "resolution_x": 960, "resolution_y": 540, "samples": 16},
    {"name": "standard", "resolution_x": 1920, "resolution_y": 1080, "samples": 32},
    {"name": "high_quality", "resolution_x": 1920, "resolution_y": 1080, "samples": 128},
]


def main():
    parser = argparse.ArgumentParser(description="Multi-config render farm")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd() / "renders"
    output_dir.mkdir(parents=True, exist_ok=True)

    with BlendBridge(host=args.host, port=args.port, timeout_ms=120_000) as client:
        info = client.ping()
        scene = client.scene_info()
        print(f"Blender {info['blender_version']} — {scene['count']} object(s) in scene\n")

        print(f"{'Config':<15} {'Resolution':<12} {'Samples':<8} {'Time':>8}")
        print("-" * 48)

        for config in RENDER_CONFIGS:
            filepath = output_dir / f"{config['name']}.png"

            start = time.perf_counter()
            result = client.render(
                filepath=str(filepath),
                resolution_x=config["resolution_x"],
                resolution_y=config["resolution_y"],
                samples=config["samples"],
            )
            elapsed = time.perf_counter() - start

            res = f"{config['resolution_x']}x{config['resolution_y']}"
            print(f"{config['name']:<15} {res:<12} {config['samples']:<8} {elapsed:>7.1f}s")

        print(f"\nAll renders saved to: {output_dir}")


if __name__ == "__main__":
    main()
