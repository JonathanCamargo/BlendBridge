"""BlendBridge handler registry.

Module-level dict + decorator factory. Bpy-free: this module must
stay importable in plain Python so it can be unit-tested in
tests/unit/test_registry.py without a running Blender.

Do NOT add any `import bpy` here.
"""
from __future__ import annotations
from typing import Callable

_HANDLERS: dict[str, Callable] = {}


def rpc_handler(command_name: str):
    """Decorator that registers a handler under `command_name`.

    Usage:
        @rpc_handler("ping")
        def ping():
            '''Return pong plus Blender version.'''
            return {"pong": True}

    The decorator returns the function unchanged, so decorated
    functions retain their original signature and can still be
    called directly (useful in tests).
    """
    def decorator(fn: Callable) -> Callable:
        _HANDLERS[command_name] = fn
        return fn
    return decorator


def register_handler(name: str, fn: Callable) -> None:
    """Programmatic alternative to @rpc_handler — used by tests."""
    _HANDLERS[name] = fn


def get_handler(name: str) -> Callable | None:
    """Look up a handler by name. Returns None if not registered."""
    return _HANDLERS.get(name)


def list_handlers() -> dict[str, str]:
    """Return {name: docstring} for every registered handler.

    Docstring defaults to '' (not None) so the router and the
    `list_handlers` RPC command can always return JSON-serializable
    values.
    """
    return {name: (fn.__doc__ or "") for name, fn in _HANDLERS.items()}


def iter_handlers():
    """Yield (name, fn) pairs for every registered handler."""
    return _HANDLERS.items()
