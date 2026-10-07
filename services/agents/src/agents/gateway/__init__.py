"""Model providers behind one interface; ``LLM_PROVIDER`` picks one."""

from agents.gateway.base import GatewayError, ModelGateway
from agents.settings import Settings


def build_gateway(settings: Settings) -> ModelGateway:
    provider = settings.llm_provider
    if provider == "anthropic":
        from agents.gateway.anthropic import AnthropicGateway

        return AnthropicGateway(settings.model_id)
    if provider == "bedrock":
        from agents.gateway.bedrock import BedrockGateway

        return BedrockGateway(settings.model_id)
    raise GatewayError(f"unknown LLM_PROVIDER {provider!r}")
