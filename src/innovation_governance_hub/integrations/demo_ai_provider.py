import re

from innovation_governance_hub.domain.schemas import MeetingSummaryResult


class DemoAIProvider:
    def summarize(self, minutes_text: str) -> MeetingSummaryResult:
        sentences = [s.strip(" -•\t") for s in re.split(r"[\n.!?]+", minutes_text) if s.strip()]
        decisions = [
            s for s in sentences if any(k in s.lower() for k in ("decid", "aprov", "defin"))
        ]
        actions = [
            s
            for s in sentences
            if any(k in s.lower() for k in ("pend", "deve", "responsável", "ação"))
        ]
        dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", minutes_text)
        return MeetingSummaryResult(
            executive_summary=". ".join(sentences[:3]) or "Ata sem conteúdo suficiente.",
            decisions=decisions[:5],
            action_items=actions[:5],
            next_steps=actions[:5],
            mentioned_deadlines=dates,
            provider_name="Regras locais determinísticas",
            mode="Modo demonstração local",
        )
