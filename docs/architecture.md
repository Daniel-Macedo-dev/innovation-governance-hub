# Arquitetura

```text
UI (Streamlit) ─┐
                ├─► Serviços de aplicação ─► SQLAlchemy ─► SQLite (WAL)
API (FastAPI) ──┘        │
                         ├─► Excel (importação e exportação)
                         └─► Auditoria (AuditEvent, append-only)
```

Streamlit monta formulários e visualizações; serviços concentram as regras de iniciativas, gates, priorização, indicadores, orçamento, governança de casos de IA, documentos, reuniões, alertas e importação; SQLAlchemy mantém sessões curtas e transações; SQLite usa foreign keys e WAL. A FastAPI é deliberadamente pequena — saúde, execução de verificações, resumo semanal e callback — e usa exatamente os mesmos serviços da interface.

**Cadastro manual e Excel seguem as mesmas regras.** A importação (`ImportService` + `excel/importers.py`) valida todas as linhas antes de persistir e reutiliza `InitiativeService`, `AIUseCaseService` e `IndicatorService` na persistência, herdando validações, auditoria e histórico decisório. Cada lote executa em transação única: qualquer erro reverte tudo. `ImportBatch` guarda fingerprint SHA-256, arquivo, contagens e responsável; as chaves de negócio (códigos) bloqueiam duplicidades mesmo entre arquivos diferentes, e atualizações exigem opção explícita do usuário.

**KPIs têm origem única.** O Comitê, a Visão Geral, o Orçamento e a Governança de IA leem os mesmos serviços de consulta (`ui_query_services`, `ExecutiveCommitteeService`, `BudgetService`); nada é calculado na camada visual. A data de negócio (`business_date()`) pode ser fixada por `DEMO_REFERENCE_DATE` para cenários reproduzíveis — os carimbos de auditoria continuam no relógio real.

**Não há IA generativa no produto.** Atas e resumos executivos de reunião são manuais. A governança de IA é uma área de negócio: cadastra e avalia casos de uso de IA da organização, com decisões humanas auditadas em `AIGovernanceDecision`.

**Integrações externas são futuras e opcionais.** O cliente n8n é um adaptador isolado, desligado por padrão, acionável apenas via API por opção explícita; nenhuma página depende dele. Veja `n8n/README.md`.

SQLite e arquivos locais reduzem a barreira de execução. A contrapartida é concorrência limitada e ausência de migrations formais; o `init_db` aplica `create_all` idempotente e adições de coluna compatíveis (bancos antigos podem conter colunas legadas sem uso, como os antigos campos de provedor de resumo em `meetings` — elas são ignoradas e não representam funcionalidade ativa). Não há autenticação porque o escopo é local e individual; o token simples protege apenas escritas da API.
