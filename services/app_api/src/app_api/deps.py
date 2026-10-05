"""Shared request dependencies: the site profile and the demo clock's today."""

import functools
import os
from datetime import date

from r2r_core import clock
from r2r_core.profile import SiteProfile, load_profile


@functools.cache
def get_profile() -> SiteProfile:
    return load_profile(os.environ.get("SITE_PROFILE", "site_a"))


def demo_today(profile: SiteProfile) -> date:
    return clock.now().astimezone(profile.site.tz).date()
