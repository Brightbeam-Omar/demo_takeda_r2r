"""The ``bedrock`` provider: a stub until the AWS deployment (T2-10)."""

from agents.gateway.base import GatewayError, ModelGateway, ModelResult, Msg, ToolSpec


class BedrockGateway(ModelGateway):
    provider = "bedrock"

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id

    def generate(
        self, *, system: str, messages: list[Msg], tools: list[ToolSpec] | None, turn: int
    ) -> ModelResult:
        raise GatewayError("the bedrock provider arrives with T2-10 (AWS deployment)")
