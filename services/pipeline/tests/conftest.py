"""Fixtures for the pipeline tests."""

import pytest
from r2r_core.profile import SiteProfile, load_profile


@pytest.fixture(scope="session")
def profile() -> SiteProfile:
    return load_profile("site_a")
