from innovation_governance_hub.domain.enums import EvaluationType, Stage

GATE_DEFINITIONS = {
    Stage.IDEA: [
        ("IDEA_PROBLEM", "Problema definido", EvaluationType.AUTOMATIC),
        ("IDEA_AREA", "Área solicitante preenchida", EvaluationType.AUTOMATIC),
        ("IDEA_OWNER", "Responsável informado", EvaluationType.AUTOMATIC),
        ("IDEA_IMPACT", "Impacto preliminar estimado", EvaluationType.AUTOMATIC),
    ],
    Stage.SCREENING: [
        ("SCREEN_PRIORITY", "Prioridade definida", EvaluationType.AUTOMATIC),
        ("SCREEN_COMPLEXITY", "Complexidade preliminar avaliada", EvaluationType.AUTOMATIC),
        ("SCREEN_COST", "Custo preliminar estimado", EvaluationType.AUTOMATIC),
        ("SCREEN_SOLUTION", "Solução proposta registrada", EvaluationType.AUTOMATIC),
    ],
    Stage.DISCOVERY: [
        ("DISC_RISK", "Riscos avaliados", EvaluationType.MANUAL),
        ("DISC_HYPOTHESIS", "Hipótese ou resultado esperado documentado", EvaluationType.MANUAL),
        ("DISC_DOCUMENT", "Documento de descoberta anexado", EvaluationType.AUTOMATIC),
        ("DISC_OWNER", "Responsável pela validação confirmado", EvaluationType.MANUAL),
    ],
    Stage.VALIDATION: [
        ("VAL_EVIDENCE", "Evidência de validação registrada", EvaluationType.MANUAL),
        ("VAL_PILOT", "Plano de piloto definido", EvaluationType.MANUAL),
        ("VAL_BUDGET", "Orçamento do piloto avaliado", EvaluationType.MANUAL),
        ("VAL_APPROVAL", "Aprovação do gate registrada", EvaluationType.APPROVAL),
    ],
    Stage.PILOT: [
        ("PILOT_RESULT", "Resultado do piloto registrado", EvaluationType.MANUAL),
        ("PILOT_KPI", "Indicadores do piloto registrados", EvaluationType.MANUAL),
        ("PILOT_RISK", "Riscos revisados", EvaluationType.MANUAL),
        ("PILOT_APPROVAL", "Aprovação do gate registrada", EvaluationType.APPROVAL),
    ],
    Stage.SCALE: [
        ("SCALE_RESULT", "Resultado final documentado", EvaluationType.MANUAL),
        ("SCALE_BENEFIT", "Benefício revisado", EvaluationType.MANUAL),
        ("SCALE_ACTIONS", "Pendências críticas encerradas", EvaluationType.AUTOMATIC),
        ("SCALE_APPROVAL", "Aprovação final registrada", EvaluationType.APPROVAL),
    ],
}
