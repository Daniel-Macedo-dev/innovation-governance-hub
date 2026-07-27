from decimal import Decimal
from pathlib import Path

import streamlit as st

from innovation_governance_hub.exceptions import DomainError
from innovation_governance_hub.services.import_service import (
    IMPORT_KIND_LABELS,
    UPDATABLE_KINDS,
)
from innovation_governance_hub.ui.context import app_services
from innovation_governance_hub.ui.formatting import brl

TEMPLATE_DIR = Path("templates")
# Rótulos de exibição da prévia; chaves internas nunca aparecem para o usuário.
FIELD_LABELS = {
    "code": "Código",
    "name": "Nome",
    "problem_description": "Descrição do problema",
    "proposed_solution": "Solução proposta",
    "requesting_area": "Área solicitante",
    "owner": "Responsável",
    "priority": "Prioridade",
    "expected_impact_level": "Impacto esperado",
    "expected_impact_description": "Descrição do impacto",
    "complexity": "Complexidade",
    "created_date": "Data de criação",
    "deadline": "Prazo",
    "status": "Status",
    "current_stage": "Estágio atual",
    "planned_cost": "Custo planejado",
    "expected_benefit": "Benefício esperado",
    "notes": "Observações",
    "competence_date": "Data de competência",
    "category": "Categoria",
    "description": "Descrição",
    "supplier": "Fornecedor",
    "tool_name": "Ferramenta",
    "cost_type": "Tipo de custo",
    "financial_status": "Status financeiro",
    "amount": "Valor",
    "responsible_area": "Área responsável",
    "objective": "Objetivo",
    "ai_tool": "Ferramenta avaliada",
    "model_or_provider": "Provedor ou modelo",
    "data_description": "Descrição dos dados",
    "uses_personal_data": "Usa dados pessoais",
    "risk_level": "Nível de risco",
    "risk_mitigation": "Mitigações",
    "expected_impact": "Impacto esperado",
    "evaluation_status": "Status da avaliação",
    "next_review_date": "Próxima revisão",
    "policy_accepted": "Política aceita",
    "governance_approved": "Aprovação da governança",
    "estimated_users": "Usuários estimados",
    "active_users": "Usuários ativos",
    "unit": "Unidade",
    "baseline_value": "Baseline",
    "target_value": "Meta",
    "current_value": "Valor atual",
    "direction": "Direção",
    "measurement_date": "Data de medição",
}
HIDDEN_PREVIEW_FIELDS = {"initiative_id"}
IMPACT_LABELS = {
    "iniciativas_ativas": "Iniciativas ativas",
    "custo_realizado_ano": "Custo realizado no ano",
    "casos_ia": "Casos de IA",
    "ia_risco_sem_aprovacao": "IA de risco sem aprovação",
    "indicadores": "Indicadores cadastrados",
}


def _templates_section() -> None:
    from innovation_governance_hub.excel.templates import ensure_templates

    st.subheader("1. Baixar modelos")
    st.caption(
        "Preencha os modelos com códigos de negócio (ex.: INI-001, IA-001). "
        "Importe iniciativas antes de custos e indicadores que dependem delas."
    )
    columns = st.columns(4)
    for column, (kind, path) in zip(columns, ensure_templates(TEMPLATE_DIR).items(), strict=True):
        column.download_button(
            IMPORT_KIND_LABELS[kind],
            path.read_bytes(),
            file_name=path.name,
            key=f"template_{kind}",
        )


def _format_impact(key: str, value: object) -> str:
    if key == "custo_realizado_ano" and isinstance(value, Decimal | int | float):
        return brl(value)
    return str(value)


def _show_last_result() -> None:
    result = st.session_state.get("last_import_result")
    if not result:
        return
    st.success(
        f"Importação de {IMPORT_KIND_LABELS.get(result['kind'], result['kind'])} confirmada: "
        f"{result['created']} registros criados, {result['updated']} atualizados."
    )
    before, after = result["before"], result["after"]
    changed = {key: (before[key], after[key]) for key in after if before[key] != after[key]}
    if changed:
        st.markdown("**Efeito imediato nos indicadores do produto:**")
        for key, (previous, current) in changed.items():
            st.write(
                f"- {IMPACT_LABELS[key]}: {_format_impact(key, previous)} → "
                f"{_format_impact(key, current)}"
            )
    st.caption(
        "Os dados importados já alimentam o Comitê, a Visão Geral, o Funil, "
        "o Orçamento e a Governança de IA — abra as páginas pelo menu lateral."
    )


