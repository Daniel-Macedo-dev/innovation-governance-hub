# Innovation Governance Hub

[![Python quality](https://github.com/Daniel-Macedo-dev/innovation-governance-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/Daniel-Macedo-dev/innovation-governance-hub/actions/workflows/ci.yml)

> Este projeto utiliza exclusivamente dados fictícios e foi desenvolvido para fins educacionais e de portfólio. Não representa processos, políticas, resultados ou informações internas de nenhuma empresa real.

Aplicação local multipage para demonstrar gestão de iniciativas, gates, governança de IA, orçamento, reuniões, documentos, Excel e automações na empresa fictícia **Horizonte Operações Integradas**. O espaço para screenshots e o checklist de captura estão em `docs/screenshots/README.md`; nenhuma imagem inexistente é apresentada como pronta.

## Funcionalidades

- Dashboard executivo com indicadores, gráficos e listas de atenção.
- Funil sequencial com critérios automáticos, manuais e aprovações; tentativas bloqueadas são auditadas.
- Documentos locais, reuniões e linha do tempo imutável de eventos relevantes.
- Casos de IA com histórico decisório, justificativas, restrições e próxima revisão.
- Orçamento em `Decimal`, compromissos, variação e projeção simples até dezembro.
- Importação transacional com fingerprint contra reprocessamento.
- Alertas com reconhecimento, resolução, descarte justificado e reabertura auditada.

## Stack e arquitetura

Python 3.11+, Streamlit, FastAPI, SQLAlchemy 2/SQLite, Pandas, Plotly, openpyxl, Pydantic, HTTPX, Google Gen AI, Pytest, Ruff e Mypy. O fluxo é `UI → serviços → persistência → SQLite`; integrações dependem de adaptadores. Veja [arquitetura](docs/architecture.md).

## Instalação e execução local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m scripts.init_db
python -m scripts.seed_demo
python -m scripts.generate_excel_templates
streamlit run app.py
```

API em outro terminal:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn api:app --host 127.0.0.1 --port 8000
```

Use `Authorization: Bearer change-me-local` nos endpoints de escrita e altere o token em `.env`. Exemplos:

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/api/v1/automations/run -H "Authorization: Bearer change-me-local" -H "Content-Type: application/json" -d '{"dispatch_n8n":false}'
```

## Configuração

Copie `.env.example` para `.env`. Sem chave, `AI_PROVIDER=demo` usa regras locais determinísticas e exibe **Modo demonstração local** — nenhuma chamada de IA é alegada. Para Gemini, defina `AI_PROVIDER=gemini`, `GEMINI_API_KEY` e `GEMINI_MODEL`. Falhas reais não acionam fallback silencioso.

n8n fica desligado por padrão. Use `docker compose --profile automation up -d n8n`, importe o workflow e siga `n8n/README.md`. A aplicação funciona integralmente sem ele.

## Operação e qualidade

```powershell
python -m scripts.run_automation_checks
python -m scripts.validate_excel_roundtrip
python -m scripts.validate_project
ruff check .
ruff format --check .
mypy src
pytest --cov=src/innovation_governance_hub/services --cov=src/innovation_governance_hub/domain --cov-report=term-missing
docker compose config
docker compose up --build app api
```

Na página Excel, baixe modelos gerados por código, escolha iniciativas ou custos, valide a planilha, revise a prévia e confirme a transação. Linhas inválidas impedem toda a persistência e produzem relatório XLSX de erros. O MVP não usa locale global e apresenta moeda/data em pt-BR.

## Métricas, estrutura e limitações

Definições completas estão em `docs/metric-definitions.md`. Código principal em `src/innovation_governance_hub`, páginas em `pages`, comandos em `scripts`, testes em `tests`, documentação em `docs` e workflow em `n8n`.

MVP local individual, sem autenticação/RBAC, migrations Alembic ou armazenamento em nuvem. SQLite/WAL é adequado à demonstração, não a alta concorrência. O seed é idempotente por códigos e descrições estáveis e não destrói alterações existentes. Casos de IA, iniciativas, despesas, documentos, reuniões e pendências possuem operações locais; exclusões destrutivas exigem confirmação na UI. Próximos passos não essenciais: autenticação, migrations e armazenamento externo.

Licença MIT; consulte `LICENSE`.
