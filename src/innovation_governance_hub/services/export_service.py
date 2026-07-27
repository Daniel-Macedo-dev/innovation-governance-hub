from sqlalchemy.orm import Session

from innovation_governance_hub.excel.exporters import committee_workbook
from innovation_governance_hub.services.executive_committee_service import ExecutiveCommitteeService
from innovation_governance_hub.services.ui_query_services import PrioritizationQueryService


class ExportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def committee(self, change_days: int = 15) -> bytes:
        brief = ExecutiveCommitteeService(self.session).brief(change_days)
        health = {item.initiative_id: item.status for item in brief.health}
        priorities = PrioritizationQueryService(self.session).portfolio(health)
        return committee_workbook(self.session, brief, priorities)
