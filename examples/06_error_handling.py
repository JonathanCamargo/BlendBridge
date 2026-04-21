#!/usr/bin/env python3
"""Demonstrate error handling with the BlendBridge client.

Shows how to catch and inspect different exception types:
- RPCError: server returned a structured error (bad command, handler failure)
- RPCTimeoutError: server didn't respond in time
- RPCConnectionError: can't reach the server at all

Usage:
  python examples/05_error_handling.py
"""
from blendbridge.client import (
    BlendBridge,
    BlendBridgeError,
    RPCConnectionError,
    RPCError,
    RPCTimeoutError,
)


def demo_unknown_command(client: BlendBridge):
    """Call a command that doesn't exist."""
    print("1. Calling unknown command 'does_not_exist' ...")
    try:
        client.call("does_not_exist")
    except RPCError as e:
        print(f"   Caught RPCError:")
        print(f"     type:      {e.error_type}")
        print(f"     message:   {e.message}")
        print(f"     traceback: {'(empty)' if not e.traceback else e.traceback[:80] + '...'}")
    print()


def demo_bad_params(client: BlendBridge):
    """Call a command with invalid parameters."""
    print("2. Calling 'render' with bad params (negative resolution) ...")
    try:
        client.call("render", resolution_x=-100)
    except RPCError as e:
        print(f"   Caught RPCError: [{e.error_type}] {e.message}")
    except Exception as e:
        print(f"   Got: {type(e).__name__}: {e}")
    print()


def demo_connection_refused():
    """Try to connect to a port where nothing is running."""
    print("3. Connecting to port 9999 (nothing there) ...")
    try:
        with BlendBridge(port=9999, timeout_ms=1000) as client:
            client.ping()
    except RPCTimeoutError as e:
        print(f"   Caught RPCTimeoutError: {e}")
    except RPCConnectionError as e:
        print(f"   Caught RPCConnectionError: {e}")
    except BlendBridgeError as e:
        print(f"   Caught BlendBridgeError: {e}")
    print()


def demo_catch_all():
    """The base class catches everything."""
    print("4. Using BlendBridgeError as a catch-all ...")
    try:
        with BlendBridge(port=9999, timeout_ms=500) as client:
            client.ping()
    except BlendBridgeError as e:
        print(f"   Caught {type(e).__name__}: {e}")
    print()


def main():
    print("=== BlendBridge Error Handling Demo ===\n")

    # Demos 1 & 2 need a running server
    print("--- Demos requiring a running server (port 5555) ---\n")
    try:
        with BlendBridge(timeout_ms=2000) as client:
            client.ping()
            demo_unknown_command(client)
            demo_bad_params(client)
    except (RPCTimeoutError, RPCConnectionError):
        print("   (skipped — no server running on port 5555)\n")

    # Demos 3 & 4 work without a server
    print("--- Demos that work without a server ---\n")
    demo_connection_refused()
    demo_catch_all()

    print("Done.")


if __name__ == "__main__":
    main()
