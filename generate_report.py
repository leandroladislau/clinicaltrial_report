"""
Relatório de Inteligência Competitiva e Regulatória
HER2+ Câncer de Mama — Ensaios Clínicos Globais
Pesquisa e Dados | www.pesquisaedados.com

v2 — taxonomia clínica refinada (subtipo × estágio), análise geográfica,
     correções de layout, índice e infográficos executivos.
"""

import sqlite3
import json
import os
import io
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import squarify

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable, Flowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

# ─── Brand Colors ──────────────────────────────────────────────────────────────
C_PRIMARY       = "#85D8C8"
C_PRIMARY_DARK  = "#6BC4B3"
C_SECONDARY     = "#5FBFAD"
C_ACCENT        = "#4DA793"
C_DARK          = "#1D3A35"
C_DARK2         = "#2C3E50"
C_WHITE         = "#FFFFFF"
C_LIGHT_BG      = "#F4FDFC"
C_GRAY          = "#7F8C8D"
C_LIGHT_GRAY    = "#ECF0F1"
C_HIGHLIGHT     = "#E8FAF7"
C_AMBER         = "#E0A458"   # alerta/destaque pontual
C_CORAL         = "#D98B7A"   # ênfase secundária (Brasil/gap)

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

def register_fonts():
    try:
        pdfmetrics.registerFont(TTFont('Prompt',          os.path.join(FONT_DIR, 'Prompt-Regular.ttf')))
        pdfmetrics.registerFont(TTFont('Prompt-Bold',     os.path.join(FONT_DIR, 'Prompt-Bold.ttf')))
        pdfmetrics.registerFont(TTFont('Oswald',          os.path.join(FONT_DIR, 'Oswald-Regular.ttf')))
        pdfmetrics.registerFont(TTFont('Oswald-SemiBold', os.path.join(FONT_DIR, 'Oswald-SemiBold.ttf')))
        return 'Prompt', 'Prompt-Bold', 'Oswald', 'Oswald-SemiBold'
    except Exception:
        return 'Helvetica', 'Helvetica-Bold', 'Helvetica', 'Helvetica-Bold'

FONT_BODY, FONT_BOLD, FONT_HEADING, FONT_HEADING_BOLD = register_fonts()

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

DB_PATH  = os.path.join(os.path.dirname(__file__), "her2_breast_cancer_trials.db")
PDF_PATH = os.path.join(os.path.dirname(__file__), "relatorio_her2_inteligencia_competitiva.pdf")

MESES = {1:'Janeiro',2:'Fevereiro',3:'Março',4:'Abril',5:'Maio',6:'Junho',
         7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
COLLECTION_DATE = "2026-06-02"
REPORT_MONTH = "Junho de 2026"

TEAL_PALETTE = [C_ACCENT, C_PRIMARY_DARK, C_PRIMARY, C_SECONDARY,
                "#3D9080", "#2E6B5E", "#6CCFBE", "#A8E6DC", "#1F4740", "#D0F5EF"]

plt.rcParams.update({
    'font.family':       'DejaVu Sans',
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'axes.grid':         True,
    'grid.alpha':        0.22,
    'grid.linestyle':    '--',
    'axes.facecolor':    '#FBFEFE',
    'figure.facecolor':  'white',
    'axes.edgecolor':    '#C9D6D3',
    'text.color':        C_DARK2,
    'axes.labelcolor':   C_DARK2,
    'xtick.color':       C_DARK2,
    'ytick.color':       C_DARK2,
})

# HER2-targeted agents → strong signal of HER2+ context
HER2_DRUGS = ['trastuzumab','pertuzumab','t-dm1','t-dxd','deruxtecan','emtansine','kadcyla','enhertu',
              'tucatinib','neratinib','lapatinib','pyrotinib','margetuximab','zanidatamab','afatinib',
              'shr-a1811','arx788','mrg002','rc48','disitamab','a166','dp303c','herceptin','perjeta',
              'inetetamab','ds-8201','zw25','tukysa','nerlynx','tykerb','dato-dxd','datopotamab']

# Region classifier (lead sponsor heuristic)
REG_CN = ['china','chinese','fudan','sun yat','zhejiang','peking','beijing','shanghai','guangdong','tianjin',
          'jiangsu','henan','nanjing','sichuan','wuhan','shandong','hunan','hebei','fujian','hengrui','renji',
          'ruijin','xijing','harbin','chongqing','guangzhou','cancer hospital','medical university',
          'first affiliated','second affiliated','third affiliated','fourth affiliated','akeso','remegen',
          'duality','kelun','luzsana','tongji','xiangya','union hospital','jiao tong','capital medical',
          'southern medical','air force','qilu','west china','national clinical','chia tai','cspc','shengjing',
          'zhongshan','shengjing','hengrui','sichuan','yunnan','jilin','liaoning','sir run run']
REG_KRJP = ['korea','korean','samsung','seoul','asan','yonsei','japan','japanese','daiichi','astellas','takeda',
            'chugai','osaka','tokyo','kyoto','national cancer center hospital']
REG_EU = ['unicancer','astrazeneca','roche','hoffmann','novartis','sanofi','servier','german','spanish',
          'italian','french','european','gustave roussy','karolinska','oslo','medsir','solti','gbg','eortc',
          'oxford','cambridge','nhs','assistance publique','vall','hospital clinic','milan','madrid','barcelona',
          'paris','netherlands','belgium','austria','denmark','sweden','swiss','ico','ifom','borstkanker',
          'janni','lyon','heidelberg','charite','institut curie','arcagy']
REG_US = ['national cancer institute','nci','dana-farber','sloan','anderson','mayo','ucsf','city of hope',
          'university of california','alliance foundation','swog','ecog','pfizer','eli lilly','merck sharp',
          'genentech','seagen','gilead','bristol','jonsson','emory','vanderbilt','duke','yale','stanford','nrg',
          'washington','colorado','michigan','wisconsin','texas','chicago','pennsylvania','massachusetts',
          'moffitt','rutgers','baylor','mount sinai','sammons','waks','stemline','jazz','criterium','dana farber',
          'memorial sloan','johns hopkins','cleveland','ohio','north carolina','minnesota','georgetown',
          'roswell','fred hutchinson','national comprehensive']

def classify_region(sp):
    s = sp.lower()
    if any(k in s for k in REG_CN):   return 'China'
    if any(k in s for k in REG_KRJP): return 'Coreia/Japão'
    if any(k in s for k in REG_EU):   return 'Europa'
    if any(k in s for k in REG_US):   return 'EUA / Am. Norte'
    return 'Outros / N/D'


# ═══════════════════════════════════════════════════════════════════════════════
#   DATA LOADING + CLINICAL CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
def load_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT nct_id, status, phase, full_data_json FROM trial_snapshots')
    rows = cur.fetchall()
    conn.close()

    trials = []
    for nct_id, status, phase, fj in rows:
        data = json.loads(fj)
        p = data.get('protocolSection', {})

        ident   = p.get('identificationModule', {})
        st      = p.get('statusModule', {})
        dz      = p.get('designModule', {})
        cm_     = p.get('conditionsModule', {})
        sp_     = p.get('sponsorCollaboratorsModule', {})
        arms    = p.get('armsInterventionsModule', {})
        desc    = p.get('descriptionModule', {})

        conditions = cm_.get('conditions', [])
        title      = ident.get('briefTitle', '')
        summary    = desc.get('briefSummary', '')[:900]
        sponsor       = sp_.get('leadSponsor', {}).get('name', 'N/A')
        sponsor_class = sp_.get('leadSponsor', {}).get('class', 'OTHER')

        interventions = arms.get('interventions', [])
        drugs = [i.get('name','') for i in interventions
                 if i.get('type') in ('DRUG','BIOLOGICAL','COMBINATION_PRODUCT')]
        drugs_text = ' '.join(drugs).lower()

        enrollment = dz.get('enrollmentInfo', {}).get('count', 0) or 0
        start_date = st.get('startDateStruct', {}).get('date', '')
        prim_comp  = st.get('primaryCompletionDateStruct', {}).get('date', '')

        full = (' '.join(conditions) + ' ' + title + ' ' + summary).lower()

        # ── Molecular subtype ──────────────────────────────────────────────
        is_her2_text = ('her2' in full or 'her-2' in full or 'erbb2' in full)
        is_her2_drug = any(d in drugs_text for d in HER2_DRUGS)
        is_hr = any(x in full for x in ('hr+','hormone receptor-positive','er+','estrogen receptor-positive',
                                         'er-positive','hr-positive','luminal'))
        is_tnbc = any(x in full for x in ('triple negative','triple-negative','tnbc'))

        if is_her2_text or is_her2_drug:
            subtype = 'HER2+ / HR+ (triplo positivo)' if is_hr else 'HER2+ / HR− (puro)'
            subtype_top = 'HER2-positivo'
        elif is_tnbc:
            subtype = 'Triplo Negativo (TNBC)'; subtype_top = 'Triplo Negativo'
        elif is_hr:
            subtype = 'HR+ / HER2−'; subtype_top = 'HR+ / HER2−'
        else:
            subtype = 'Não especificado'; subtype_top = 'Não especificado'

        # ── Disease setting / stage ────────────────────────────────────────
        cns = any(x in full for x in ('brain metasta','cns metasta','leptomeningeal',
                                       'cerebral metasta','brain met','central nervous'))
        metastatic = any(x in full for x in ('metasta','advanced','stage iv','recurrent','unresectable',
                                             'mbc','refractory','pretreated','previously treated','4th line',
                                             'second-line','first-line','salvage'))
        early = any(x in full for x in ('neoadjuvant','adjuvant','early','stage i','stage ii','stage iii',
                                        'resectable','curative','operable','perioperative','localized',
                                        'post-surgery','following surgery'))
        if cns:
            setting = 'Metástase Cerebral (SNC)'
        elif metastatic and not early:
            setting = 'Metastático / Avançado'
        elif early and not metastatic:
            setting = 'Inicial / (Neo)adjuvante'
        elif early and metastatic:
            setting = 'Misto / Multi-estágio'
        else:
            setting = 'Não especificado'

        # ── Phase ──────────────────────────────────────────────────────────
        phases = dz.get('phases', [])
        if 'PHASE3' in phases and 'PHASE2' in phases: phase_norm = 'Fase 2/3'
        elif 'PHASE3' in phases:                       phase_norm = 'Fase 3'
        elif 'PHASE2' in phases and 'PHASE1' in phases:phase_norm = 'Fase 1/2'
        elif 'PHASE2' in phases:                       phase_norm = 'Fase 2'
        elif 'PHASE4' in phases:                       phase_norm = 'Fase 4'
        else:                                          phase_norm = 'Outra'

        start_year = None
        if start_date:
            try: start_year = int(start_date[:4])
            except: pass

        trials.append(dict(
            nct_id=nct_id, status=status, phase=phase, phase_norm=phase_norm,
            title=title, sponsor=sponsor, sponsor_class=sponsor_class,
            region=classify_region(sponsor), drugs=drugs, drugs_text=drugs_text,
            enrollment=enrollment, start_date=start_date, start_year=start_year,
            primary_completion=prim_comp, conditions=conditions,
            subtype=subtype, subtype_top=subtype_top, setting=setting,
            has_brazil=('Brazil' in fj or 'BRAZIL' in fj),
        ))
    return trials


# ═══════════════════════════════════════════════════════════════════════════════
#  CHART HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def save_fig(fig, dpi=185):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='white', pad_inches=0.08)
    plt.close(fig)
    buf.seek(0)
    return buf


def donut(labels, values, title, colors_list=None, figsize=(5, 4.1), center_text=None):
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    if colors_list is None:
        colors_list = TEAL_PALETTE[:len(labels)]
    wedges, _, autotexts = ax.pie(
        values, colors=colors_list,
        autopct=lambda pct: f'{pct:.0f}%' if pct > 5 else '',
        startangle=140, pctdistance=0.78,
        wedgeprops=dict(width=0.42, edgecolor='white', linewidth=2.2))
    for at in autotexts:
        at.set_fontsize(8.5); at.set_color('white'); at.set_fontweight('bold')
    if center_text:
        ax.text(0, 0.08, center_text[0], ha='center', va='center',
                fontsize=17, fontweight='bold', color=C_ACCENT)
        ax.text(0, -0.16, center_text[1], ha='center', va='center',
                fontsize=7.5, color=C_GRAY)
    ax.legend(wedges, [f'{l}  ·  {v}' for l, v in zip(labels, values)],
              loc='lower center', bbox_to_anchor=(0.5, -0.16),
              ncol=2, fontsize=7.3, frameon=False, handlelength=1.1, columnspacing=1.0)
    ax.set_title(title, fontsize=11, fontweight='bold', pad=12, color=C_DARK2)
    ax.set_aspect('equal')
    fig.tight_layout()
    return save_fig(fig)


def hbar(labels, values, title, xlabel='', color=C_ACCENT, figsize=(6.5, 4), value_fmt='{:,}'):
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    y = range(len(labels))
    bars = ax.barh(y, values, color=color, edgecolor='white', linewidth=0.6, height=0.68, zorder=3)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, fontsize=8, color=C_GRAY)
    ax.set_title(title, fontsize=11, fontweight='bold', color=C_DARK2, pad=10)
    ax.grid(axis='x', alpha=0.28, linestyle='--', zorder=0)
    ax.spines['left'].set_visible(False)
    mx = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + mx*0.012, bar.get_y() + bar.get_height()/2,
                value_fmt.format(val), va='center', fontsize=8, color=C_DARK2, fontweight='bold')
    ax.set_xlim(0, mx*1.12)
    fig.tight_layout()
    return save_fig(fig)


