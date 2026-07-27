# n8n — prova de conceito de integração futura

O n8n **não faz parte do fluxo principal do produto**. A aplicação calcula, persiste e administra todos os alertas internamente; nenhuma página, dashboard ou importação depende de automação externa. Este diretório guarda apenas uma prova de conceito de como os alertas poderiam ser encaminhados para fora (por exemplo, e-mail corporativo) em uma evolução futura.

## Como experimentar (opcional)

Inicie com `docker compose --profile automation up -d n8n`, abra `http://localhost:5678` e importe `workflows/innovation_governance_automation.json`. Configure `HUB_API_URL` para a API (em Compose, `http://api:8000`) e o token como credencial/header Bearer nos nós de escrita. Copie a URL de produção do webhook para `N8N_WEBHOOK_URL` e defina `N8N_ENABLED=true`. O envio só ocorre quando solicitado explicitamente pela API (`dispatch_n8n=true`); a interface nunca chama o webhook.

O nó final é deliberadamente `No Op` — o workflow é referência, não uma entrega operacional de envio de e-mail. Substitua-o por um nó real somente depois de cadastrar credenciais no n8n. Para callback, adicione um HTTP Request para `/api/v1/notifications/callback` com o fingerprint e o token. Em Docker, `localhost` dentro de um contêiner não aponta para o host; use nomes de serviço ou `host.docker.internal`. Não há credenciais hardcoded.

O Hub mantém ciclo de vida e auditoria completos com o n8n desligado. Falhas de webhook permanecem visíveis e podem ser reprocessadas; o workflow não deve receber chaves ou conteúdo integral de documentos.
