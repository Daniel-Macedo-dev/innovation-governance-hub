# Capturas automatizadas da aplicação

Os onze arquivos PNG desta pasta são capturas reais do Streamlit em execução, produzidas por um navegador headless em viewport 1440 × 1000. Todos os nomes, organizações, valores e acontecimentos exibidos são fictícios.

| Arquivo | Evidência apresentada |
| --- | --- |
| `00-comite-inovacao.png` | Comitê com decisões requeridas, saúde do portfólio e síntese executiva. |
| `01-dashboard-executivo.png` | Indicadores do portfólio, projetos ativos e dentro do prazo por área e distribuição por estágio. |
| `02-funil-inovacao.png` | Iniciativas, estágio, status, prazo e posição financeira. |
| `03-gate-bloqueado.png` | Tentativa real de avanço impedida por critérios pendentes. |
| `04-timeline-iniciativa.png` | Eventos de iniciativa, reunião, despesa e bloqueio de gate. |
| `05-governanca-ia.png` | Casos de IA, risco, status, adoção e revisão. |
| `06-orcamento-projecao.png` | Planejado, realizado, comprometido, saldo e projeção simples. |
| `07-resumo-reuniao.png` | Reunião fictícia com ata e resumo executivo manual. |
| `08-importacao-excel.png` | Upload real de XLSX, validação linha a linha e prévia sem persistência. |
| `09-automacoes-alertas.png` | Verificações internas, severidades e ciclo de vida dos alertas. |
| `10-priorizacao-indicadores.png` | Matriz Valor × Esforço e indicadores de resultado do portfólio. |

## Reproduzir

No diretório raiz do projeto:

```powershell
python -m pip install -e ".[dev,screenshots]"
python -m scripts.capture_screenshots
```

O script usa a porta dedicada `8511` e o banco temporário `data/screenshots_demo.db`. Ele inicializa e popula esse banco, gera os modelos Excel, executa as verificações locais, abre a interface e substitui somente os onze PNGs esperados. Navegador, Streamlit, banco, WAL, XLSX de upload e log temporário são encerrados ou removidos no bloco de cleanup, inclusive quando há erro.

A seleção de navegador tenta, nesta ordem:

1. Microsoft Edge instalado (`msedge`).
2. Google Chrome instalado (`chrome`).
3. Chromium gerenciado pelo Playwright.

Para usar o fallback gerenciado quando Edge e Chrome não estiverem disponíveis, instale somente o Chromium:

```powershell
python -m playwright install chromium
python -m scripts.capture_screenshots
```

Para trocar a prioridade de channel, ajuste `browser_candidates()` em `scripts/capture_screenshots.py`. O módulo faz importação tardia do Playwright; a suíte normal e o GitHub Actions continuam funcionando apenas com `.[dev]`, sem download de browser.
