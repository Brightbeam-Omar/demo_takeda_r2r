"""F09 T0 [TDD] (OQ-060): every stage rule lists the columns it reads, and all of them are published."""

import re

from r2r_core.stage_rules import RULES
from r2r_pipeline.publish import STAGE_COLUMNS
from r2r_pipeline.schemas import BATCH_FLAT_SCHEMA

SQL_WORDS = {"AND", "OR", "NOT", "IS", "NULL", "IN", "TRUE", "FALSE"}


def referenced_columns(condition_sql: str) -> set[str]:
    without_strings = re.sub(r"'[^']*'", "", condition_sql)
    return {word for word in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", without_strings) if word.upper() not in SQL_WORDS}


def test_f09_fr06_every_column_in_a_condition_is_listed_in_the_rule_inputs() -> None:
    for rule in RULES:
        assert set(rule.inputs) == referenced_columns(rule.condition_sql), rule.id


def test_f09_fr06_every_rule_input_is_a_published_column() -> None:
    published = {*BATCH_FLAT_SCHEMA.names, *STAGE_COLUMNS}
    for rule in RULES:
        assert set(rule.inputs) <= published, (rule.id, set(rule.inputs) - published)
