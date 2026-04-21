"""blendbridge console script entry point.

Full Click command group implementing ping, call, handlers, and launch
subcommands for interacting with a BlendBridge server from the terminal.
"""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager

import click

from blendbridge import __version__
from blendbridge.client import BlendBridge
from blendbridge.client.exceptions import (
    BlendBridgeError,
    RPCConnectionError,
    RPCError,
    RPCTimeoutError,
)


# ---------------------------------------------------------------------------
# Error handling helpers
# ---------------------------------------------------------------------------

@contextmanager
def _handle_errors(host: str, port: int):
    """Context manager that catches BlendBridgeError subclasses and exits(1)."""
    try:
        yield
    except RPCConnectionError:
        click.echo(f"Error: cannot connect to {host}:{port}", err=True)
        sys.exit(1)
    except RPCTimeoutError as exc:
        click.echo(f"Error: timeout — {exc}", err=True)
        sys.exit(1)
    except RPCError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except BlendBridgeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


def _coerce_value(v: str):
    """Coerce a CLI string value to bool, int, float, or str.

    Conversion precedence:
    1. "true"/"false" (case-insensitive) -> bool
    2. Parseable as int -> int
    3. Parseable as float -> float
    4. Fallback -> str
    """
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(version=__version__, prog_name="blendbridge")
@click.option("--host", default="localhost", help="Server host", show_default=True)
@click.option("--port", default=5555, type=int, help="Server port", show_default=True)
@click.pass_context
def main(ctx: click.Context, host: str, port: int) -> None:
    """BlendBridge client command-line interface.

    Connect to a running BlendBridge server and send commands, inspect
    registered handlers, or launch a fresh headless Blender instance.
    """
    ctx.ensure_object(dict)
    ctx.obj["host"] = host
    ctx.obj["port"] = port


# ---------------------------------------------------------------------------
# CMDL-01: ping
# ---------------------------------------------------------------------------

@main.command()
@click.pass_context
def ping(ctx: click.Context) -> None:
    """Ping the RPC server and print version info."""
    host = ctx.obj["host"]
    port = ctx.obj["port"]
    with _handle_errors(host, port):
        with BlendBridge(host=host, port=port) as client:
            result = client.ping()
            click.echo(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# CMDL-02: call
# ---------------------------------------------------------------------------

@main.command()
@click.argument("command")
@click.option(
    "--param", "-p",
    multiple=True,
    help="Key=value param (repeatable). Supports bool/int/float/str coercion.",
)
@click.option(
    "--json-params", "--json",
    "json_str",
    default=None,
    help="JSON params string. Takes precedence over --param when both are given.",
)
@click.pass_context
def call(
    ctx: click.Context,
    command: str,
    param: tuple[str, ...],
    json_str: str | None,
) -> None:
    """Send an arbitrary command to the server and print the JSON response."""
    host = ctx.obj["host"]
    port = ctx.obj["port"]

    # Parse params: --json takes precedence per user decision
    if json_str is not None:
        try:
            params = json.loads(json_str)
        except json.JSONDecodeError as exc:
            click.echo(f"Error: invalid JSON in --json: {exc}", err=True)
            sys.exit(1)
    else:
        params = {}
        for p in param:
            key, _, value = p.partition("=")
            params[key] = _coerce_value(value)

    with _handle_errors(host, port):
        with BlendBridge(host=host, port=port) as client:
            result = client.call(command, **params)
            click.echo(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# CMDL-03: handlers
# ---------------------------------------------------------------------------

@main.command()
@click.pass_context
def handlers(ctx: click.Context) -> None:
    """List registered handlers with docstrings."""
    host = ctx.obj["host"]
    port = ctx.obj["port"]
    with _handle_errors(host, port):
        with BlendBridge(host=host, port=port) as client:
            result = client.list_handlers()
            for h in result.get("handlers", []):
                name = h.get("name", "?")
                doc = h.get("doc", "")
                click.echo(f"  {name:20s} {doc}")


# ---------------------------------------------------------------------------
# CMDL-04: launch
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--blender", "blender_path",
    required=False,
    default=None,
    help="Path to Blender executable. Falls back to $BLENDER_PATH env var.",
)
@click.option(
    "--timeout",
    default=30.0,
    type=float,
    help="Launch timeout in seconds.",
    show_default=True,
)
@click.pass_context
def launch(ctx: click.Context, blender_path: str | None, timeout: float) -> None:
    """Launch headless Blender with RPC server and hold until Ctrl+C."""
    host = ctx.obj["host"]
    port = ctx.obj["port"]
    click.echo(f"Launching Blender on {host}:{port}...")
    with _handle_errors(host, port):
        try:
            with BlendBridge.launch(
                blender_path=blender_path,
                port=port,
                host=host,
                timeout=timeout,
            ) as client:
                result = client.ping()
                click.echo(
                    f"Connected — Blender {result.get('blender_version', '?')}"
                )
                click.echo("Press Ctrl+C to stop.")
                # Block until interrupted
                import signal
                if sys.platform == "win32":
                    import time
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        pass
                else:
                    try:
                        signal.pause()
                    except KeyboardInterrupt:
                        pass
        except KeyboardInterrupt:
            click.echo("\nShutting down...")


if __name__ == "__main__":
    main()
