"""Smoke test: the blendbridge package must import cleanly after `pip install -e .`."""


def test_import_blendbridge():
    import blendbridge

    assert hasattr(blendbridge, "__version__")
    assert blendbridge.__version__ == "0.1.0"


def test_import_blendbridge_client():
    import blendbridge.client  # noqa: F401
