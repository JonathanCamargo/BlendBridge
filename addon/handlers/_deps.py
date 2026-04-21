"""Lazy-dependency helpers for BlendBridge handlers.

``@requires_dependency`` defers an setup/ensure function until the
decorated RPC handler is actually *called*.  This lets ``@rpc_handler``
decorators always execute (registering the handler) even when an
optional dependency is missing.
"""
from __future__ import annotations

from functools import wraps
from typing import Callable


def requires_dependency(ensure_fn: Callable[[], None]):
    """Decorator that calls *ensure_fn* before the wrapped handler.

    Use it *below* ``@rpc_handler`` so registration happens first::

        @rpc_handler("blendgen_gripper_finger")
        @requires_dependency(_ensure_blendgenerators)
        def blendgen_gripper_finger(...):
            from blend_generators.generators.gripper_finger.api import generate
            ...

    If *ensure_fn* raises (e.g. ``ImportError``), the RPC router
    catches it and returns a structured error to the client.
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ensure_fn()
            return fn(*args, **kwargs)
        return wrapper
    return decorator