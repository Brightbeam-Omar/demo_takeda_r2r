"""The ``transform`` step: SQL files over the staging tables build ``batch_flat`` and ``batch_stage``."""

from datetime import date
from pathlib import Path
from typing import Any

from r2r_core.profile import SiteProfile

_PACKAGE_SQL = Path(__file__).parent / "sql"
SQL_DIR = (
    _PACKAGE_SQL if _PACKAGE_SQL.is_dir() else Path(__file__).resolve().parents[2] / "sql"
) / "transform"


def transform_files() -> list[Path]:
    """The transform SQL files in lexical order (``.sql`` and ``.sql.j2``)."""
    return sorted(p for p in SQL_DIR.iterdir() if p.name.endswith((".sql", ".sql.j2")))


def template_variables(profile: SiteProfile, snapshot_date: date) -> dict[str, Any]:
    """What the SQL templates may use: the snapshot date and everything that comes from the profile."""
    return {
        "snapshot_date": snapshot_date,
        "accept_codes": list(profile.ud_codes.accept),
        "reject_codes": list(profile.ud_codes.reject),
        "cancel_codes": list(profile.ud_codes.cancel),
        "timezone": profile.site.timezone,
        "full_spec_pairs": [(p.material, p.supplier) for p in profile.full_spec_pairs],
    }
