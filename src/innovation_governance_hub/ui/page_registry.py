"""Registro explícito das páginas da aplicação.

Os títulos visíveis usam acentuação correta; as URLs preservam os caminhos
históricos sem acento (`Comite_de_Inovacao`, `Governanca_de_IA`, ...), que são
consumidos por `st.switch_page`, pelo launcher da demonstração, pelas capturas
de tela e pela documentação.
"""

from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st
from streamlit.navigation.page import StreamlitPage


def _overview_page() -> None:
    from innovation_governance_hub.ui.views.overview import overview

    st.title("Visão Geral")
    overview()


@dataclass(frozen=True)
class PageSpec:
    source: str | Callable[[], None]
    title: str
    url_path: str | None = None
    default: bool = False


PAGE_SPECS: tuple[PageSpec, ...] = (
    PageSpec(_overview_page, "Visão Geral", default=True),
    PageSpec("pages/0_Comite_de_Inovacao.py", "Comitê de Inovação", "Comite_de_Inovacao"),
    PageSpec("pages/1_Funil_de_Inovacao.py", "Funil de Inovação", "Funil_de_Inovacao"),
    PageSpec(
        "pages/2_Detalhes_da_Iniciativa.py", "Detalhes da Iniciativa", "Detalhes_da_Iniciativa"
    ),
    PageSpec("pages/3_Governanca_de_IA.py", "Governança de IA", "Governanca_de_IA"),
    PageSpec("pages/4_Orcamento_e_Custos.py", "Orçamento e Custos", "Orcamento_e_Custos"),
    PageSpec("pages/5_Reunioes_e_Atas.py", "Reuniões e Atas", "Reunioes_e_Atas"),
    PageSpec(
        "pages/6_Importacao_e_Exportacao.py", "Importação e Exportação", "Importacao_e_Exportacao"
    ),
    PageSpec("pages/7_Automacoes.py", "Automações", "Automacoes"),
    PageSpec("pages/8_Sobre_o_Projeto.py", "Sobre o Projeto", "Sobre_o_Projeto"),
)


def build_pages() -> list[StreamlitPage]:
    return [
        st.Page(spec.source, title=spec.title, url_path=spec.url_path, default=spec.default)
        for spec in PAGE_SPECS
    ]
