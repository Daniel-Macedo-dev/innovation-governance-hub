# Dicionário de dados

`Initiative` contém identidade, problema, solução, área, responsável, prioridade, impacto, complexidade, datas, status/estágio e valores planejados. `GateCriterionDefinition` define critérios; `InitiativeGateCheck` guarda evidência humana; `StageTransition` audita tentativa. `InitiativeDocument` referencia arquivo local sanitizado.

`Meeting`, `MeetingDecision` e `ActionItem` registram ata, decisões e pendências. `AIUseCase` guarda finalidade, ferramenta/provedor, dados, risco, avaliação, revisão e adoção. `AnnualBudget` é único por ano; `Expense` é a fonte de verdade realizada/prevista. `NotificationLog` deduplica alertas por fingerprint e registra entrega. IDs são internos; códigos `INI-xxx` e `IA-xxx` são estáveis.

`AuditEvent` registra ator, ação, resumo e mudanças sanitizadas. `AIGovernanceDecision` mantém decisões sem sobrescrever o passado. `ImportBatch` registra fingerprint, tipo, arquivo original, quantidades criadas/atualizadas e responsável. `NotificationLog.lifecycle_status` usa Novo, Reconhecido, Resolvido ou Ignorado. JSON de auditoria não armazena tokens, senhas, chaves ou conteúdo integral de documentos.
