"""A hand-built fixture world: a few rows in each source table, written as staging Delta tables.

It lets the transform tests run without Postgres. The helpers mirror what the simulators' events write.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
from r2r_pipeline.lake import write_delta
from r2r_pipeline.schemas import STAGING_SCHEMAS

NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
TABLE_FOR = {
    "mara": "stg_mara",
    "lfa1": "stg_lfa1",
    "t001l": "stg_t001l",
    "mcha": "stg_mcha",
    "mchb": "stg_mchb",
}


class World:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {name: [] for name in STAGING_SCHEMAS}
        self._document = 4_900_000_000
        self._sample = 0
        self.add(
            "stg_mara",
            matnr="RM1",
            maktx="Excipient 001",
            mtart="ROH",
            zmolty="small_molecule",
            zclass="drug_substance",
        )
        self.add("stg_lfa1", lifnr="SUP1", name1="Supplier 001", land1="IE")
        for lgort, name, kind in (
            ("0100", "Main Warehouse", "onsite"),
            ("0200", "3PL North", "3pl"),
            ("0300", "Cold Store", "onsite"),
        ):
            self.add("stg_t001l", lgort=lgort, lgobe=name, zloctype=kind)

    def add(self, table: str, **values: Any) -> None:
        row: dict[str, Any] = dict.fromkeys(STAGING_SCHEMAS[table].names)
        row["updated_at"] = NOW
        row.update(values)
        self.rows[table].append(row)

    def document(self) -> str:
        self._document += 1
        return str(self._document)

    def move(
        self,
        bwart: str,
        charg: str,
        lgort: str,
        day: date,
        qty: int = 100,
        matnr: str = "RM1",
        umlgo: str | None = None,
    ) -> str:
        number = self.document()
        self.add(
            "stg_mseg",
            mblnr=number,
            zeile="0001",
            bwart=bwart,
            matnr=matnr,
            charg=charg,
            lgort=lgort,
            umlgo=umlgo,
            budat=day,
            menge=Decimal(qty),
        )
        return number

    def stock(
        self, charg: str, lgort: str, insme: int = 0, speme: int = 0, clabs: int = 0, matnr: str = "RM1"
    ) -> None:
        self.add(
            "stg_mchb",
            matnr=matnr,
            charg=charg,
            lgort=lgort,
            insme=Decimal(insme),
            speme=Decimal(speme),
            clabs=Decimal(clabs),
        )

    def receive(
        self,
        charg: str,
        lot: str,
        day: date,
        lgort: str = "0100",
        qty: int = 100,
        matnr: str = "RM1",
        hold: bool = False,
        qnext: date | None = None,
    ) -> str:
        """Goods receipt as F04 writes it: batch, 101, QI stock, lot 01 and an open inbound check."""
        self.add(
            "stg_mcha",
            matnr=matnr,
            charg=charg,
            lifnr="SUP1",
            licha=charg,
            zstat="H" if hold else "",
            qnext=qnext,
        )
        self.move("101", charg, lgort, day, qty, matnr)
        self.stock(charg, lgort, insme=qty, matnr=matnr)
        self.add("stg_qals", prueflos=lot, art="01", matnr=matnr, charg=charg, pastrterm=day)
        self.add("stg_zinbchk", prueflos=lot, status="open")
        return lot

    def reeval(self, charg: str, lot: str, start: date, matnr: str = "RM1") -> str:
        self.add("stg_qals", prueflos=lot, art="09", matnr=matnr, charg=charg, pastrterm=start)
        return lot

    def check(self, lot: str, status: str, day: date | None) -> None:
        for row in self.rows["stg_zinbchk"]:
            if row["prueflos"] == lot:
                row["status"], row["completed_on"] = status, day

    def items(self, lot: str, outcomes: list[tuple[str, str, str]]) -> None:
        """Inbound sub-checks of the lot's check, in order: ``(code, label, outcome)``."""
        for seq, (code, label, outcome) in enumerate(outcomes, start=1):
            self.add(
                "stg_zinbchk_item", prueflos=lot, seq=seq, check_code=code, check_label=label, outcome=outcome
            )

    def lot_field(self, lot: str, **values: Any) -> None:
        for row in self.rows["stg_qals"]:
            if row["prueflos"] == lot:
                row.update(values)

    def sample(
        self,
        lot: str,
        collected: date,
        status: str = "in_progress",
        offsite: bool = False,
        shipped: date | None = None,
        approved_at: datetime | None = None,
        matnr: str = "RM1",
        charg: str = "B1",
    ) -> str:
        self._sample += 1
        sample_id = f"S-{self._sample:07d}"
        self.add(
            "stg_sample",
            sample_id=sample_id,
            inspection_lot_no=lot,
            material_no=matnr,
            batch_no=charg,
            collected_date=collected,
            offsite_test=offsite,
            external_lab="External Lab A" if offsite else None,
            shipped_date=shipped,
            status=status,
            approved_at=approved_at,
        )
        return sample_id

    def demand(
        self,
        ident: int,
        requirement: date,
        campaign: str = "CMP-ALPHA",
        is_open: bool = True,
        matnr: str = "RM1",
    ) -> None:
        self.add(
            "stg_mdez",
            id=ident,
            matnr=matnr,
            campaign=campaign,
            bdter=requirement,
            bdmng=Decimal(100),
            is_open=is_open,
        )

    def po_line(
        self,
        ebeln: str,
        scheduled: date,
        is_open: bool = True,
        matnr: str = "RM1",
        lgort: str = "0100",
        ebelp: str = "00010",
    ) -> None:
        self.add(
            "stg_ekpo",
            ebeln=ebeln,
            ebelp=ebelp,
            matnr=matnr,
            lifnr="SUP1",
            eindt=scheduled,
            menge=Decimal(100),
            lgort=lgort,
            is_open=is_open,
        )

    def deviation(self, number: str, status: str, links: list[tuple[str, str]]) -> None:
        self.add(
            "stg_deviation",
            deviation_no=number,
            title="t",
            description="d",
            severity="minor",
            status=status,
            opened_on=date(2026, 10, 1),
            owner="QA",
        )
        for material, batch in links:
            self.add("stg_deviation_link", deviation_no=number, material_no=material, batch_no=batch)

    def write(self, lake_root: Path) -> None:
        for name, schema in STAGING_SCHEMAS.items():
            write_delta(lake_root, f"staging.{name}", pa.Table.from_pylist(self.rows[name], schema=schema))
