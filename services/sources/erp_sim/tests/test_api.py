"""T4: ERP API against a real database [F04-FR-03, F04-AC-02, F04-AC-03, F04-AC-05]. Needs Postgres."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from erp_sim.app import app
from erp_sim.db import get_session
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

TOKEN = {"X-Scenario-Token": "s3cret"}
RECEIPT = {"matnr": "RM10001", "charg": "B1001", "lifnr": "SUP001", "lgort": "0100", "menge": 100}


@pytest.fixture
def client(factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")

    def session_for_request() -> Iterator[Session]:
        with factory() as session:
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise

    app.dependency_overrides[get_session] = session_for_request
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_f04_ac02_goods_receipt_over_http_returns_the_consistent_rows(client: TestClient) -> None:
    response = client.post("/events/goods-receipt", json=RECEIPT, headers=TOKEN)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"mcha", "mseg", "mchb", "qals", "zinbchk"}
    assert body["mseg"]["bwart"] == "101"
    assert body["qals"]["art"] == "01"
    assert body["zinbchk"]["status"] == "open"
    demo_now = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
    for row in body.values():
        assert datetime.fromisoformat(row["updated_at"]) == demo_now


def test_f04_fr10_duplicates_are_409_and_unknown_references_422(client: TestClient) -> None:
    assert client.post("/events/goods-receipt", json=RECEIPT, headers=TOKEN).status_code == 200
    assert client.post("/events/goods-receipt", json=RECEIPT, headers=TOKEN).status_code == 409
    unknown = {**RECEIPT, "charg": "B2", "matnr": "NOPE"}
    assert client.post("/events/goods-receipt", json=unknown, headers=TOKEN).status_code == 422


def test_f04_ac05_usage_decision_with_a_code_not_in_the_profile_is_422(client: TestClient) -> None:
    """F04-AC-05."""
    lot = client.post("/events/goods-receipt", json=RECEIPT, headers=TOKEN).json()["qals"]["prueflos"]
    bad = client.post("/events/usage-decision", json={"prueflos": lot, "vcode": "Z9"}, headers=TOKEN)
    assert bad.status_code == 422
    assert "usage decision code" in bad.json()["detail"]
    good = client.post("/events/usage-decision", json={"prueflos": lot, "vcode": "A"}, headers=TOKEN)
    assert good.status_code == 200
    assert good.json()["qals"]["vcode"] == "A"


def test_f04_fr03_reads_return_the_batch_with_stock_movements_and_lots(client: TestClient) -> None:
    client.post("/events/goods-receipt", json=RECEIPT, headers=TOKEN)
    detail = client.get("/batches/RM10001/B1001").json()
    assert detail["batch"]["charg"] == "B1001"
    assert [m["bwart"] for m in detail["movements"]] == ["101"]
    assert Decimal(detail["stock"][0]["insme"]) == 100  # quantities are JSON strings: no precision loss
    assert [lot["art"] for lot in detail["lots"]] == ["01"]
    lot = client.get(f"/lots/{detail['lots'][0]['prueflos']}").json()
    assert lot["inbound_check"]["status"] == "open"
    assert [m["matnr"] for m in client.get("/materials").json()] == ["RM10001"]


def test_f04_fr03_unknown_reads_are_404(client: TestClient) -> None:
    assert client.get("/batches/RM10001/NOPE").status_code == 404
    assert client.get("/lots/19999999").status_code == 404


def test_f04_fr03_every_event_endpoint_works_end_to_end(client: TestClient) -> None:
    post = lambda path, body: client.post(f"/events/{path}", json=body, headers=TOKEN)  # noqa: E731
    first = post("goods-receipt", {**RECEIPT, "lgort": "0200"}).json()
    lot = first["qals"]["prueflos"]
    assert (
        post(
            "transfer", {"matnr": "RM10001", "charg": "B1001", "from_lgort": "0200", "to_lgort": "0100"}
        ).status_code
        == 200
    )
    assert post("inbound-check", {"prueflos": lot, "status": "passed"}).status_code == 200
    assert post("stock-block", {"matnr": "RM10001", "charg": "B1001", "menge": 10}).status_code == 200
    assert post("stock-unblock", {"matnr": "RM10001", "charg": "B1001"}).status_code == 200
    assert post("hold", {"matnr": "RM10001", "charg": "B1001", "hold": True}).status_code == 200
    assert post("usage-decision", {"prueflos": lot, "vcode": "A"}).status_code == 200
    assert post("reeval-lot", {"matnr": "RM10001", "charg": "B1001"}).status_code == 200
    demand = {"matnr": "RM10001", "campaign": "CMP-ALPHA", "requirement_date": "2026-12-03", "quantity": 500}
    assert post("demand", demand).status_code == 200
    second = post("goods-receipt", {**RECEIPT, "charg": "B1002"})
    assert second.status_code == 200
    assert post("goods-receipt-reversal", {"matnr": "RM10001", "charg": "B1002"}).status_code == 200
