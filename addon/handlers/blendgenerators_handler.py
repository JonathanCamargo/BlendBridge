"""BlendGenerators integration handler for BlendBridge.

This handler provides RPC access to BlendGenerators' gripper finger and flat spring
generators.

Requires:
    - BlendGenerators installed as Blender addon/extension
    - BlendBridge addon enabled in Blender

Optional dependencies are declared via ``@requires_dependency`` so that
handlers register even when BlendGenerators is missing. The dependency
check only runs when a handler is actually called.

Usage from Python client:
    from blendbridge.client import BlendBridge
    
    with BlendBridge() as client:
        # Generate a gripper finger
        result = client.call("blendgen_gripper_finger", 
                            finger_length=100, 
                            base_width=25,
                            texture_type="RIDGES")
        
        # Generate a flat spring
        result = client.call("blendgen_flat_spring",
                            spring_length=80,
                            spine_type="SINUSOID")
"""
from __future__ import annotations

import sys
import os
import importlib
from typing import Any, Dict, Optional

from ..registry import rpc_handler
from ._deps import requires_dependency
import bpy


def _ensure_blendgenerators():
    """Locate the BlendGenerators addon and ensure it is importable.

    Adds the *parent* directory of the ``blend_generators`` package to
    ``sys.path`` so that ``from blend_generators.generators...`` resolves
    correctly and relative imports inside the addon still work.

    Called via ``@requires_dependency(_ensure_blendgenerators)`` so that
    ``@rpc_handler`` decorators always execute (registering the handler)
    regardless of whether BlendGenerators is installed.
    """
    # If already importable, nothing to do.
    try:
        import blend_generators  # noqa: F401
        return
    except ImportError:
        pass
    # Find the addon via Blender's addon_utils and add its parent dir.
    try:
        import addon_utils
        for mod in addon_utils.modules():
            mod_name = mod.__name__.lower()
            if 'blend_generators' in mod_name or 'blendgenerators' in mod_name:
                pkg_dir = os.path.dirname(mod.__file__)       # .../blend_generators
                parent_dir = os.path.dirname(pkg_dir)         # .../extensions/user_default
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                    importlib.invalidate_caches()
                return
    except Exception:
        pass
    raise ImportError(
        "BlendGenerators addon not found. Please install it: "
        "Edit > Preferences > Add-ons > Install from Disk"
    )


# =============================================================================
# Gripper Finger Handlers
# =============================================================================

