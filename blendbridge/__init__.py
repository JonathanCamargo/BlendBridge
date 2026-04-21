"""blendbridge — ZeroMQ RPC framework exposing Blender as a microservice.

The `blendbridge` package is the external, pip-installable client.
The Blender-side code lives in the `addon/` directory at the repo root
and is shipped separately as a zip (see scripts/build_addon_zip.py).
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
