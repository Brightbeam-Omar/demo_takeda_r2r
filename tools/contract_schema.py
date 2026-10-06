"""Generate ``specs/contract.json``, the published contract as the Schema Reference page shows it (F21-FR-06).

    uv run python tools/contract_schema.py            # write specs/contract.json
    uv run python tools/contract_schema.py --check    # exit 1 when the committed file is stale

Sources (OQ-132):
* object names: the ``published/`` list of 04-data-contracts section 2, checked against the pipeline (the
  pipeline's publish order is the order of the page, ``pipeline_status_v`` last);
* column names and types: the Arrow schemas the pipeline publishes (``r2r_pipeline.contract_schemas``), which
  a pipeline test compares with the real Delta tables;
* descriptions: the derivation table of 04 section 3, and ``specs/contract_descriptions.yaml``.

The generator stops with a message when the three disagree: an object missing from 04, a column the 04 text
never mentions, or a column nobody described.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import yaml
from r2r_pipeline.contract_schemas import published_schemas

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MD = ROOT / "specs" / "04-data-contracts.md"
DESCRIPTIONS = ROOT / "specs" / "contract_descriptions.yaml"
OUTPUT = ROOT / "specs" / "contract.json"


class ContractError(Exception):
    """The sources disagree; the message says where."""


def type_name(kind: pa.DataType) -> str:
    if pa.types.is_string(kind):
        return "string"
    if pa.types.is_date(kind):
        return "date"
    if pa.types.is_timestamp(kind):
        return "timestamp"
    if pa.types.is_boolean(kind):
        return "boolean"
    if pa.types.is_integer(kind):
        return "integer"
    if pa.types.is_decimal(kind):
        return f"decimal({kind.precision},{kind.scale})"
    raise ContractError(f"no type name for {kind}")


def objects_in_section_2(text: str) -> list[str]:
    """The published objects listed under ``published/`` in the lakehouse layout block."""
    block = text.split("published/", 1)[1].split("```", 1)[0]
    return re.findall(r"\b([a-z_]+_v)\b", block)


def names_in(text: str) -> set[str]:
    """Every identifier the document puts in backticks (comma lists inside one span included)."""
    names: set[str] = set()
    for line in text.splitlines():  # per line: a stray backtick must not pair spans across lines
        for span in re.findall(r"`([^`]+)`", line):
            names.update(re.findall(r"[a-z][a-z0-9_]*", span))
    return names


def derivations(text: str) -> dict[str, str]:
    """The column to derivation rows of the section 3 table (``open_/closed_deviation_count`` is split)."""
    start = text.index("Derivations (non-obvious columns)")
    table = text[start : text.index("### 3b.", start)]
    found: dict[str, str] = {}
    for column, derivation in re.findall(r"^\| `([a-z_/]+)` \| (.+) \|$", table, re.MULTILINE):
        cleaned = derivation.replace("**", "").strip()
        if column == "open_/closed_deviation_count":
            found["open_deviation_count"] = found["closed_deviation_count"] = cleaned
        else:
            found[column] = cleaned
    return found


def build() -> dict[str, Any]:
    markdown = CONTRACT_MD.read_text(encoding="utf-8")
    described = yaml.safe_load(DESCRIPTIONS.read_text(encoding="utf-8"))
    schemas = published_schemas()
    listed = objects_in_section_2(markdown)
    if set(listed) != set(schemas):
        raise ContractError(
            f"04 section 2 lists {sorted(listed)}, the pipeline publishes {sorted(schemas)}: "
            "update the document"
        )
    mentioned = names_in(markdown)
    derivation = derivations(markdown)
    objects = []
    for name, schema in schemas.items():
        info = described["objects"].get(name)
        if not info:
            raise ContractError(f"contract_descriptions.yaml has no entry for object {name}")
        columns = []
        for field in schema:
            if field.name not in mentioned:
                raise ContractError(f"{name}.{field.name} is never mentioned in 04-data-contracts.md")
            text = (
                described["columns"].get(name, {}).get(field.name)
                or (derivation.get(field.name) if name == "batch_pipeline_v" else None)
                or described["columns"]["_common"].get(field.name)
            )
            if not text:
                raise ContractError(f"{name}.{field.name} has no description (contract_descriptions.yaml)")
            columns.append({"name": field.name, "type": type_name(field.type), "description": text})
        objects.append(
            {"name": name, "description": info["description"], "grain": info["grain"], "columns": columns}
        )
    return {
        "generated_from": ["specs/04-data-contracts.md", "specs/contract_descriptions.yaml", "r2r_pipeline"],
        "objects": objects,
    }


def render() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="fail when specs/contract.json is stale")
    args = parser.parse_args(argv)
    try:
        text = render()
    except ContractError as error:
        print(f"contract_schema: {error}", file=sys.stderr)
        return 2
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            print("contract_schema: specs/contract.json is stale. Run: make contract-json", file=sys.stderr)
            return 1
        print("contract_schema: specs/contract.json is current")
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"contract_schema: wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
