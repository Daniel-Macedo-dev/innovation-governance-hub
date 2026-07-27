from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from innovation_governance_hub.database import SessionLocal
from innovation_governance_hub.services.ai_governance_service import AIUseCaseService
from innovation_governance_hub.services.automation_service import AutomationService
from innovation_governance_hub.services.budget_service import BudgetService
from innovation_governance_hub.services.executive_committee_service import ExecutiveCommitteeService
from innovation_governance_hub.services.gate_service import GateService
from innovation_governance_hub.services.indicator_service import IndicatorService
from innovation_governance_hub.services.initiative_service import InitiativeService
from innovation_governance_hub.services.meeting_service import MeetingService
from innovation_governance_hub.services.notification_service import NotificationService
from innovation_governance_hub.services.prioritization_service import PrioritizationService


@dataclass
class AppServices:
    initiatives: InitiativeService
    gates: GateService
    ai_governance: AIUseCaseService
    budget: BudgetService
    meetings: MeetingService
    automations: AutomationService
    notifications: NotificationService
    executive: ExecutiveCommitteeService
    prioritization: PrioritizationService
    indicators: IndicatorService


@contextmanager
def app_services() -> Iterator[AppServices]:
    session = SessionLocal()
    try:
        yield AppServices(
            InitiativeService(session),
            GateService(session),
            AIUseCaseService(session),
            BudgetService(session),
            MeetingService(session),
            AutomationService(session),
            NotificationService(session),
            ExecutiveCommitteeService(session),
            PrioritizationService(session),
            IndicatorService(session),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
