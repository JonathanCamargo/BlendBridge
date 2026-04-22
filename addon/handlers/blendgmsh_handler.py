"""BlendGmsh integration handler for BlendBridge.

Exposes BlendGmsh's ``matching_library`` (boundary-condition assignment
for FEM meshes) over the BlendBridge RPC. Handlers cover the full
pipeline (STEP/STL + bc_groups.json -> tagged .msh), re-tagging an
existing mesh, inspection, and PyVista visualization.

Requires:
    - BlendGmsh installed as a Blender extension (id: ``blendgmsh``)
      OR ``matching_library`` otherwise importable in Blender's Python.
    - BlendBridge addon enabled in Blender.

Optional dependencies are declared via ``@requires_dependency`` so that
handlers register even when BlendGmsh is missing. The dependency check
only runs when a handler is actually called.

Usage from Python client:
    from blendbridge.client import BlendBridge

    with BlendBridge() as client:
        # Full pipeline: STEP + bc_groups JSON -> tagged .msh
        report = client.call(
            "blendgmsh_run_pipeline",
            bc_json_path="bc_groups.json",
            geometry_path="model.step",
            output_msh="output.msh",
        )

        # Re-tag an existing mesh
        report = client.call(
            "blendgmsh_tag_mesh",
            bc_json_path="bc_groups.json",
            input_msh="existing.msh",
            output_msh="tagged.msh",
        )

        # Inspect outputs
        info = client.call("blendgmsh_inspect_msh", msh_path="output.msh")
"""
from __future__ import annotations

import importlib
import os
import sys
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional

from ..registry import rpc_handler
from ._deps import requires_dependency


def _ensure_blendgmsh() -> None:
    """Make ``matching_library`` importable from Blender's Python.

    When BlendGmsh is installed as a Blender extension, ``export.ps1`` /
    ``export.sh`` copy ``matching_library/``, ``step_converter/`` and
    ``schema/`` *into* the extension directory. So the parent of
    ``matching_library`` is the extension directory itself — we find it
    via ``addon_utils.modules()`` and prepend it to ``sys.path``.

    An explicit ``BLENDGMSH_PATH`` environment variable (pointing at the
    directory that *contains* ``matching_library``) takes precedence and
    is the recommended override for dev checkouts (e.g. ``C:/git/BlendGmsh``).
    """
    try:
        import matching_library  # noqa: F401
        return
    except ImportError:
        pass

    override = os.environ.get("BLENDGMSH_PATH")
    if override and os.path.isdir(override):
        if override not in sys.path:
            sys.path.insert(0, override)
            importlib.invalidate_caches()
        try:
            import matching_library  # noqa: F401
            return
        except ImportError:
            pass

    try:
        import addon_utils
        for mod in addon_utils.modules():
            name_lower = mod.__name__.lower()
            if "blendgmsh" in name_lower or "blend_gmsh" in name_lower:
                ext_dir = os.path.dirname(mod.__file__)
                if ext_dir not in sys.path:
                    sys.path.insert(0, ext_dir)
                    importlib.invalidate_caches()
                import matching_library  # noqa: F401
                return
    except Exception:
        pass

    raise ImportError(
        "BlendGmsh not found. Install the Blender extension (Edit > "
        "Preferences > Add-ons > Install from Disk on blendgmsh.zip) or "
        "set the BLENDGMSH_PATH environment variable to a directory that "
        "contains the 'matching_library' package."
    )


def _coverage_to_dict(report: Any) -> Dict[str, Any]:
    """Convert a CoverageReport dataclass into a JSON-serializable dict."""
    if is_dataclass(report):
        return asdict(report)
    # Fallback: best-effort attribute read
    return {
        "group_stats": getattr(report, "group_stats", {}),
        "unmatched_surfaces": list(getattr(report, "unmatched_surfaces", [])),
        "total_boundary_facets": int(getattr(report, "total_boundary_facets", 0)),
    }


# =============================================================================
# Pipeline handlers
# =============================================================================

