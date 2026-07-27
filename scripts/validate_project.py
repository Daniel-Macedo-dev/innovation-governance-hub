import json
from pathlib import Path

from sqlalchemy import func, select, text

from innovation_governance_hub.database import SessionLocal, init_db
from innovation_governance_hub.persistence.models import AIUseCase, Initiative
from scripts.generate_excel_templates import main as templates
from scripts.seed_demo import seed
from scripts.validate_excel_roundtrip import main as excel_roundtrip


def main() -> None:
    init_db()
    first = seed()
    second = seed()
    if first != second:
        raise RuntimeError(f"Seed não idempotente: {first} != {second}")
    with SessionLocal() as session:
        session.execute(text("select 1"))
        assert session.scalar(select(func.count()).select_from(Initiative)) == 20
        assert session.scalar(select(func.count()).select_from(AIUseCase)) == 12
    templates()
    excel_roundtrip()
    json.loads(
        Path("n8n/workflows/innovation_governance_automation.json").read_text(encoding="utf-8")
    )
    print({"status": "ok", "seed": second})


if __name__ == "__main__":
    main()
