"""
Weekly cron wrapper for the HER2 competitive intelligence PDF.

Proven pattern from references/her2-weekly-update-runbook.md:
- Import the report module WITHOUT editing its source.
- Override module.PDF_PATH at runtime to a timestamped filename.
- Load DB snapshot via the report's own load_data() (single source of truth
  for collection_date, taxonomy, region classifier, etc.).
- Compute KPIs from the loaded trial list BEFORE build(), persist to a
  sidecar JSON for later comparison.
- Invoke build() to write the PDF.
- Run verify_pdf_artifact.verify() as the final gate (SKILL.md §5 item 8).

Usage (from project dir):
    .venv/bin/python scripts/run_weekly_report.py
        [--project /path/to/project]
        [--module generate_report_updated]
        [--prefix relatorio_her2_inteligencia_competitiva]

The script is intentionally self-contained and exits non-zero on any failure
so cron can surface problems.

Exit codes:
    0  build + verify passed
    1  verifier failed (artefact passed build() but failed structural checks)
    2  project dir not found
    3  report module failed to import
    4  build() raised
    5  build() returned but output file not on disk
    6  verify_pdf_artifact raised or reported FAIL
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _compute_kpis(trials: list) -> dict:
    """Replicate the headline KPIs the report prints on the cover/exec summary.

    These five numbers appear in the stacked metric block on page 3 of the
    PDF, in top-to-bottom order. Keep this function aligned with the
    report's own load_data() / build() computation — if the report's
    classifier changes, update this.
    """
    total = len(trials)
    recruiting = sum(1 for t in trials if t.get("status") == "RECRUITING")
    phase3 = sum(1 for t in trials
                 if t.get("phase_norm") in ("Fase 3", "Fase 2/3"))
    total_enroll = sum(t.get("enrollment", 0) or 0 for t in trials)
    brazil = sum(1 for t in trials if t.get("has_brazil"))
    china = sum(1 for t in trials if t.get("region") == "China")
    her2 = sum(1 for t in trials if t.get("subtype_top") == "HER2-positivo")
    collection_date = sorted({t.get("collection_date") for t in trials
                              if t.get("collection_date")})[-1] if trials else None

    return {
        "total": total,
        "recruiting": recruiting,
        "phase3": phase3,
        "enrollment_k": round(total_enroll / 1000, 1),
        "brazil": brazil,
        "china_n": china,
        "china_pct": round(100 * china / total, 1) if total else 0,
        "her2_n": her2,
        "her2_pct": round(100 * her2 / total, 1) if total else 0,
        "collection_date": collection_date,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
    }


def _import_verifier():
    """Import verify() from verify_pdf_artifact (sibling script).

    Handles two layout cases: scripts/ on sys.path already (package-style
    import) and bare invocation from outside the scripts/ dir (need to
    add the dir to sys.path).
    """
    try:
        from verify_pdf_artifact import verify  # noqa: F401
    except ImportError:
        scripts_dir = Path(__file__).resolve().parent
        sys.path.insert(0, str(scripts_dir))
        from verify_pdf_artifact import verify  # type: ignore  # noqa: F401
    return verify


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project",
                    default=str(Path(__file__).resolve().parent.parent),
                    help="Project directory containing the report module and the SQLite DB")
    ap.add_argument("--module", default="generate_report_updated",
                    help="Report-module name to import (without .py)")
    ap.add_argument("--prefix", default="relatorio_her2_inteligencia_competitiva",
                    help="Filename prefix; <prefix>_YYYY-MM-DD.pdf is emitted")
    args = ap.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(f"ERROR: project dir not found: {project}", file=sys.stderr)
        return 2
    sys.path.insert(0, str(project))

    try:
        gr = importlib.import_module(args.module)
    except Exception:
        traceback.print_exc()
        return 3

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = str(project / f"{args.prefix}_{date_str}.pdf")
    gr.PDF_PATH = out_path  # runtime override — never edit the source

    print(f"[run] loading {args.module} from {project}")
    print(f"[run] DB: {getattr(gr, 'DB_PATH', '?')}")
    trials = gr.load_data()
    print(f"[run] loaded {len(trials)} trials")

    kpis = _compute_kpis(trials)
    kpi_json = project / f".kpis_{date_str}.json"
    kpi_json.write_text(json.dumps(kpis, indent=2))
    print(f"[run] KPIs: {kpis}")
    print(f"[run] KPIs persisted to {kpi_json.name}")

    print(f"[run] building PDF -> {out_path}")
    try:
        gr.build(trials)
    except Exception:
        traceback.print_exc()
        return 4

    if not os.path.exists(out_path):
        print(f"ERROR: build() returned but {out_path} not found", file=sys.stderr)
        return 5
    size_kb = os.path.getsize(out_path) / 1024
    print(f"[run] PDF written: {size_kb:.0f} KB")
    if size_kb < 100:
        print(f"WARNING: PDF suspiciously small ({size_kb:.0f} KB)", file=sys.stderr)

    # Self-enforce the "real gate, not stdout echo" contract (SKILL.md §5 item 8).
    # Chain the verifier so cron does not have to remember to run it as a
    # separate step. If the artefact fails structural checks (page count,
    # exec-summary tokens) the job exits non-zero even though build() returned.
    print("[run] verifying artefact …")
    try:
        verify = _import_verifier()
        ok, issues = verify(out_path)
    except Exception:
        traceback.print_exc()
        return 6
    if ok:
        print("[run] verification: PASS")
        return 0
    print("[run] verification: FAIL", file=sys.stderr)
    for it in issues:
        print(f"  - {it}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
