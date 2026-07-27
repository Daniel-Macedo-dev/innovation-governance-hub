from pathlib import Path

import streamlit as st

from innovation_governance_hub.config import get_settings
from innovation_governance_hub.database import init_db

BRAND_LOGO = Path("assets/brand/innovation-governance-hub.svg")


def run_app() -> None:
    """Configura a aplicação e executa a navegação explícita.

    Único ponto com `st.set_page_config`, logo e avisos globais da sidebar;
    cada página cuida apenas do próprio título e conteúdo.
    """
    from innovation_governance_hub.ui.page_registry import build_pages

    st.set_page_config(page_title="Innovation Governance Hub", page_icon="💡", layout="wide")
    init_db()
    if BRAND_LOGO.exists():
        st.logo(str(BRAND_LOGO), size="large")
    navigation = st.navigation(build_pages())
    st.sidebar.info("Ambiente demonstrativo — dados totalmente fictícios")
    st.sidebar.caption(f"Organização fictícia: {get_settings().demo_company_name}")
    navigation.run()


def page_header(title: str) -> None:
    """Cabeçalho comum das páginas; `init_db` é idempotente e barato."""
    init_db()
    st.title(title)
