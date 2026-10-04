"""``source_refs_json``: where each published row came from, for lineage and the Explain view (F06-FR-07)."""

import json
from collections import defaultdict

import pyarrow as pa


def build_source_refs(flat: pa.Table, mseg: pa.Table, deviation_link: pa.Table) -> dict[str, str]:
    """``{row_key: json}``. Every material document of the batch is listed, netted ones included (OQ-041)."""
    documents: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in mseg.select(["matnr", "charg", "mblnr"]).to_pylist():
        documents[(row["matnr"], row["charg"])].append(row["mblnr"])
    deviations: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in deviation_link.select(["material_no", "batch_no", "deviation_no"]).to_pylist():
        deviations[(row["material_no"], row["batch_no"])].append(row["deviation_no"])
    out: dict[str, str] = {}
    for row in flat.select(
        ["row_key", "material_no", "batch_no", "inspection_lot_no", "sample_id"]
    ).to_pylist():
        key = (row["material_no"], row["batch_no"])
        refs = {
            "erp": {
                "mcha": f"{row['material_no']}|{row['batch_no']}",
                "qals": row["inspection_lot_no"],
                "mseg": sorted(documents.get(key, [])),
            },
            "lims": {"sample": row["sample_id"]},
            "qms": {"deviation": sorted(deviations.get(key, []))},
        }
        out[row["row_key"]] = json.dumps(refs, separators=(",", ":"))
    return out
