# Definições das métricas

- **Projeto ativo:** não está Concluída nem Arquivada.
- **Atrasado:** ativo e prazo anterior à data atual.
- **Parado:** ativo sem atividade por pelo menos `STALE_PROJECT_DAYS` (14 por padrão).
- **Taxa de avanço:** avanços bem-sucedidos / tentativas de avanço × 100; arquivamentos excluídos e ausência retorna zero.
- **Tempo médio em estágio:** intervalo entre entrada e saída; estágio aberto vai até hoje.
- **Custo realizado:** soma de despesas `Realizado`.
- **Gasto futuro:** soma de despesas `Previsto` do período.
- **Saldo anual:** orçamento anual menos realizado.
- **Percentual consumido:** realizado / orçamento × 100; orçamento zero retorna zero.
- **Acima do orçamento:** realizado da iniciativa maior que planejado.
- **Adoção de IA:** ativos / estimados × 100, limitada entre 0 e 100; estimativa zero retorna zero.
- **Comprometido:** realizado acumulado mais despesas previstas cadastradas.
- **Saldo após compromissos:** planejado menos comprometido.
- **Variação:** planejado menos realizado; percentual usa o planejado e retorna zero quando ele é zero.
- **Média recente:** média dos três últimos meses decorridos, incluindo meses sem gasto.
- **Projeção até dezembro:** realizado + previsto + média recente nos meses futuros. É demonstrativa, não estatística.