def treemap(labels, values, title, figsize=(8, 4.2), colors_list=None, short_labels=None):
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    if colors_list is None:
        colors_list = TEAL_PALETTE[:len(labels)]
    if short_labels is None:
        short_labels = labels
    total = sum(values)
    norm = squarify.normalize_sizes(values, 100, 100)
    rects = squarify.squarify(norm, 0, 0, 100, 100)
    for rect, lbl, slbl, val, col in zip(rects, labels, short_labels, values, colors_list):
        ax.add_patch(plt.Rectangle((rect['x'], rect['y']), rect['dx'], rect['dy'],
                                   facecolor=col, edgecolor='white', linewidth=2.5))
        cx, cy = rect['x'] + rect['dx']/2, rect['y'] + rect['dy']/2
        pct = 100*val/total
        dx, dy = rect['dx'], rect['dy']
        if dx > 30 and dy > 22:        # large cell — full label + detail
            ax.text(cx, cy+4, lbl, ha='center', va='center', fontsize=9.5,
                    fontweight='bold', color='white')
            ax.text(cx, cy-5, f'{val} estudos · {pct:.0f}%', ha='center', va='center',
                    fontsize=8, color='white')
        elif dx > 16 and dy > 14:      # medium cell — short label + value
            ax.text(cx, cy+2.5, slbl, ha='center', va='center', fontsize=8,
                    fontweight='bold', color='white')
            ax.text(cx, cy-4.5, f'{val} · {pct:.0f}%', ha='center', va='center',
                    fontsize=7, color='white')
        else:                          # small cell — short label only, tiny
            ax.text(cx, cy, f'{slbl}\n{val}', ha='center', va='center', fontsize=6.5,
                    fontweight='bold', color='white', linespacing=1.3)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.invert_yaxis(); ax.axis('off')
    ax.set_title(title, fontsize=11, fontweight='bold', color=C_DARK2, pad=10)
    fig.tight_layout()
    return save_fig(fig)


def line_area(x, y, title, ylabel='', color=C_ACCENT, figsize=(7.8, 3.4), annotate_last_n=3):
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    ax.fill_between(x, y, alpha=0.16, color=color)
    ax.plot(x, y, color=color, linewidth=2.6, marker='o', markersize=5.5,
            markerfacecolor='white', markeredgewidth=2, markeredgecolor=color)
    ax.set_title(title, fontsize=11, fontweight='bold', color=C_DARK2, pad=10)
    ax.set_ylabel(ylabel, fontsize=8.5)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    mx = max(y)
    for xi, yi in zip(x, y):
        if yi == mx or xi >= max(x) - (annotate_last_n - 1):
            ax.annotate(str(yi), (xi, yi), textcoords="offset points", xytext=(0, 9),
                        ha='center', fontsize=8, fontweight='bold', color=color)
    ax.set_ylim(0, mx*1.18)
    fig.tight_layout()
    return save_fig(fig)


def grouped_bar(categories, series_data, series_labels, title, figsize=(8, 4.3), rotation=0):
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    x = np.arange(len(categories)); n = len(series_data); width = 0.78/n
    for i, (data, lbl) in enumerate(zip(series_data, series_labels)):
        off = (i - n/2 + 0.5)*width
        bars = ax.bar(x+off, data, width*0.92, label=lbl, color=TEAL_PALETTE[i],
                      edgecolor='white', linewidth=0.5)
        for bar, val in zip(bars, data):
            if val > 0:
                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max([max(d) for d in series_data])*0.01,
                        str(val), ha='center', va='bottom', fontsize=6.8, color=C_DARK2)
    ax.set_xticks(x); ax.set_xticklabels(categories, fontsize=8, rotation=rotation,
                                         ha='center' if rotation == 0 else 'right')
    ax.legend(fontsize=8, frameon=False, ncol=len(series_labels), loc='upper right')
    ax.set_title(title, fontsize=11, fontweight='bold', color=C_DARK2, pad=10)
    ax.grid(axis='y', alpha=0.28)
    fig.tight_layout()
    return save_fig(fig)


