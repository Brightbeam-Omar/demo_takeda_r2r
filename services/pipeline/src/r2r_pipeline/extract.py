"""The ``extract`` step: copy the source tables into ``staging.stg_*`` Delta tables (F06-FR-01, F06-FR-02).

Tables are copied as they are, with two exceptions on ``qals``: lot types other than ``01``/``09`` and lots
whose usage decision is a cancel code never enter the pipeline. Goods receipts are not netted here: the raw
movements stay in ``stg_mseg`` and ``transform`` nets them (OQ-041).

Reads use SQLAlchemy and convert to Arrow with the schemas of ``schemas.py`` (OQ-043).
"""

from collections.abc import Sequence
from datetime import datetime

import pyarrow as pa
import pyarrow.compute as pc
from r2r_core import clock
from sqlalchemy import Engine, create_engine, text

from r2r_pipeline.context import RunContext, SourceDsns
from r2r_pipeline.lake import write_delta
from r2r_pipeline.schemas import STAGING

LOT_TYPES = ("01", "09")


def filter_qals(table: pa.Table, cancel_codes: Sequence[str]) -> pa.Table:
    """Keep initial and re-evaluation lots, and drop lots closed with a cancel usage decision."""
    keep = pc.and_(
        pc.is_in(table["art"], value_set=pa.array(LOT_TYPES)),
        pc.invert(
            pc.fill_null(pc.is_in(table["vcode"], value_set=pa.array(list(cancel_codes), pa.string())), False)
        ),
    )
    return table.filter(keep)


def read_table(engine: Engine, source_table: str, schema: pa.Schema) -> pa.Table:
    columns = ", ".join(schema.names)
    with engine.connect() as connection:
        rows = [
            dict(row._mapping) for row in connection.execute(text(f"SELECT {columns} FROM {source_table}"))
        ]
    return pa.Table.from_pylist(rows, schema=schema)


def max_updated_at(tables: Sequence[pa.Table]) -> datetime | None:
    latest: datetime | None = None
    for table in tables:
        value = pc.max(table["updated_at"]).as_py()
        if value is not None and (latest is None or value > latest):
            latest = value
    return latest


def extract(ctx: RunContext) -> None:
    """Fill ``staging.stg_*`` and ``ctx.freshness`` ({source: {max_updated_at, extracted_at}})."""
    dsns = ctx.dsns or SourceDsns.from_env()
    sources = {"erp": dsns.erp, "lims": dsns.lims, "qms": dsns.qms}
    extracted_at = clock.now()
    for source, dsn in sources.items():
        engine = create_engine(dsn)
        try:
            staged: list[pa.Table] = []
            for name, (source_table, schema) in STAGING[source].items():
                table = read_table(engine, source_table, schema)
                staged.append(table)
                if name == "stg_qals":
                    table = filter_qals(table, ctx.profile.ud_codes.cancel)
                write_delta(ctx.lake_root, f"staging.{name}", table)
        finally:
            engine.dispose()
        latest = max_updated_at(staged)
        ctx.freshness[source] = {
            "max_updated_at": latest.isoformat() if latest else None,
            "extracted_at": extracted_at.isoformat(),
        }