@rpc_handler("blendgmsh_run_pipeline")
@requires_dependency(_ensure_blendgmsh)
def blendgmsh_run_pipeline(
    bc_json_path: str,
    geometry_path: str,
    output_msh: str,
) -> Dict[str, Any]:
    """Run the full BlendGmsh pipeline: geometry + BC JSON -> tagged .msh.

    Mode (BREP vs mesh) is auto-detected from ``bc_json_path``. BREP mode
    assigns physical groups by surface tag before meshing; mesh mode
    KDTree-matches Blender vertex selections post-meshing.

    Args:
        bc_json_path: Path to a ``bc_groups_v1`` JSON file.
        geometry_path: Path to the source geometry (``.step``/``.stp`` for
            BREP mode, ``.stl``/``.obj`` for mesh mode).
        output_msh: Destination path for the tagged ``.msh`` file.

    Returns:
        Dict with the serialized ``CoverageReport`` and the output path.
    """
    from matching_library import run_full_pipeline

    report = run_full_pipeline(bc_json_path, geometry_path, output_msh)
    return {
        "output_msh": output_msh,
        "coverage": _coverage_to_dict(report),
    }


@rpc_handler("blendgmsh_tag_mesh")
@requires_dependency(_ensure_blendgmsh)
def blendgmsh_tag_mesh(
    bc_json_path: str,
    input_msh: str,
    output_msh: str,
) -> Dict[str, Any]:
    """Re-tag an existing ``.msh`` file using a BC groups JSON.

    Args:
        bc_json_path: Path to a ``bc_groups_v1`` JSON file.
        input_msh: Path to the existing ``.msh`` file to re-tag.
        output_msh: Destination path for the tagged ``.msh`` file.

    Returns:
        Dict with the serialized ``CoverageReport`` and the output path.
    """
    from matching_library import tag_existing_mesh

    report = tag_existing_mesh(bc_json_path, input_msh, output_msh)
    return {
        "output_msh": output_msh,
        "coverage": _coverage_to_dict(report),
    }


# =============================================================================
# Inspection handlers
# =============================================================================

@rpc_handler("blendgmsh_inspect_msh")
@requires_dependency(_ensure_blendgmsh)
def blendgmsh_inspect_msh(msh_path: str) -> Dict[str, Any]:
    """Inspect a ``.msh`` file: nodes, elements, physical groups, surfaces.

    Args:
        msh_path: Path to the ``.msh`` file to inspect.

    Returns:
        Dict with keys ``nodes``, ``elements``, ``physical_groups``, ``surfaces``.
    """
    from matching_library import inspect_msh

    return inspect_msh(msh_path)


@rpc_handler("blendgmsh_inspect_bc_groups")
@requires_dependency(_ensure_blendgmsh)
def blendgmsh_inspect_bc_groups(
    bc_json_path: str,
    step_path: str,
) -> Dict[str, Any]:
    """Cross-reference a BC groups JSON against STEP geometry.

    For each group, reports the surface tags, centroids, bounding boxes,
    and areas from the BREP model — useful for debugging tag mismatches.

    Args:
        bc_json_path: Path to a ``bc_groups_v1`` JSON file (BREP mode).
        step_path: Path to the STEP file.

    Returns:
        Dict keyed by group name with per-surface diagnostics.
    """
    from matching_library import inspect_bc_groups

    return inspect_bc_groups(bc_json_path, step_path)


@rpc_handler("blendgmsh_visualize_bc_groups")
@requires_dependency(_ensure_blendgmsh)
def blendgmsh_visualize_bc_groups(
    bc_json_path: str,
    msh_path: str,
    output_png: Optional[str] = None,
) -> Dict[str, Any]:
    """Render a tagged mesh with BC groups color-coded (PyVista).

    When ``output_png`` is provided, rendering is off-screen and saved to
    that path. When omitted, an interactive PyVista window is shown —
    only useful when Blender is running with a display.

    Args:
        bc_json_path: Path to a ``bc_groups_v1`` JSON file.
        msh_path: Path to the tagged ``.msh`` file.
        output_png: Optional PNG output path for off-screen rendering.

    Returns:
        Dict with ``output_png`` (or ``None`` for interactive mode).
    """
    from matching_library import visualize_bc_groups

    visualize_bc_groups(bc_json_path, msh_path, output_png=output_png)
    return {"output_png": output_png}
