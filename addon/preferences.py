"""BlendBridge addon preferences.

Provides:
- BlendBridgePreferences(bpy.types.AddonPreferences):
    Properties: host (StringProperty), port (IntProperty), autostart (BoolProperty)
    draw() renders all three props in the Preferences > Add-ons panel.

- _load_post_autostart: @persistent load_post handler that starts the server
    automatically on Blender launch / file open when prefs.autostart is True.
    CRITICAL: @persistent is mandatory (RESEARCH.md Pitfall 5) — without it,
    File > Open clears the handler and autostart silently stops working.

- register_autostart() / unregister_autostart(): called from __init__.py's
    register() / unregister() hooks to manage handler list membership.

SRV-07: bl_idname must exactly match __package__ ("addon" during development,
"blendbridge_server" in Phase 6 packaging). Using __package__ here keeps the
file portable across rename.
"""
from __future__ import annotations
import bpy
from bpy.app.handlers import persistent
from . import server


class BlendBridgePreferences(bpy.types.AddonPreferences):
    """Preferences for the BlendBridge addon."""

    # bl_idname must match the addon's module name (the package name Blender
    # uses to look up the addon in context.preferences.addons[__package__]).
    bl_idname = __package__

    host: bpy.props.StringProperty(  # type: ignore[assignment]
        name="Host",
        description="ZMQ bind address ('*' for all interfaces, or a specific IP)",
        default="*",
    )

    port: bpy.props.IntProperty(  # type: ignore[assignment]
        name="Port",
        description="Port number for the ZMQ REP server",
        default=5555,
        min=1024,
        max=65535,
    )

    autostart: bpy.props.BoolProperty(  # type: ignore[assignment]
        name="Autostart server on Blender launch",
        description="Automatically start the RPC server when Blender opens a file",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "host")
        layout.prop(self, "port")
        layout.prop(self, "autostart")


@persistent
def _load_post_autostart(_dummy):
    """load_post handler: start the RPC server if prefs.autostart is True.

    The @persistent decorator ensures this handler survives File > Open /
    File > New (RESEARCH.md Pitfall 5). Without it, autostart stops working
    after the first file load.
    """
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        # Addon not yet registered or preferences not available — skip.
        return
    if prefs.autostart and not server.is_running():
        try:
            server.start_server(host=prefs.host, port=prefs.port)
        except Exception as e:
            print(f"blendbridge: autostart failed: {e}")


def register_autostart() -> None:
    """Append _load_post_autostart to bpy.app.handlers.load_post (idempotent)."""
    if _load_post_autostart not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_autostart)


def unregister_autostart() -> None:
    """Remove _load_post_autostart from bpy.app.handlers.load_post (safe)."""
    if _load_post_autostart in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_autostart)
