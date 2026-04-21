"""BlendBridge sidebar panel.

Provides BLENDBRIDGE_PT_sidebar, shown in the 3D View sidebar ("N" panel)
under the "RPC" category.

SRV-08: The panel draws:
- Status row: "RUNNING  port {port}" (CHECKMARK icon) or "STOPPED" (X icon)
- Start / Stop buttons (aligned row)
- Copy endpoint button showing tcp://localhost:{port}
- A boxed list of all registered handler names (sorted alphabetically)

Panel draw is demand-driven (Blender only redraws on UI events). Status
accuracy: after Start/Stop operations the operator calls area.tag_redraw()
(RESEARCH.md Pitfall 10), so the panel updates immediately after a click.
"""
from __future__ import annotations
import bpy
from . import server
from .registry import list_handlers


class BLENDBRIDGE_PT_sidebar(bpy.types.Panel):
    """RPC server control panel in the 3D View sidebar."""

    bl_label = "BlendBridge"
    bl_idname = "BLENDBRIDGE_PT_sidebar"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RPC"

    def draw(self, context):
        layout = self.layout
        running = server.is_running()
        port = server.get_port()

        # Status row
        row = layout.row()
        if running:
            row.label(text=f"RUNNING  port {port}", icon='CHECKMARK')
        else:
            row.label(text="STOPPED", icon='X')

        # Start / Stop buttons
        row = layout.row(align=True)
        row.operator("blendbridge.start_server", text="Start")
        row.operator("blendbridge.stop_server", text="Stop")

        # Copy endpoint button
        port_display = port if port is not None else "?"
        layout.operator(
            "blendbridge.copy_endpoint",
            text=f"Copy  tcp://localhost:{port_display}",
        )

        # Handler list
        box = layout.box()
        box.label(text="Registered handlers:")
        for name in sorted(list_handlers().keys()):
            box.label(text=f"  {name}")
