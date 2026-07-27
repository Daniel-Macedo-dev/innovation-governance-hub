HEALTH_COLORS = {
    "Saudável": "#238636",
    "Atenção": "#9A6700",
    "Crítica": "#CF222E",
    "Concluída": "#238636",
    "Arquivada": "#6E7781",
}
STATUS_ICONS = {
    "Saudável": "●",
    "Atenção": "▲",
    "Crítica": "■",
    "No caminho": "●",
    "Fora do esperado": "■",
    "Sem medição": "○",
}


def status_label(status: str) -> str:
    return f"{STATUS_ICONS.get(status, '●')} {status}"
