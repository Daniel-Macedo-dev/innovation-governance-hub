from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import Initiative, InitiativeAssessment
from innovation_governance_hub.services.audit_service import AuditService


@dataclass(frozen=True)
class PriorityAssessmentResult:
    initiative_id: int
    value: float
    effort: float
    execution_ease: float
    score: float
    quadrant: str


class PrioritizationService:
    VALUE_WEIGHTS = {
        "strategic_alignment": 0.30,
        "expected_value": 0.30,
        "urgency": 0.20,
        "confidence": 0.20,
    }
    EFFORT_WEIGHTS = {"complexity": 0.60, "execution_risk": 0.40}

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def calculate(assessment: InitiativeAssessment) -> PriorityAssessmentResult:
        values = [
            assessment.strategic_alignment,
            assessment.expected_value,
            assessment.urgency,
            assessment.confidence,
            assessment.complexity,
            assessment.execution_risk,
        ]
        if any(value < 1 or value > 5 for value in values):
            raise ValidationError("Os critérios de priorização devem estar entre 1 e 5.")
        value = sum(
            getattr(assessment, key) * weight
            for key, weight in PrioritizationService.VALUE_WEIGHTS.items()
        )
        effort = sum(
            getattr(assessment, key) * weight
            for key, weight in PrioritizationService.EFFORT_WEIGHTS.items()
        )
        normalized_value = (value - 1) / 4
        ease = 1 - (effort - 1) / 4
        score = round((normalized_value * 0.70 + ease * 0.30) * 100, 1)
        quadrant = (
            "Priorizar"
            if value >= 3 and effort < 3
            else "Planejar"
            if value >= 3
            else "Avaliar"
            if effort < 3
            else "Reconsiderar"
        )
        return PriorityAssessmentResult(
            assessment.initiative_id,
            round(value, 2),
            round(effort, 2),
            round(ease * 5, 2),
            score,
            quadrant,
        )

    def save(
        self, initiative_id: int, data: dict[str, object], actor: str
    ) -> PriorityAssessmentResult:
        if not self.session.get(Initiative, initiative_id):
            raise ValidationError("Iniciativa não encontrada.")
        assessment = self.session.scalar(
            select(InitiativeAssessment).where(InitiativeAssessment.initiative_id == initiative_id)
        )
        created = assessment is None
        if assessment is None:
            assessment = InitiativeAssessment(initiative_id=initiative_id)
        for field in (*self.VALUE_WEIGHTS, *self.EFFORT_WEIGHTS):
            setattr(assessment, field, int(str(data[field])))
        assessment.rationale = str(data.get("rationale", "")).strip()
        assessment.assessed_by = actor.strip() or "Sistema"
        assessment.assessed_at = datetime.now()
        self.session.add(assessment)
        self.session.flush()
        result = self.calculate(assessment)
        AuditService(self.session).record(
            event_type="assessment.created" if created else "assessment.updated",
            entity_type="Iniciativa",
            entity_id=initiative_id,
            action="avaliação de prioridade",
            actor=actor,
            summary=f"Avaliação de prioridade registrada: {result.score} pontos.",
            metadata={"score": result.score, "quadrant": result.quadrant},
        )
        return result

    def list_ranked(self) -> list[PriorityAssessmentResult]:
        results = [
            self.calculate(item)
            for item in self.session.scalars(select(InitiativeAssessment)).all()
        ]
        return sorted(results, key=lambda item: item.score, reverse=True)
