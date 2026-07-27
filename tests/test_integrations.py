import httpx
import pytest

from innovation_governance_hub.config import Settings
from innovation_governance_hub.exceptions import DomainError
from innovation_governance_hub.integrations.ai_provider_factory import create_ai_provider
from innovation_governance_hub.integrations.demo_ai_provider import DemoAIProvider
from innovation_governance_hub.integrations.gemini_ai_provider import GeminiAIProvider
from innovation_governance_hub.integrations.n8n_client import N8NClient


def test_demo_summary_structured():
    result = DemoAIProvider().summarize(
        "Foi decidido aprovar o piloto. Ana deve entregar até 15/08/2026."
    )
    assert result.mode == "Modo demonstração local"
    assert result.decisions
    assert result.mentioned_deadlines == ["15/08/2026"]


def test_factory_without_key_and_n8n_disabled():
    settings = Settings(ai_provider="gemini", gemini_api_key="", n8n_enabled=False)
    assert isinstance(create_ai_provider(settings), DemoAIProvider)
    assert N8NClient(settings).send({})["status"] == "disabled"


class FakeModels:
    def __init__(self, response_text: str | None = None, error: Exception | None = None):
        self.response_text = response_text
        self.error = error

    def generate_content(self, **_kwargs):
        if self.error:
            raise self.error
        return type("Response", (), {"text": self.response_text})()


class FakeClient:
    def __init__(self, models: FakeModels):
        self.models = models


def test_gemini_with_fake_client_preserves_real_mode():
    text = '{"executive_summary":"Resumo","decisions":[],"action_items":[],"next_steps":[],"mentioned_people":[],"mentioned_deadlines":[]}'
    provider = GeminiAIProvider("fake", "fake-model", client=FakeClient(FakeModels(text)))
    result = provider.summarize("Ata fictícia")
    assert result.provider_name == "Google Gemini"
    assert result.mode == "Modo real"


def test_gemini_timeout_is_explicit_error():
    provider = GeminiAIProvider(
        "fake", "fake-model", client=FakeClient(FakeModels(error=TimeoutError()))
    )
    with pytest.raises(DomainError, match="Falha no provedor Gemini"):
        provider.summarize("Ata fictícia")


def test_n8n_webhook_success_and_connection_failure():
    settings = Settings(n8n_enabled=True, n8n_webhook_url="https://n8n.test/webhook")
    success_transport = httpx.MockTransport(lambda _request: httpx.Response(202, json={"ok": True}))
    success = N8NClient(settings, httpx.Client(transport=success_transport)).send({"event": "test"})
    assert success == {"sent": True, "status": "success", "status_code": 202}

    def timeout(_request):
        raise httpx.ReadTimeout("tempo esgotado")

    failed = N8NClient(settings, httpx.Client(transport=httpx.MockTransport(timeout))).send(
        {"event": "test"}
    )
    assert failed["sent"] is False
    assert failed["status"] == "failed"
