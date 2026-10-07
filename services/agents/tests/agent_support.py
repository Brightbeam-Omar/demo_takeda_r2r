"""Test doubles shared by the agents tests."""

import json

import httpx

USERS = {
    "pat": ("Pat", "planner"),
    "quinn": ("Quinn", "qc_lead"),
    "alex": ("Alex", "qa_release"),
    "sam": ("Sam", "viewer"),
    "admin": ("Admin", "admin"),
}


def fake_app_api() -> httpx.Client:
    """An app-api stand-in that answers ``/api/me`` like the real one (default persona: pat)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/me":
            return httpx.Response(404)
        key = request.headers.get("X-Demo-User", "pat")
        if key not in USERS:
            return httpx.Response(401, json={"detail": "unknown X-Demo-User"})
        name, role = USERS[key]
        return httpx.Response(200, content=json.dumps({"user_key": key, "display_name": name, "role": role}))

    return httpx.Client(base_url="http://app-api.test", transport=httpx.MockTransport(handler))
