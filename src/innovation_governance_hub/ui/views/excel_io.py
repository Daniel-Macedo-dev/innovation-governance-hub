from pathlib import Path

import streamlit as st

from innovation_governance_hub.ui.context import app_services


def excel_io() -> None:
    st.write("Modelos e relatórios utilizam exclusivamente dados fictícios.")
    for filename in ("modelo_iniciativas.xlsx", "modelo_custos.xlsx"):
        path = Path("templates") / filename
        if path.exists():
            st.download_button(f"Baixar {filename}", path.read_bytes(), file_name=filename)
    with app_services(read_only=True) as services:
        report = services.export.committee()
    st.download_button(
        "Exportar pacote do Comitê",
        report,
        file_name="relatorio_comite_inovacao.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.info(
        "A importação transacional permanece disponível pela API de importação e pelos serviços validados do projeto."
    )