@rpc_handler("blendgen_gripper_finger")
@requires_dependency(_ensure_blendgenerators)
def blendgen_gripper_finger(
    finger_length: float = 80.0,
    base_width: float = 20.0,
    base_height: float = 10.0,
    texture_type: str = "NONE",  # NONE, RIDGES, BUMPS, SERRATIONS
    vgroove_enabled: bool = False,
    # Ridge parameters (when texture_type="RIDGES")
    ridge_depth: float = 2.0,
    ridge_count: int = 5,
    ridge_width_ratio: float = 0.5,
    ridge_orientation: float = 0.0,
    # Bump parameters (when texture_type="BUMPS")
    bump_depth: float = 2.0,
    bump_diameter: float = 4.0,
    bump_spacing: float = 6.0,
    bump_shape: float = 0.0,
    # Serration parameters (when texture_type="SERRATIONS")
    serration_depth: float = 2.0,
    serration_pitch: float = 4.0,
    serration_orientation: float = 0.0,
    # V-groove parameters (when vgroove_enabled=True)
    vgroove_depth: float = 2.0,
    vgroove_angle: float = 60.0,
    location: Optional[list] = None,
) -> Dict[str, Any]:
    """Generate a gripper finger mesh using BlendGenerators.
    
    Args:
        finger_length: Total length along Y axis (20-200 mm)
        base_width: Width along X axis (5-80 mm)
        base_height: Height along Z axis (3-40 mm)
        texture_type: Surface texture (NONE, RIDGES, BUMPS, SERRATIONS)
        vgroove_enabled: Add V-groove tip channel
        ridge_depth: Ridge protrusion depth (0.5-5.0 mm)
        ridge_count: Number of ridges (2-20)
        ridge_width_ratio: Ridge vs groove duty cycle (0.2-0.8)
        ridge_orientation: Ridge angle in degrees (0-90)
        bump_depth: Bump height (0.5-5.0 mm)
        bump_diameter: Bump diameter (0.5-10.0 mm)
        bump_spacing: Center-to-center spacing (1.0-15.0 mm)
        bump_shape: 0=hemisphere, 1=truncated cone (0.0-1.0)
        serration_depth: Tooth height (0.5-5.0 mm)
        serration_pitch: Tooth-to-tooth distance (1.0-10.0 mm)
        serration_orientation: Serration angle in degrees (0-90)
        vgroove_depth: Groove depth (0.5-5.0 mm)
        vgroove_angle: V-groove opening angle (30-120 degrees)
        location: [x, y, z] position (default: origin)
    
    Returns:
        Dict with object info including name, dimensions, vertex/edge/face counts,
        and diagnostic report.
    """
    from blend_generators.generators.gripper_finger.api import generate as generate_finger

    # Build parameter dict
    beta = {
        "finger_length": finger_length,
        "base_width": base_width,
        "base_height": base_height,
        "texture_type": texture_type,
        "vgroove_enabled": vgroove_enabled,
    }
    
    # Add texture-specific parameters
    if texture_type == "RIDGES":
        beta.update({
            "ridge_depth": ridge_depth,
            "ridge_count": ridge_count,
            "ridge_width_ratio": ridge_width_ratio,
            "ridge_orientation": ridge_orientation,
        })
    elif texture_type == "BUMPS":
        beta.update({
            "bump_depth": bump_depth,
            "bump_diameter": bump_diameter,
            "bump_spacing": bump_spacing,
            "bump_shape": bump_shape,
        })
    elif texture_type == "SERRATIONS":
        beta.update({
            "serration_depth": serration_depth,
            "serration_pitch": serration_pitch,
            "serration_orientation": serration_orientation,
        })
    
    # Add V-groove parameters
    if vgroove_enabled:
        beta.update({
            "vgroove_depth": vgroove_depth,
            "vgroove_angle": vgroove_angle,
        })
    
    from blend_generators.generators.gripper_finger.api import generate as generate_finger

    # Generate the finger
    obj = generate_finger(beta)
    
    # Move to specified location if provided
    if location:
        obj.location = tuple(location)
    
    # Get diagnostic info
    diagnostic_report = obj.get("diagnostic_report", "{}")
    diagnostic_severity = obj.get("diagnostic_severity", "UNKNOWN")
    
    return {
        "name": obj.name,
        "type": "gripper_finger",
        "location": list(obj.location),
        "dimensions": list(obj.dimensions),
        "vertices": len(obj.data.vertices),
        "edges": len(obj.data.edges),
        "faces": len(obj.data.polygons),
        "diagnostic_severity": diagnostic_severity,
        "diagnostic_report": diagnostic_report,
    }


@rpc_handler("blendgen_gripper_finger_export")
@requires_dependency(_ensure_blendgenerators)
def blendgen_gripper_finger_export(
    output_path: str,
    finger_length: float = 80.0,
    base_width: float = 20.0,
    base_height: float = 10.0,
    texture_type: str = "NONE",
    **kwargs
) -> Dict[str, Any]:
    """Generate a gripper finger and export to STL.
    
    Args:
        output_path: Destination path for the exported STL file
        **kwargs: Same parameters as blendgen_gripper_finger()
    
    Returns:
        Dict with export result including file path, size, and diagnostic info.
    """
    from blend_generators.generators.gripper_finger.api import generate_and_export as generate_and_export_finger

    # Build parameter dict
    beta = {
        "finger_length": finger_length,
        "base_width": base_width,
        "base_height": base_height,
        "texture_type": texture_type,
    }
    
    # Add any additional kwargs
    beta.update(kwargs)
    
    # Generate and export
    obj, ok, msg = generate_and_export_finger(beta, output_path)
    
    return {
        "success": ok,
        "message": msg,
        "file": output_path if ok else None,
        "object_name": obj.name if obj else None,
    }


