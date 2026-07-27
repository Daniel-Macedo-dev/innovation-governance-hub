import streamlit as st

from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.navigation import selected


def ai_governance() -> None:
    with app_services(read_only=True) as services:
        items = services.ai_query.list()
    st.dataframe(
        [
            {
                "Código": item["code"],
                "Nome": item["name"],
                "Risco": item["risk_level"],
                "Status": item["evaluation_status"],
                "Dados pessoais": item["uses_personal_data"],
                "Adoção": f"{item['adoption']:.1f}%",
                "Revisão vencida": item["review_overdue"],
            }
            for item in items
        ],
        use_container_width=True,
        hide_index=True,
    )
    if not items:
        st.info("Nenhum caso de IA cadastrado.")
        return
    ids = [int(str(item["id"])) for item in items]
    target = selected("selected_ai_case_id", ids, ids[0])
    options = {f"{item['code']} — {item['name']}": int(str(item["id"])) for item in items}
    labels = list(options)
    label = st.selectbox("Caso de IA", labels, index=ids.index(target) if target in ids else 0)
    item = next(value for value in items if value["id"] == options[label])
    st.subheader("Revisão de governança")
    st.write(
        f"Risco: **{item['risk_level']}** · Responsável: {item['owner']} · Próxima revisão: {item['next_review_date']}"
    )
    st.write(f"Mitigação: {item['risk_mitigation'] or 'Não registrada'}")
    st.caption("A aplicação apoia a revisão; aprovação ou restrição permanece uma decisão humana.")
