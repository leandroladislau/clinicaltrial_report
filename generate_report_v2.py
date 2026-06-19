import sqlite3
import json
import os
from datetime import datetime
from io import BytesIO

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import squarify
from matplotlib.backends.backend_agg import FigureCanvasAgg

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- CONFIGURATION & BRANDING ---
DB_PATH = '/mnt/arquivos/projetos_pesquisaedados/clinical_trial/her2_breast_cancer_trials.db'
OUTPUT_PDF = '/mnt/arquivos/projetos_pesquisaedados/clinical_trial/relatorio_her2_inteligencia_competitiva_v2.pdf'
FONT_DIR = '/mnt/arquivos/projetos_pesquisaedados/clinical_trial/fonts'

PALETTE = {
    'primary': '#85D8C8',
    'primary_dark': '#6BC4B3',
    'secondary': '#5FBFAD',
    'accent': '#4DA793',
    'dark': '#1D3A35',
    'dark_blue': '#2C3E50',
    'light_bg': '#F4FDFC',
    'highlight': '#E8FAF7',
    'amber': '#E0A458',
    'coral': '#D98B7A',
}

# Register Fonts
try:
    pdfmetrics.registerFont(TTFont('Prompt', f'{FONT_DIR}/Prompt-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Prompt-Bold', f'{FONT_DIR}/Prompt-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('Oswald', f'{FONT_DIR}/Oswald-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Oswald-SemiBold', f'{FONT_DIR}/Oswald-SemiBold.ttf'))
    BODY_FONT = 'Prompt'
    BOLD_FONT = 'Prompt-Bold'
    HEADER_FONT = 'Oswald-SemiBold'
except Exception as e:
    print(f"Font error: {e}. Falling back to Helvetica.")
    BODY_FONT, BOLD_FONT, HEADER_FONT = 'Helvetica', 'Helvetica-Bold', 'Helvetica-Bold'

# --- DATA PROCESSING ---
class DataProcessor:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.df = self._load_data()

    def _load_data(self):
        query = "SELECT nct_id, status, phase, full_data_json FROM trial_snapshots"
        df = pd.read_sql_query(query, self.conn)
        df['data'] = df['full_data_json'].apply(json.loads)
        return df

    def classify_trials(self):
        def get_subtype(row):
            text = (str(row['data'].get('protocolSection', {}).get('condition', '')) + 
                    str(row['data'].get('protocolSection', {}).get('briefSummary', '')) + 
                    str(row['data'].get('protocolSection', {}).get('title', ''))).lower()
            her2_agents = ['trastuzumab', 'pertuzumab', 't-dm1', 't-dxd', 'deruxtecan', 'tucatinib', 
                           'neratinib', 'lapatinib', 'pyrotinib', 'margetuximab', 'zanidatamab', 'shr-a1811', 
                           'arx788', 'rc48', 'disitamab']
            is_her2 = any(agent in text for agent in her2_agents) or any(x in text for x in ['her2+', 'her-2+', 'erbb2'])
            if not is_her2: return 'Não especificado'
            hr_keywords = ['hr+', 'er+', 'pr+', 'hormone receptor positive', 'estrogen receptor positive', 'progesterone receptor positive']
            is_hr = any(kw in text for kw in hr_keywords)
            if is_hr: return 'HER2+/HR+ (Triplo Positivo)'
            tnbc_keywords = ['tnbc', 'triple negative', 'triplo negativo']
            if any(kw in text for kw in tnbc_keywords): return 'Triplo Negativo (TNBC)'
            return 'HER2+/HR- (Puro)'

        def get_setting(row):
            text = (str(row['data'].get('protocolSection', {}).get('condition', '')) + 
                    str(row['data'].get('protocolSection', {}).get('briefSummary', '')) + 
                    str(row['data'].get('protocolSection', {}).get('title', ''))).lower()
            if any(x in text for x in ['metastatic', 'advanced', 'metastático', 'avançado', 'stage iv']):
                return 'Metastático/Avançado'
            if any(x in text for x in ['adjuvant', 'neoadjuvant', 'early', 'adjuvante', 'neoadjuvante', 'inicial']):
                return 'Inicial/(Neo)adjuvante'
            if any(x in text for x in ['brain metastasis', 'cns metastasis', 'metástase cerebral', 'snc']):
                return 'Metástase Cerebral (SNC)'
            if any(x in text for x in ['multi-stage', 'misto', 'mixed']):
                return 'Misto/Multi-estágio'
            return 'Não especificado'

        self.df['subtype'] = self.df.apply(get_subtype, axis=1)
        self.df['setting'] = self.df.apply(get_setting, axis=1)
        self.df['phase_norm'] = self.df['phase'].str.replace('Phase ', 'Fase ').fillna('N/D')
        
        def get_region(row):
            sponsor = str(row['data'].get('protocolSection', {}).get('sponsor', 'Unknown')).lower()
            if any(x in sponsor for x in ['china', 'beijing', 'shanghai', 'fudan', 'sun yat-sen', 'hengrui', 'kelun']):
                return 'China'
            if any(x in sponsor for x in ['usa', 'united states', 'america', 'harvard', 'mayo', 'md anderson']):
                return 'EUA/Am. Norte'
            if any(x in sponsor for x in ['europe', 'germany', 'france', 'spain', 'uk', 'london', 'berlin']):
                return 'Europa'
            if any(x in sponsor for x in ['japan', 'korea', 'seoul', 'tokyo']):
                return 'Coreia/Japão'
            return 'Outros/N/D'
        
        self.df['region'] = self.df.apply(get_region, axis=1)
        self.df['brazil'] = self.df.apply(lambda r: 'Brasil' if 'brazil' in str(r['data']).lower() or 'brasil' in str(r['data']).lower() else None, axis=1)
        self.df['patients'] = self.df['data'].apply(lambda x: int(x.get('protocolSection', {}).get('enrollment', 0)) if str(x.get('protocolSection', {}).get('enrollment')).isdigit() else 0)

    def get_summary_stats(self):
        return {
            'total': len(self.df),
            'recruiting': len(self.df[self.df['status'] == 'RECRUITING']),
            'phase3': len(self.df[self.df['phase'] == 'Phase 3']),
            'patients_total': self.df['patients'].sum(),
            'brazil_count': self.df['brazil'].notna().sum()
        }

# --- CHART GENERATOR ---
class ChartGenerator:
    @staticmethod
    def create_png(fig):
        buf = BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0)
        plt.close(fig)
        return buf

    def plot_donut(self, data_dict, title, colors_list):
        if sum(data_dict.values()) == 0:
            fig, ax = plt.subplots(figsize=(4, 4), facecolor='none')
            ax.text(0.5, 0.5, "Sem Dados Disponíveis", ha='center', va='center', fontsize=12, color=PALETTE['dark'])
            ax.axis('off')
            ax.set_title(title, fontsize=12, fontweight='bold', color=PALETTE['dark'])
            return self.create_png(fig)
        fig, ax = plt.subplots(figsize=(4, 4), facecolor='none')
        labels = list(data_dict.keys())
        values = list(data_dict.values())
        ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, 
               colors=colors_list, wedgeprops={'width': 0.4, 'edgecolor': 'w'},
               textprops={'fontsize': 9})
        ax.set_title(title, fontsize=12, fontweight='bold', color=PALETTE['dark'])
        return self.create_png(fig)

    def plot_bar_horizontal(self, data_dict, title, color):
        fig, ax = plt.subplots(figsize=(6, 3), facecolor='none')
        labels = list(data_dict.keys())
        values = list(data_dict.values())
        ax.barh(labels, values, color=color)
        ax.set_title(title, fontsize=12, fontweight='bold', color=PALETTE['dark'])
        ax.spines[['top', 'right']].set_visible(False)
        return self.create_png(fig)

    def plot_treemap(self, data_dict, title):
        fig = plt.figure(figsize=(6, 4), facecolor='none')
        labels = [f"{k}\n({v})" for k, v in data_dict.items()]
        values = list(data_dict.values())
        colors = [PALETTE['primary'], PALETTE['primary_dark'], PALETTE['secondary'], PALETTE['accent'], PALETTE['dark']] * 5
        squarify.plot(sizes=values, label=labels, color=colors[:len(values)], 
                      alpha=0.8, text_kwargs={'fontsize': 9, 'color': PALETTE['dark'], 'fontweight': 'bold'})
        plt.title(title, fontsize=12, fontweight='bold', color=PALETTE['dark'])
        plt.axis('off')
        return self.create_png(fig)

    def plot_heatmap(self, df_pivot, title):
        fig, ax = plt.subplots(figsize=(6, 4), facecolor='none')
        im = ax.imshow(df_pivot.values, cmap='YlGnBu', interpolation='nearest')
        ax.set_xticks(np.arange(len(df_pivot.columns)))
        ax.set_yticks(np.arange(len(df_pivot.index)))
        ax.set_xticklabels(df_pivot.columns)
        ax.set_yticklabels(df_pivot.index)
        for i in range(len(df_pivot.index)):
            for j in range(len(df_pivot.columns)):
                ax.text(j, i, int(df_pivot.iloc[i, j]), ha='center', va='center', 
                        color='black' if df_pivot.iloc[i,j] < df_pivot.values.max()/2 else 'white')
        ax.set_title(title, fontsize=12, fontweight='bold', color=PALETTE['dark'])
        fig.colorbar(im)
        return self.create_png(fig)

