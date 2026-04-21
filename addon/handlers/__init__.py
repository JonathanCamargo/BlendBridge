"""Built-in handlers for the BlendBridge server.

Importing this package triggers side-effect registration of every
handler via the @rpc_handler decorator. Called from addon/__init__.py's
register() hook so the registry is populated the moment the addon
is enabled.

Handler modules are discovered automatically — just drop a ``.py`` file
into this directory and its ``@rpc_handler`` decorated functions will
be registered on the next addon reload.  No need to edit this file.
"""
import importlib
import pkgutil

for _info in pkgutil.iter_modules(__path__):
    importlib.import_module(f".{_info.name}", __package__)