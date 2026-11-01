"""
Weekly HER2 competitive intelligence report runner.

Generates a timestamped PDF without mutating generate_report_updated.py
constants permanently. Pattern from references/her2-weekly-update-runbook.md.
"""
import os
import sys
import json
import datetime as dt

# Ensure the project dir is on sys.path so we can import the report module
PROJECT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT)

import generate_report_updated as gr  # noqa: E402

# Date stamp for this run
date_str = dt.datetime.now().strftime('%Y-%m-%d')
out_path = os.path.join(PROJECT, f'relatorio_her2_inteligencia_competitiva_{date_str}.pdf')

# Override the report's hardcoded PDF_PATH at runtime (do not edit the script)
gr.PDF_PATH = out_path

print(f"Carregando dados de {gr.DB_PATH}…")
trials = gr.load_data()
print(f"  {len(trials)} estudos carregados.")

# Compute current KPIs for the shift summary
from collections import defaultdict
total = len(trials)
recruiting = sum(1 for t in trials if t['status'] == 'RECRUITING')
phase3 = sum(1 for t in trials if t['phase_norm'] in ('Fase 3', 'Fase 2/3'))
total_enroll = sum(t['enrollment'] for t in trials)
brazil = sum(1 for t in trials if t['has_brazil'])
china = sum(1 for t in trials if t['region'] == 'China')
her2 = sum(1 for t in trials if t['subtype_top'] == 'HER2-positivo')
collection_date = sorted({t.get('collection_date') for t in trials if t.get('collection_date')})[-1]

kpis = {
    'total': total,
    'recruiting': recruiting,
    'phase3': phase3,
    'enrollment_k': round(total_enroll / 1000, 1),
    'brazil': brazil,
    'china_n': china,
    'china_pct': round(100 * china / total, 1) if total else 0,
    'her2_n': her2,
    'her2_pct': round(100 * her2 / total, 1) if total else 0,
    'collection_date': collection_date,
}
with open(os.path.join(PROJECT, f'.kpis_{date_str}.json'), 'w') as f:
    json.dump(kpis, f, indent=2)
print("  KPIs:", kpis)

print(f"Gerando relatório PDF → {out_path}")
gr.build(trials)

# Verify artifact
if os.path.exists(out_path):
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Relatório salvo em: {out_path}  ({size_kb:.0f} KB)")
else:
    print("  ERRO: relatório não foi criado.")
    sys.exit(1)
