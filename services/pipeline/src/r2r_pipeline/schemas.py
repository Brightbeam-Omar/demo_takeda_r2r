"""Arrow schemas of the staging tables: the columns of ``04-data-contracts`` section 1, as extract reads them.

The pipeline does not import the simulators; this module is the contract it reads against.
"""

import pyarrow as pa

TEXT = pa.string()
DATE = pa.date32()
STAMP = pa.timestamp("us", tz="UTC")
QTY = pa.decimal128(13, 3)
BOOL = pa.bool_()
INT = pa.int64()


def _schema(**columns: pa.DataType) -> pa.Schema:
    return pa.schema([*columns.items(), ("updated_at", STAMP)])


# source -> {staging table: (source table, schema)}
STAGING: dict[str, dict[str, tuple[str, pa.Schema]]] = {
    "erp": {
        "stg_mara": ("mara", _schema(matnr=TEXT, maktx=TEXT, mtart=TEXT, zmolty=TEXT, zclass=TEXT)),
        "stg_lfa1": ("lfa1", _schema(lifnr=TEXT, name1=TEXT, land1=TEXT)),
        "stg_t001l": ("t001l", _schema(lgort=TEXT, lgobe=TEXT, zloctype=TEXT)),
        "stg_mcha": (
            "mcha",
            _schema(
                matnr=TEXT,
                charg=TEXT,
                lifnr=TEXT,
                licha=TEXT,
                hsdat=DATE,
                vfdat=DATE,
                zstat=TEXT,
                qnext=DATE,
                zexprq=DATE,
                zexpdd=DATE,
            ),
        ),
        "stg_mchb": (
            "mchb",
            _schema(matnr=TEXT, charg=TEXT, lgort=TEXT, insme=QTY, speme=QTY, clabs=QTY),
        ),
        "stg_mseg": (
            "mseg",
            _schema(
                mblnr=TEXT,
                zeile=TEXT,
                bwart=TEXT,
                matnr=TEXT,
                charg=TEXT,
                lgort=TEXT,
                umlgo=TEXT,
                budat=DATE,
                menge=QTY,
            ),
        ),
        "stg_qals": (
            "qals",
            _schema(
                prueflos=TEXT,
                art=TEXT,
                matnr=TEXT,
                charg=TEXT,
                pastrterm=DATE,
                vcode=TEXT,
                vdatum=DATE,
                zresrec=STAMP,
            ),
        ),
        "stg_zinbchk": (
            "zinbchk",
            _schema(prueflos=TEXT, status=TEXT, completed_on=DATE, notes=TEXT),
        ),
        "stg_zinbchk_item": (
            "zinbchk_item",
            _schema(prueflos=TEXT, seq=INT, check_code=TEXT, check_label=TEXT, outcome=TEXT),
        ),
        "stg_mdez": (
            "mdez",
            _schema(id=INT, matnr=TEXT, campaign=TEXT, bdter=DATE, bdmng=QTY, is_open=BOOL),
        ),
        "stg_ekpo": (
            "ekpo",
            _schema(
                ebeln=TEXT,
                ebelp=TEXT,
                matnr=TEXT,
                lifnr=TEXT,
                eindt=DATE,
                menge=QTY,
                lgort=TEXT,
                is_open=BOOL,
            ),
        ),
    },
    "lims": {
        "stg_sample": (
            "sample",
            _schema(
                sample_id=TEXT,
                inspection_lot_no=TEXT,
                material_no=TEXT,
                batch_no=TEXT,
                collected_date=DATE,
                offsite_test=BOOL,
                external_lab=TEXT,
                shipped_date=DATE,
                status=TEXT,
                approved_at=STAMP,
            ),
        ),
    },
    "qms": {
        "stg_deviation": (
            "deviation",
            _schema(
                deviation_no=TEXT,
                title=TEXT,
                description=TEXT,
                severity=TEXT,
                status=TEXT,
                opened_on=DATE,
                closed_on=DATE,
                root_cause_category=TEXT,
                causal_factor=TEXT,
                investigation_summary=TEXT,
                owner=TEXT,
            ),
        ),
        "stg_deviation_link": (
            "deviation_link",
            _schema(deviation_no=TEXT, material_no=TEXT, batch_no=TEXT),
        ),
        "stg_change_control": (
            "change_control",
            _schema(
                cc_no=TEXT,
                title=TEXT,
                status=TEXT,
                current_state=TEXT,
                proposed_state=TEXT,
                opened_on=DATE,
                effective_on=DATE,
            ),
        ),
        "stg_change_control_link": (
            "change_control_link",
            _schema(cc_no=TEXT, material_no=TEXT, batch_no=TEXT),
        ),
    },
}

STAGING_SCHEMAS: dict[str, pa.Schema] = {
    name: schema for tables in STAGING.values() for name, (_, schema) in tables.items()
}


_FLAT_COLUMNS: dict[str, pa.DataType] = dict(
    row_key=TEXT, material_no=TEXT, material_desc=TEXT, material_class=TEXT, molecule_type=TEXT,
    supplier_id=TEXT, supplier_name=TEXT, supplier_batch=TEXT, batch_no=TEXT, batch_status_code=TEXT,
    inspection_lot_no=TEXT, lot_type=TEXT, lot_start_date=DATE, storage_location=TEXT, location_type=TEXT,
    received_location_type=TEXT, stock_category=TEXT, gr_date=DATE, transfer_to_site_date=DATE,
    inbound_check_status=TEXT, inbound_check_completed_date=DATE, sample_id=TEXT, sample_collected_date=DATE,
    offsite_test=BOOL, external_lab=TEXT, sample_shipped_date=DATE, lims_status=TEXT, lims_approved_date=DATE,
    lims_approved_at=STAMP, ud_code=TEXT, ud_date=DATE, erp_results_recorded_at=STAMP, campaign=TEXT,
    system_need_by_date=DATE, open_deviation_count=INT, closed_deviation_count=INT,
    next_inspection_date=DATE, need_by_at_release=DATE, expedite_requested_on=DATE, expedite_due_date=DATE,
)  # fmt: skip

# ``staging.batch_flat`` (04-data-contracts section 3): the stage engine's input.
BATCH_FLAT_SCHEMA = pa.schema(list(_FLAT_COLUMNS.items()))

# ``staging.expected_deliveries`` (F17-FR-03): the open purchase-order lines; publish adds ``run_id``.
EXPECTED_DELIVERIES_SCHEMA = pa.schema(
    [
        ("ebeln", TEXT), ("ebelp", TEXT), ("material_no", TEXT), ("material_desc", TEXT),
        ("molecule_type", TEXT), ("material_class", TEXT), ("supplier_id", TEXT), ("supplier_name", TEXT),
        ("campaign", TEXT), ("scheduled_date", DATE), ("quantity", QTY), ("planned_location", TEXT),
        ("planned_location_type", TEXT), ("overdue", BOOL),
    ]
)  # fmt: skip
