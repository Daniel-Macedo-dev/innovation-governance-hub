from datetime import date

from pydantic import BaseModel, Field


class MeetingSummaryResult(BaseModel):
    executive_summary: str
    decisions: list[str] = []
    action_items: list[str] = []
    next_steps: list[str] = []
    mentioned_people: list[str] = []
    mentioned_deadlines: list[str] = []
    provider_name: str
    mode: str


class Alert(BaseModel):
    notification_type: str
    severity: str
    entity_type: str
    entity_id: int
    title: str
    message: str
    detected_at: date = Field(default_factory=date.today)
    fingerprint: str