# =============================================================================
# Flat Spring Handlers
# =============================================================================

@rpc_handler("blendgen_flat_spring")
@requires_dependency(_ensure_blendgenerators)
def blendgen_flat_spring(
    spring_length: float = 100.0,
    spring_width: float = 3.0,
    spring_thickness: float = 1.2,
    spine_type: str = "SINUSOID",  # SINUSOID, SERPENTINE, ZIGZAG, SPIRAL, CUSTOM
    # Sinusoid parameters
    sinusoid_amplitude: float = 5.0,
    sinusoid_frequency: float = 3.0,
    sinusoid_phase: float = 0.0,
    # Serpentine parameters
    serpentine_amplitude: float = 5.0,
    serpentine_wavelength: float = 20.0,
    serpentine_phase: float = 0.0,
    # Zigzag parameters
    zigzag_amplitude: float = 5.0,
    zigzag_wavelength: float = 15.0,
    zigzag_phase: float = 0.0,
    # Spiral parameters
    spiral_turns: float = 3.0,
    spiral_radius: float = 10.0,
    spiral_growth: float = 2.0,
    # End tabs
    end_tab_length: float = 10.0,
    end_tab_width: float = 5.0,
    end_tab_style: str = "ROUNDED",  # ROUNDED, SQUARE, TAPERED
    location: Optional[list] = None,
) -> Dict[str, Any]:
    """Generate a flat spring mesh using BlendGenerators.
    
    Args:
        spring_length: Total length along Y axis (20-300 mm)
        spring_width: Strip width along X axis (1-80 mm)
        spring_thickness: Material thickness (0.3-5.0 mm)
        spine_type: Wave pattern (SINUSOID, SERPENTINE, ZIGZAG, SPIRAL, CUSTOM)
        sinusoid_amplitude: Wave amplitude (mm)
        sinusoid_frequency: Cycles per unit length
        sinusoid_phase: Phase offset (radians)
        serpentine_amplitude: Serpentine amplitude (mm)
        serpentine_wavelength: Serpentine wavelength (mm)
        serpentine_phase: Phase offset (radians)
        zigzag_amplitude: Zigzag amplitude (mm)
        zigzag_wavelength: Zigzag wavelength (mm)
        zigzag_phase: Phase offset (radians)
        spiral_turns: Number of spiral turns
        spiral_radius: Base spiral radius (mm)
        spiral_growth: Radius growth per turn (mm)
        end_tab_length: End tab length (mm)
        end_tab_width: End tab width (mm)
        end_tab_style: Tab shape (ROUNDED, SQUARE, TAPERED)
        location: [x, y, z] position (default: origin)
    
    Returns:
        Dict with object info including name, dimensions, vertex/edge/face counts,
        and diagnostic report.
    """
    from blend_generators.generators.flat_spring.api import generate_spring

    # Build parameter dict
    params = {
        "spring_length": spring_length,
        "spring_width": spring_width,
        "spring_thickness": spring_thickness,
        "spine_type": spine_type,
        "end_tab_length": end_tab_length,
        "end_tab_width": end_tab_width,
        "end_tab_style": end_tab_style,
    }
    
    # Add spine-specific parameters
    if spine_type == "SINUSOID":
        params.update({
            "sinusoid_amplitude": sinusoid_amplitude,
            "sinusoid_frequency": sinusoid_frequency,
            "sinusoid_phase": sinusoid_phase,
        })
    elif spine_type == "SERPENTINE":
        params.update({
            "serpentine_amplitude": serpentine_amplitude,
            "serpentine_wavelength": serpentine_wavelength,
            "serpentine_phase": serpentine_phase,
        })
    elif spine_type == "ZIGZAG":
        params.update({
            "zigzag_amplitude": zigzag_amplitude,
            "zigzag_wavelength": zigzag_wavelength,
            "zigzag_phase": zigzag_phase,
        })
    elif spine_type == "SPIRAL":
        params.update({
            "spiral_turns": spiral_turns,
            "spiral_radius": spiral_radius,
            "spiral_growth": spiral_growth,
        })
    
    # Generate the spring
    obj = generate_spring(params)
    
    # Move to specified location if provided
    if location:
        obj.location = tuple(location)
    
    # Get diagnostic info
    diagnostic_report = obj.get("diagnostic_report", "{}")
    diagnostic_severity = obj.get("diagnostic_severity", "UNKNOWN")
    
    return {
        "name": obj.name,
        "type": "flat_spring",
        "location": list(obj.location),
        "dimensions": list(obj.dimensions),
        "vertices": len(obj.data.vertices),
        "edges": len(obj.data.edges),
        "faces": len(obj.data.polygons),
        "diagnostic_severity": diagnostic_severity,
        "diagnostic_report": diagnostic_report,
    }


