"""O uso normal e o cenário de apresentação devem compartilhar a mesma aplicação."""

import inspect
from pathlib import Path

from scripts import prepare_interview_demo, run_interview_demo

ALLOWED_DEMO_ENV_KEYS = {
    "APP_ENV",
    "DATABASE_URL",
    "DEMO_REFERENCE_DATE",
    "INTERVIEW_GUIDE_ENABLED",
    "N8N_ENABLED",
}


def test_demo_runner_starts_full_application():
    source = inspect.getsource(run_interview_demo.main)
    assert '"app.py"' in source
    assert "pages/" not in source


def test_demo_environment_only_uses_allowed_differences():
    assert set(prepare_interview_demo.DEMO_ENV) <= ALLOWED_DEMO_ENV_KEYS
    assert prepare_interview_demo.DEMO_ENV["DATABASE_URL"].endswith("interview_demo.db")


def test_demo_database_is_isolated_from_default():
    assert "interview_demo" in str(prepare_interview_demo.DEMO_DATABASE)
    assert "innovation_governance_hub.db" not in str(prepare_interview_demo.DEMO_DATABASE)


def test_no_feature_branches_on_interview_environment():
    """Nenhuma view ou serviço pode esconder funcionalidade no modo de apresentação."""
    roots = [Path("src/innovation_governance_hub"), Path("pages"), Path("app.py")]
    offenders = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in files:
            text = path.read_text(encoding="utf-8")
            if "app_env" in text and path.name not in {"config.py"}:
                offenders.append(str(path))
    assert not offenders, f"Uso de app_env fora da configuração: {offenders}"
