"""Export the API's OpenAPI schema: ``python -m app_api.openapi`` writes ``services/app_api/openapi.json``.

The file is committed. ``npm run gen:api`` in ``frontend/`` turns it into the typed client schema, and a test
fails when the committed file no longer matches the code (F09-FR-08).
"""

import json
from pathlib import Path
from typing import Any

from app_api.main import create_app

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


def build_schema() -> dict[str, Any]:
    schema: dict[str, Any] = create_app().openapi()
    return schema


def render() -> str:
    return json.dumps(build_schema(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    OPENAPI_PATH.write_text(render())
    print(f"wrote {OPENAPI_PATH}")


if __name__ == "__main__":
    main()