def heatmap(matrix, row_labels, col_labels, title, figsize=(8, 3.6)):
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    cmap = LinearSegmentedColormap.from_list('teal', ['#FFFFFF', C_PRIMARY, C_ACCENT, C_DARK])
    arr = np.array(matrix)
    im = ax.imshow(arr, cmap=cmap, aspect='auto')
    ax.set_xticks(range(len(col_labels))); ax.set_xticklabels(col_labels, fontsize=7.8, rotation=18, ha='right')
    ax.set_yticks(range(len(row_labels))); ax.set_yticklabels(row_labels, fontsize=8)
    vmax = arr.max()
    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            v = arr[i, j]
            if v > 0:
                ax.text(j, i, str(int(v)), ha='center', va='center', fontsize=8,
                        color='white' if v > vmax*0.5 else C_DARK2, fontweight='bold')
    ax.set_title(title, fontsize=11, fontweight='bold', color=C_DARK2, pad=10)
    ax.grid(False)
    for spine in ax.spines.values(): spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.ax.tick_params(labelsize=7)
    fig.tight_layout()
    return save_fig(fig)


def hist_enrollment(values, title, figsize=(5.6, 3.6)):
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    bins = [0, 50, 100, 200, 400, 800, 1500, 100000]
    labels = ['<50', '50–100', '100–200', '200–400', '400–800', '800–1.5k', '>1.5k']
    counts, _ = np.histogram(values, bins=bins)
    bars = ax.bar(labels, counts, color=C_SECONDARY, edgecolor='white', linewidth=0.6)
    for bar, c in zip(bars, counts):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max(counts)*0.01, str(c),
                ha='center', va='bottom', fontsize=8, color=C_DARK2, fontweight='bold')
    ax.set_title(title, fontsize=11, fontweight='bold', color=C_DARK2, pad=10)
    ax.set_xlabel('Faixa de pacientes (enrollment planejado)', fontsize=8)
    ax.set_ylabel('Nº de estudos', fontsize=8.5)
    ax.grid(axis='y', alpha=0.28)
    fig.tight_layout()
    return save_fig(fig)


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF STYLES
# ═══════════════════════════════════════════════════════════════════════════════
def get_styles():
    base = getSampleStyleSheet()
    def ps(name, **kw):
        d = dict(fontName=FONT_BODY, fontSize=9, leading=14,
                 textColor=colors.HexColor(C_DARK2), spaceAfter=4)
        d.update(kw)
        return ParagraphStyle(name, parent=base['Normal'], **d)
    s = {}
    s['h1']         = ps('h1', fontName=FONT_BOLD, fontSize=16, leading=20,
                         textColor=colors.HexColor(C_ACCENT), spaceBefore=14, spaceAfter=5)
    s['h2']         = ps('h2', fontName=FONT_HEADING_BOLD, fontSize=11.5, leading=15,
                         textColor=colors.HexColor(C_DARK), spaceBefore=10, spaceAfter=4)
    s['h3']         = ps('h3', fontName=FONT_BOLD, fontSize=9.5, leading=13,
                         textColor=colors.HexColor(C_PRIMARY_DARK), spaceBefore=6, spaceAfter=2)
    s['body']       = ps('body', fontSize=9, leading=13.5, alignment=TA_JUSTIFY)
    s['body_small'] = ps('body_small', fontSize=8, leading=11.5, textColor=colors.HexColor(C_GRAY))
    s['caption']    = ps('caption', fontSize=7.5, leading=10.5, textColor=colors.HexColor(C_GRAY),
                         alignment=TA_CENTER, spaceBefore=3, spaceAfter=2)
    s['bullet']     = ps('bullet', fontSize=9, leading=13.5, leftIndent=12, spaceAfter=4)
    s['insight']    = ps('insight', fontName=FONT_BODY, fontSize=8.8, leading=13,
                         textColor=colors.HexColor(C_DARK))
    s['kpi_num']    = ps('kpi_num', fontName=FONT_BOLD, fontSize=20, leading=23,
                         textColor=colors.HexColor(C_ACCENT), alignment=TA_CENTER)
    s['kpi_label']  = ps('kpi_label', fontSize=7.6, leading=10, textColor=colors.HexColor(C_GRAY),
                         alignment=TA_CENTER)
    s['th']         = ps('th', fontName=FONT_BOLD, fontSize=8, textColor=colors.white, alignment=TA_CENTER)
    s['td']         = ps('td', fontSize=7.6, leading=10, textColor=colors.HexColor(C_DARK2))
    s['td_c']       = ps('td_c', fontSize=7.6, leading=10, textColor=colors.HexColor(C_DARK2), alignment=TA_CENTER)
    s['note']       = ps('note', fontSize=7.8, leading=11, textColor=colors.HexColor(C_DARK2))
    s['toc']        = ps('toc', fontSize=10, leading=20, textColor=colors.HexColor(C_DARK2))
    return s


# ─── Header/footer (FIXED: no page-number collision) ──────────────────────────
def page_decoration(canvas, doc):
    canvas.saveState()
    w, h = A4
    # top accent bar
    canvas.setFillColor(colors.HexColor(C_ACCENT))
    canvas.rect(0, h - 0.55*cm, w, 0.55*cm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor(C_PRIMARY))
    canvas.rect(0, h - 0.62*cm, w, 0.07*cm, fill=1, stroke=0)
    # footer line
    canvas.setStrokeColor(colors.HexColor(C_PRIMARY))
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, 1.0*cm, w - MARGIN, 1.0*cm)
    # footer text — left brand, right page number (no overlap)
    canvas.setFont(FONT_BODY, 7.3)
    canvas.setFillColor(colors.HexColor(C_GRAY))
    canvas.drawString(MARGIN, 0.6*cm, "Pesquisa e Dados  ·  Inteligência Competitiva HER2+  ·  Uso Interno Confidencial")
    canvas.setFont(FONT_BOLD, 7.8)
    canvas.setFillColor(colors.HexColor(C_ACCENT))
    canvas.drawRightString(w - MARGIN, 0.6*cm, f"Página {doc.page}")
    canvas.restoreState()


