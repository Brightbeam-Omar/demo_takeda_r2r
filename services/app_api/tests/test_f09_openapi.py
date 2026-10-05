"""F09-FR-08: the committed OpenAPI file matches the code, and covers every endpoint of the spec."""

from app_api.openapi import OPENAPI_PATH, build_schema, render

EXPECTED = {
    ("get", "/api/me"), ("get", "/api/clock"), ("get", "/api/users"), ("get", "/api/reference"),
    ("get", "/api/overview"), ("get", "/api/metrics"), ("get", "/api/rows/{row_key}"),
    ("get", "/api/rows/{row_key}/explain"), ("get", "/api/explain"),
    ("put", "/api/rows/{row_key}/need-by"), ("put", "/api/rows/{row_key}/status"),
    ("post", "/api/rows/{row_key}/comments"), ("get", "/api/audit"), ("get", "/api/export.csv"),
}  # fmt: skip


def test_f09_fr08_every_endpoint_of_the_spec_is_in_the_schema() -> None:
    present = {(method, path) for path, item in build_schema()["paths"].items() for method in item}
    assert present >= EXPECTED


def test_f09_fr08_the_committed_openapi_json_is_current() -> None:
    assert OPENAPI_PATH.read_text() == render(), "run: uv run python -m app_api.openapi"
