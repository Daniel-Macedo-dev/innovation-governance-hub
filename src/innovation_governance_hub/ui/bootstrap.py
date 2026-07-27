import streamlit as st

from innovation_governance_hub.config import get_settings
from innovation_governance_hub.database import init_db


def bootstrap(title: str) -> None:
    st.set_page_config(
        page_title=f"{title} | Innovation Governance Hub", page_icon="💡", layout="wide"
    )
    init_db()
    settings = get_settings()
    st.sidebar.info("Ambiente demonstrativo — dados totalmente fictícios")
    st.sidebar.caption(f"Organização fictícia: {settings.demo_company_name}")
    if settings.interview_guide_enabled:
        with st.sidebar.expander("Guia de apresentação (local)"):
            st.markdown(
                "1. **Comitê de Inovação** — decisões requeridas e saúde do portfólio.\n"
                "2. **Funil** — estágios, gates e cadastro de iniciativas.\n"
                "3. **Detalhes** — priorização, indicadores e linha do tempo.\n"
                "4. **Orçamento** — realizado, compromissos e projeção.\n"
                "5. **Governança de IA** — riscos, adoção e aprovações.\n"
                "6. **Excel** — importação validada e exportação executiva.\n\n"
                "O guia é apenas visual: nenhuma regra ou dado muda com ele."
            )
    st.title(title)
