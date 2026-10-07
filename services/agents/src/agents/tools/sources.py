"""One fetcher per source record, each returning a **stable projection** (OQ-139, OQ-140).

The projection keeps the fields an air-gap ticket can cite and drops what moves between runs without
meaning anything: freshness, mirror and sync times, run ids, ``updated_at``. Two reads of the same facts give
byte-identical results, which lets a recording be found again after a reset. The validator uses the same
fetchers to re-read the sources (V2), so the tool and the check always see a record the same way.

Evidence field names are the keys of these projections (see ``air_gap/evidence.py``).
"""

from typing import Any
from urllib.parse import quote

from agents.tools.http import ReadOnlyHttp


def fetch_row(http: ReadOnlyHttp, row_key: str, demo_user: str | None) -> dict[str, Any]:
    body = http.get_json("app", f"/api/rows/{quote(row_key, safe='')}", demo_user=demo_user)
    facts = body.get("facts", {})
    plan = body.get("plan") or {}
    return {
        "row_key": body["row_key"],
        "material_no": body["material_no"],
        "material_desc": body.get("material_desc"),
        "batch_no": body["batch_no"],
        "supplier_name": body.get("supplier_name"),
        "campaign": body.get("campaign"),
        "stage_key": body["stage_key"],
        "inspection_lot_no": body["inspection_lot_no"],
        "sample_id": facts.get("sample_id"),
        "lims_status": body["lims_status"],
        "lims_approved_at": facts.get("lims_approved_at"),
        "ud_code": body.get("ud_code"),
        "erp_results_recorded_at": facts.get("erp_results_recorded_at"),
        "air_gap": body["air_gap"],
        "air_gap_hours": body["air_gap_hours"],
        "operative_need_by": body.get("operative_need_by"),
        "late": body["late"],
        "rag": plan.get("rag"),
        "open_deviation_count": facts.get("open_deviation_count"),
    }


def fetch_lims_sample(http: ReadOnlyHttp, sample_id: str) -> dict[str, Any]:
    body = http.get_json("lims", f"/samples/{quote(sample_id, safe='')}")
    return {
        "sample_id": body["sample_id"],
        "inspection_lot_no": body["inspection_lot_no"],
        "material_no": body["material_no"],
        "batch_no": body["batch_no"],
        "status": body["status"],
        "approved_at": body["approved_at"],
        "collected_date": body["collected_date"],
        "offsite_test": body["offsite_test"],
    }


def fetch_lims_results(http: ReadOnlyHttp, sample_id: str) -> list[dict[str, Any]]:
    body = http.get_json("lims", f"/samples/{quote(sample_id, safe='')}/results")
    return [{k: v for k, v in item.items() if k != "updated_at"} for item in body]


def fetch_erp_lot(http: ReadOnlyHttp, prueflos: str) -> dict[str, Any]:
    body = http.get_json("erp", f"/lots/{quote(prueflos, safe='')}")
    lot = body["lot"]
    check = body.get("inbound_check") or {}
    return {
        "prueflos": lot["prueflos"],
        "lot_type": lot["art"],
        "material_no": lot["matnr"],
        "batch_no": lot["charg"],
        "ud_code": lot["vcode"],
        "ud_date": lot["vdatum"],
        "results_recorded_at": lot["zresrec"],
        "inbound_check_status": check.get("status"),
    }


def fetch_deviations(http: ReadOnlyHttp, batch_no: str) -> list[dict[str, Any]]:
    body = http.get_json("qms", "/deviations", params={"batch_no": batch_no})
    return [
        {
            "deviation_no": d["deviation_no"],
            "title": d["title"],
            "severity": d["severity"],
            "status": d["status"],
            "opened_on": d["opened_on"],
            "closed_on": d["closed_on"],
        }
        for d in body
    ]


def fetch_deviation(http: ReadOnlyHttp, deviation_no: str) -> dict[str, Any]:
    body = http.get_json("qms", f"/deviations/{quote(deviation_no, safe='')}")
    return {
        "deviation_no": body["deviation_no"],
        "title": body["title"],
        "severity": body["severity"],
        "status": body["status"],
        "opened_on": body["opened_on"],
        "closed_on": body["closed_on"],
    }
