"""SRV-01: registry decorator + register_handler/get_handler/list_handlers."""
from __future__ import annotations
import pytest

# Lazy import so pytest collection doesn't fail if Plan 02-02 hasn't landed yet.
registry = pytest.importorskip("addon.registry")


def _reset():
    # Tests own a clean registry each time; registry module has _HANDLERS dict.
    registry._HANDLERS.clear()


def test_rpc_handler_decorator_registers_function():
    _reset()
    @registry.rpc_handler("ping")
    def ping():
        """Return pong."""
        return {"pong": True}
    assert registry.get_handler("ping") is ping


def test_register_handler_function_form():
    _reset()
    def my_fn():
        return "ok"
    registry.register_handler("custom", my_fn)
    assert registry.get_handler("custom") is my_fn


def test_get_handler_returns_none_for_unknown():
    _reset()
    assert registry.get_handler("nonexistent") is None


def test_list_handlers_returns_name_to_docstring_map():
    _reset()
    @registry.rpc_handler("a")
    def a():
        """Docstring A."""
    @registry.rpc_handler("b")
    def b():
        """Docstring B."""
    result = registry.list_handlers()
    assert result == {"a": "Docstring A.", "b": "Docstring B."}


def test_list_handlers_empty_when_no_registrations():
    _reset()
    assert registry.list_handlers() == {}


def test_decorator_returns_original_function_unchanged():
    _reset()
    @registry.rpc_handler("x")
    def x():
        return 42
    # Decorator must not wrap — the function itself is still callable with its original signature
    assert x() == 42
