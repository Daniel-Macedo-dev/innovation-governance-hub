from datetime import date

from pydantic import BaseModel, Field


class Alert(BaseModel):
    notification_type: str
    severity: str
    entity_type: str
    entity_id: int
    title: str
    message: str
    detected_at: date = Field(default_factory=date.today)
    fingerprint: str
