"""Shared pytest fixtures for Phase 2 unit tests.

Installs a sys.modules['bpy'] MagicMock so handler modules can be
imported in plain Python without a real Blender process. This only
affects tests/unit/ — the handlers themselves still do `import bpy` at
runtime inside Blender, but under pytest they get the stub.

registry.py and router.py MUST stay bpy-free and do not need this stub.
"""
from __future__ import annotations
import sys
from unittest.mock import MagicMock

# Install the bpy stub exactly once, at collection time, before any
# `from addon.handlers...` import happens in a test module.
if "bpy" not in sys.modules:
    bpy_stub = MagicMock()
    bpy_stub.app.version_string = "4.2.0"
    bpy_stub.app.version = (4, 2, 0)
    sys.modules["bpy"] = bpy_stub
    # Submodules that handler code may touch:
    sys.modules["bpy.app"] = bpy_stub.app
    sys.modules["bpy.app.handlers"] = bpy_stub.app.handlers
    sys.modules["bpy.types"] = bpy_stub.types
    sys.modules["bpy.props"] = bpy_stub.props
