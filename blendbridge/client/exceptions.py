"""Exception hierarchy for the blendbridge client library.

All exceptions raised by BlendBridge are subclasses of BlendBridgeError,
which is itself a subclass of the built-in Exception.
"""
from __future__ import annotations


class BlendBridgeError(Exception):
    """Base class for all blendbridge client exceptions."""


class RPCError(BlendBridgeError):
    """Raised when the server returns an error envelope.

    Attributes
    ----------
    error_type:
        The exception class name as reported by the server (e.g. "ValueError").
    message:
        The human-readable error description from the server.
    traceback:
        The formatted traceback string from the server, or empty string if absent.
    """

    def __init__(self, error_type: str, message: str, traceback: str = "") -> None:
        self.error_type = error_type
        self.message = message
        self.traceback = traceback
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"{self.error_type}: {self.message}"


class RPCTimeoutError(BlendBridgeError):
    """Raised when no response arrives within the configured timeout.

    Attributes
    ----------
    timeout_ms:
        The timeout value (in milliseconds) that was exceeded.
    command:
        The command name that timed out, or empty string if unknown.
    """

    def __init__(self, timeout_ms: int, command: str = "") -> None:
        self.timeout_ms = timeout_ms
        self.command = command
        super().__init__(str(self))

    def __str__(self) -> str:
        cmd_part = f" (command={self.command!r})" if self.command else ""
        return f"RPC call timed out after {self.timeout_ms}ms{cmd_part}"


class RPCConnectionError(BlendBridgeError):
    """Raised when a ZMQ connection cannot be established.

    Attributes
    ----------
    url:
        The ZMQ endpoint URL that was being connected to.
    reason:
        A description of why the connection failed, or empty string if unknown.
    """

    def __init__(self, url: str, reason: str = "") -> None:
        self.url = url
        self.reason = reason
        super().__init__(str(self))

    def __str__(self) -> str:
        reason_part = f": {self.reason}" if self.reason else ""
        return f"Could not connect to {self.url}{reason_part}"
