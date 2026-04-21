"""Unit tests for BlendBridge typed convenience methods.

Each test verifies that the convenience method delegates to self.call()
with the correct command name and keyword arguments.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from blendbridge.client import BlendBridge


@pytest.fixture()
def rpc() -> BlendBridge:
    """A BlendBridge instance with a mocked call() method."""
    client = BlendBridge()
    client.call = MagicMock(return_value={"ok": True})
    return client


class TestPing:
    def test_ping_delegates_to_call(self, rpc: BlendBridge) -> None:
        result = rpc.ping()
        rpc.call.assert_called_once_with("ping")

    def test_ping_returns_call_result(self, rpc: BlendBridge) -> None:
        rpc.call.return_value = {"pong": True, "blender_version": "4.5.1"}
        assert rpc.ping() == {"pong": True, "blender_version": "4.5.1"}


class TestSceneInfo:
    def test_scene_info_delegates_to_call(self, rpc: BlendBridge) -> None:
        rpc.scene_info()
        rpc.call.assert_called_once_with("scene_info")

    def test_scene_info_returns_call_result(self, rpc: BlendBridge) -> None:
        rpc.call.return_value = {"objects": [], "count": 0, "active": None}
        assert rpc.scene_info() == {"objects": [], "count": 0, "active": None}


class TestClearScene:
    def test_clear_scene_default_args(self, rpc: BlendBridge) -> None:
        rpc.clear_scene()
        rpc.call.assert_called_once_with("clear_scene", keep_camera=True)

    def test_clear_scene_keep_camera_false(self, rpc: BlendBridge) -> None:
        rpc.clear_scene(keep_camera=False)
        rpc.call.assert_called_once_with("clear_scene", keep_camera=False)

    def test_clear_scene_returns_call_result(self, rpc: BlendBridge) -> None:
        rpc.call.return_value = {"removed": ["Cube"], "count": 1, "keep_camera": True}
        assert rpc.clear_scene() == {"removed": ["Cube"], "count": 1, "keep_camera": True}


class TestListHandlers:
    def test_list_handlers_delegates_to_call(self, rpc: BlendBridge) -> None:
        rpc.list_handlers()
        rpc.call.assert_called_once_with("list_handlers")

    def test_list_handlers_returns_call_result(self, rpc: BlendBridge) -> None:
        rpc.call.return_value = {"handlers": [{"name": "ping", "doc": ""}]}
        assert rpc.list_handlers() == {"handlers": [{"name": "ping", "doc": ""}]}


class TestExportObj:
    def test_export_obj_no_args(self, rpc: BlendBridge) -> None:
        rpc.export_obj()
        rpc.call.assert_called_once_with("export_obj", filepath=None, selection_only=False)

    def test_export_obj_with_filepath(self, rpc: BlendBridge) -> None:
        rpc.export_obj(filepath="/tmp/test.obj")
        rpc.call.assert_called_once_with("export_obj", filepath="/tmp/test.obj", selection_only=False)

    def test_export_obj_selection_only(self, rpc: BlendBridge) -> None:
        rpc.export_obj(filepath="/tmp/test.obj", selection_only=True)
        rpc.call.assert_called_once_with("export_obj", filepath="/tmp/test.obj", selection_only=True)

    def test_export_obj_returns_call_result(self, rpc: BlendBridge) -> None:
        rpc.call.return_value = {"file": "/tmp/test.obj", "size_bytes": 1024}
        assert rpc.export_obj(filepath="/tmp/test.obj") == {"file": "/tmp/test.obj", "size_bytes": 1024}


class TestExportStl:
    def test_export_stl_no_args(self, rpc: BlendBridge) -> None:
        rpc.export_stl()
        rpc.call.assert_called_once_with("export_stl", filepath=None, selection_only=False)

    def test_export_stl_with_filepath(self, rpc: BlendBridge) -> None:
        rpc.export_stl(filepath="/tmp/test.stl")
        rpc.call.assert_called_once_with("export_stl", filepath="/tmp/test.stl", selection_only=False)

    def test_export_stl_selection_only(self, rpc: BlendBridge) -> None:
        rpc.export_stl(filepath="/tmp/test.stl", selection_only=True)
        rpc.call.assert_called_once_with("export_stl", filepath="/tmp/test.stl", selection_only=True)


class TestExportGlb:
    def test_export_glb_no_args(self, rpc: BlendBridge) -> None:
        rpc.export_glb()
        rpc.call.assert_called_once_with("export_glb", filepath=None)

    def test_export_glb_with_filepath(self, rpc: BlendBridge) -> None:
        rpc.export_glb(filepath="/tmp/test.glb")
        rpc.call.assert_called_once_with("export_glb", filepath="/tmp/test.glb")

    def test_export_glb_returns_call_result(self, rpc: BlendBridge) -> None:
        rpc.call.return_value = {"file": "/tmp/test.glb", "size_bytes": 2048}
        assert rpc.export_glb(filepath="/tmp/test.glb") == {"file": "/tmp/test.glb", "size_bytes": 2048}


class TestRender:
    def test_render_default_args(self, rpc: BlendBridge) -> None:
        rpc.render()
        rpc.call.assert_called_once_with(
            "render",
            filepath=None,
            resolution_x=1920,
            resolution_y=1080,
            samples=32,
        )

    def test_render_custom_resolution(self, rpc: BlendBridge) -> None:
        rpc.render(resolution_x=800, resolution_y=600, samples=16)
        rpc.call.assert_called_once_with(
            "render",
            filepath=None,
            resolution_x=800,
            resolution_y=600,
            samples=16,
        )

    def test_render_with_filepath(self, rpc: BlendBridge) -> None:
        rpc.render(filepath="/tmp/render.png")
        rpc.call.assert_called_once_with(
            "render",
            filepath="/tmp/render.png",
            resolution_x=1920,
            resolution_y=1080,
            samples=32,
        )

    def test_render_returns_call_result(self, rpc: BlendBridge) -> None:
        rpc.call.return_value = {"file": "/tmp/render.png"}
        assert rpc.render(filepath="/tmp/render.png") == {"file": "/tmp/render.png"}
