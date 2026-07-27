from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from innovation_governance_hub.config import get_settings
from innovation_governance_hub.database import SessionLocal, init_db
from innovation_governance_hub.integrations.n8n_client import N8NClient
from innovation_governance_hub.persistence.models import (
    ActionItem,
    AIUseCase,
    Initiative,
    NotificationLog,
)
from innovation_governance_hub.services.automation_service import AutomationService
from innovation_governance_hub.services.budget_service import BudgetService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Innovation Governance Hub — Integrações", version="0.1.0", lifespan=lifespan)


def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def require_token(authorization: str = Header(default="")) -> None:
    if authorization != f"Bearer {get_settings().integration_api_token}":
        raise HTTPException(401, "Token inválido")


class RunRequest(BaseModel):
    dispatch_n8n: bool = False


class Callback(BaseModel):
    fingerprint: str
    delivery_status: str
    external_reference: str = ""
    error_message: str = ""


@app.get("/health")
def health(session: Session = Depends(db_session)) -> dict[str, object]:
    session.execute(text("select 1"))
    return {"status": "ok", "database": "ok"}


@app.post("/api/v1/automations/run", dependencies=[Depends(require_token)])
def run_automations(body: RunRequest, session: Session = Depends(db_session)) -> dict[str, object]:
    alerts = AutomationService(session).run()
    session.commit()
    payload = {
        "event": "innovation_governance_alerts",
        "generated_at": datetime.now().isoformat(),
        "summary": {"total": len(alerts)},
        "alerts": [a.model_dump(mode="json") for a in alerts],
    }
    delivery = (
        N8NClient().send(payload)
        if body.dispatch_n8n
        else {"sent": False, "status": "not_requested"}
    )
    return {**payload, "delivery": delivery}


@app.get("/api/v1/automations/weekly-summary")
def weekly_summary(session: Session = Depends(db_session)) -> dict[str, object]:
    alerts = AutomationService(session).run(persist=False)
    counts = {
        kind: sum(a.notification_type == kind for a in alerts)
        for kind in {a.notification_type for a in alerts}
    }
    totals = BudgetService(session).totals(date.today().year)
    return {
        "projetos_ativos": session.scalar(
            select(func.count())
            .select_from(Initiative)
            .where(Initiative.status.not_in(["Concluída", "Arquivada"]))
        ),
        "casos_ia": session.scalar(select(func.count()).select_from(AIUseCase)),
        "pendencias_vencidas": session.scalar(
            select(func.count())
            .select_from(ActionItem)
            .where(
                ActionItem.deadline < date.today(),
                ActionItem.status.in_(["Aberta", "Em andamento"]),
            )
        ),
        "projetos_atrasados": counts.get("projeto_atrasado", 0),
        "projetos_parados": counts.get("projeto_parado", 0),
        "gates_pendentes": counts.get("gate_pendente", 0),
        "revisoes_ia_vencidas": counts.get("revisao_ia_vencida", 0),
        "alertas_risco": counts.get("ia_risco_sem_aprovacao", 0),
        "situacao_orcamentaria": {
            "planejado": str(totals["planned"]),
            "realizado": str(totals["actual"]),
            "previsto": str(totals["forecast"]),
            "saldo": str(totals["balance"]),
            "percentual_consumido": str(totals["consumed_percent"]),
        },
        "alertas": counts,
    }


@app.post("/api/v1/notifications/callback", dependencies=[Depends(require_token)])
def callback(body: Callback, session: Session = Depends(db_session)) -> dict[str, str]:
    log = session.scalar(
        select(NotificationLog).where(NotificationLog.fingerprint == body.fingerprint)
    )
    if not log:
        raise HTTPException(404, "Notificação não encontrada")
    log.delivery_status, log.external_reference, log.error_message = (
        body.delivery_status,
        body.external_reference,
        body.error_message,
    )
    session.commit()
    return {"status": "updated"}
