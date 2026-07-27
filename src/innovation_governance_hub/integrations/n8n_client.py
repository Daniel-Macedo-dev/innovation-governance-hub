import httpx

from innovation_governance_hub.config import Settings, get_settings


class N8NClient:
    def __init__(
        self, settings: Settings | None = None, client: httpx.Client | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or httpx.Client()

    def send(self, payload: dict[str, object]) -> dict[str, object]:
        if not self.settings.n8n_enabled:
            return {"sent": False, "status": "disabled"}
        if not self.settings.n8n_webhook_url:
            return {"sent": False, "status": "misconfigured"}
        try:
            response = self.client.post(
                self.settings.n8n_webhook_url,
                json=payload,
                timeout=self.settings.n8n_request_timeout_seconds,
            )
            response.raise_for_status()
            return {"sent": True, "status": "success", "status_code": response.status_code}
        except httpx.HTTPError as exc:
            return {"sent": False, "status": "failed", "error": str(exc)}
