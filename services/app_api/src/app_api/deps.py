"""Shared request dependencies: the site profile and the demo clock's today."""

import functools
import os
from datetime import date
from pathlib import Path

from r2r_core import clock
from r2r_core.profile import SiteProfile, load_profile


@functools.cache
def get_profile() -> SiteProfile:
    return load_profile(os.environ.get("SITE_PROFILE", "site_a"))


def profile_file() -> str:
    """File name of the active site profile (``site_a.yaml``), for pages that say where it is configured."""
    active = os.environ.get("SITE_PROFILE", "site_a")
    return Path(active).name if "/" in active or active.endswith((".yaml", ".yml")) else f"{active}.yaml"


def demo_today(profile: SiteProfile) -> date:
    return clock.now().astimezone(profile.site.tz).date()
