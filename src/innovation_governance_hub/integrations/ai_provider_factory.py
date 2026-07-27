from innovation_governance_hub.config import Settings, get_settings
from innovation_governance_hub.integrations.demo_ai_provider import DemoAIProvider
from innovation_governance_hub.integrations.gemini_ai_provider import GeminiAIProvider


def create_ai_provider(settings: Settings | None = None) -> DemoAIProvider | GeminiAIProvider:
    config = settings or get_settings()
    if config.ai_provider.lower() == "gemini" and config.gemini_api_key:
        return GeminiAIProvider(
            config.gemini_api_key, config.gemini_model, config.ai_request_timeout_seconds
        )
    return DemoAIProvider()
