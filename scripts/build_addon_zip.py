#!/usr/bin/env python3
"""build_addon_zip - package addon/ into a Blender-installable zip.

Usage:
    python scripts/build_addon_zip.py [--output DIR]

Reads the version from pyproject.toml and produces
    <output>/blendbridge_addon_v{version}.zip

The zip contains the addon/ directory at its root so Blender can install it
via Preferences -> Add-ons -> Install.

Exit codes:
    0  zip built successfully
    1  missing addon/ or unreadable pyproject.toml
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ADDON_DIR = REPO_ROOT / "addon"
PYPROJECT = REPO_ROOT / "pyproject.toml"

EXCLUDE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

# Regex-based version extraction (Python 3.10 has no stdlib tomllib; avoid
# pulling `tomli` in just to read one line).
VERSION_RE = re.compile(r'^\s*version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def read_version() -> str:
    """Read [project].version from pyproject.toml using a scoped regex.

    Python 3.10 lacks stdlib tomllib and adding `tomli` as a dependency just
    to read one line is overkill. We scope the regex to the `[project]`
    section so `[tool.*]` sections with their own `version =` keys don't
    collide.
    """
    if not PYPROJECT.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {PYPROJECT}")
    text = PYPROJECT.read_text(encoding="utf-8")
    project_section = re.search(
        r"\[project\](.*?)(?=^\[|\Z)", text, re.DOTALL | re.MULTILINE
    )
    if not project_section:
        raise KeyError("pyproject.toml missing [project] section")
    m = VERSION_RE.search(project_section.group(1))
    if not m:
        raise KeyError('pyproject.toml [project] missing version = "..."')
    return m.group(1)


def iter_addon_files() -> list[Path]:
    """Walk the addon/ tree, filtering out caches and compiled artifacts."""
    if not ADDON_DIR.exists():
        raise FileNotFoundError(f"addon/ directory not found at {ADDON_DIR}")
    files: list[Path] = []
    for path in sorted(ADDON_DIR.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        files.append(path)
    return files


def build_zip(output_dir: Path, version: str) -> Path:
    """Write <output_dir>/blendbridge_addon_v{version}.zip. Returns the zip path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"blendbridge_addon_v{version}.zip"
    if zip_path.exists():
        zip_path.unlink()  # overwrite cleanly

    files = iter_addon_files()
    if not files:
        raise RuntimeError(f"no files to zip under {ADDON_DIR}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src in files:
            # Archive name is relative to REPO_ROOT so the zip contains `addon/...`
            arcname = src.relative_to(REPO_ROOT).as_posix()
            zf.write(src, arcname)

    return zip_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_addon_zip",
        description="Package addon/ into dist/blendbridge_addon_v{version}.zip.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "dist",
        help="Output directory (default: dist/).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        version = read_version()
        zip_path = build_zip(args.output, version)
    except (FileNotFoundError, KeyError, RuntimeError) as e:
        print(f"[build_addon_zip] ERROR: {e}", file=sys.stderr)
        return 1

    size_kb = zip_path.stat().st_size / 1024
    print(f"[build_addon_zip] Wrote {zip_path} ({size_kb:.1f} KB)")
    # Summary of contents
    with zipfile.ZipFile(zip_path) as zf:
        print("[build_addon_zip] Contents:")
        for info in zf.infolist():
            print(f"  {info.filename} ({info.file_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
