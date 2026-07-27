# Estudo de caso: Innovation Governance Hub

> Todos os dados, pessoas, organizações e cenários são fictícios.

O projeto explora como uma área de inovação poderia transformar ideias dispersas em decisões rastreáveis. As hipóteses são que responsáveis precisam enxergar critérios de gate, risco, orçamento, resultados e pendências no mesmo fluxo, enquanto um comitê precisa de síntese sem perder explicabilidade.

Os usuários fictícios são responsáveis por iniciativas, governança de IA, controle financeiro e membros de comitê. As jornadas cobrem entrada no funil, avaliação transparente, acompanhamento de indicador, decisão de gate, revisão de IA, reunião e exportação.

A solução local usa Streamlit, serviços de aplicação, SQLAlchemy, SQLite, Excel e integrações opcionais desacopladas. Foram validados tecnicamente regras determinísticas, persistência, importação/exportação, testes automatizados e execução reproduzível. Não houve validação com usuários reais, adoção real ou mensuração de benefício empresarial.

Os principais riscos são confundir demonstração com produto pronto, interpretar score como decisão automática e escalar SQLite para uso concorrente. Em produção seriam necessários descoberta com usuários, segurança, observabilidade, migrações formais e infraestrutura adequada.
