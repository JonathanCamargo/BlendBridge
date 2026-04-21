"""Render handler (HAND-08)."""
from __future__ import annotations
import os
import tempfile
import uuid
import bpy

from ..registry import rpc_handler


@rpc_handler("render")
def render(filepath: str = None,
           resolution_x: int = 1920,
           resolution_y: int = 1080,
           samples: int = 32) -> dict:
    """Render the current scene to a still image.

    Sets scene.render.filepath/resolution_x/resolution_y and configures
    samples on whichever engine is active (Cycles: scene.cycles.samples;
    Eevee: scene.eevee.taa_render_samples). Then calls
    bpy.ops.render.render(write_still=True).

    Force PNG output format so the filepath extension matches the
    file written (RESEARCH.md Pitfall 7).

    Returns {"file": <path>}.
    """
    path = filepath or os.path.join(
        tempfile.gettempdir(), f"blendbridge_{uuid.uuid4().hex}.png"
    )
    scene = bpy.context.scene
    scene.render.filepath = path
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    # Force PNG so the file on disk matches the filepath extension
    scene.render.image_settings.file_format = "PNG"
    # Samples on both engines (guarded by hasattr — depends on active engine)
    if hasattr(scene, "cycles"):
        scene.cycles.samples = samples
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = samples
    bpy.ops.render.render(write_still=True)
    return {"file": path}
