from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Destination:
    page: str
    state_key: str


INITIATIVE = Destination("pages/2_Detalhes_da_Iniciativa.py", "selected_initiative_id")
AI_CASE = Destination("pages/3_Governanca_de_IA.py", "selected_ai_case_id")
COMMITTEE = Destination("pages/0_Comite_de_Inovacao.py", "committee_return")


def go(destination: Destination, entity_id: int | None = None) -> None:
    if entity_id is not None:
        st.session_state[destination.state_key] = entity_id
    st.switch_page(destination.page)


def selected(key: str, valid_ids: list[int], fallback: int | None = None) -> int | None:
    value = st.session_state.get(key, fallback)
    return int(value) if value in valid_ids else fallback