def _import_section() -> None:
    st.subheader("2. Importar planilha")
    labels = {label: kind for kind, label in IMPORT_KIND_LABELS.items()}
    chosen_label = st.selectbox("Tipo de importação", list(labels))
    kind = labels[chosen_label]
    allow_updates = False
    if kind in UPDATABLE_KINDS:
        allow_updates = st.checkbox(
            "Permitir atualização de registros existentes",
            help=(
                "Desmarcado, códigos já cadastrados são bloqueados. Marcado, as linhas "
                "correspondentes atualizam o registro existente e ficam identificadas na prévia. "
                "Nada é sobrescrito sem esta escolha explícita e sem a confirmação final."
            ),
        )
    uploaded = st.file_uploader("Arquivo XLSX", type=["xlsx"], key=f"upload_{kind}")
    if uploaded is None:
        st.info("Envie um arquivo para validar e visualizar a prévia antes de confirmar.")
        return
    source = uploaded.getvalue()
    with app_services(read_only=True) as services:
        preview = services.imports.preview(kind, source, allow_updates)
        duplicated = services.imports.already_imported(preview.fingerprint)
    _show_last_result()
    if duplicated:
        st.warning(
            "Este arquivo já foi importado (mesmo conteúdo). "
            "Altere a planilha ou consulte o histórico abaixo."
        )
        return
    if preview.rows:
        st.markdown(
            f"**Prévia:** {len(preview.rows)} linhas — "
            f"{preview.create_count} a criar, {preview.update_count} a atualizar."
        )
        st.dataframe(
            [
                {
                    "Ação": action,
                    **{
                        FIELD_LABELS.get(str(key), str(key)): str(value)
                        for key, value in row.items()
                        if key not in HIDDEN_PREVIEW_FIELDS
                    },
                }
                for action, row in zip(preview.actions, preview.rows, strict=True)
            ][:50],
            use_container_width=True,
            hide_index=True,
        )
    if not preview.valid:
        st.error(f"{len(preview.issues)} erros impedem a importação. Nada foi salvo.")
        st.dataframe(
            [
                {"Linha": issue.row, "Coluna": issue.column, "Erro": issue.message}
                for issue in preview.issues
            ],
            use_container_width=True,
            hide_index=True,
        )
        from innovation_governance_hub.excel.importers import error_report

        st.download_button(
            "Baixar relatório de erros (XLSX)",
            error_report(preview),
            file_name="relatorio_erros_importacao.xlsx",
        )
        return
    actor = st.text_input("Importado por", value="Usuário local")
    if st.button("Confirmar importação", type="primary"):
        try:
            with app_services() as services:
                before = services.imports.impact_snapshot()
                outcome = services.imports.persist(preview, actor, uploaded.name)
                after = services.imports.impact_snapshot()
            st.session_state["last_import_result"] = {
                "kind": outcome.kind,
                "created": outcome.created,
                "updated": outcome.updated,
                "before": before,
                "after": after,
            }
            st.rerun()
        except (DomainError, ValueError) as exc:
            st.error(f"{exc} A transação foi revertida e nenhum dado foi salvo.")


def _history_section() -> None:
    st.subheader("3. Histórico de importações")
    with app_services(read_only=True) as services:
        history = services.imports.history()
    if not history:
        st.info("Nenhuma importação registrada.")
        return
    st.dataframe(
        [
            {
                "Data e hora": item["imported_at"],
                "Tipo": item["kind"],
                "Arquivo": item["original_filename"] or "—",
                "Linhas": item["row_count"],
                "Criados": item["created_count"],
                "Atualizados": item["updated_count"],
                "Responsável": item["imported_by"],
                "Fingerprint": item["fingerprint"],
            }
            for item in history
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Cada arquivo possui fingerprint SHA-256: o mesmo conteúdo não é reprocessado, "
        "e chaves de negócio bloqueiam duplicidades mesmo em arquivos diferentes."
    )


def _export_section() -> None:
    st.subheader("4. Exportações executivas")
    with app_services(read_only=True) as services:
        report = services.export.committee()
    st.download_button(
        "Exportar pacote do Comitê (Excel)",
        report,
        file_name="relatorio_comite_inovacao.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def excel_io() -> None:
    st.caption(
        "Importação transacional: todas as linhas são validadas antes de persistir; "
        "qualquer erro reverte a operação inteira. Modelos e relatórios usam dados fictícios."
    )
    _templates_section()
    _import_section()
    _history_section()
    _export_section()
