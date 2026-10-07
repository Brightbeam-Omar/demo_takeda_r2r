"""The tool registry (F12-FR-04): JSON-schema described, read-only, allow-listed, and traced by the runner.

A tool is a name, a description for the model, an input schema and a function returning a stable projection.
The registry validates the arguments against the schema, runs the function and returns the answer as canonical
JSON text, the same text every time for the same facts, so it can be part of a replay key.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agents.gateway.base import ToolSpec
from agents.tools.http import ReadOnlyHttp, ToolError
from agents.tools.sources import (
    fetch_deviations,
    fetch_erp_lot,
    fetch_lims_results,
    fetch_lims_sample,
    fetch_row,
)

MAX_TOOL_CALLS = 8

ToolFunction = Callable[[dict[str, Any], str | None], Any]


@dataclass(frozen=True)
class Tool:
    name: str
    system: str  # which system it reads, shown in the trace
    description: str
    input_schema: dict[str, Any]
    run: ToolFunction

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, input_schema=self.input_schema)


@dataclass(frozen=True)
class ToolOutput:
    content: str  # canonical JSON text handed to the model
    is_error: bool
    system: str


def _one_string(name: str, description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {name: {"type": "string", "description": description}},
        "required": [name],
        "additionalProperties": False,
    }


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def system_of(self, name: str) -> str:
        return self._tools[name].system

    def call(self, name: str, arguments: dict[str, Any], demo_user: str | None) -> ToolOutput:
        tool = self._tools.get(name)
        if tool is None:
            return ToolOutput(canonical({"error": f"unknown tool {name!r}"}), True, "none")
        problem = _check_arguments(tool.input_schema, arguments)
        if problem:
            return ToolOutput(canonical({"error": problem}), True, tool.system)
        try:
            return ToolOutput(canonical(tool.run(arguments, demo_user)), False, tool.system)
        except ToolError as error:
            return ToolOutput(canonical({"error": str(error)}), True, tool.system)


def _check_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> str | None:
    properties: dict[str, Any] = schema.get("properties", {})
    for required in schema.get("required", []):
        if required not in arguments:
            return f"missing argument {required!r}"
    for key, value in arguments.items():
        if key not in properties:
            return f"unexpected argument {key!r}"
        if properties[key].get("type") == "string" and not isinstance(value, str):
            return f"argument {key!r} must be a string"
    return None


def read_only_tools(http: ReadOnlyHttp) -> ToolRegistry:
    """The five tools of the air-gap agent."""
    return ToolRegistry(
        [
            Tool(
                "get_row",
                "app",
                "Read one batch row of the pipeline (stage, LIMS status and approval time, ERP usage "
                "decision "
                "and results record, air-gap hours, need-by date, late flag, open deviation count).",
                _one_string("row_key", "The row key, for example 'RM10067|B5003|10000459'."),
                lambda args, user: fetch_row(http, args["row_key"], user),
            ),
            Tool(
                "get_lims_sample",
                "LIMS",
                "Read one LIMS sample: its status and approval time.",
                _one_string("sample_id", "The LIMS sample id, for example 'S-0000404'."),
                lambda args, user: fetch_lims_sample(http, args["sample_id"]),
            ),
            Tool(
                "get_lims_results",
                "LIMS",
                "Read the LIMS test results recorded for one sample (may be empty).",
                _one_string("sample_id", "The LIMS sample id."),
                lambda args, user: fetch_lims_results(http, args["sample_id"]),
            ),
            Tool(
                "get_erp_lot",
                "ERP",
                "Read one ERP inspection lot: usage decision code and date, and when the ERP recorded the "
                "LIMS "
                "results (null when it never did).",
                _one_string("prueflos", "The inspection lot number, for example '10000459'."),
                lambda args, user: fetch_erp_lot(http, args["prueflos"]),
            ),
            Tool(
                "list_deviations",
                "QMS",
                "List the quality deviations linked to a batch, with their status.",
                _one_string("batch_no", "The batch number, for example 'B5003'."),
                lambda args, user: fetch_deviations(http, args["batch_no"]),
            ),
        ]
    )
