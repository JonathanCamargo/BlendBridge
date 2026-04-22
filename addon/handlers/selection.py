"""Selection handlers: extract subsets of a mesh as BC-group-shaped data.

``select_faces_by_bbox`` filters a mesh object's polygons by world-space
centroid and returns the selected faces in the exact shape expected by
a BlendGmsh ``bc_groups_v1`` mesh-mode group — so the client can drop
the result straight into a ``bc_groups.json`` without further reshaping.

``get_mesh_stats`` returns the ``mesh_stats`` block required by the
``bc_groups_v1`` schema (vertex/face counts + world-space bounding box).

Example client usage::

    from blendbridge.client import BlendBridge

    with BlendBridge() as c:
        c.call("blendgen_flat_spring", spine_type="SINUSOID", spring_length=100)
        c.call("export_stl", filepath="/tmp/spring.stl", selection_only=False)

        mesh_stats = c.call("get_mesh_stats", object_name="flat_spring")
        fixed = c.call("select_faces_by_bbox",
                       object_name="flat_spring",
                       bbox_max=[None, -45, None])   # Y <= -45 (start tab)
        slide = c.call("select_faces_by_bbox",
                       object_name="flat_spring",
                       bbox_min=[None,  45, None])   # Y >=  45 (end tab)

    bc = {
        "schema_version": 1, "source": "blendbridge", "mode": "mesh",
        "step_file": "/tmp/spring.stl", "units": "millimeters",
        "groups": {"fixed": fixed, "slide": slide},
        "mesh_stats": mesh_stats,
    }
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import bpy

from ..registry import rpc_handler


def _resolve_bounds(
    bbox_min: Optional[List[Optional[float]]],
    bbox_max: Optional[List[Optional[float]]],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Normalize optional per-axis bounds into full (min, max) 3-tuples.

    ``None`` (either the whole list or an individual entry) means unbounded
    on that axis — represented with ``±inf`` so a single ``<=`` / ``>=``
    check covers every case.
    """
    def axis(lo_hi: Optional[List[Optional[float]]], default: float) -> tuple:
        if lo_hi is None:
            return (default, default, default)
        if len(lo_hi) != 3:
            raise ValueError(
                f"bbox must have exactly 3 entries, got {len(lo_hi)}"
            )
        return tuple(default if v is None else float(v) for v in lo_hi)

    return axis(bbox_min, -math.inf), axis(bbox_max, math.inf)


@rpc_handler("select_faces_by_bbox")
def select_faces_by_bbox(
    object_name: str,
    bbox_min: Optional[List[Optional[float]]] = None,
    bbox_max: Optional[List[Optional[float]]] = None,
) -> Dict[str, Any]:
    """Return faces whose world-space centroid lies inside a bbox.

    The return shape matches a ``bc_groups_v1`` mesh-mode group entry:
    ``{vertices, face_vertex_indices, vertex_count, face_count}``. Polygons
    are fan-triangulated from ``polygon.vertices[0]`` so the output is a
    pure triangle list — matching what STL export produces and what
    BlendGmsh's KDTree centroid matching expects.

    Coordinates are in world space (``obj.matrix_world`` applied), so they
    line up with the STL emitted by ``export_stl`` and with the Gmsh mesh
    BlendGmsh builds from it.

    Args:
        object_name: Name of the target object in ``bpy.data.objects``.
        bbox_min: Optional ``[x, y, z]`` lower bound. ``None`` for the whole
            list, or ``None`` for any single entry, leaves that axis
            unbounded below.
        bbox_max: Optional ``[x, y, z]`` upper bound with the same semantics.

    Returns:
        Dict with ``vertices`` (``list[list[float]]``),
        ``face_vertex_indices`` (``list[list[int]]`` into ``vertices``),
        ``vertex_count``, and ``face_count``.

    Raises:
        ValueError: Object not found, not a mesh, or malformed bbox.
    """
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object '{object_name}' not found")
    if obj.type != "MESH":
        raise ValueError(
            f"Object '{object_name}' is type {obj.type}, expected MESH"
        )

    (xmin, ymin, zmin), (xmax, ymax, zmax) = _resolve_bounds(bbox_min, bbox_max)

    mesh = obj.data
    mw = obj.matrix_world

    world_verts = [mw @ v.co for v in mesh.vertices]

    out_verts: List[List[float]] = []
    out_faces: List[List[int]] = []
    remap: Dict[int, int] = {}

    def _local_index(src_idx: int) -> int:
        mapped = remap.get(src_idx)
        if mapped is not None:
            return mapped
        wv = world_verts[src_idx]
        mapped = len(out_verts)
        out_verts.append([wv.x, wv.y, wv.z])
        remap[src_idx] = mapped
        return mapped

    for poly in mesh.polygons:
        cx, cy, cz = mw @ poly.center
        if not (xmin <= cx <= xmax and ymin <= cy <= ymax and zmin <= cz <= zmax):
            continue

        vids = list(poly.vertices)
        if len(vids) < 3:
            continue

        v0 = _local_index(vids[0])
        for i in range(1, len(vids) - 1):
            vi = _local_index(vids[i])
            vj = _local_index(vids[i + 1])
            out_faces.append([v0, vi, vj])

    return {
        "vertices": out_verts,
        "face_vertex_indices": out_faces,
        "vertex_count": len(out_verts),
        "face_count": len(out_faces),
    }


@rpc_handler("get_mesh_stats")
def get_mesh_stats(object_name: str) -> Dict[str, Any]:
    """Return mesh stats for an object in the ``bc_groups_v1`` schema shape.

    Returns a dict matching the ``mesh_stats`` field required by the
    ``bc_groups_v1`` JSON schema:

    .. code-block:: json

        {
            "total_vertices": <int>,
            "total_faces": <int>,
            "bounding_box": {
                "min": [x, y, z],
                "max": [x, y, z]
            }
        }

    Coordinates are in world space (``obj.matrix_world`` applied).

    Args:
        object_name: Name of the target object in ``bpy.data.objects``.

    Returns:
        Dict with ``total_vertices``, ``total_faces``, and ``bounding_box``.

    Raises:
        ValueError: Object not found or not a mesh.
    """
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object '{object_name}' not found")
    if obj.type != "MESH":
        raise ValueError(
            f"Object '{object_name}' is type {obj.type}, expected MESH"
        )

    mesh = obj.data
    mw = obj.matrix_world

    xs, ys, zs = [], [], []
    for v in mesh.vertices:
        wv = mw @ v.co
        xs.append(wv.x)
        ys.append(wv.y)
        zs.append(wv.z)

    if xs:
        bb_min = [min(xs), min(ys), min(zs)]
        bb_max = [max(xs), max(ys), max(zs)]
    else:
        bb_min = [0.0, 0.0, 0.0]
        bb_max = [0.0, 0.0, 0.0]

    return {
        "total_vertices": len(mesh.vertices),
        "total_faces": len(mesh.polygons),
        "bounding_box": {
            "min": bb_min,
            "max": bb_max,
        },
    }
