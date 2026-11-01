# HER2 Weekly Snapshot Helper

> Acompanhar este script (executado semanalmente) para gerar o PDF
> executivo de inteligência competitiva HER2+ a partir do último snapshot
> em `her2_breast_cancer_trials.db`.

## Como rodar
```bash
cd <raiz do projeto>
uv run scripts/monthly_update.py   # fluxo atual (mensal); veja o README principal
```

O script:
1. Importa `generate_report_updated` sem modificar seus defaults.
2. Sobrescreve `gr.PDF_PATH` em runtime para `relatorio_her2_inteligencia_competitiva_YYYY-MM-DD.pdf`.
3. Carrega dados via `gr.load_data()` e gera o PDF via `gr.build(trials)`.
4. Persiste KPIs do snapshot em `.kpis_YYYY-MM-DD.json` (gitignored) para auditoria.

## Verificações pós-build
- Arquivo existe e tem tamanho > 100 KB.
- PyMuPDF confirma 13–15 páginas.
- Comparar KPIs do JSON contra o relatório anterior para detectar drift.
