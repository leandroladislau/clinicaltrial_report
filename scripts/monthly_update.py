"""
Atualização mensal do relatório de inteligência competitiva HER2+.

Fluxo (executado todo dia 1º do mês pela rotina agendada):
  1. Registra o hash de todos os arquivos de HISTÓRICO existentes
     (relatorio_*.pdf/.txt, .kpis_*.json).
  2. Coleta os estudos no ClinicalTrials.gov (fetch_trials.py) e atualiza o .db.
  3. Confirma que o banco ficou com a coleta de hoje.
  4. Gera o PDF datado + .kpis_YYYY-MM-DD.json (scripts/run_weekly_report.py)
     e valida o artefato (scripts/verify_pdf_artifact.py).
  5. Compara os KPIs com a edição anterior.
  6. Confere que NENHUM arquivo de histórico foi alterado ou removido.

Uso (na raiz do projeto):
    uv run scripts/monthly_update.py [--skip-fetch] [--force]

    --skip-fetch  não consulta a API (usa o .db atual; útil para testes)
    --force       permite sobrescrever o PDF do dia, se já existir

Códigos de saída:
    0  tudo certo
    10 PDF do dia já existe (use --force)
    11 fetch_trials.py falhou (banco preservado)
    12 banco não contém a coleta de hoje (dados desatualizados)
    13 geração/validação do relatório falhou
    14 arquivo de histórico alterado/removido (NÃO commitar!)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PREFIX = "relatorio_her2_inteligencia_competitiva"
HISTORY_GLOBS = ("relatorio_*.pdf", "relatorio_*.txt", ".kpis_*.json")
KPI_KEYS = ("total", "recruiting", "phase3", "enrollment_k", "brazil",
            "china_n", "china_pct", "her2_n", "her2_pct")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def history_snapshot() -> dict[str, str]:
    files = {}
    for pattern in HISTORY_GLOBS:
        for p in PROJECT.glob(pattern):
            files[p.name] = sha256(p)
    return files


def run(cmd: list[str]) -> int:
    print(f"[monthly] $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=PROJECT).returncode


def db_collection_dates() -> list[str]:
    conn = sqlite3.connect(PROJECT / "her2_breast_cancer_trials.db")
    try:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT collection_date FROM trial_snapshots ORDER BY 1")]
    finally:
        conn.close()


def previous_kpis(today: str) -> tuple[str, dict] | None:
    files = sorted(p for p in PROJECT.glob(".kpis_*.json") if p.name != f".kpis_{today}.json")
    if not files:
        return None
    return files[-1].name, json.loads(files[-1].read_text())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    pdf = PROJECT / f"{PREFIX}_{today}.pdf"
    kpi_file = PROJECT / f".kpis_{today}.json"

    if (pdf.exists() or kpi_file.exists()) and not args.force:
        print(f"[monthly] {pdf.name} ou {kpi_file.name} já existe; use --force para refazer.",
              file=sys.stderr)
        return 10

    before = history_snapshot()
    # Em --force, o PDF/KPI do dia podem ser regravados; os demais devem ficar intactos.
    protected = {k: v for k, v in before.items() if k not in (pdf.name, kpi_file.name)}
    print(f"[monthly] {len(protected)} arquivos de histórico protegidos.")

    if not args.skip_fetch:
        if run([sys.executable, "fetch_trials.py"]) != 0:
            print("[monthly] fetch_trials.py falhou — banco preservado.", file=sys.stderr)
            return 11
        dates = db_collection_dates()
        if dates != [today]:
            print(f"[monthly] banco com coleta(s) {dates}, esperado ['{today}'].", file=sys.stderr)
            return 12
    else:
        print(f"[monthly] --skip-fetch: usando coleta existente {db_collection_dates()}")

    if run([sys.executable, "scripts/run_weekly_report.py", "--project", str(PROJECT)]) != 0:
        print("[monthly] geração/validação do relatório falhou.", file=sys.stderr)
        return 13

    # Comparação com a edição anterior
    cur = json.loads(kpi_file.read_text())
    prev = previous_kpis(today)
    print("\n[monthly] KPIs desta edição vs. anterior:")
    for k in KPI_KEYS:
        if prev:
            pv = prev[1].get(k)
            delta = f"{cur[k] - pv:+.1f}" if isinstance(pv, (int, float)) else "n/d"
            print(f"  {k:13} {cur[k]!s:>8}  (anterior {pv!s:>8}, Δ {delta})")
        else:
            print(f"  {k:13} {cur[k]!s:>8}")
    if prev:
        print(f"  (anterior = {prev[0]}, coleta {prev[1].get('collection_date')})")

    # Trava de histórico
    after = history_snapshot()
    broken = sorted(k for k, v in protected.items() if after.get(k) != v)
    if broken:
        print("[monthly] ERRO: histórico alterado/removido:", *broken, sep="\n  - ", file=sys.stderr)
        return 14

    new_files = sorted(set(after) - set(before))
    print(f"\n[monthly] OK. Novos arquivos: {', '.join(new_files) or '(regravados via --force)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
