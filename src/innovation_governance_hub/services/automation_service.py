from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from innovation_governance_hub.automation.fingerprints import fingerprint
from innovation_governance_hub.config import Settings, get_settings
from innovation_governance_hub.domain.clock import business_date
from innovation_governance_hub.domain.enums import AIStatus, InitiativeStatus, RiskLevel
from innovation_governance_hub.domain.schemas import Alert
from innovation_governance_hub.persistence.models import (
    ActionItem,
    AIUseCase,
    AnnualBudget,
    Initiative,
)
from innovation_governance_hub.services.budget_service import BudgetService
from innovation_governance_hub.services.gate_service import GateService
from innovation_governance_hub.services.notification_service import NotificationService


class AutomationService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session, self.settings = session, settings or get_settings()

    def run(self, persist: bool = True) -> list[Alert]:
        alerts: list[Alert] = []
        active = self.session.scalars(
            select(Initiative).where(
                Initiative.status.not_in([InitiativeStatus.COMPLETED, InitiativeStatus.ARCHIVED])
            )
        ).all()
        for item in active:
            if item.deadline and item.deadline < business_date():
                alerts.append(
                    self._alert(
                        "projeto_atrasado",
                        "Alta",
                        "Iniciativa",
                        item.id,
                        f"{item.code} está atrasada",
                        "Prazo da iniciativa expirou.",
                    )
                )
            if item.last_activity_at < datetime.now() - timedelta(
                days=self.settings.stale_project_days
            ):
                alerts.append(
                    self._alert(
                        "projeto_parado",
                        "Atenção",
                        "Iniciativa",
                        item.id,
                        f"{item.code} sem atividade",
                        "Iniciativa atingiu o limite de inatividade.",
                    )
                )
            missing = GateService(self.session).evaluate(item)
            if missing:
                alerts.append(
                    self._alert(
                        "gate_pendente",
                        "Atenção",
                        "Iniciativa",
                        item.id,
                        f"Gate pendente em {item.code}",
                        f"{len(missing)} critérios obrigatórios pendentes.",
                    )
                )
                if "Documento de descoberta anexado" in missing:
                    alerts.append(
                        self._alert(
                            "documentacao_pendente",
                            "Alta",
                            "Iniciativa",
                            item.id,
                            f"Documentação pendente em {item.code}",
                            "O documento obrigatório de descoberta ainda não foi anexado.",
                        )
                    )
            actual = BudgetService(self.session).initiative_actual(item.id)
            if item.planned_cost and actual > item.planned_cost:
                alerts.append(
                    self._alert(
                        "orcamento_excedido",
                        "Crítica",
                        "Iniciativa",
                        item.id,
                        f"{item.code} excedeu o orçamento",
                        "Custo realizado supera o planejado.",
                    )
                )
            elif item.planned_cost and actual / item.planned_cost * 100 >= Decimal(
                self.settings.budget_warning_percent
            ):
                alerts.append(
                    self._alert(
                        "orcamento_proximo",
                        "Alta",
                        "Iniciativa",
                        item.id,
                        f"{item.code} próxima do orçamento",
                        "Consumo atingiu o limite de alerta.",
                    )
                )
        for use_case in self.session.scalars(select(AIUseCase)).all():
            if use_case.next_review_date and use_case.next_review_date < business_date():
                alerts.append(
                    self._alert(
                        "revisao_ia_vencida",
                        "Alta",
                        "CasoIA",
                        use_case.id,
                        f"Revisão vencida: {use_case.code}",
                        "A próxima revisão está vencida.",
                    )
                )
            if use_case.risk_level in (
                RiskLevel.HIGH,
                RiskLevel.CRITICAL,
            ) and use_case.evaluation_status not in (AIStatus.APPROVED, AIStatus.RESTRICTED):
                alerts.append(
                    self._alert(
                        "ia_risco_sem_aprovacao",
                        "Crítica" if use_case.risk_level == RiskLevel.CRITICAL else "Alta",
                        "CasoIA",
                        use_case.id,
                        f"Risco sem aprovação: {use_case.code}",
                        "Caso de alto risco ainda não aprovado.",
                    )
                )
        for action in self.session.scalars(
            select(ActionItem).where(
                ActionItem.deadline < business_date(),
                ActionItem.status.in_(["Aberta", "Em andamento"]),
            )
        ).all():
            alerts.append(
                self._alert(
                    "pendencia_vencida",
                    "Alta",
                    "Pendencia",
                    action.id,
                    "Pendência de reunião vencida",
                    action.description,
                )
            )
        annual_budget = self.session.scalar(
            select(AnnualBudget).where(AnnualBudget.year == business_date().year)
        )
        if annual_budget:
            totals = BudgetService(self.session).totals(annual_budget.year)
            if totals["consumed_percent"] >= Decimal(self.settings.annual_budget_warning_percent):
                alerts.append(
                    self._alert(
                        "orcamento_anual_proximo",
                        "Crítica" if totals["consumed_percent"] >= 100 else "Alta",
                        "OrcamentoAnual",
                        annual_budget.id,
                        f"Orçamento anual em {totals['consumed_percent']:.1f}%",
                        "O consumo anual atingiu o limite configurado.",
                    )
                )
        if persist:
            for alert in alerts:
                data = alert.model_dump(exclude={"detected_at"})
                NotificationService(self.session).register(**data)
        return alerts

    def _alert(
        self, kind: str, severity: str, entity: str, entity_id: int, title: str, message: str
    ) -> Alert:
        return Alert(
            notification_type=kind,
            severity=severity,
            entity_type=entity,
            entity_id=entity_id,
            title=title,
            message=message,
            fingerprint=fingerprint(kind, entity, entity_id),
        )