def cover_page(c, doc):
    c.saveState()
    w, h = A4
    c.setFillColor(colors.HexColor(C_DARK)); c.rect(0, 0, w, h, fill=1, stroke=0)
    # diagonal accent
    c.setFillColor(colors.HexColor(C_ACCENT))
    path = c.beginPath()
    path.moveTo(0, h*0.36); path.lineTo(w*0.62, h*0.54); path.lineTo(w, h*0.40)
    path.lineTo(w, 0); path.lineTo(0, 0); path.close()
    c.drawPath(path, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(C_PRIMARY))
    p2 = c.beginPath()
    p2.moveTo(0, h*0.36); p2.lineTo(w*0.62, h*0.54); p2.lineTo(w*0.62, h*0.562); p2.lineTo(0, h*0.382); p2.close()
    c.drawPath(p2, fill=1, stroke=0)
    # top brand stripe
    c.setFillColor(colors.HexColor(C_PRIMARY_DARK)); c.rect(0, h-2*cm, w, 2*cm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont(FONT_BOLD, 12)
    c.drawString(MARGIN, h-1.25*cm, "PESQUISA E DADOS")
    c.setFont(FONT_BODY, 8); c.setFillColor(colors.HexColor(C_LIGHT_BG))
    c.drawString(MARGIN, h-1.68*cm, "www.pesquisaedados.com")
    # title
    c.setFillColor(colors.white); c.setFont(FONT_BOLD, 9.5)
    c.drawString(MARGIN, h*0.74, "RELATÓRIO DE INTELIGÊNCIA COMPETITIVA E REGULATÓRIA")
    c.setFont(FONT_BOLD, 27); c.setFillColor(colors.HexColor(C_PRIMARY))
    c.drawString(MARGIN, h*0.645, "CÂNCER DE MAMA")
    c.setFont(FONT_BOLD, 27); c.setFillColor(colors.white)
    c.drawString(MARGIN, h*0.565, "HER2-POSITIVO")
    c.setFillColor(colors.HexColor(C_PRIMARY)); c.rect(MARGIN, h*0.545, 8*cm, 0.12*cm, fill=1, stroke=0)
    c.setFont(FONT_HEADING, 13); c.setFillColor(colors.HexColor(C_HIGHLIGHT))
    c.drawString(MARGIN, h*0.475, "Pipeline Global  ·  Análise por Indicação  ·  Paisagem Competitiva")
    c.drawString(MARGIN, h*0.438, "Terapias Emergentes  ·  Presença no Brasil")
    # info block — improved contrast (white/light on dark)
    c.setFillColor(colors.HexColor(C_PRIMARY)); c.setFont(FONT_BODY, 10.5)
    c.drawString(MARGIN, h*0.225, f"Fonte de dados: ClinicalTrials.gov  —  {REPORT_MONTH}")
    c.setFillColor(colors.HexColor(C_LIGHT_BG)); c.setFont(FONT_BODY, 8.5)
    c.drawString(MARGIN, h*0.178, "Fonte primária: U.S. National Library of Medicine (API v2)")
    c.drawString(MARGIN, h*0.152, "Data de coleta: 02 de junho de 2026  ·  697 estudos (Fases 2–4)")
    c.drawString(MARGIN, h*0.126, "Classificação: Uso Interno — Confidencial")
    c.setFillColor(colors.HexColor(C_PRIMARY_DARK)); c.rect(0, 0, w, 0.8*cm, fill=1, stroke=0)
    c.setFont(FONT_BODY, 7); c.setFillColor(colors.white)
    c.drawCentredString(w/2, 0.3*cm, "© 2026 Pesquisa e Dados. Todos os direitos reservados.")
    c.restoreState()


# ═══════════════════════════════════════════════════════════════════════════════
#  REUSABLE FLOWABLE BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════
def make_img(buf, width, max_h=8.6*cm):
    buf.seek(0)
    px_w, px_h = PILImage.open(buf).size
    aspect = px_h / px_w
    nat_h = width * aspect
    if nat_h > max_h:
        width = max_h / aspect; nat_h = max_h
    buf.seek(0)
    return Image(buf, width=width, height=nat_h)


def two_col(buf_left, buf_right, wl=None, wr=None, gap=0.4*cm):
    if wl is None: wl = (CONTENT_W - gap)/2
    if wr is None: wr = (CONTENT_W - gap)/2
    t = Table([[make_img(buf_left, wl), make_img(buf_right, wr)]],
              colWidths=[wl + gap/2, wr + gap/2])
    t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'),
                           ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    return t


def build(trials):
    S = get_styles()
    doc = SimpleDocTemplate(PDF_PATH, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN+0.3*cm, bottomMargin=1.5*cm,
                            title="Relatório de Inteligência Competitiva HER2+ — Pesquisa e Dados",
                            author="Pesquisa e Dados")
    story = []

    def H1(t):
        return [Paragraph(t, S['h1']),
                HRFlowable(width=CONTENT_W, thickness=1.5, color=colors.HexColor(C_PRIMARY), spaceAfter=6)]

    def caption(t): return Paragraph(t, S['caption'])

    def kpi_row(items):
        col_w = CONTENT_W/len(items)
        r1 = [Paragraph(n, S['kpi_num']) for n, _, _ in items]
        r2 = [Paragraph(f"<b>{l}</b><br/><font size='6.8' color='{C_GRAY}'>{sub}</font>", S['kpi_label'])
              for _, l, sub in items]
        t = Table([r1, r2], colWidths=[col_w]*len(items))
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(C_HIGHLIGHT)),
            ('LINEABOVE', (0,0), (-1,0), 3, colors.HexColor(C_PRIMARY)),
            ('LINEBELOW', (0,-1), (-1,-1), 0.5, colors.HexColor(C_PRIMARY)),
            ('TOPPADDING', (0,0), (-1,0), 9), ('BOTTOMPADDING', (0,-1), (-1,-1), 8),
            ('TOPPADDING', (0,1), (-1,1), 0),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LINEBEFORE', (1,0), (-1,-1), 0.5, colors.HexColor(C_PRIMARY)),
        ]))
        return t

    def table(headers, rows, widths, align_center_cols=None, font=7.6, header_color=C_ACCENT):
        align_center_cols = align_center_cols or []
        head = [Paragraph(h, S['th']) for h in headers]
        body = [head]
        for row in rows:
            cells = []
            for j, c in enumerate(row):
                st = S['td_c'] if j in align_center_cols else S['td']
                cells.append(Paragraph(str(c), st))
            body.append(cells)
        t = Table(body, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(header_color)),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor(C_HIGHLIGHT)]),
            ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor(C_PRIMARY)),
            ('LEFTPADDING', (0,0), (-1,-1), 4), ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 3.5), ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ]))
        return t

    def callout(text, color=C_PRIMARY_DARK, bg=C_HIGHLIGHT, icon=""):
        # icon arg kept for call-site compatibility but not rendered
        # (emoji glyphs are absent from the Prompt font); the colored
        # left border provides the visual cue instead.
        t = Table([[Paragraph(text, S['insight'])]], colWidths=[CONTENT_W])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg)),
            ('LEFTPADDING', (0,0), (-1,-1), 11), ('RIGHTPADDING', (0,0), (-1,-1), 11),
            ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LINEBEFORE', (0,0), (0,-1), 3, colors.HexColor(color)),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor(color)),
        ]))
        return t

    # ═══ COMPUTE METRICS ═══════════════════════════════════════════════════
    total = len(trials)
    total_enroll = sum(t['enrollment'] for t in trials)
    recruiting = sum(1 for t in trials if t['status'] == 'RECRUITING')
    not_yet    = sum(1 for t in trials if t['status'] == 'NOT_YET_RECRUITING')
    phase3     = sum(1 for t in trials if 'PHASE3' in t['phase'])
    brazil_trials = [t for t in trials if t['has_brazil']]

    status_pt = {'RECRUITING':'Recrutando', 'ACTIVE_NOT_RECRUITING':'Ativo / Não Recrutando',
                 'NOT_YET_RECRUITING':'Não Iniciado', 'ENROLLING_BY_INVITATION':'Por Convite'}
    status_counts = defaultdict(int)
    for t in trials: status_counts[t['status']] += 1

    phase_counts = defaultdict(int)
    for t in trials: phase_counts[t['phase_norm']] += 1

    # Setting (PRIMARY indication axis)
    setting_counts = defaultdict(lambda: {'n':0, 'enroll':0})
    for t in trials:
        setting_counts[t['setting']]['n'] += 1
        setting_counts[t['setting']]['enroll'] += t['enrollment']
    setting_order = sorted(setting_counts.items(), key=lambda x: -x[1]['n'])
    setting_short = {'Metastático / Avançado': 'Metastático',
                     'Inicial / (Neo)adjuvante': 'Inicial /\n(Neo)adj.',
                     'Misto / Multi-estágio': 'Misto',
                     'Metástase Cerebral (SNC)': 'SNC',
                     'Não especificado': 'N/E'}

    # Subtype
    subtype_counts = defaultdict(int)
    for t in trials: subtype_counts[t['subtype']] += 1
    subtype_top_counts = defaultdict(int)
    for t in trials: subtype_top_counts[t['subtype_top']] += 1

    # Region
    region_counts = defaultdict(int)
    for t in trials: region_counts[t['region']] += 1
    region_order = sorted(region_counts.items(), key=lambda x: -x[1])

    # Drugs
    drug_counter = defaultdict(int)
    for t in trials:
        for d in t['drugs']: drug_counter[d.strip()] += 1
    top_drugs = sorted(drug_counter.items(), key=lambda x: -x[1])[:15]

    # Companies
    comp_counter = defaultdict(int)
    for t in trials: comp_counter[t['sponsor']] += 1
    top_comp = sorted(comp_counter.items(), key=lambda x: -x[1])[:12]

    pharma = sum(1 for t in trials if t['sponsor_class'] == 'INDUSTRY')
    gov    = sum(1 for t in trials if t['sponsor_class'] in ('NIH','U.S. FED'))
    acad   = total - pharma - gov

    # Year trend
    yc = defaultdict(int)
    for t in trials:
        if t['start_year'] and 2015 <= t['start_year'] <= 2026: yc[t['start_year']] += 1
    years = sorted(yc); yvals = [yc[y] for y in years]

    # Drug classes
    classes = {
        'Anti-HER2 (mAb/ADC)': ['trastuzumab','pertuzumab','t-dm1','emtansine','deruxtecan','t-dxd','ds-8201',
                                'kadcyla','enhertu','herceptin','perjeta','inetetamab','margetuximab'],
        'TKI Anti-HER2': ['neratinib','lapatinib','tucatinib','pyrotinib','afatinib'],
        'CDK4/6i': ['abemaciclib','palbociclib','ribociclib','dalpiciclib'],
        'Imuno-oncologia': ['pembrolizumab','atezolizumab','nivolumab','durvalumab','ipilimumab','camrelizumab'],
        'ADC emergentes': ['shr-a1811','arx788','mrg002','rc48','disitamab','bat8001','a166','dp303c','zanidatamab'],
        'PI3K/AKT/mTOR': ['alpelisib','everolimus','capivasertib','inavolisib','copanlisib'],
        'Hormonioterapia': ['fulvestrant','letrozole','anastrozole','exemestane','tamoxifen','giredestrant'],
        'Quimioterapia': ['paclitaxel','docetaxel','capecitabine','carboplatin','cyclophosphamide','epirubicin'],
    }
    class_count = defaultdict(int)
    for t in trials:
        for cls, kws in classes.items():
            if any(any(kw in d for kw in kws) for d in [x.lower() for x in t['drugs']]):
                class_count[cls] += 1
    class_sorted = sorted(class_count.items(), key=lambda x: -x[1])

    # Subtype × setting matrix
    sub_rows = ['HER2+ / HR+ (triplo positivo)', 'HER2+ / HR− (puro)', 'HR+ / HER2−',
                'Triplo Negativo (TNBC)', 'Não especificado']
    set_cols = ['Inicial / (Neo)adjuvante', 'Metastático / Avançado', 'Misto / Multi-estágio',
                'Metástase Cerebral (SNC)', 'Não especificado']
    set_cols_short = ['Inicial /\n(Neo)adj.', 'Metast./\nAvançado', 'Misto /\nMulti', 'SNC', 'N/E']
    matrix = [[0]*len(set_cols) for _ in sub_rows]
    for t in trials:
        if t['subtype'] in sub_rows and t['setting'] in set_cols:
            matrix[sub_rows.index(t['subtype'])][set_cols.index(t['setting'])] += 1
    sub_rows_short = ['HER2+/HR+', 'HER2+/HR−', 'HR+/HER2−', 'TNBC', 'N/E']

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 1 — COVER
    # ═══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 2 — ÍNDICE + METODOLOGIA
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("Índice")
    toc_items = [
        ("1.  Sumário Executivo", "3"),
        ("2.  Panorama Geral do Pipeline", "4"),
        ("3.  Concentração Geográfica da Pesquisa", "5"),
        ("4.  Análise por Indicação (subtipo × estágio)", "6"),
        ("5.  Paisagem Terapêutica — Fármacos e Classes", "8"),
        ("6.  Análise Competitiva — Patrocinadores", "9"),
        ("7.  Pipeline Emergente — ADCs e Novas Moléculas", "10"),
        ("8.  Presença no Brasil", "11"),
        ("9.  Análise Regulatória e Ciclo de Vida", "12"),
        ("10. Conclusões e Recomendações Estratégicas", "13"),
    ]
    toc_rows = [[Paragraph(t, S['toc']),
                 Paragraph(f"<font color='{C_GRAY}'>{p}</font>", S['toc'])] for t, p in toc_items]
    toc_tbl = Table(toc_rows, colWidths=[CONTENT_W-1.5*cm, 1.5*cm])
    toc_tbl.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 0.4, colors.HexColor(C_LIGHT_GRAY)),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
    ]))
    story.append(toc_tbl)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Metodologia e Escopo", S['h2']))
    story.append(callout(
        "<b>Fonte:</b> ClinicalTrials.gov (U.S. National Library of Medicine), API v2, coleta em 02/06/2026.  "
        "<b>Universo:</b> 697 ensaios intervencionais em câncer de mama relacionados a HER2, nas Fases 2, 3 e 4, "
        "com status ativo (recrutando, ativo/não-recrutando, não iniciado ou por convite).  "
        "<b>Classificação clínica:</b> cada estudo foi categorizado por <b>subtipo molecular</b> (HER2+, HR+/HER2−, "
        "TNBC) e por <b>estágio da doença</b> (inicial/(neo)adjuvante, metastático/avançado, metástase cerebral), "
        "a partir de processamento textual de condições, título, resumo e intervenções.  "
        "<b>Limitações:</b> o módulo de localizações geográficas não foi preservado na coleta — a presença no "
        "Brasil e a região do patrocinador são estimativas conservadoras (ver seções 3 e 8).",
        color=C_ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(callout(
        "<b>Como ler este relatório:</b> os números refletem a <b>atividade de pesquisa</b> (volume de estudos e "
        "capacidade de pacientes), não vendas ou participação de mercado. Um alto volume de estudos sinaliza "
        "intensidade competitiva e prioridade estratégica das empresas naquela indicação ou molécula.",
        color=C_PRIMARY_DARK, bg=C_LIGHT_BG))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 3 — SUMÁRIO EXECUTIVO
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("1.  Sumário Executivo")
    story.append(Paragraph(
        "Este relatório mapeia o <b>panorama global de ensaios clínicos em câncer de mama HER2-positivo</b>, "
        "com base em <b>697 estudos ativos</b> (Fases 2–4) e mais de <b>397 mil pacientes</b> planejados. "
        "A análise segmenta o pipeline por indicação clínica, paisagem terapêutica, concentração competitiva "
        "e geográfica, com foco nas implicações estratégicas para a indústria farmacêutica e na oportunidade "
        "ainda subexplorada do mercado brasileiro.", S['body']))
    story.append(Spacer(1, 0.3*cm))
    story.append(kpi_row([
        (f"{total}", "Estudos ativos", "Fases 2, 3 e 4"),
        (f"{recruiting}", "Recrutando", "Abertos a pacientes"),
        (f"{phase3}", "Em Fase 3", "Pipeline de registro"),
        (f"{total_enroll/1000:.0f}k", "Pacientes", "Capacidade planejada"),
        (f"{len(brazil_trials)}", "Com Brasil", "< 1% do pipeline"),
    ]))
    story.append(Spacer(1, 0.35*cm))

    story.append(Paragraph("Principais Achados Estratégicos", S['h2']))
    findings = [
        "<b>Pipeline em expansão acelerada:</b> os novos estudos por ano cresceram de ~19 (2019) para "
        "<b>135 (2025)</b> — alta superior a 7×. O semestre parcial de 2026 já soma 92 estudos, indicando "
        "que o recorde deve ser superado.",
        "<b>O foco migrou para a doença metastática:</b> a indicação <b>Metastático/Avançado lidera com "
        f"{setting_counts['Metastático / Avançado']['n']} estudos</b>, seguida de perto pela doença inicial/"
        f"(neo)adjuvante ({setting_counts['Inicial / (Neo)adjuvante']['n']}), que concentra a maior capacidade "
        "de pacientes (intenção curativa, estudos maiores).",
        "<b>ADCs redefinem o padrão de cuidado:</b> liderados por Trastuzumab Deruxtecan (T-DXd), os "
        "Anticorpo-Conjugados a Drogas são a classe de inovação mais dinâmica, com uma onda de candidatos "
        "asiáticos (SHR-A1811, ARX788, RC48) desafiando o paradigma.",
        f"<b>A China é o epicentro da pesquisa:</b> ao menos <b>{region_counts['China']} estudos "
        f"({100*region_counts['China']//total}%)</b> têm patrocinador chinês — mais que EUA e Europa juntos "
        "entre os classificáveis, sinalizando uma mudança no eixo global de P&D oncológico.",
        f"<b>Brasil sub-representado:</b> apenas <b>{len(brazil_trials)} estudos</b> com menção ao país "
        "(< 1% do pipeline), evidenciando uma oportunidade estratégica de atração de centros e investimento.",
    ]
    for f in findings:
        story.append(Paragraph(f"<font color='{C_ACCENT}'><b>•</b></font>  {f}", S['bullet']))
        story.append(Spacer(1, 0.08*cm))

    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("O Pipeline em um Relance — Estudos por Estágio Clínico", S['h3']))
    b_summary = hbar([k for k, _ in setting_order], [v['n'] for _, v in setting_order],
                     "", xlabel="Nº de estudos", color=C_ACCENT, figsize=(8, 2.7))
    story.append(make_img(b_summary, CONTENT_W, max_h=5.4*cm))
    story.append(caption("A doença metastática e a inicial/(neo)adjuvante respondem pela maioria do pipeline "
                         "ativo (detalhamento na seção 4)."))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 4 — PANORAMA GERAL
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("2.  Panorama Geral do Pipeline")
    b_status = donut([status_pt[k] for k in status_counts], list(status_counts.values()),
                     "Distribuição por Status", center_text=(str(total), "estudos"))
    b_phase  = donut(list(phase_counts.keys()), list(phase_counts.values()),
                     "Distribuição por Fase Clínica")
    story.append(two_col(b_status, b_phase))
    story.append(caption("Figura 1 — Status de recrutamento (esq.) e fase clínica (dir.) dos 697 estudos. "
                         "Metade está em recrutamento ativo; 30% em Fase 3 (estágio de registro)."))
    story.append(Spacer(1, 0.25*cm))
    b_trend = line_area(years, yvals, "Evolução Temporal — Novos Estudos por Ano de Início",
                        ylabel="Novos estudos", color=C_ACCENT)
    story.append(make_img(b_trend, CONTENT_W, max_h=6.4*cm))
    story.append(caption("Figura 2 — Novos ensaios iniciados por ano (2015–2026). Crescimento >7× na última década."))
    story.append(Spacer(1, 0.15*cm))
    story.append(callout(
        "<b>Nota:</b> os dados de 2026 são parciais (coleta em junho/2026). Os 92 estudos já registrados "
        "representam apenas o 1º semestre — em ritmo de superar o recorde de 135 estudos de 2025.",
        color=C_AMBER, bg="#FBF3E6", icon="⚠"))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 5 — CONCENTRAÇÃO GEOGRÁFICA
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("3.  Concentração Geográfica da Pesquisa")
    story.append(Paragraph(
        "A origem do patrocinador líder revela onde está sendo gerado o conhecimento clínico em HER2+. "
        "A classificação abaixo é uma <b>estimativa por heurística sobre o nome do patrocinador</b> "
        "(instituições e empresas reconhecidas); estudos não classificáveis aparecem como “Outros / N/D”.",
        S['body']))
    story.append(Spacer(1, 0.2*cm))
    b_region = donut([k for k, _ in region_order], [v for _, v in region_order],
                     "Estudos por Região do Patrocinador", figsize=(5.2, 4.2))
    # Sponsor category donut
    b_spcat = donut(['Indústria Farmacêutica', 'Academia / Hospitais', 'Governo / Agências'],
                    [pharma, acad, gov], "Patrocinadores por Categoria",
                    colors_list=[C_ACCENT, C_PRIMARY, C_PRIMARY_DARK], figsize=(5.2, 4.2))
    story.append(two_col(b_region, b_spcat))
    story.append(caption("Figura 3 — Região do patrocinador líder (esq.) e categoria institucional (dir.)."))
    story.append(Spacer(1, 0.25*cm))
    cn = region_counts['China']
    story.append(callout(
        f"<b>O eixo da pesquisa migrou para a Ásia.</b> Com pelo menos <b>{cn} estudos ({100*cn//total}%)</b>, "
        "a China supera EUA e Europa individualmente — e provavelmente é subestimada, pois parte do bucket "
        "“Outros / N/D” também é chinesa (farmacêuticas e hospitais regionais). Instituições como Fudan "
        "University, Henan Cancer Hospital e Sun Yat-Sen lideram em volume, combinando alta produtividade "
        "acadêmica com acesso a grandes populações de pacientes. <b>Implicação:</b> dados regulatórios "
        "relevantes serão crescentemente gerados na Ásia — o monitoramento competitivo precisa incluir "
        "publicações e agências regulatórias asiáticas.", color=C_ACCENT, icon="🌐"))
    story.append(Spacer(1, 0.2*cm))
    story.append(callout(
        "Cerca de dois terços dos estudos têm patrocínio acadêmico/hospitalar — muitos testando combinações, "
        "biossimilares e otimização de regimes já aprovados. A indústria farmacêutica concentra-se nos "
        "ativos proprietários de maior valor (ADCs, novas moléculas), tema das seções 5 a 7.",
        color=C_PRIMARY_DARK, bg=C_LIGHT_BG))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 6-7 — ANÁLISE POR INDICAÇÃO
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("4.  Análise por Indicação (subtipo × estágio)")
    story.append(Paragraph(
        "Para uma leitura clínica acionável, segmentamos o pipeline em dois eixos: o <b>subtipo molecular</b> "
        "(que define a biologia do tumor e a estratégia de droga) e o <b>estágio da doença</b> (que define o "
        "objetivo terapêutico — curativo vs. controle). Como esperado para uma busca centrada em HER2, "
        f"<b>{subtype_top_counts['HER2-positivo']} estudos ({100*subtype_top_counts['HER2-positivo']//total}%)</b> "
        "são HER2-positivos.", S['body']))
    story.append(Spacer(1, 0.2*cm))

    b_setting = treemap([k for k, _ in setting_order], [v['n'] for _, v in setting_order],
                        "Estudos por Estágio da Doença (área ∝ nº de estudos)",
                        short_labels=[setting_short.get(k, k) for k, _ in setting_order])
    story.append(make_img(b_setting, CONTENT_W, max_h=6.6*cm))
    story.append(caption("Figura 4 — Mapa de árvore do pipeline por estágio clínico. A doença metastática e a "
                         "inicial/(neo)adjuvante concentram a grande maioria dos estudos."))
    story.append(Spacer(1, 0.2*cm))

    b_subtype = donut([k for k in subtype_counts], list(subtype_counts.values()),
                      "Subtipo Molecular", figsize=(5.2, 4.2))
    # Setting enrollment bar
    b_set_enr = hbar([k for k, _ in setting_order], [v['enroll'] for _, v in setting_order],
                     "Pacientes Planejados por Estágio", xlabel="Pacientes", color=C_SECONDARY,
                     figsize=(6.2, 4.2))
    story.append(two_col(b_subtype, b_set_enr))
    story.append(caption("Figura 5 — Subtipo molecular (esq.) e capacidade de pacientes por estágio (dir.). "
                         "A doença inicial concentra a maior capacidade — estudos adjuvantes são grandes."))

    story.append(PageBreak())

    # Heatmap matrix
    story.append(Paragraph("Matriz Subtipo × Estágio", S['h2']))
    b_heat = heatmap(matrix, sub_rows_short, set_cols_short,
                     "Nº de Estudos por Subtipo Molecular e Estágio da Doença")
    story.append(make_img(b_heat, CONTENT_W, max_h=6.4*cm))
    story.append(caption("Figura 6 — Cruzamento entre subtipo e estágio. Concentra-se onde a competição é mais "
                         "intensa: HER2+ (triplo positivo e puro) na doença metastática e inicial."))
    story.append(Spacer(1, 0.25*cm))

    story.append(Paragraph("Resumo Quantitativo por Estágio Clínico", S['h2']))
    ind_rows = []
    for setting, vals in setting_order:
        ph3 = sum(1 for t in trials if t['setting'] == setting and 'PHASE3' in t['phase'])
        rec = sum(1 for t in trials if t['setting'] == setting and t['status'] == 'RECRUITING')
        ind_rows.append([setting, vals['n'], f"{vals['enroll']:,}", ph3, rec])
    story.append(table(["Estágio da doença", "Nº Estudos", "Pacientes Est.", "Fase 3", "Recrutando"],
                       ind_rows, [6.5*cm, 2.2*cm, 3.0*cm, 2.0*cm, 2.5*cm],
                       align_center_cols=[1,2,3,4]))
    story.append(Spacer(1, 0.25*cm))
    story.append(callout(
        "<b>Leitura estratégica:</b> a doença <b>metastática</b> é o campo de batalha competitivo mais ativo "
        "(maior nº de estudos, ciclos mais rápidos), enquanto a doença <b>inicial/(neo)adjuvante</b> é o "
        "território de maior valor de longo prazo (estudos grandes, intenção curativa, desfechos definitivos). "
        "A <b>metástase cerebral (SNC)</b>, embora pequena em volume, é um <i>unmet need</i> de alto valor "
        "onde TKIs como tucatinib e pyrotinib se diferenciam.", color=C_ACCENT, icon="🎯"))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 8 — PAISAGEM TERAPÊUTICA
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("5.  Paisagem Terapêutica — Fármacos e Classes")
    b_class = donut([k for k, _ in class_sorted], [v for _, v in class_sorted],
                    "Estudos por Classe Terapêutica", figsize=(5.4, 4.4))
    b_topdrug = hbar([d[0] for d in top_drugs], [d[1] for d in top_drugs],
                     "Top 15 Fármacos (nº de estudos)", xlabel="Estudos", color=C_PRIMARY_DARK,
                     figsize=(6.2, 4.6))
    story.append(two_col(b_class, b_topdrug))
    story.append(caption("Figura 7 — Classes terapêuticas (esq.) e fármacos mais frequentes (dir.). "
                         "Trastuzumab e pertuzumab seguem como espinha dorsal; ADCs e CDK4/6i em ascensão."))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Análise por Classe Terapêutica", S['h2']))
    drug_analysis = [
        ("Anti-HER2 (mAb / ADC)", C_ACCENT,
         "<b>Backbone</b> do tratamento. Trastuzumab e pertuzumab continuam como base, mas os <b>ADCs de "
         "nova geração</b> — liderados por T-DXd (AstraZeneca/Daiichi Sankyo) — estão redefinindo o padrão "
         "de cuidado na doença metastática e avançando para linhas mais precoces."),
        ("TKI Anti-HER2", C_PRIMARY_DARK,
         "Inibidores de tirosina quinase (tucatinib, pyrotinib, neratinib) com destaque em <b>metástase "
         "cerebral</b>. Pyrotinib domina na China; tucatinib avança no Ocidente."),
        ("CDK4/6 Inibidores", C_PRIMARY,
         "Investigados em combinação com anti-HER2 e hormonioterapia, testando se a eficácia em HR+/HER2− "
         "se traduz no contexto HER2+/HR+ (triplo positivo)."),
        ("Imuno-oncologia", C_SECONDARY,
         "Combinações de checkpoint inhibitors com anti-HER2; resultados mistos, com hipótese ativa no "
         "subgrupo PD-L1 alto."),
        ("ADCs Emergentes", "#3D9080",
         "A próxima geração (SHR-A1811, ARX788, RC48) está majoritariamente em desenvolvimento na China — "
         "concorrentes diretos de T-DXd, com cargas úteis e perfis de segurança diferenciados."),
    ]
    for name, col, txt in drug_analysis:
        r = Table([[Paragraph(name, ParagraphStyle('dc', fontName=FONT_BOLD, fontSize=8.5, textColor=colors.white)),
                    Paragraph(txt, S['body'])]], colWidths=[3.3*cm, CONTENT_W-3.3*cm])
        r.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,0), colors.HexColor(col)),
            ('BACKGROUND', (1,0), (1,0), colors.HexColor(C_HIGHLIGHT)),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor(C_PRIMARY)),
        ]))
        story.append(r); story.append(Spacer(1, 0.12*cm))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 9 — ANÁLISE COMPETITIVA
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("6.  Análise Competitiva — Patrocinadores")
    b_top = hbar([c[0][:38] for c in top_comp], [c[1] for c in top_comp],
                 "Top 12 Patrocinadores Globais", xlabel="Nº de estudos", color=C_PRIMARY, figsize=(8.2, 4.6))
    story.append(make_img(b_top, CONTENT_W, max_h=7.0*cm))
    story.append(caption("Figura 8 — Ranking de patrocinadores por nº de estudos ativos. "
                         "Instituições acadêmicas chinesas lideram em volume."))
    story.append(Spacer(1, 0.25*cm))

    story.append(Paragraph("Posicionamento Estratégico — Grandes Farmacêuticas", S['h2']))
    pharma_detail = [
        ("AstraZeneca", 20, "T-DXd (metastático → early)", "Fase 3 / Comercial", "Líder global em ADCs"),
        ("Roche", 18, "Trastuzumab, Pertuzumab, Giredestrant", "Fase 3 / Comercial", "Fundador do padrão de cuidado"),
        ("Novartis", 12, "Alpelisib + anti-HER2, CDK4/6", "Fase 2/3", "Foco em combinações"),
        ("Eli Lilly", 11, "Abemaciclib", "Fase 3 / Comercial", "Liderança em CDK4/6"),
        ("Pfizer / Seagen", 10, "Palbociclib, Tucatinib", "Fase 2/3", "TKI + CDK4/6"),
        ("MSD (Merck)", 8, "Pembrolizumab (IO + anti-HER2)", "Fase 2/3", "Imuno-oncologia"),
    ]
    story.append(table(["Empresa", "Estudos", "Foco Principal", "Estágio", "Diferencial"],
                       pharma_detail, [3.0*cm, 1.5*cm, 4.8*cm, 2.7*cm, 4.2*cm],
                       align_center_cols=[1]))
    story.append(Spacer(1, 0.25*cm))
    story.append(callout(
        "<b>Dois jogos paralelos:</b> as <b>Big Pharma ocidentais</b> (AstraZeneca, Roche, Novartis, Lilly, "
        "Pfizer) competem por ativos proprietários de alto valor — ADCs, TKIs seletivos e combinações com "
        "CDK4/6. Em paralelo, o <b>ecossistema acadêmico/farmacêutico chinês</b> gera volume massivo de "
        "estudos, incluindo ADCs concorrentes e biossimilares, com impacto regulatório crescente no maior "
        "mercado oncológico do mundo.", color=C_ACCENT, icon="💡"))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 10 — PIPELINE EMERGENTE
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("7.  Pipeline Emergente — ADCs e Novas Moléculas")
    story.append(Paragraph(
        "Os Anticorpos Conjugados a Drogas (ADCs) são o segmento de <b>maior dinamismo inovador</b> no "
        "pipeline HER2+. A tabela consolida os principais ADCs em investigação clínica ativa na base.", S['body']))
    story.append(Spacer(1, 0.2*cm))

    adc_kw = ['deruxtecan','t-dxd','ds-8201','shr-a1811','arx788','mrg002','rc48','disitamab','bat8001',
              'a166','dp303c','datopotamab','dato-dxd']
    # Canonical display name per known ADC (case-insensitive merge)
    adc_canon = {
        'trastuzumab deruxtecan': 'Trastuzumab Deruxtecan', 't-dxd': 'Trastuzumab Deruxtecan',
        'ds-8201': 'Trastuzumab Deruxtecan', 'fam-trastuzumab deruxtecan': 'Trastuzumab Deruxtecan',
        'trastuzumab emtansine': 'Trastuzumab Emtansine', 't-dm1': 'Trastuzumab Emtansine',
        'ado-trastuzumab emtansine': 'Trastuzumab Emtansine',
        'datopotamab deruxtecan': 'Datopotamab Deruxtecan', 'dato-dxd': 'Datopotamab Deruxtecan',
        'patritumab deruxtecan': 'Patritumab Deruxtecan',
        'disitamab vedotin': 'Disitamab Vedotin', 'rc48': 'Disitamab Vedotin',
        'shr-a1811': 'SHR-A1811', 'arx788': 'ARX788', 'mrg002': 'MRG002',
        'a166': 'A166', 'dp303c': 'DP303c', 'bat8001': 'BAT8001',
    }
    def canon_adc(name):
        n = name.strip().lower()
        for key, disp in adc_canon.items():
            if key in n:
                return disp
        return name.strip().title()[:26]

    adc_compound = defaultdict(list)
    for t in trials:
        matched = [d for d in t['drugs'] if any(kw in d.lower() for kw in adc_kw)
                   or ('emtansine' in d.lower())]
        if matched:
            adc_compound[canon_adc(matched[0])].append(t)
    adc_rows = []
    for comp, ts in sorted(adc_compound.items(), key=lambda x: -len(x[1]))[:10]:
        sponsors = sorted(set(t['sponsor'] for t in ts))
        phases = sorted(set(t['phase_norm'] for t in ts))
        enr = sum(t['enrollment'] for t in ts)
        adc_rows.append([comp, len(ts), ', '.join(phases[:2]), sponsors[0][:26], f"{enr:,}"])
    story.append(Paragraph("ADCs em Investigação Clínica Ativa", S['h3']))
    story.append(table(["Composto (ADC)", "Estudos", "Fases", "Patrocinador (1º)", "Pacientes"],
                       adc_rows, [4.0*cm, 1.6*cm, 2.4*cm, 5.0*cm, 2.2*cm], align_center_cols=[1,4]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Outras Terapias Emergentes de Destaque", S['h3']))
    emerging = [
        ("Trastuzumab Deruxtecan", "ADC HER2 (DXd)", "AstraZeneca / Daiichi", "Comercial / Fase 3",
         "Redefine o padrão em metastático; expandindo para HER2-low e early"),
        ("SHR-A1811", "ADC HER2", "Jiangsu Hengrui", "Fase 2/3",
         "Principal concorrente asiático de T-DXd; dados promissores"),
        ("Zanidatamab", "Bispecífico HER2", "Zymeworks / Jazz", "Fase 2/3",
         "Anticorpo bispecífico com mecanismo duplo de ligação"),
        ("Tucatinib", "TKI HER2-seletivo", "Seagen (Pfizer)", "Fase 2/3",
         "Alta seletividade; eficaz em metástase cerebral"),
        ("Pyrotinib", "TKI pan-HER", "Hengrui", "Fase 2/3",
         "Dominante na China; dados maduros de Fase 3"),
        ("Margetuximab", "Anti-HER2 (Fc-otimizado)", "MacroGenics", "Fase 3",
         "Engenharia de Fc para maior atividade imune; aprovado FDA"),
    ]
    story.append(table(["Molécula", "Classe", "Empresa", "Estágio", "Descrição"],
                       emerging, [3.0*cm, 2.6*cm, 2.8*cm, 2.4*cm, 5.4*cm]))
    story.append(Spacer(1, 0.25*cm))
    story.append(callout(
        "<b>Tese de inovação:</b> a competição em HER2+ está se deslocando de “qual anti-HER2” para “qual ADC” — "
        "e, dentro dos ADCs, para a diferenciação por carga útil, taxa droga:anticorpo (DAR) e perfil de "
        "segurança. A entrada de candidatos asiáticos pressiona preço e acelera o ciclo de inovação global.",
        color=C_PRIMARY_DARK, bg=C_LIGHT_BG, icon="🧬"))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 11 — PRESENÇA NO BRASIL
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("8.  Presença no Brasil")
    story.append(callout(
        "<b>Nota metodológica:</b> a coleta não preservou o módulo de localizações (centros por país) para "
        "reduzir o tamanho do banco. A identificação de estudos com o Brasil foi feita por <b>busca textual "
        "no JSON</b> — portanto é <b>conservadora e possivelmente subestimada</b>. Recomenda-se recoleta com "
        "o módulo <i>contactsLocationsModule</i> e cruzamento com o REBEC para o quadro geográfico completo.",
        color=C_AMBER, bg="#FBF3E6", icon="⚠"))
    story.append(Spacer(1, 0.25*cm))
    story.append(Paragraph(
        f"Foram identificados <b>{len(brazil_trials)} estudos</b> com menção ao Brasil:", S['body']))
    story.append(Spacer(1, 0.2*cm))

    brazil_details = [
        ("NCT03155997", "Abemaciclib + Terapia Endócrina pós-cirurgia (monarchE)", "Eli Lilly",
         "Ativo / Não Recrutando", "Fase 3", "5.637",
         "Brasil como local de recrutamento ativo (144 pacientes na análise basal)"),
        ("NCT02763566", "Abemaciclib em Câncer de Mama (monarcHER)", "Eli Lilly",
         "Ativo / Não Recrutando", "Fase 3", "463",
         "Brasil incluído com 21 pacientes no grupo basal"),
        ("NCT04576455", "Giredestrant vs. Monoterapia Endócrina (acelERA)", "Roche",
         "Ativo / Não Recrutando", "Fase 2", "303",
         "Brasil entre países participantes (indicação HR+/HER2−)"),
        ("NCT04208178", "Alpelisib + Trastuzumab + Pertuzumab (mutação PIK3CA)", "Novartis",
         "Ativo / Não Recrutando", "Fase 3", "19",
         "Brasil removido da lista de países durante o estudo"),
    ]
    for nct, title_br, sp_br, status_br, ph_br, enr_br, obs in brazil_details:
        head = Paragraph(f"<b><font color='white'>{nct}</font></b><br/>"
                         f"<font size='7' color='{C_HIGHLIGHT}'>{ph_br}</font>",
                         ParagraphStyle('bh', fontName=FONT_BOLD, fontSize=8.3, leading=12,
                                        textColor=colors.white, alignment=TA_CENTER))
        meta = Paragraph(f"<b>{title_br}</b><br/>"
                         f"<font size='7.5' color='{C_GRAY}'>Status: {status_br}  ·  "
                         f"Pacientes: {enr_br}  ·  Patrocinador: {sp_br}</font><br/>"
                         f"<font size='7.5'><i>{obs}</i></font>", S['body'])
        card = Table([[head, meta]], colWidths=[3.0*cm, CONTENT_W-3.0*cm])
        card.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,0), colors.HexColor(C_ACCENT)),
            ('BACKGROUND', (1,0), (1,0), colors.HexColor(C_HIGHLIGHT)),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor(C_PRIMARY_DARK)),
        ]))
        story.append(card); story.append(Spacer(1, 0.18*cm))

    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("Oportunidade Estratégica para o Brasil", S['h2']))
    story.append(callout(
        "O Brasil é uma <b>oportunidade significativamente subutilizada</b> no pipeline HER2+. Com apenas "
        "4 estudos em 697 (< 1%), a presença nacional está muito aquém do potencial do país — população "
        "expressiva, alta incidência e infraestrutura oncológica de referência (INCA, A.C. Camargo, "
        "Sírio-Libanês, Albert Einstein, HCor, entre outros). <b>Recomendação:</b> mapeamento proativo via "
        "REBEC, articulação com patrocinadores globais para inclusão de centros brasileiros em estudos "
        "Fase 2/3 ainda em <i>site selection</i>, e posicionamento do país como hub regional de pesquisa.",
        color=C_CORAL, bg="#FBEEE9", icon="🇧🇷"))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 12 — ANÁLISE REGULATÓRIA
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("9.  Análise Regulatória e Ciclo de Vida do Pipeline")
    story.append(Paragraph(
        "Esta seção avalia a <b>maturidade do pipeline</b> — estudos Fase 3 (pré-registro) com maior "
        "potencial de impacto regulatório — e o horizonte de geração de dados dos estudos em recrutamento.",
        S['body']))
    story.append(Spacer(1, 0.2*cm))

    p3 = sorted([t for t in trials if 'PHASE3' in t['phase']], key=lambda x: -x['enrollment'])[:9]
    p3_rows = []
    for t in p3:
        ds = ', '.join(t['drugs'][:2]) + ('…' if len(t['drugs']) > 2 else '')
        p3_rows.append([t['nct_id'],
                        (t['title'][:48] + '…') if len(t['title']) > 48 else t['title'],
                        t['sponsor'][:22], ds[:26],
                        f"{t['enrollment']:,}", t['start_date'][:7] if t['start_date'] else 'N/D'])
    story.append(Paragraph("Top 9 Estudos Fase 3 por Capacidade de Pacientes", S['h3']))
    story.append(table(["NCT ID", "Título (resumido)", "Patrocinador", "Fármacos", "Pacientes", "Início"],
                       p3_rows, [2.1*cm, 5.0*cm, 2.6*cm, 2.9*cm, 1.7*cm, 1.4*cm],
                       align_center_cols=[4,5], font=7.2))
    story.append(Spacer(1, 0.2*cm))

    # Recruitment horizon + enrollment scale, side by side
    yf = defaultdict(int)
    for t in trials:
        if t['status'] == 'RECRUITING' and t['primary_completion']:
            try:
                y = int(t['primary_completion'][:4])
                if 2026 <= y <= 2030: yf[y] += 1
            except: pass
    b_future = line_area(sorted(yf), [yf[y] for y in sorted(yf)],
                         "Horizonte de Conclusão Primária (estudos recrutando)",
                         ylabel="Nº de estudos", color=C_PRIMARY_DARK, annotate_last_n=5, figsize=(5.6, 3.6))
    enrolls = [t['enrollment'] for t in trials if t['enrollment'] > 0]
    b_enr = hist_enrollment(enrolls, "Distribuição por Tamanho (enrollment)")
    story.append(two_col(b_future, b_enr))
    story.append(caption("Figura 9 — Horizonte de leitura de dados (esq.): o pico de 2026–2027 antecipa uma onda "
                         "de resultados. Figura 10 — Tamanho dos estudos (dir.): predominam estudos pequenos/médios "
                         "(Fase 2); poucos megaestudos adjuvantes concentram a maior capacidade."))
    story.append(Spacer(1, 0.2*cm))
    story.append(callout(
        "<b>Síntese regulatória:</b> com 208 estudos em Fase 3 e um pico de leituras previsto para 2026–2027, "
        "os próximos 24 meses devem trazer múltiplos marcos capazes de redefinir o padrão de cuidado — "
        "especialmente na doença metastática e na expansão de ADCs para linhas mais precoces.",
        color=C_ACCENT))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 13 — CONCLUSÕES E RECOMENDAÇÕES
    # ═══════════════════════════════════════════════════════════════════════
    story += H1("10.  Conclusões e Recomendações Estratégicas")
    story.append(Paragraph(
        "Com base na análise de 697 ensaios clínicos ativos em câncer de mama HER2+, destacamos as "
        "recomendações prioritárias para a tomada de decisão executiva:", S['body']))
    story.append(Spacer(1, 0.25*cm))

    recs = [
        ("Monitorar a corrida dos ADCs", C_ACCENT,
         "T-DXd já redefine o padrão em metastático e avança para linhas precoces; SHR-A1811, ARX788 e RC48 "
         "formam a próxima onda (sobretudo asiática). <b>Ação:</b> alertas regulatórios e de publicação "
         "dedicados a estes compostos, incluindo agências da China, Japão e Coreia."),
        ("Capturar valor nas combinações CDK4/6 + anti-HER2", C_PRIMARY_DARK,
         "Dezenas de estudos testam essa combinação no subgrupo triplo positivo. <b>Ação:</b> acompanhar "
         "leituras de 2026–2027 (ver Figura 9) para antecipar reposicionamento de portfólio."),
        ("Ativar centros brasileiros", C_CORAL,
         "Presença < 1% do pipeline global representa oportunidade competitiva clara. <b>Ação:</b> mapear "
         "centros tier-1 nacionais e abrir diálogo com patrocinadores globais em fase de seleção de sites."),
        ("Construir inteligência sobre metástase cerebral (SNC)", C_SECONDARY,
         "Volume baixo, mas <i>unmet need</i> alto, onde TKIs (tucatinib, pyrotinib) se diferenciam. "
         "<b>Ação:</b> avaliar protocolo nacional específico e parcerias acadêmicas."),
        ("Estabelecer vigilância competitiva sobre a China", "#3D9080",
         "O eixo de P&D migrou para a Ásia (≥36% dos estudos). <b>Ação:</b> incluir periódicos e registros "
         "regulatórios chineses no monitoramento contínuo de literatura e pipeline."),
    ]
    for i, (title_rec, col, txt) in enumerate(recs, 1):
        r = Table([[Paragraph(str(i), ParagraphStyle('n', fontName=FONT_BOLD, fontSize=15,
                                                      textColor=colors.white, alignment=TA_CENTER)),
                    Paragraph(f"<b>{title_rec}</b><br/>{txt}", S['body'])]],
                  colWidths=[1.1*cm, CONTENT_W-1.1*cm])
        r.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,0), colors.HexColor(col)),
            ('BACKGROUND', (1,0), (1,0), colors.HexColor(C_HIGHLIGHT)),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 9),
            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor(col)),
        ]))
        story.append(r); story.append(Spacer(1, 0.15*cm))

    story.append(Spacer(1, 0.2*cm))
    story.append(HRFlowable(width=CONTENT_W, thickness=1, color=colors.HexColor(C_PRIMARY), spaceAfter=8))
    story.append(Paragraph("Próximos Passos Recomendados", S['h2']))
    for step in [
        "Recoleta dos dados preservando o módulo de localizações para análise geográfica completa",
        "Cruzamento com o REBEC para identificar estudos registrados no Brasil",
        "Monitoramento trimestral de novos registros nas indicações e moléculas prioritárias",
        "Análise de endpoints dos estudos Fase 3 para antecipar marcos regulatórios (2026–2027)",
        "Mapeamento de KOLs associados aos estudos de maior impacto, com foco em Ásia e Brasil",
    ]:
        story.append(Paragraph(f"→  {step}", S['bullet']))

    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=colors.HexColor(C_LIGHT_GRAY)))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        f"<b>Fontes:</b> ClinicalTrials.gov (U.S. National Library of Medicine).  <b>Coleta:</b> 02/06/2026.  "
        f"<b>Análise:</b> Pesquisa e Dados.  <b>Metodologia:</b> API v2; filtros Fase 2/3/4, tipo "
        "Interventional, status ativo/recrutando; classificação clínica por processamento textual.  "
        "Relatório de uso interno exclusivo e confidencial — gerado em " + REPORT_MONTH + ".",
        S['body_small']))

    # BUILD
    doc.build(story, onFirstPage=cover_page, onLaterPages=page_decoration)


if __name__ == "__main__":
    print("Carregando dados…")
    trials = load_data()
    print(f"  {len(trials)} estudos carregados.")
    print("Gerando relatório PDF…")
    build(trials)
    print(f"  Relatório salvo em: {PDF_PATH}")
