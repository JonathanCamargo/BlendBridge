#!/usr/bin/env python3
"""install_zmq_blender - install pyzmq into Blender's embedded Python.

Usage:
    python scripts/install_zmq_blender.py [--blender PATH] [--dry-run]

If --blender is omitted, the script tries to auto-detect a Blender installation
using platform conventions. If given an executable path, it resolves to the
bundled Python interpreter shipped alongside that Blender.

Exit codes:
    0  success (or dry-run completed)
    1  auto-detect failed or the given path is invalid
    2  pip install failed
"""
from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path


# Common install locations per platform. Order = priority.
COMMON_BLENDER_PATHS: dict[str, list[str]] = {
    "Linux": [
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/opt/blender/blender",
        "/snap/bin/blender",
        str(Path.home() / ".local/bin/blender"),
    ],
    "Darwin": [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        str(Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"),
    ],
    "Windows": [
        r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    ],
}


def auto_detect_blender() -> Path | None:
    """Search common install locations for a Blender executable.

    Returns the first existing path or None if nothing is found.
    """
    system = platform.system()
    candidates = COMMON_BLENDER_PATHS.get(system, [])
    for candidate in candidates:
        p = Path(candidate)
        if p.exists() and p.is_file():
            return p
    return None


def find_bundled_python(blender_path: Path) -> Path | None:
    """Given a Blender executable (or a Python binary), return the Python interpreter
    that ships with Blender.

    Blender 4.x layouts:
        Linux:   <blender_dir>/4.x/python/bin/python3.11
        macOS:   <app>/Contents/Resources/4.x/python/bin/python3.11
        Windows: <blender_dir>\\4.x\\python\\bin\\python.exe

    Strategy:
        1. If the given path is already a python executable (filename starts
           with 'python'), return it unchanged.
        2. Otherwise, walk upward from blender_path looking for a '*/python/bin'
           directory and return the python binary inside it.
    """
    blender_path = Path(blender_path).resolve()
    if blender_path.name.lower().startswith("python"):
        return blender_path if blender_path.exists() else None

    # Candidate search roots:
    # - Linux/Windows: same directory as blender executable
    # - macOS: Contents/Resources sibling to Contents/MacOS
    search_roots: list[Path] = [blender_path.parent]
    if platform.system() == "Darwin":
        # /Applications/Blender.app/Contents/MacOS/Blender
        # -> /Applications/Blender.app/Contents/Resources
        resources = blender_path.parent.parent / "Resources"
        if resources.exists():
            search_roots.append(resources)

    python_name = "python.exe" if platform.system() == "Windows" else "python3.11"
    python_fallback_names = ["python3.11", "python3.10", "python3", "python"]

    for root in search_roots:
        # Look for <root>/<version>/python/bin/<python_name>
        for version_dir in sorted(root.glob("[0-9].[0-9]*")):
            py_bin_dir = version_dir / "python" / "bin"
            if not py_bin_dir.exists():
                continue
            # Try platform-preferred name first, then fallbacks
            names = [python_name] + [n for n in python_fallback_names if n != python_name]
            for name in names:
                candidate = py_bin_dir / name
                if candidate.exists() and candidate.is_file():
                    return candidate
    return None


def _ensure_pip(python_path: Path, dry_run: bool = False) -> bool:
    """Bootstrap pip via ensurepip if it's not already available."""
    check = subprocess.run(
        [str(python_path), "-m", "pip", "--version"],
        capture_output=True, check=False,
    )
    if check.returncode == 0:
        return True
    print("[install_zmq_blender] pip not available, bootstrapping via ensurepip...")
    cmd = [str(python_path), "-m", "ensurepip", "--upgrade"]
    print(f"[install_zmq_blender] Command: {' '.join(cmd)}")
    if dry_run:
        print("[install_zmq_blender] --dry-run set; not executing ensurepip.")
        return True
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(
            "[install_zmq_blender] ERROR: ensurepip failed. "
            "You may need to install pip manually.",
            file=sys.stderr,
        )
        return False
    print("[install_zmq_blender] pip bootstrapped successfully.")
    return True


def install_pyzmq(python_path: Path, dry_run: bool = False) -> int:
    """Run `<python_path> -m pip install pyzmq` (or print it in dry-run mode).

    Must be run with write access to Blender's site-packages
    (i.e. admin/elevated shell on Windows when Blender is in Program Files).
    """
    if not _ensure_pip(python_path, dry_run):
        return 2
    cmd = [str(python_path), "-m", "pip", "install", "--upgrade", "pyzmq"]
    print(f"[install_zmq_blender] Target: {python_path}")
    print(f"[install_zmq_blender] Command: {' '.join(cmd)}")
    if dry_run:
        print("[install_zmq_blender] --dry-run set; not executing.")
        return 0
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print(
            f"[install_zmq_blender] ERROR: {python_path} does not exist or is not executable.",
            file=sys.stderr,
        )
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install_zmq_blender",
        description="Install pyzmq into Blender's embedded Python interpreter.",
    )
    parser.add_argument(
        "--blender",
        type=Path,
        default=None,
        help="Path to the Blender executable OR its bundled Python interpreter. "
        "If omitted, auto-detect from common install locations.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the pip install command without executing it.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    blender_path: Path | None = args.blender
    if blender_path is None:
        print("[install_zmq_blender] No --blender given; auto-detecting...")
        blender_path = auto_detect_blender()
        if blender_path is None:
            print(
                "[install_zmq_blender] ERROR: could not auto-detect Blender. "
                "Pass --blender /path/to/blender explicitly.",
                file=sys.stderr,
            )
            return 1
        print(f"[install_zmq_blender] Auto-detected: {blender_path}")

    if not blender_path.exists():
        # In --dry-run mode we still allow a fake path so tests can smoke-check the CLI
        if not args.dry_run:
            print(
                f"[install_zmq_blender] ERROR: {blender_path} does not exist.",
                file=sys.stderr,
            )
            return 1
        print(
            f"[install_zmq_blender] WARNING: {blender_path} does not exist "
            "(continuing because --dry-run)."
        )
        python_path = blender_path
    else:
        python_path = find_bundled_python(blender_path)
        if python_path is None:
            print(
                f"[install_zmq_blender] ERROR: could not find bundled Python next to {blender_path}.",
                file=sys.stderr,
            )
            return 1

    return install_pyzmq(python_path, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
