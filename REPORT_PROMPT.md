# Prompt — Relatório de Inteligência Competitiva HER2+

Reusable prompt to regenerate `relatorio_her2_inteligencia_competitiva.pdf`.
Captures the data source, branding, two-axis clinical taxonomy, and all 13 pages of
analysis as they appear in the final report. Assumes `her2_breast_cancer_trials.db` and
the `fonts/` folder are present in the project.

---

Build a competitive and regulatory intelligence report on HER2-positive breast cancer
clinical trials, as a polished PDF for senior pharma executives. Output the file as
relatorio_her2_inteligencia_competitiva.pdf in the project folder. The entire report
must be in pt-BR, highly visual (charts, infographics, KPI tiles, heatmaps, treemaps),
and intuitive enough to skim. Write a single generate_report.py that produces it.

## DATA
Source: her2_breast_cancer_trials.db (SQLite). Table `trial_snapshots` has columns
nct_id, collection_date, status, phase, full_data_json. The JSON is a ClinicalTrials.gov
API v2 study object (protocolSection.*). Universe = 697 interventional trials, phases 2-4,
active statuses (RECRUITING, ACTIVE_NOT_RECRUITING, NOT_YET_RECRUITING,
ENROLLING_BY_INVITATION). Collected 2026-06-02. NOTE: the locations module was stripped
on collection, so geographic/Brazil presence must be derived conservatively (sponsor-name
heuristic + text search) and that limitation must be stated transparently in the report.

## BRANDING (www.pesquisaedados.com)
Teal palette — primary #85D8C8, primary-dark #6BC4B3, secondary #5FBFAD, accent #4DA793,
dark #1D3A35 / #2C3E50, light bg #F4FDFC, highlight #E8FAF7, amber #E0A458 (alerts),
coral #D98B7A (Brazil/gap). Fonts from ./fonts: Prompt (Regular/Bold) for body, Oswald
(Regular/SemiBold) for headings; fall back to Helvetica if missing. A4, ~1.8cm margins.
Every page: top accent bar, footer with "Pesquisa e Dados · Inteligência Competitiva
HER2+ · Uso Interno Confidencial" on the left and "Página X" on the right (must NOT
overlap). Use reportlab (platypus) for layout and matplotlib + squarify for charts
(render charts to in-memory PNG buffers, embed as Images). Use pt-BR month names
(no English months) and thousands formatting.

## CLINICAL CLASSIFICATION (the analytical core — do this well)
For each trial, derive a TWO-DIMENSIONAL taxonomy from text (conditions + title + brief
summary + intervention names), NOT a single vague bucket:
  1. Molecular subtype: HER2+/HR+ (triplo positivo), HER2+/HR− (puro), HR+/HER2−,
     Triplo Negativo (TNBC), Não especificado. Treat a trial as HER2+ if HER2/HER-2/
     ERBB2 appears in text OR a known HER2-targeted agent appears in the drugs
     (trastuzumab, pertuzumab, T-DM1, T-DXd/deruxtecan, tucatinib, neratinib, lapatinib,
     pyrotinib, margetuximab, zanidatamab, SHR-A1811, ARX788, RC48/disitamab, etc.).
  2. Disease setting: Metastático/Avançado, Inicial/(Neo)adjuvante, Misto/Multi-estágio,
     Metástase Cerebral (SNC), Não especificado.
"Não especificado" must stay low (~4%, not ~50%) — tune keyword lists until it does.
Also derive: normalized phase (Fase 2, 2/3, 3, etc.), start year, primary completion year,
sponsor class (INDUSTRY / academia / government), and a sponsor-region heuristic
(China, Coreia/Japão, Europa, EUA/Am. Norte, Outros/N/D) by matching the lead sponsor
name against curated institution/company keyword lists. Flag Brazil presence by text-
searching "Brazil" in the JSON.

## REPORT STRUCTURE (13 pages)
1. Cover — dark branded cover, diagonal teal accent, title "CÂNCER DE MAMA HER2-POSITIVO",
   source/collection metadata, "Uso Interno — Confidencial".
2. Índice (clickable-style TOC, 10 sections) + Metodologia e Escopo callouts (source,
   universe, classification method, limitations; plus a "how to read this" note that the
   numbers reflect research activity, not sales/market share).
3. Sumário Executivo — intro paragraph; a KPI tile row (total studies, recruiting,
   phase 3, ~planned patients in 'k', trials mentioning Brazil); 5 bolded strategic
   findings (pipeline growth >7× 2019→2025; shift to metastatic; ADCs redefining
   standard of care; China as research epicenter; Brazil <1%); and a horizontal bar of
   studies by clinical stage.
4. Panorama Geral — two donuts (status, phase) + an area/line chart of new studies by
   start year (2015–2026) with a note that 2026 is partial.
5. Concentração Geográfica — donut by sponsor region + donut by sponsor category, with a
   prominent callout on the China shift (≥36% of studies; likely underestimated) and its
   heuristic caveat.
6-7. Análise por Indicação — treemap of studies by disease setting; donut by molecular
   subtype; horizontal bar of planned patients by stage; a subtype × setting HEATMAP;
   and a quantitative table per stage (n studies, est. patients, phase-3 count,
   recruiting count) + strategic-reading callout.
8. Paisagem Terapêutica — donut by therapeutic class (Anti-HER2 mAb/ADC, anti-HER2 TKI,
   CDK4/6i, IO, emerging ADCs, PI3K/AKT/mTOR, hormone, chemo) + top-15 drugs bar +
   per-class narrative rows.
9. Análise Competitiva — top-12 sponsors bar + a "big pharma positioning" table
   (company, #studies, focus, stage, differentiator) + "two parallel games" callout
   (Western big pharma vs. Chinese academic/pharma ecosystem).
10. Pipeline Emergente — table of active ADCs (canonical-merged names: studies, phases,
   lead sponsor, patients) + a highlighted emerging-molecules table (T-DXd, SHR-A1811,
   zanidatamab, tucatinib, pyrotinib, margetuximab) + innovation-thesis callout.
11. Presença no Brasil — methodology caveat callout; per-trial cards for the trials found
   mentioning Brazil (NCT, title, sponsor, status, phase, patients, note); strategic-
   opportunity callout (Brazil <1% — underutilized; REBEC, tier-1 sites).
12. Análise Regulatória e Ciclo de Vida — top phase-3 studies by enrollment table; a
   line chart of primary-completion horizon (2026–2030) for recruiting trials; an
   enrollment-size histogram; regulatory synthesis callout (2026–2027 readout wave).
13. Conclusões e Recomendações — 5 numbered strategic recommendations (monitor ADC race;
   capture CDK4/6 + anti-HER2 combos; activate Brazilian sites; build CNS-metastasis
   intelligence; establish China surveillance) + "próximos passos" list + sources footer.

## QUALITY BAR
Audience is C-level pharma. No tofu/missing glyphs (avoid emoji and bullets not in the
Prompt font — use colored left-borders on callouts instead). No half-empty or orphan
pages. Verify the output by rendering the PDF to images and inspecting every page; fix
layout overlaps, label collisions, and any English text before finishing.

---

## Data acquisition (optional — regenerate the DB)
The DB is produced by `fetch_trials.py`, which queries the ClinicalTrials.gov API v2
(`query.term="HER2-positive Breast Cancer"`), keeps interventional phase-2/3/4 studies in
active statuses, and stores the full study JSON per snapshot — **deleting the
`locations` list** to keep the DB small. To unlock a real geographic/Brazil section,
re-fetch preserving `contactsLocationsModule.locations` and cross-reference REBEC.
