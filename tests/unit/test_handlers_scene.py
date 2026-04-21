"""HAND-01: ping. HAND-02: scene_info. HAND-04: list_handlers."""
from __future__ import annotations
from unittest.mock import MagicMock
import sys
import pytest


@pytest.fixture(autouse=True)
def _clean_registry():
    # Ensure a fresh registry for each test; conftest already stubs bpy.
    registry = pytest.importorskip("addon.registry")
    registry._HANDLERS.clear()
    yield
    registry._HANDLERS.clear()


def test_ping_returns_pong_and_version():
    scene = pytest.importorskip("addon.handlers.scene")
    result = scene.ping()
    assert result["pong"] is True
    assert "blender_version" in result
    assert isinstance(result["blender_version"], str)


def test_scene_info_returns_objects_count_active():
    # Re-stub bpy.context.scene.objects for this specific test
    bpy = sys.modules["bpy"]
    obj_a = MagicMock()
    obj_a.name = "Cube"
    obj_a.type = "MESH"
    obj_b = MagicMock()
    obj_b.name = "Camera"
    obj_b.type = "CAMERA"
    bpy.context.scene.objects = [obj_a, obj_b]
    bpy.context.view_layer.objects.active = obj_a

    scene = pytest.importorskip("addon.handlers.scene")
    # Reload to pick up fresh bpy state — handler reads bpy at call time, not import time
    result = scene.scene_info()

    assert result["count"] == 2
    assert result["active"] == "Cube"
    names = [o["name"] for o in result["objects"]]
    assert "Cube" in names and "Camera" in names


def test_list_handlers_handler_returns_registry_dict():
    scene = pytest.importorskip("addon.handlers.scene")
    # Importing addon.handlers.scene registers ping, scene_info, clear_scene, list_handlers
    result = scene.list_handlers()
    assert "ping" in result
    assert "scene_info" in result
    assert "clear_scene" in result
    assert "list_handlers" in result
