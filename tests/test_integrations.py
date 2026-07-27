import httpx

from innovation_governance_hub.config import Settings
from innovation_governance_hub.integrations.n8n_client import N8NClient


def test_n8n_disabled_by_default_never_sends():
    settings = Settings(n8n_enabled=False)
    assert N8NClient(settings).send({})["status"] == "disabled"


def test_n8n_enabled_without_url_is_misconfigured():
    settings = Settings(n8n_enabled=True, n8n_webhook_url="")
    assert N8NClient(settings).send({})["status"] == "misconfigured"


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
