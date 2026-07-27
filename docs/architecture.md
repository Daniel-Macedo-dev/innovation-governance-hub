# Arquitetura

Streamlit monta formulários e visualizações; serviços concentram regras de iniciativas, gates, IA, orçamento, documentos, reuniões e automações; SQLAlchemy mantém sessões curtas e transações; SQLite usa foreign keys e WAL. A FastAPI é deliberadamente pequena e atende saúde, automações, resumo semanal e callback. Provedores de ata e cliente n8n são adaptadores substituíveis. Excel combina Pandas e openpyxl, valida todas as linhas antes de persistir e executa cada lote em uma transação única.

SQLite e arquivos locais reduzem a barreira para entrevista. A contrapartida é concorrência limitada e ausência de migrations; para o MVP, `create_all` idempotente é documentado. Não há autenticação porque o escopo é local, individual e demonstrativo; o token simples protege apenas escritas de integração. O fluxo de dados está nos diagramas. Nenhuma chamada externa é necessária para operar o produto.
