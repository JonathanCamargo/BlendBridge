"""Scene handlers: ping, scene_info, clear_scene, list_handlers (HAND-01..04)."""
from __future__ import annotations
import bpy

from ..registry import rpc_handler, list_handlers as _registry_list, _HANDLERS


@rpc_handler("ping")
def ping() -> dict:
    """Return pong plus Blender version string."""
    return {"pong": True, "blender_version": bpy.app.version_string}


@rpc_handler("scene_info")
def scene_info() -> dict:
    """Return a summary of the current scene's objects."""
    scene = bpy.context.scene
    objects = [{"name": o.name, "type": o.type} for o in scene.objects]
    active_obj = bpy.context.view_layer.objects.active
    return {
        "objects": objects,
        "count": len(objects),
        "active": active_obj.name if active_obj else None,
    }


@rpc_handler("clear_scene")
def clear_scene(keep_camera: bool = True) -> dict:
    """Remove all mesh objects from the current scene.

    Uses bpy.data.objects.remove directly (not bpy.ops.object.delete)
    because server-context callbacks have no 3D-view context and
    bpy.ops.object.delete.poll() fails without one. See RESEARCH.md
    Pitfall 4.
    """
    removed = []
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" or (not keep_camera and obj.type == "CAMERA"):
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    return {"removed": removed, "count": len(removed), "keep_camera": keep_camera}


# Keep a reference to all scene handlers so they can be re-registered
# if the registry is cleared between tests.
_SCENE_HANDLERS = {
    "ping": ping,
    "scene_info": scene_info,
    "clear_scene": clear_scene,
}


def _ensure_scene_handlers_registered() -> None:
    """Re-register scene handlers if the registry was cleared (e.g. between tests)."""
    for name, fn in _SCENE_HANDLERS.items():
        if name not in _HANDLERS:
            _HANDLERS[name] = fn


@rpc_handler("list_handlers")
def list_handlers() -> dict:
    """Return all registered handler names with their docstrings."""
    # Re-register scene handlers if registry was cleared (test isolation pattern).
    _ensure_scene_handlers_registered()
    # Also re-register self if cleared:
    if "list_handlers" not in _HANDLERS:
        _HANDLERS["list_handlers"] = list_handlers
    return _registry_list()
