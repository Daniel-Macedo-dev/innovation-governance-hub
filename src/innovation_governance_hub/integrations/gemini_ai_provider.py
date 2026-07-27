import json
from typing import Any

from google import genai
from google.genai import types

from innovation_governance_hub.domain.schemas import MeetingSummaryResult
from innovation_governance_hub.exceptions import DomainError


class GeminiAIProvider:
    def __init__(
        self, api_key: str, model: str, timeout_seconds: int = 30, client: Any | None = None
    ) -> None:
        self.client = client or genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000)
        )
        self.model = model

    def summarize(self, minutes_text: str) -> MeetingSummaryResult:
        prompt = (
            "Extraia da ata um JSON com executive_summary, decisions, action_items, next_steps, mentioned_people e mentioned_deadlines. Não invente fatos. Ata:\n"
            + minutes_text
        )
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=prompt, config={"response_mime_type": "application/json"}
            )
            if not isinstance(response.text, str):
                raise ValueError("Resposta Gemini sem texto JSON.")
            data = json.loads(response.text)
            return MeetingSummaryResult(**data, provider_name="Google Gemini", mode="Modo real")
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise DomainError("Falha no provedor Gemini; o resultado não foi salvo.") from exc
