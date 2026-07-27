import os
from pathlib import Path

DEMO_DATABASE = Path("data/interview_demo.db")
DEMO_ENV = {
    "APP_ENV": "interview",
    "DATABASE_URL": "sqlite:///data/interview_demo.db",
    "AI_PROVIDER": "demo",
    "N8N_ENABLED": "false",
    "INTERVIEW_GUIDE_ENABLED": "true",
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
    from innovation_governance_hub.database import SessionLocal
    from innovation_governance_hub.services.automation_service import AutomationService

    with SessionLocal.begin() as session:
        AutomationService(session).run()
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
