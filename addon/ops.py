"""BlendBridge operators.

Three operators wired to Blender's operator system:
- BLENDBRIDGE_OT_start_server  (bl_idname = "blendbridge.start_server")
- BLENDBRIDGE_OT_stop_server   (bl_idname = "blendbridge.stop_server")
- BLENDBRIDGE_OT_copy_endpoint (bl_idname = "blendbridge.copy_endpoint")

SRV-06: these operators are the bridge between the Blender UI (sidebar buttons)
and the server module. They run on the main thread inside Blender's operator
system, so they can safely call bpy.* and server.*.

Error handling: start_server catches zmq.ZMQError (port in use, SRV-05) and
calls self.report({'ERROR'}, ...) so the user sees the message in Blender's
info bar / console, then returns {'CANCELLED'}.

Panel redraw: after Start/Stop, context.area.tag_redraw() is called if an area
is available so the N-panel updates immediately (RESEARCH.md Pitfall 10 note).
"""
from __future__ import annotations
import bpy
from . import server


class BLENDBRIDGE_OT_start_server(bpy.types.Operator):
    """Start the BlendBridge ZeroMQ server on the configured port."""

    bl_idname = "blendbridge.start_server"
    bl_label = "Start RPC Server"
    bl_description = "Start the BlendBridge ZeroMQ server on the configured port"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        try:
            server.start_server(host=prefs.host, port=prefs.port)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to start server: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"RPC server started on port {prefs.port}")
        if context.area is not None:
            context.area.tag_redraw()
        return {'FINISHED'}


class BLENDBRIDGE_OT_stop_server(bpy.types.Operator):
    """Stop the BlendBridge ZeroMQ server."""

    bl_idname = "blendbridge.stop_server"
    bl_label = "Stop RPC Server"
    bl_description = "Stop the BlendBridge ZeroMQ server"

    def execute(self, context):
        server.stop_server()
        self.report({'INFO'}, "RPC server stopped")
        if context.area is not None:
            context.area.tag_redraw()
        return {'FINISHED'}


class BLENDBRIDGE_OT_copy_endpoint(bpy.types.Operator):
    """Copy tcp://localhost:{port} to clipboard."""

    bl_idname = "blendbridge.copy_endpoint"
    bl_label = "Copy tcp:// endpoint"
    bl_description = "Copy the RPC endpoint URL to the clipboard"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        port = server.get_port() or prefs.port
        endpoint = f"tcp://localhost:{port}"
        context.window_manager.clipboard = endpoint
        self.report({'INFO'}, f"Copied: {endpoint}")
        return {'FINISHED'}