@rpc_handler("blendgen_flat_spring_export")
@requires_dependency(_ensure_blendgenerators)
def blendgen_flat_spring_export(
    output_path: str,
    spring_length: float = 100.0,
    spring_width: float = 3.0,
    spring_thickness: float = 1.2,
    spine_type: str = "SINUSOID",
    **kwargs
) -> Dict[str, Any]:
    """Generate a flat spring and export to STL.
    
    Args:
        output_path: Destination path for the exported STL file
        **kwargs: Same parameters as blendgen_flat_spring()
    
    Returns:
        Dict with export result including file path, size, and diagnostic info.
    """
    from blend_generators.generators.flat_spring.api import generate_spring_and_export

    # Build parameter dict
    params = {
        "spring_length": spring_length,
        "spring_width": spring_width,
        "spring_thickness": spring_thickness,
        "spine_type": spine_type,
    }
    
    # Add any additional kwargs
    params.update(kwargs)
    
    # Generate and export
    obj, ok, msg = generate_spring_and_export(params, output_path)
    
    return {
        "success": ok,
        "message": msg,
        "file": output_path if ok else None,
        "object_name": obj.name if obj else None,
    }


# =============================================================================
# Utility Handlers
# =============================================================================

@rpc_handler("blendgen_clear_scene")
def blendgen_clear_scene(keep_camera: bool = True) -> Dict[str, Any]:
    """Clear the scene, optionally keeping the camera.
    
    Useful before generating multiple objects in batch.
    
    Args:
        keep_camera: If True, preserve the default camera
    
    Returns:
        Dict with count of removed objects
    """
    removed = []
    
    for obj in bpy.context.scene.objects:
        if keep_camera and obj.type == 'CAMERA':
            continue
        removed.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)
    
    return {
        "removed": removed,
        "count": len(removed),
        "keep_camera": keep_camera,
    }


@rpc_handler("blendgen_get_schema")
@requires_dependency(_ensure_blendgenerators)
def blendgen_get_schema(generator_type: str = "gripper_finger") -> Dict[str, Any]:
    """Get the parameter schema for a generator.
    
    Args:
        generator_type: "gripper_finger" or "flat_spring"
    
    Returns:
        Dict with parameter definitions including types, ranges, and defaults
    """
    if generator_type == "gripper_finger":
        from blend_generators.generators.gripper_finger.schema import BETA_SCHEMA
        return {
            "generator": generator_type,
            "schema": BETA_SCHEMA,
        }
    elif generator_type == "flat_spring":
        from blend_generators.generators.flat_spring.schema import SPRING_SCHEMA
        return {
            "generator": generator_type,
            "schema": SPRING_SCHEMA,
        }
    else:
        return {
            "error": f"Unknown generator type: {generator_type}",
            "available": ["gripper_finger", "flat_spring"],
        }
