import os
from pathlib import Path

DEMO_DATABASE = Path("data/interview_demo.db")
DEMO_ENV = {
    "APP_ENV": "interview",
    "DATABASE_URL": "sqlite:///data/interview_demo.db",
    "N8N_ENABLED": "false",
    "DEMO_REFERENCE_DATE": "2026-07-27",
}


def prepare() -> dict[str, int]:
    for key, value in DEMO_ENV.items():
        os.environ[key] = value
    for suffix in ("", "-shm", "-wal"):
        path = Path(f"{DEMO_DATABASE}{suffix}")
        if path.exists():
            path.unlink()
    from innovation_governance_hub.config import get_settings

    get_settings.cache_clear()
    from scripts.seed_demo import seed

    result = seed()
    from sqlalchemy import select

    from innovation_governance_hub.database import SessionLocal
    from innovation_governance_hub.persistence.models import NotificationLog
    from innovation_governance_hub.services.automation_service import AutomationService
    from innovation_governance_hub.services.notification_service import NotificationService

    with SessionLocal.begin() as session:
        AutomationService(session).run()
        alerts = list(session.scalars(select(NotificationLog).order_by(NotificationLog.id)).all())
        lifecycle = NotificationService(session)
        if alerts:
            lifecycle.acknowledge(alerts[0].id, "Gestora demonstrativa")
        if len(alerts) > 1:
            lifecycle.close(
                alerts[1].id,
                "Gestora demonstrativa",
                "Tratamento fictício validado para a demonstração.",
            )
        if len(alerts) > 2:
            lifecycle.close(
                alerts[2].id,
                "Gestora demonstrativa",
                "Alerta fictício sem impacto no cenário.",
                ignored=True,
            )
    return result


def main() -> None:
    print(
        {
            "database": str(DEMO_DATABASE),
            "reference_date": DEMO_ENV["DEMO_REFERENCE_DATE"],
            "seed": prepare(),
        }
    )


if __name__ == "__main__":
    main()
