import streamlit as st

from innovation_governance_hub.config import get_settings
from innovation_governance_hub.database import init_db


def bootstrap(title: str) -> None:
    st.set_page_config(
        page_title=f"{title} | Innovation Governance Hub", page_icon="💡", layout="wide"
    )
    init_db()
    st.sidebar.info("Ambiente demonstrativo — dados totalmente fictícios")
    st.sidebar.caption(f"Organização fictícia: {get_settings().demo_company_name}")
    st.title(title)
