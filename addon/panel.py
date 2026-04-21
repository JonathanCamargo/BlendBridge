"""BlendBridge sidebar panel.

Provides BLENDBRIDGE_PT_sidebar, shown in the 3D View sidebar ("N" panel)
under the "Bridge" category.

The panel draws:
- Status row: "RUNNING  port {port}" (CHECKMARK icon) or "STOPPED" (X icon)
- Start / Stop buttons (aligned row)
- Copy endpoint button showing tcp://localhost:{port}
- Handlers grouped by source module, each in a collapsible box.

Group collapse state is stored as per-group BoolProperties on
WindowManager, registered in register_group_props() from the module
names seen in the registry.
"""
from __future__ import annotations
import bpy
from . import server
from .registry import iter_handlers


_GROUP_PROPS: list[str] = []


def _group_label(module_name: str) -> str:
    """Turn ``addon.handlers.blendgenerators_handler`` into ``Blendgenerators``."""
    last = module_name.rsplit(".", 1)[-1]
    if last.endswith("_handler"):
        last = last[: -len("_handler")]
    return last.replace("_", " ").title()


def _group_prop_name(label: str) -> str:
    return "bb_group_" + label.lower().replace(" ", "_")


def _grouped_handlers() -> list[tuple[str, list[str]]]:
    """Return [(group_label, sorted handler names)] sorted by label."""
    groups: dict[str, list[str]] = {}
    for name, fn in iter_handlers():
        label = _group_label(getattr(fn, "__module__", "") or "Other")
        groups.setdefault(label, []).append(name)
    return sorted(((g, sorted(names)) for g, names in groups.items()), key=lambda p: p[0])


def register_group_props() -> None:
    """Create a BoolProperty on WindowManager per handler group."""
    for label, _ in _grouped_handlers():
        prop = _group_prop_name(label)
        if hasattr(bpy.types.WindowManager, prop):
            continue
        setattr(
            bpy.types.WindowManager,
            prop,
            bpy.props.BoolProperty(name=label, default=True),
        )
        _GROUP_PROPS.append(prop)


def unregister_group_props() -> None:
    for prop in _GROUP_PROPS:
        try:
            delattr(bpy.types.WindowManager, prop)
        except Exception:
            pass
    _GROUP_PROPS.clear()


class BLENDBRIDGE_PT_sidebar(bpy.types.Panel):
    """RPC server control panel in the 3D View sidebar."""

    bl_label = "BlendBridge"
    bl_idname = "BLENDBRIDGE_PT_sidebar"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bridge"

    def draw(self, context):
        layout = self.layout
        running = server.is_running()
        port = server.get_port()

        row = layout.row()
        if running:
            row.label(text=f"RUNNING  port {port}", icon='CHECKMARK')
        else:
            row.label(text="STOPPED", icon='X')

        row = layout.row(align=True)
        row.operator("blendbridge.start_server", text="Start")
        row.operator("blendbridge.stop_server", text="Stop")

        port_display = port if port is not None else "?"
        layout.operator(
            "blendbridge.copy_endpoint",
            text=f"Copy  tcp://localhost:{port_display}",
        )

        wm = context.window_manager
        layout.label(text="Registered handlers:")
        for label, names in _grouped_handlers():
            prop = _group_prop_name(label)
            expanded = getattr(wm, prop, True)
            box = layout.box()
            header = box.row()
            header.prop(
                wm,
                prop,
                text=f"{label}  ({len(names)})",
                icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT',
                emboss=False,
            )
            if expanded:
                for name in names:
                    box.label(text=f"  {name}")
