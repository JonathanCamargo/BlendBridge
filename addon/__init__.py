"""BlendBridge — addon entry point.

This module is loaded by Blender when the addon is enabled. It is NOT part
of the pip-installable `blendbridge` package — it ships separately as a zip
built by `scripts/build_addon_zip.py`.

Registration order matters:
1. pyzmq is auto-installed into Blender's Python if missing.
2. BlendBridgePreferences must be registered BEFORE any operator that accesses
   context.preferences.addons[__package__].preferences.
3. Handlers import happens as a side effect of `from . import handlers` —
   it triggers @rpc_handler decoration that populates the registry dict.
4. preferences.register_autostart() appends the @persistent load_post handler
   so File > Open auto-starts the server when prefs.autostart is True.

Unregistration order is the reverse of registration (reversed(_CLASSES)).
"""

bl_info = {
    "name": "BlendBridge",
    "author": "Jonathan / roboticos.co",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "category": "Development",
    "description": "ZeroMQ RPC server — exposes Blender as a controllable microservice",
}

import bpy  # noqa: E402 — must come after bl_info for Blender's addon loader
import importlib
import subprocess
import sys


def _add_user_site_packages() -> None:
    """Add the user site-packages directory to sys.path.

    Blender disables user site-packages by default, but pip installs
    land there when the Blender directory (Program Files) isn't writable.
    Adding it to sys.path makes those packages importable.
    """
    try:
        import site
        user_sp = site.getusersitepackages()
        if isinstance(user_sp, str) and user_sp not in sys.path:
            sys.path.append(user_sp)
            print(f"blendbridge: added user site-packages to path: {user_sp}")
    except Exception:
        pass


def _ensure_pip() -> bool:
    """Bootstrap pip via ensurepip if it's not already available."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        return True
    except Exception:
        pass
    print("blendbridge: pip not available, bootstrapping via ensurepip...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            timeout=120,
        )
        print("blendbridge: pip bootstrapped successfully")
        return True
    except Exception as e:
        print(f"blendbridge: failed to bootstrap pip: {e}")
        return False


def _ensure_pyzmq() -> bool:
    """Install pyzmq into Blender's Python if not already present."""
    try:
        import zmq  # noqa: F401
        return True
    except ImportError:
        pass
    # Blender disables user site-packages — add it and retry before installing.
    _add_user_site_packages()
    importlib.invalidate_caches()
    try:
        import zmq  # noqa: F401
        return True
    except ImportError:
        pass
    print("blendbridge: pyzmq not found, installing...")
    if not _ensure_pip():
        print("blendbridge: pip is not available and could not be bootstrapped.")
        print("blendbridge: run 'python scripts/install_zmq_blender.py' manually")
        return False
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyzmq>=25"],
            timeout=120,
        )
        print("blendbridge: pyzmq installed successfully")
    except Exception as e:
        print(f"blendbridge: failed to install pyzmq: {e}")
        print("blendbridge: run 'python scripts/install_zmq_blender.py' manually")
        return False
    # After pip install, Python's import caches are stale — refresh them
    # so the newly installed package is discoverable.
    importlib.invalidate_caches()
    try:
        import zmq  # noqa: F401
        return True
    except ImportError:
        print("blendbridge: pyzmq was installed but still not importable. "
              "Restart Blender and re-enable the addon.")
        return False


_ZMQ_OK = _ensure_pyzmq()

if _ZMQ_OK:
    from . import server       # noqa: F401
    from . import ops
    from . import preferences
    from . import panel
    from . import handlers     # noqa: F401 — side-effect: runs @rpc_handler decorators

    _CLASSES = (
        preferences.BlendBridgePreferences,
        ops.BLENDBRIDGE_OT_start_server,
        ops.BLENDBRIDGE_OT_stop_server,
        ops.BLENDBRIDGE_OT_copy_endpoint,
        panel.BLENDBRIDGE_PT_sidebar,
    )
else:
    _CLASSES = ()


def register() -> None:
    if not _ZMQ_OK:
        raise RuntimeError(
            "blendbridge: pyzmq is required but could not be installed automatically. "
            "Run 'python scripts/install_zmq_blender.py' manually, then re-enable the addon."
        )
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    preferences.register_autostart()


def unregister() -> None:
    if not _ZMQ_OK:
        return
    preferences.unregister_autostart()
    try:
        server.stop_server()
    except Exception:
        pass
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
