# Decisões técnicas

- **Streamlit:** acelera uma experiência analítica local; uma implantação multiusuário exigiria avaliar outra camada web.
- **SQLite:** torna a demonstração portátil e isolada; não é a escolha final para alta concorrência.
- **Serviços:** concentram regras e transações fora das novas views, permitindo testes sem interface.
- **Sem autenticação:** decisão consciente de escopo local; produção exigiria identidade, autorização e trilhas protegidas.
- **Sem IA generativa:** atas e resumos executivos são manuais; a governança de IA é uma área de negócio que controla casos de uso de IA da organização, sempre com decisão humana.
- **n8n como integração futura:** verificações e alertas são internos; o encaminhamento externo é apenas uma prova de conceito isolada e opcional.
- **Excel:** arquivos sem macros, com valores calculados em Python e validação por reabertura.
- **Escala real:** banco servidor, migrações formais, filas, observabilidade, segurança e pesquisa com usuários.
