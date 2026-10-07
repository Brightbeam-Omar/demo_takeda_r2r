"""Service settings, read from the environment once (``.env`` is the only source of secrets)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# services/agents/recordings next to this package when run from the repository; compose sets the variable.
DEFAULT_RECORDINGS = Path(__file__).resolve().parents[2] / "recordings"


@dataclass(frozen=True)
class Settings:
    app_api_url: str
    erp_url: str
    lims_url: str
    qms_url: str
    llm_provider: str
    model_id: str
    price_in_per_1k: float
    price_out_per_1k: float
    autorun: bool
    service_user: str
    recordings_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        return cls(
            app_api_url=source.get("APP_API_URL", "http://app-api:8000").rstrip("/"),
            erp_url=source.get("ERP_URL", "http://erp-sim:8101").rstrip("/"),
            lims_url=source.get("LIMS_URL", "http://lims-sim:8102").rstrip("/"),
            qms_url=source.get("QMS_URL", "http://qms-sim:8103").rstrip("/"),
            llm_provider=source.get("LLM_PROVIDER", "replay"),
            model_id=source.get("MODEL_ID", "claude-sonnet-5-5"),
            price_in_per_1k=float(source.get("LLM_PRICE_IN_PER_1K", "0.003")),
            price_out_per_1k=float(source.get("LLM_PRICE_OUT_PER_1K", "0.015")),
            autorun=source.get("AGENTS_AUTORUN", "false").lower() == "true",
            service_user=source.get("AGENTS_SERVICE_USER", "admin"),
            recordings_dir=Path(source.get("AGENTS_RECORDINGS_DIR") or DEFAULT_RECORDINGS),
        )
