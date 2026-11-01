"""
Verify a generated HER2 competitive-intelligence PDF.

Checks (per references/her2-weekly-update-runbook.md and the SKILL.md
verification checklist):
  1. File exists at the expected path.
  2. File size > 100 KB (chart-heavy deck; smaller = broken render).
  3. Page count within 13–15 (cover + index + exec + body + conclusions; the report
     grew from 13 to 14 pages in Oct/2026 as the dataset grew).
  4. Page 3 (executive summary) contains the standard KPI tokens.

Exits non-zero on any check failure. Use as the final gate of a cron run
before reporting "OK".

Usage:
    .venv/bin/python scripts/verify_pdf_artifact.py PATH/TO/report.pdf
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pymupdf  # PyMuPDF


MIN_PAGES = 13
MAX_PAGES = 15
MIN_SIZE_KB = 100

# Tokens that must appear in the executive summary text (page 3, 0-based index 2)
EXEC_SUMMARY_TOKENS=(
    "1. Sumário Executivo",
    "Estudos ativos",
    "Com Brasil",
    "Principais Achados Estrat",
)


def verify(pdf_path):
    issues = []
    p = Path(pdf_path)
    if not p.is_file():
        return False, [f"missing: {pdf_path}"]
    size_kb = p.stat().st_size / 1024
    if size_kb < MIN_SIZE_KB:
        issues.append(f"size {size_kb:.0f} KB < {MIN_SIZE_KB} KB (suspicious)")

    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        return False, [f"pymupdf open failed: {e}"]

    try:
        pages = doc.page_count
        if not (MIN_PAGES <= pages <= MAX_PAGES):
            issues.append(f"page count {pages} outside expected {MIN_PAGES}-{MAX_PAGES}")

        if pages >= 3:
            text = doc[2].get_text()  # page 3, 0-based index 2
            for tok in EXEC_SUMMARY_TOKENS:
                if tok not in text:
                    issues.append(f"exec summary missing token: {tok!r}")
        else:
            issues.append("PDF has fewer than 3 pages; cannot check exec summary")
    finally:
        doc.close()

    return (not issues), issues


def main():
    if len(sys.argv) < 2:
        print("Usage: verify_pdf_artifact.py PATH/TO/report.pdf", file=sys.stderr)
        return 2
    pdf_path = sys.argv[1]
    ok, issues = verify(pdf_path)
    size_kb = os.path.getsize(pdf_path) / 1024 if os.path.exists(pdf_path) else 0
    print(f"verify: {pdf_path}")
    print(f"  size: {size_kb:.0f} KB")
    if ok:
        print("  status: OK")
        return 0
    print("  status: FAIL")
    for it in issues:
        print(f"    - {it}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
