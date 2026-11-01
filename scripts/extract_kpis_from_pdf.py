"""
Extract the five headline KPIs from a previously generated HER2 report PDF,
using anchor strings (NOT loose regex) so it survives text-reordering in the
PDF.

Anchor strategy (see references/her2-kpi-extraction-anchors.md for the full
layout and rationale):

  total      <- "em N estudos ativos (Fases 2\xe2\x80\x934)"
  recruiting <- (from KPI block, position 2 in vertical order)
  phase3     <- (from KPI block, position 3)
  enrollment_k <- "mais de N mil pacientes planejados"  (N treated as thousands)
  brazil     <- (from KPI block, position 5; label is "Com Brasil")
  china_n    <- "ao menos N estudos (X%) t\xc3\xaam patrocinador chin\xc3\xaas"
  china_pct  <- same anchor, percent in parens

Two strategies are provided and the more robust one (KPI block, position-based)
is the default; the paragraph-anchor strategy is kept as a fallback for
reports that don't have a full block.

Usage:
    .venv/bin/python scripts/extract_kpis_from_pdf.py PATH/TO/prior.pdf
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf  # PyMuPDF


def _page_text(path: str, page_index: int = 2) -> str:
    """Page 3 is the executive summary; index 2 (0-based)."""
    doc = pymupdf.open(path)
    try:
        if page_index >= doc.page_count:
            raise ValueError(f"PDF has only {doc.page_count} pages; "
                             f"asked for index {page_index}")
        return doc[page_index].get_text()
    finally:
        doc.close()


def extract_via_paragraph_anchors(text: str) -> dict:
    """Extract KPIs by matching the long-form Portuguese sentence on page 3."""
    out = {}

    m = re.search(r"em (\d[\d.]*) estudos ativos", text)
    if m:
        out["total"] = int(m.group(1).replace(".", ""))

    m = re.search(r"mais de (\d[\d.]*) mil pacientes planejados", text)
    if m:
        out["enrollment_k"] = float(m.group(1).replace(".", "").replace(",", "."))

    m = re.search(r"ao menos (\d[\d.]*) estudos\s*\((\d+)\s*%\)\s*t[eê]m\s+patrocinador chin[eê]s",
                  text, flags=re.IGNORECASE)
    if m:
        out["china_n"] = int(m.group(1).replace(".", ""))
        out["china_pct"] = int(m.group(2))

    m = re.search(r"apenas (\d+) estudos com men[cç]\w* ao pa[ií]s", text, flags=re.IGNORECASE)
    if m:
        out["brazil"] = int(m.group(1))

    return out


def extract_via_kpi_block(text: str) -> dict:
    """Extract KPIs by locating the stacked metric block on the executive summary.

    The block on page 3 is laid out as: <blank line> <5 numbers stacked
    vertically> <blank line> <5 labels stacked vertically>. The five numbers
    appear in this order:
        1. total (Estudos ativos)
        2. recruiting (Recrutando)
        3. phase3 (Em Fase 3)
        4. enrollment (e.g. "399k" — may end in 'k')
        5. brazil (Com Brasil)

    Because pymupdf linearizes vertical text into a stream, we identify the
    block by the boundary anchors "Estudos ativos" and "Principais Achados
    Estrat[eé]gicos" and pick the five numeric tokens that fall between them.
    """
    # Locate block boundaries
    start = re.search(r"Estudos ativos", text)
    end = re.search(r"Principais Achados Estrat", text)
    if not (start and end) or end.start() <= start.start():
        return {}

    block = text[start.start():end.start()]

    # Match: pure digits, or digits + optional thousands separators, or
    # digits followed by 'k' (enrollment shorthand). Order preserved.
    tokens = re.findall(r"(\d{1,3}(?:\.\d{3})*|\d+k|\d+)", block)

    # Heuristics: the enrollment tile ends in 'k' OR is 3+ digits, and the
    # brazil tile is almost always 1-2 digits. We'll pick the first five
    # qualifying tokens and label them positionally.
    kpi_values = []
    for tok in tokens:
        if tok.endswith("k"):
            kpi_values.append(("enrollment_k", float(tok[:-1])))
        else:
            n = int(tok.replace(".", ""))
            kpi_values.append((None, n))

    # Map positionally: [total, recruiting, phase3, enrollment, brazil]
    # We can only confidently assign enrollment and brazil; the three
    # position-1..3 numbers are total/recruiting/phase3 and we need their
    # own anchor strings to disambiguate. Pull the labels below the block
    # for that.
    out = {}
    nums = [v for _, v in kpi_values[:5]]
    if len(nums) < 5:
        return out

    # Pull label area to disambiguate
    label_block = text[end.start():end.start() + 600]
    has_phase3 = "Em Fase 3" in label_block
    has_recruit = "Recrutando" in label_block
    has_total = "Estudos ativos" in label_block
    has_brasil = "Com Brasil" in label_block

    # total, recruiting, phase3, enrollment, brazil
    if has_total and has_recruit and has_phase3 and has_brasil:
        out["total"] = int(nums[0])
        out["recruiting"] = int(nums[1])
        out["phase3"] = int(nums[2])
        out["enrollment_k"] = float(nums[3])
        out["brazil"] = int(nums[4])
    return out


def extract_kpis(pdf_path: str) -> dict:
    text = _page_text(pdf_path, page_index=2)
    out = extract_via_kpi_block(text)
    if not out:
        out = extract_via_paragraph_anchors(text)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: extract_kpis_from_pdf.py PATH/TO/report.pdf", file=sys.stderr)
        return 2
    pdf_path = sys.argv[1]
    if not Path(pdf_path).is_file():
        print(f"ERROR: not a file: {pdf_path}", file=sys.stderr)
        return 3
    kpis = extract_kpis(pdf_path)
    print(json.dumps(kpis, indent=2, ensure_ascii=False))
    return 0 if kpis else 4


if __name__ == "__main__":
    raise SystemExit(main())
