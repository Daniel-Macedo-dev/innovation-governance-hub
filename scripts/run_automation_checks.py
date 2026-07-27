from innovation_governance_hub.database import SessionLocal, init_db
from innovation_governance_hub.services.automation_service import AutomationService


def main() -> None:
    init_db()
    with SessionLocal.begin() as session:
        alerts = AutomationService(session).run()
        for alert in alerts:
            print(f"[{alert.severity}] {alert.title}")
        print(f"Total: {len(alerts)}")


if __name__ == "__main__":
    main()
