"""Navegação explícita: títulos, rotas, destinos internos e ausência do guia."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from innovation_governance_hub.ui import navigation
from innovation_governance_hub.ui.page_registry import PAGE_SPECS

EXPECTED_TITLES = [
    "Visão Geral",
    "Comitê de Inovação",
    "Funil de Inovação",
    "Detalhes da Iniciativa",
    "Governança de IA",
    "Orçamento e Custos",
    "Reuniões e Atas",
    "Importação e Exportação",
    "Automações",
    "Sobre o Projeto",
]


def test_titles_are_exact_and_ordered():
    assert [spec.title for spec in PAGE_SPECS] == EXPECTED_TITLES


def test_no_app_label_single_default_and_unique_urls():
    titles = {spec.title.lower() for spec in PAGE_SPECS}
    assert "app" not in titles
    defaults = [spec for spec in PAGE_SPECS if spec.default]
    assert len(defaults) == 1
    assert defaults[0].title == "Visão Geral"
    urls = [spec.url_path for spec in PAGE_SPECS if spec.url_path]
    assert len(urls) == len(set(urls))
    assert {"Comite_de_Inovacao", "Governanca_de_IA", "Importacao_e_Exportacao"} <= set(urls)


def test_sources_are_valid():
    for spec in PAGE_SPECS:
        if isinstance(spec.source, str):
            assert Path(spec.source).is_file(), spec.source
        else:
            assert callable(spec.source)


def test_internal_navigation_targets_are_registered_pages():
    registered = {spec.source for spec in PAGE_SPECS if isinstance(spec.source, str)}
    for destination in (navigation.INITIATIVE, navigation.AI_CASE, navigation.COMMITTEE):
        assert destination.page in registered, destination.page


def test_interview_guide_is_gone_from_runtime_and_public_docs():
    roots = [
        Path("app.py"),
        Path("api.py"),
        Path(".env.example"),
        Path("README.md"),
        Path("src"),
        Path("pages"),
        Path("scripts"),
        Path("docs"),
    ]
    forbidden = ("INTERVIEW_GUIDE_ENABLED", "interview_guide_enabled", "Guia de apresentação")
    offenders = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in files:
            if path.suffix not in {".py", ".md", ".example", ".toml", ".yml"} and path.name != (
                ".env.example"
            ):
                continue
            text = path.read_text(encoding="utf-8")
            for term in forbidden:
                if term in text:
                    offenders.append(f"{path}: {term}")
    assert not offenders, offenders


def test_app_entrypoint_runs_navigation_with_default_overview():
    at = AppTest.from_file("app.py", default_timeout=15).run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Visão Geral"
    infos = at.sidebar.info
    assert len(infos) == 1
    assert "fictícios" in infos[0].value
