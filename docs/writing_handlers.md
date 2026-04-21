# Writing Custom Handlers

How to add your own RPC commands to blendbridge.

## Basics

A handler is a Python function decorated with `@rpc_handler`:

```python
from addon.registry import rpc_handler

@rpc_handler("greet")
def greet(name: str = "World") -> dict:
    """Say hello."""
    return {"greeting": f"Hello, {name}!"}
```

That's it. Once imported, this handler responds to `{"command": "greet", "params": {"name": "Alice"}}`.

## Rules

### Parameters

- Parameters come from the request's `params` dict as keyword arguments
- Use default values for optional parameters
- The router passes `**params` directly — type validation is your responsibility
- Raise `ValueError` or `TypeError` for bad input (the router catches them and returns structured errors)

### Return Value

- Must return a `dict` (or anything JSON-serializable that becomes a dict)
- The return value goes into `response["result"]`
- Keep return values simple: strings, numbers, lists, dicts

### Errors

- Raise exceptions for error conditions — don't return error dicts manually
- The router catches all exceptions and wraps them in the error envelope format:
  ```json
  {"status": "error", "error": {"type": "ValueError", "message": "...", "traceback": "..."}}
  ```
- The server never crashes. Even unhandled exceptions produce a valid error response.

### bpy Access

- Handlers run on Blender's main thread (via `bpy.app.timers`), so `bpy` calls are safe
- Import `bpy` inside the handler function or at the module top level
- Don't spawn threads that touch `bpy`

## Step-by-Step Example

Let's build a handler that creates a UV sphere and returns its stats.

### 1. Create the handler file

```python
# addon/handlers/shapes.py
from addon.registry import rpc_handler
import bpy


@rpc_handler("create_sphere")
def create_sphere(
    radius: float = 1.0,
    segments: int = 32,
    rings: int = 16,
    location: list = None,
) -> dict:
    """Create a UV sphere and return its mesh stats."""
    if radius <= 0:
        raise ValueError(f"radius must be positive, got {radius}")
    if segments < 3:
        raise ValueError(f"segments must be >= 3, got {segments}")

    loc = tuple(location) if location else (0, 0, 0)

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius,
        segments=segments,
        ring_count=rings,
        location=loc,
    )

    obj = bpy.context.active_object
    mesh = obj.data

    return {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.polygons),
        "edges": len(mesh.edges),
        "location": list(obj.location),
    }
```

### 2. Register it

Add the import to `addon/handlers/__init__.py`:

```python
from . import scene
from . import export
from . import render
from . import shapes  # <-- add this line
```

The import triggers the `@rpc_handler` decorator, which registers the function.

### 3. Call it

From Python:

```python
from blendbridge.client import BlendBridge

with BlendBridge() as client:
    result = client.call("create_sphere", radius=2.5, segments=64)
    print(result)
    # {'name': 'Sphere', 'vertices': 1954, 'faces': 1984, 'edges': 3936, 'location': [0.0, 0.0, 0.0]}
```

From CLI:

```bash
blendbridge call create_sphere --param radius=2.5 --param segments=64
```

### 4. Handle errors

```python
# Bad input -> structured error
result = client.call("create_sphere", radius=-1)
# Raises: RPCError(error_type="ValueError", message="radius must be positive, got -1")
```

## Handler Discovery

Handlers are discovered through Python's import system. When the addon loads, `addon/__init__.py` calls `register()`, which imports `addon.handlers`. Each module in `handlers/` uses `@rpc_handler` to register its functions.

For handlers outside the addon package (contrib, plugins), import them in a startup script:

```python
# my_startup.py
import sys
sys.path.insert(0, "/path/to/my/handlers")
import my_handlers  # triggers @rpc_handler decorators
```

## Contrib Handlers

Domain-specific handlers live in `contrib/`, not in the core addon. This keeps the core generic. See `contrib/spring_generator/` for the reference implementation.

The pattern:
1. Pure geometry function (no bpy operators, no UI)
2. `@rpc_handler` wrapper that validates inputs and calls the geometry function
3. Example script showing usage from the client side

## Built-in Handlers Reference

| Command | Parameters | Returns |
|---------|-----------|---------|
| `ping` | (none) | `{pong, blender_version}` |
| `scene_info` | (none) | `{objects, count, active}` |
| `clear_scene` | `keep_camera=True` | `{removed, count, keep_camera}` |
| `list_handlers` | (none) | `{handlers: [{name, doc}, ...]}` |
| `export_obj` | `filepath=None, selection_only=False` | `{file, size_bytes}` |
| `export_stl` | `filepath=None, selection_only=False` | `{file, size_bytes}` |
| `export_glb` | `filepath=None` | `{file, size_bytes}` |
| `render` | `filepath=None, resolution_x=1920, resolution_y=1080, samples=32` | `{file}` |

## Tips

- **Keep handlers focused.** One handler, one operation. Compose from the client side.
- **Return enough context.** Include file paths, counts, names — anything the caller needs to proceed without a follow-up call.
- **Auto-generate temp paths.** If `filepath` is None, generate a temp path (see `addon/handlers/export.py` for the pattern).
- **Test without Blender.** If your handler logic is pure geometry math, extract it into a function that doesn't import `bpy` and unit test it directly.