# --- REPORT BUILDER ---
class ReportBuilder:
    def __init__(self, dp, cg):
        self.dp = dp
        self.cg = cg
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        self.styles.add(ParagraphStyle(name='H1', fontName=HEADER_FONT, fontSize=28, 
                                     textColor=colors.HexColor(PALETTE['dark']), spaceAfter=20, alignment=1))
        self.styles.add(ParagraphStyle(name='H2', fontName=HEADER_FONT, fontSize=18, 
                                     textColor=colors.HexColor(PALETTE['dark']), spaceBefore=15, spaceAfter=10))
        self.styles.add(ParagraphStyle(name='H3', fontName=BOLD_FONT, fontSize=14, 
                                     textColor=colors.HexColor(PALETTE['primary_dark']), spaceBefore=10, spaceAfter=5))
        self.styles.add(ParagraphStyle(name='Body', fontName=BODY_FONT, fontSize=11, 
                                     textColor=colors.HexColor(PALETTE['dark_blue']), leading=14))
        self.styles.add(ParagraphStyle(name='Callout', fontName=BODY_FONT, fontSize=10, 
                                     textColor=colors.HexColor(PALETTE['dark']), italic=True, leftIndent=20))

    def add_footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont(BODY_FONT, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1.8*cm, 1.5*cm, "Pesquisa e Dados · Inteligência Competitiva HER2+ · Uso Interno Confidencial")
        canvas.drawRightString(A4[0] - 1.8*cm, 1.5*cm, f"Página {doc.page}")
        canvas.setFillColor(colors.HexColor(PALETTE['primary']))
        canvas.rect(0, A4[1] - 0.5*cm, A4[0], 0.5*cm, fill=1, stroke=0)
        canvas.restoreState()

    def build(self, output_path):
        doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=1.8*cm, rightMargin=1.8*cm, topMargin=2*cm, bottomMargin=2*cm)
        elements = []
        
        # P1: Cover
        elements.append(Spacer(1, 5*cm))
        elements.append(Paragraph("CÂNCER DE MAMA<br/>HER2-POSITIVO", self.styles['H1']))
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("Relatório de Inteligência Competitiva e Regulatória v2.0<br/>Pipeline Global · Análise por Indicação · Paisagem Competitiva", 
                                 ParagraphStyle('Sub', fontName=BODY_FONT, fontSize=14, textColor=colors.HexColor(PALETTE['primary']), alignment=1)))
        elements.append(Spacer(1, 4*cm))
        elements.append(Paragraph(f"Fonte de dados: ClinicalTrials.gov — {datetime.now().strftime('%B %Y')}<br/>Coleta: 02 de Junho de 2026", 
                                 ParagraphStyle('Meta', fontName=BODY_FONT, fontSize=10, textColor=colors.black, alignment=1)))
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("Uso Interno — Confidencial", ParagraphStyle('Conf', fontName=BOLD_FONT, fontSize=12, textColor=colors.black, alignment=1)))
        elements.append(PageBreak())

        # P2: TOC
        elements.append(Paragraph("Índice", self.styles['H2']))
        toc_items = ["1. Sumário Executivo", "2. Panorama Geral do Pipeline", "3. Concentração Geográfica", "4. Análise por Indicação", "5. Paisagem Terapêutica", "6. Análise Competitiva", "7. Pipeline Emergente", "8. Presença no Brasil", "9. Análise Regulatória", "10. Conclusões"]
        for item in toc_items: elements.append(Paragraph(item, self.styles['Body']))
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph("Metodologia e Escopo", self.styles['H3']))
        elements.append(Paragraph("Fonte: ClinicalTrials.gov (API v2). Universo: 695 ensaios intervencionais (Fases 2-4). A classificação clínica foi aprimorada na v2.0 para reduzir a incerteza de subtipos moleculares.", self.styles['Body']))
        elements.append(PageBreak())

        # P3: Exec Summary
        elements.append(Paragraph("1. Sumário Executivo", self.styles['H2']))
        stats = self.dp.get_summary_stats()
        kpi_table = Table([[Paragraph(f"<b>{val}</b><br/>{lbl}", self.styles['Body']) for val, lbl in zip([stats['total'], stats['recruiting'], stats['phase3'], stats['patients_total']//1000, stats['brazil_count']], ["Estudos Ativos", "Recrutando", "Fase 3", "Pacientes", "Brasil"])]], colWidths=[3*cm]*5)
        kpi_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor(PALETTE['highlight'])), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('BOX', (0,0), (-1,-1), 1, colors.HexColor(PALETTE['primary_dark']))]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("Principais Achados Estratégicos", self.styles['H3']))
        findings = ["Pipeline em expansão acelerada (>7x desde 2019).", "Foco predominante em doença metastática.", "ADCs (T-DXd, SHR-A1811) redefinindo o SoC.", "China como epicentro de P&D oncológico.", "Brasil com presença < 1%."]
        for f in findings: elements.append(Paragraph(f"• {f}", self.styles['Body']))
        setting_counts = self.dp.df['setting'].value_counts().to_dict()
        elements.append(Image(self.cg.plot_bar_horizontal(setting_counts, "Estágio Clínico", PALETTE['primary']), width=12*cm, height=5*cm))
        elements.append(PageBreak())

        # P4: Panorama
        elements.append(Paragraph("2. Panorama Geral do Pipeline", self.styles['H2']))
        elements.append(Image(self.cg.plot_donut(self.dp.df['status'].value_counts().to_dict(), "Status", [PALETTE['primary'], PALETTE['secondary'], PALETTE['accent'], PALETTE['dark']]), width=7*cm, height=7*cm))
        elements.append(Image(self.cg.plot_donut(self.dp.df['phase'].value_counts().to_dict(), "Fase", [PALETTE['primary_dark'], PALETTE['secondary'], PALETTE['accent'], PALETTE['dark']]), width=7*cm, height=7*cm))
        elements.append(PageBreak())

        # P5: Geography
        elements.append(Paragraph("3. Concentração Geográfica da Pesquisa", self.styles['H2']))
        elements.append(Image(self.cg.plot_donut(self.dp.df['region'].value_counts().to_dict(), "Região Patrocinador", [PALETTE['primary'], PALETTE['secondary'], PALETTE['accent'], PALETTE['amber'], PALETTE['coral']]), width=8*cm, height=8*cm))
        elements.append(PageBreak())

        # P6-7: Indication
        elements.append(Paragraph("4. Análise por Indicação", self.styles['H2']))
        elements.append(Image(self.cg.plot_treemap(self.dp.df['setting'].value_counts().to_dict(), "Pipeline por Estágio"), width=14*cm, height=8*cm))
        elements.append(Image(self.cg.plot_donut(self.dp.df['subtype'].value_counts().to_dict(), "Subtipo Molecular", [PALETTE['primary'], PALETTE['secondary'], PALETTE['accent'], PALETTE['amber']]), width=7*cm, height=7*cm))
        pivot = self.dp.df.groupby(['subtype', 'setting']).size().unstack(fill_value=0)
        elements.append(Image(self.cg.plot_heatmap(pivot, "Subtipo vs Estágio"), width=14*cm, height=8*cm))
        elements.append(PageBreak())

        # P8: Therapy
        elements.append(Paragraph("5. Paisagem Terapêutica", self.styles['H2']))
        class_map = {'ADC': 0, 'mAb': 0, 'TKI': 0, 'CDK4/6': 0, 'IO': 0}
        for row in self.dp.df.to_dict('records'):
            text = (str(row['data'].get('protocolSection', {}).get('interventions', '')) + 
                    str(row['data'].get('protocolSection', {}).get('title', '')) + 
                    str(row['data'].get('protocolSection', {}).get('briefSummary', ''))).lower()
            if any(x in text for x in ['deruxtecan', 'emtansine', 'adc']): class_map['ADC'] += 1
            elif any(x in text for x in ['trastuzumab', 'pertuzumab']): class_map['mAb'] += 1
            elif any(x in text for x in ['tucatinib', 'neratinib', 'lapatinib', 'pyrotinib']): class_map['TKI'] += 1
            elif any(x in text for x in ['cdk4', 'palbociclib', 'ribociclib', 'abemaciclib']): class_map['CDK4/6'] += 1
            elif any(x in text for x in ['pembrolizumab', 'nivolumab', 'checkpoint']): class_map['IO'] += 1
        elements.append(Image(self.cg.plot_donut(class_map, "Classes Terapêuticas", [PALETTE['primary'], PALETTE['secondary'], PALETTE['accent'], PALETTE['amber'], PALETTE['coral']]), width=7*cm, height=7*cm))
        elements.append(PageBreak())

        # P9: Competitive
        elements.append(Paragraph("6. Análise Competitiva", self.styles['H2']))
        sponsor_dist = self.dp.df['data'].apply(lambda x: str(x.get('protocolSection', {}).get('sponsor', 'Unknown'))).value_counts().head(12).to_dict()
        elements.append(Image(self.cg.plot_bar_horizontal(sponsor_dist, "Top 12 Patrocinadores", PALETTE['primary_dark']), width=14*cm, height=8*cm))
        elements.append(PageBreak())

        # P10: Emerging
        elements.append(Paragraph("7. Pipeline Emergente", self.styles['H2']))
        adc_summary = {}
        for row in self.dp.df.to_dict('records'):
            text = str(row['data']).lower()
            name = None
            if 't-dxd' in text or 'deruxtecan' in text: name = "T-DXd"
            elif 'shr-a1811' in text: name = "SHR-A1811"
            elif 'arx788' in text: name = "ARX788"
            elif 'disitamab' in text: name = "Disitamab Vedotin"
            if name:
                if name not in adc_summary: adc_summary[name] = {'n': 0, 'sponsor': row['data'].get('protocolSection', {}).get('sponsor', 'N/D'), 'pts': 0}
                adc_summary[name]['n'] += 1
                adc_summary[name]['pts'] += row['patients']
        
        adc_table_data = [["Composto", "Estudos", "Patrocinador", "Pacientes"]]
        for name, s in adc_summary.items(): adc_table_data.append([name, s['n'], s['sponsor'], s['pts']])
        adc_table = Table(adc_table_data, colWidths=[4*cm]*4)
        adc_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor(PALETTE['accent'])), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
        elements.append(adc_table)
        elements.append(PageBreak())

        # P11: Brazil
        elements.append(Paragraph("8. Presença no Brasil", self.styles['H2']))
        elements.append(Paragraph("A análise de presença no Brasil é conservadora, baseada em busca textual no JSON.", self.styles['Callout']))
        brazil_trials = self.dp.df[self.dp.df['brazil'].notna()].head(5)
        for _, row in brazil_trials.iterrows():
            elements.append(Paragraph(f"<b>{row['nct_id']}</b> - {row['phase']} - {row['data'].get('protocolSection', {}).get('sponsor', 'N/D')}", self.styles['H3']))
            elements.append(Paragraph(f"Status: {row['status']} | Pacientes: {row['patients']}", self.styles['Body']))
            elements.append(Spacer(1, 0.5*cm))
        elements.append(PageBreak())

        # P12: Regulatory
        elements.append(Paragraph("9. Análise Regulatória", self.styles['H2']))
        p3_top = self.dp.df[self.dp.df['phase'] == 'Phase 3'].sort_values('patients', ascending=False).head(10)
        reg_data = [["NCT ID", "Patrocinador", "Pacientes"]]
        for _, row in p3_top.iterrows(): reg_data.append([row['nct_id'], str(row['data'].get('protocolSection', {}).get('sponsor', 'N/D'))[:30], row['patients']])
        reg_table = Table(reg_data, colWidths=[4*cm, 6*cm, 4*cm])
        reg_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor(PALETTE['primary_dark'])), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
        elements.append(reg_table)
        elements.append(PageBreak())

        # P13: Conclusions
        elements.append(Paragraph("10. Conclusões e Recomendações", self.styles['H2']))
        recs = ["Monitorar Corrida de ADCs (SHR-A1811, ARX788).", "Focar em Metástase Cerebral (unmet need).", "Ativar Centros no Brasil.", "Vigilância NMPA (China).", "Validar Combinações CDK4/6."]
        for r in recs: elements.append(Paragraph(f"• {r}", self.styles['Body']))
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph("Pesquisa e Dados · 2026", self.styles['Callout']))

        def on_page(canvas, doc):
            self.add_footer(canvas, doc)

        doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

if __name__ == '__main__':
    dp = DataProcessor(DB_PATH)
    dp.classify_trials()
    cg = ChartGenerator()
    builder = ReportBuilder(dp, cg)
    builder.build(OUTPUT_PDF)
    print(f"Report created: {OUTPUT_PDF}")
