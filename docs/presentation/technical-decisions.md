# Decisões técnicas

- **Streamlit:** acelera uma experiência analítica local; uma implantação multiusuário exigiria avaliar outra camada web.
- **SQLite:** torna a demonstração portátil e isolada; não é a escolha final para alta concorrência.
- **Serviços:** concentram regras e transações fora das novas views, permitindo testes sem interface.
- **Sem autenticação:** decisão consciente de escopo local; produção exigiria identidade, autorização e trilhas protegidas.
- **IA local:** o modo demonstrativo funciona sem credenciais e nunca aprova decisões humanas.
- **n8n desacoplado:** verificações são locais e o envio externo é opcional e explícito.
- **Excel:** arquivos sem macros, com valores calculados em Python e validação por reabertura.
- **Escala real:** banco servidor, migrações formais, filas, observabilidade, segurança e pesquisa com usuários.
