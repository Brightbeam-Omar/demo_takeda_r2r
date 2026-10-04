"""Smoke test: the r2r_core package imports and exposes a version."""

import r2r_core


def test_package_imports() -> None:
    assert r2r_core.__version__ == "0.1.0"
