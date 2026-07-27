"""Limites do produto: sem IA generativa integrada e n8n fora do fluxo principal."""

from pathlib import Path

from innovation_governance_hub.config import Settings

SOURCE_ROOTS = [Path("src"), Path("scripts"), Path("pages"), Path("app.py"), Path("api.py")]
FORBIDDEN_GENERATIVE_TERMS = ("google.genai", "google-genai", "gemini", "generativeai")


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        if root.is_file():
            files.append(root)
        else:
            files.extend(sorted(root.rglob("*.py")))
    return files


def test_no_generative_ai_integration_remains():
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN_GENERATIVE_TERMS:
            if term in text:
                offenders.append(f"{path}: {term}")
    assert not offenders, offenders
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8").lower()
    assert "genai" not in pyproject
    env_example = Path(".env.example").read_text(encoding="utf-8").upper()
    assert "GEMINI" not in env_example
    assert "AI_PROVIDER" not in env_example


def test_settings_have_no_generative_ai_fields():
    fields = set(Settings.model_fields)
    assert not {"ai_provider", "gemini_api_key", "gemini_model"} & fields


def test_n8n_stays_out_of_ui_and_pages():
    allowed = {
        Path("src/innovation_governance_hub/integrations/n8n_client.py"),
        Path("src/innovation_governance_hub/config.py"),
        Path("api.py"),
        Path("scripts/prepare_interview_demo.py"),
        Path("scripts/capture_screenshots.py"),
        # Valida apenas que o JSON de referência futura continua bem-formado.
        Path("scripts/validate_project.py"),
    }
    offenders = [
        str(path)
        for path in _python_files()
        if "n8n" in path.read_text(encoding="utf-8").lower() and path not in allowed
    ]
    assert not offenders, f"n8n citado fora dos adaptadores opcionais: {offenders}"


def test_application_defaults_do_not_require_n8n():
    settings = Settings(_env_file=None)
    assert settings.n8n_enabled is False
    assert settings.n8n_webhook_url == ""


def test_readme_does_not_promise_generative_ai():
    readme = Path("README.md").read_text(encoding="utf-8").lower()
    assert "gemini" not in readme
    assert "google gen ai" not in readme
    assert "google-genai" not in readme
