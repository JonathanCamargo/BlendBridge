"""HAND-05/06/07: the pure-Python slice of export handlers — temp path generation + _size.

The real bpy.ops.wm.*_export call is validated by the manual smoke script
(Plan 02-06). Here we only verify that:
  - auto-generated temp paths live in tempfile.gettempdir()
  - auto-generated temp paths include uuid4 randomness
  - auto-generated paths use correct extensions (obj/stl/glb)
  - _size returns 0 for nonexistent files and correct size for existing files
"""
from __future__ import annotations
import os
import tempfile
import pytest


export = pytest.importorskip("addon.handlers.export")


def test_tmp_path_uses_system_tempdir():
    path = export._tmp_path("obj")
    assert path.startswith(tempfile.gettempdir())


def test_tmp_path_has_correct_extension():
    assert export._tmp_path("obj").endswith(".obj")
    assert export._tmp_path("stl").endswith(".stl")
    assert export._tmp_path("glb").endswith(".glb")


def test_tmp_path_includes_uuid_randomness():
    p1 = export._tmp_path("obj")
    p2 = export._tmp_path("obj")
    assert p1 != p2  # uuid4 collision probability is astronomical


def test_tmp_path_prefix_matches_spec():
    path = export._tmp_path("obj")
    basename = os.path.basename(path)
    assert basename.startswith("blendbridge_")


def test_size_returns_zero_for_nonexistent():
    assert export._size("/nonexistent/path/xyz.obj") == 0


def test_size_returns_file_size_for_existing(tmp_path):
    target = tmp_path / "fake.obj"
    target.write_text("hello world")
    assert export._size(str(target)) == 11
