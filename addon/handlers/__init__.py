"""Built-in handlers for the BlendBridge server.

Importing this package triggers side-effect registration of every
handler via the @rpc_handler decorator. Called from addon/__init__.py's
register() hook so the registry is populated the moment the addon
is enabled.
"""
from . import scene   # noqa: F401 — side-effect: registers ping, scene_info, clear_scene, list_handlers
from . import export  # noqa: F401 — side-effect: registers export_obj, export_stl, export_glb
from . import render  # noqa: F401 — side-effect: registers render
