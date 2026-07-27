# n8n opcional

Inicie com `docker compose --profile automation up -d n8n`, abra `http://localhost:5678` e importe `workflows/innovation_governance_automation.json`. Configure `HUB_API_URL` para a API (em Compose, `http://api:8000`) e o token como credencial/header Bearer nos nós de escrita. Copie a URL de produção do webhook para `N8N_WEBHOOK_URL` e defina `N8N_ENABLED=true`.

O nó final é deliberadamente `No Op`: substitua-o por e-mail somente depois de cadastrar credenciais reais no n8n. Para callback, adicione um HTTP Request para `/api/v1/notifications/callback` com o fingerprint e o token. Em Docker, `localhost` dentro de um contêiner não aponta para o host; use nomes de serviço ou `host.docker.internal`. Não há credenciais hardcoded.

