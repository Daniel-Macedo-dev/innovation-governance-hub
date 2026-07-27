import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.domain.enums import (
    STAGE_ORDER,
    EvaluationType,
    InitiativeStatus,
    Stage,
)
from innovation_governance_hub.exceptions import GateBlockedError, ValidationError
from innovation_governance_hub.persistence.models import (
    ActionItem,
    GateCriterionDefinition,
    Initiative,
    InitiativeDocument,
    InitiativeGateCheck,
    StageTransition,
)


class GateService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _automatic(self, initiative: Initiative, code: str) -> bool:
        values = {
            "IDEA_PROBLEM": bool(initiative.problem_description.strip()),
            "IDEA_AREA": bool(initiative.requesting_area.strip()),
            "IDEA_OWNER": bool(initiative.owner.strip()),
            "IDEA_IMPACT": bool(initiative.expected_impact_level),
            "SCREEN_PRIORITY": bool(initiative.priority),
            "SCREEN_COMPLEXITY": bool(initiative.complexity),
            "SCREEN_COST": initiative.planned_cost > 0,
            "SCREEN_SOLUTION": bool(initiative.proposed_solution.strip()),
            "DISC_DOCUMENT": bool(
                self.session.scalar(
                    select(InitiativeDocument.id).where(
                        InitiativeDocument.initiative_id == initiative.id
                    )
                )
            ),
            "SCALE_ACTIONS": not bool(
                self.session.scalar(
                    select(ActionItem.id).where(
                        ActionItem.initiative_id == initiative.id,
                        ActionItem.status.in_(["Aberta", "Em andamento"]),
                    )
                )
            ),
        }
        return values.get(code, False)

    def evaluate(self, initiative: Initiative) -> list[str]:
        definitions = self.session.scalars(
            select(GateCriterionDefinition)
            .where(
                GateCriterionDefinition.stage == initiative.current_stage,
                GateCriterionDefinition.active.is_(True),
            )
            .order_by(GateCriterionDefinition.display_order)
        ).all()
        checks = {
            c.criterion_definition_id: c
            for c in self.session.scalars(
                select(InitiativeGateCheck).where(
                    InitiativeGateCheck.initiative_id == initiative.id
                )
            ).all()
        }
        missing = []
        for criterion in definitions:
            complete = (
                self._automatic(initiative, criterion.code)
                if criterion.evaluation_type == EvaluationType.AUTOMATIC
                else bool(checks.get(criterion.id) and checks[criterion.id].completed)
            )
            if criterion.mandatory and not complete:
                missing.append(criterion.name)
        return missing

    def set_manual_check(
        self, initiative_id: int, criterion_id: int, completed: bool, evidence: str, actor: str
    ) -> InitiativeGateCheck:
        criterion = self.session.get(GateCriterionDefinition, criterion_id)
        if not criterion or criterion.evaluation_type == EvaluationType.AUTOMATIC:
            raise ValidationError("Critério manual inválido.")
        if completed and not evidence.strip():
            raise ValidationError("Informe a evidência.")
        check = self.session.scalar(
            select(InitiativeGateCheck).where(
                InitiativeGateCheck.initiative_id == initiative_id,
                InitiativeGateCheck.criterion_definition_id == criterion_id,
            )
        )
        if not check:
            check = InitiativeGateCheck(
                initiative_id=initiative_id, criterion_definition_id=criterion_id
            )
            self.session.add(check)
        check.completed, check.evidence = completed, evidence.strip()
        check.completed_by = actor if completed else None
        check.completed_at = datetime.now() if completed else None
        return check

    def advance(self, initiative_id: int, actor: str) -> Initiative:
        initiative = self.session.get(Initiative, initiative_id)
        if not initiative:
            raise ValidationError("Iniciativa não encontrada.")
        current = Stage(initiative.current_stage)
        if current in (Stage.COMPLETED, Stage.ARCHIVED):
            raise ValidationError("Estágio terminal não permite avanço.")
        target = STAGE_ORDER[STAGE_ORDER.index(current) + 1]
        missing = self.evaluate(initiative)
        transition = StageTransition(
            initiative_id=initiative.id,
            from_stage=current,
            to_stage=target,
            successful=not missing,
            reason="Critérios atendidos" if not missing else "Critérios obrigatórios pendentes",
            missing_criteria_snapshot=json.dumps(missing, ensure_ascii=False),
            performed_by=actor,
        )
        self.session.add(transition)
        if missing:
            self.session.flush()
            raise GateBlockedError(missing)
        initiative.current_stage = target
        initiative.last_activity_at = datetime.now()
        if target == Stage.COMPLETED:
            initiative.status = InitiativeStatus.COMPLETED
        return initiative

    def archive(self, initiative_id: int, actor: str, reason: str) -> Initiative:
        if not reason.strip():
            raise ValidationError("Informe o motivo do arquivamento.")
        initiative = self.session.get(Initiative, initiative_id)
        if not initiative or initiative.current_stage in (Stage.COMPLETED, Stage.ARCHIVED):
            raise ValidationError("Iniciativa não pode ser arquivada.")
        self.session.add(
            StageTransition(
                initiative_id=initiative.id,
                from_stage=initiative.current_stage,
                to_stage=Stage.ARCHIVED,
                successful=False,
                reason=f"Arquivamento: {reason}",
                performed_by=actor,
            )
        )
        initiative.current_stage, initiative.status = Stage.ARCHIVED, InitiativeStatus.ARCHIVED
        initiative.last_activity_at = datetime.now()
        return initiative
