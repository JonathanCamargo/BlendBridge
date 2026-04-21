"""Export handlers: obj, stl, glb (HAND-05..07).

Parameter names verified from 02-EXPORTER-PROBE.md against Blender 4.5.1 LTS:
  - bpy.ops.wm.obj_export       uses filepath + export_selected_objects
  - bpy.ops.wm.stl_export       uses filepath + export_selected_objects
  - bpy.ops.export_scene.gltf   uses filepath + export_format + use_selection

Key operator choices (RESEARCH.md Pitfall 1):
  - bpy.ops.wm.obj_export       (NOT bpy.ops.export_scene.obj — removed 4.0)
  - bpy.ops.wm.stl_export       (NOT bpy.ops.export_mesh.stl — legacy 4.1)
  - bpy.ops.export_scene.gltf   (glTF stays in export_scene, NOT moved to wm)
"""
from __future__ import annotations
import os
import tempfile
import uuid
import bpy

from ..registry import rpc_handler


def _tmp_path(ext: str) -> str:
    """Generate a cross-platform temp path with uuid4 randomness.

    Uses tempfile.gettempdir() (not '/tmp') so Windows users don't hit
    C:\\tmp-doesn't-exist errors. RESEARCH.md "Don't Hand-Roll" table.
    """
    return os.path.join(tempfile.gettempdir(), f"blendbridge_{uuid.uuid4().hex}.{ext}")


def _size(path: str) -> int:
    """Return file size in bytes, or 0 if the file doesn't exist."""
    try:
        return os.path.getsize(path) if os.path.exists(path) else 0
    except OSError:
        return 0


@rpc_handler("export_obj")
def export_obj(filepath: str = None, selection_only: bool = False) -> dict:
    """Export scene (or selection) to OBJ via Blender 4.x wm.obj_export.

    Returns {"file": <path>, "size_bytes": <int>}.
    """
    path = filepath or _tmp_path("obj")
    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=selection_only)
    return {"file": path, "size_bytes": _size(path)}


@rpc_handler("export_stl")
def export_stl(filepath: str = None, selection_only: bool = False) -> dict:
    """Export scene (or selection) to STL via Blender 4.1+ wm.stl_export.

    Returns {"file": <path>, "size_bytes": <int>}.
    """
    path = filepath or _tmp_path("stl")
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=selection_only)
    return {"file": path, "size_bytes": _size(path)}


@rpc_handler("export_glb")
def export_glb(filepath: str = None) -> dict:
    """Export scene to binary glTF via the Khronos io_scene_gltf2 addon.

    Returns {"file": <path>, "size_bytes": <int>}.
    Note: GLTF uses use_selection (not export_selected_objects) — confirmed
    in 02-EXPORTER-PROBE.md for Blender 4.5.1 LTS.
    """
    path = filepath or _tmp_path("glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB")
    return {"file": path, "size_bytes": _size(path)}
