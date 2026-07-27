from typing import Protocol

from innovation_governance_hub.domain.schemas import MeetingSummaryResult


class MeetingSummaryProvider(Protocol):
    def summarize(self, minutes_text: str) -> MeetingSummaryResult: ...
