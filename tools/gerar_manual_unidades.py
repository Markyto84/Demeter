"""Gera o PDF do manual a partir do Markdown versionado (requer ReportLab)."""
from html import escape
from pathlib import Path
import re
import textwrap

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output/pdf/Manual-implantacao-unidades-Demeter.pdf'
FONTES = Path('C:/Windows/Fonts')
if (FONTES / 'segoeui.ttf').exists():
    pdfmetrics.registerFont(TTFont('Manual', str(FONTES / 'segoeui.ttf')))
    pdfmetrics.registerFont(TTFont('ManualBold', str(FONTES / 'segoeuib.ttf')))
    pdfmetrics.registerFontFamily('Manual', normal='Manual', bold='ManualBold', italic='Manual', boldItalic='ManualBold')
else:
    # DejaVu Sans, normalmente disponível no Linux.
    fontes = Path('/usr/share/fonts/truetype/dejavu')
    pdfmetrics.registerFont(TTFont('Manual', str(fontes / 'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('ManualBold', str(fontes / 'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFontFamily('Manual', normal='Manual', bold='ManualBold', italic='Manual', boldItalic='ManualBold')

AZUL = colors.HexColor('#0070AD')
CLARO = colors.HexColor('#17ABDA')
TEXTO = colors.HexColor('#233A4C')
styles = {
    'body': ParagraphStyle('Corpo', fontName='Manual', fontSize=10, leading=15, textColor=TEXTO, spaceAfter=8),
    'h2': ParagraphStyle('Secao', fontName='ManualBold', fontSize=15, leading=20, textColor=AZUL, spaceBefore=19, spaceAfter=10, keepWithNext=True),
    'table': ParagraphStyle('Tabela', fontName='Manual', fontSize=8.4, leading=12, textColor=TEXTO),
    'th': ParagraphStyle('CabecalhoTabela', fontName='ManualBold', fontSize=8.6, leading=12, textColor=colors.white),
    'code': ParagraphStyle('Codigo', fontName='Courier', fontSize=8, leading=12, backColor=colors.HexColor('#EDF4F8'), borderPadding=10, spaceBefore=8, spaceAfter=12),
}


def inline(texto):
    texto = escape(texto)
    texto = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', texto)
    texto = re.sub(r'`(.+?)`', r'<font color="#0070AD">\1</font>', texto)
    texto = re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'\1', texto)
    return texto


def rodape(canvas, doc):
    w, h = A4
    canvas.setStrokeColor(CLARO); canvas.setLineWidth(1.2)
    canvas.line(46, 42, w-46, 42)
    canvas.setFont('Manual', 8); canvas.setFillColor(TEXTO)
    canvas.drawString(46, 28, 'Deméter | Implantação dos servidores das unidades | 0.2.0')
    canvas.drawRightString(w-46, 28, str(doc.page))
    if doc.page > 1:
        canvas.setFont('ManualBold', 8); canvas.setFillColor(AZUL)
        canvas.drawString(46, h-31, 'CONTINUIDADE DO CUIDADO - MANUAL DA TI')


def gerar():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    story = [Spacer(1, 40), Paragraph('DEMÉTER', ParagraphStyle('Marca', fontName='ManualBold', fontSize=16, textColor=AZUL, leading=24)),
        Spacer(1, 45), Paragraph('O cuidado continua<br/>na unidade.', ParagraphStyle('Capa', fontName='ManualBold', fontSize=34, leading=43, textColor=AZUL)),
        Spacer(1, 22), Paragraph('A gestão acompanha pela central.', ParagraphStyle('Subcapa', fontName='Manual', fontSize=19, leading=27, textColor=TEXTO)),
        Spacer(1, 55), Paragraph('Manual de implantação<br/><b>Servidores por unidade e consolidação da rede</b>', ParagraphStyle('ResumoCapa', fontName='Manual', fontSize=13, leading=21, textColor=TEXTO)),
        Spacer(1, 22), Paragraph('Versão 0.2.0 | Novembro de 2026', styles['body']),
        Spacer(1, 25), Table([[Paragraph('Um servidor local por unidade. Pedidos, cozinha, impressões e entregas continuam na rede local. A sincronização reúne os dados para a gestão da rede.', styles['body'])]], colWidths=[500], style=TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#E9F5FA')),('BOX',(0,0),(-1,-1),0.6,CLARO),('LEFTPADDING',(0,0),(-1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),16),('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),8)])), PageBreak()]
    linhas = (ROOT / 'IMPLEMENTACAO-UNIDADES.md').read_text(encoding='utf-8').splitlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        if not linha.strip() or linha.startswith('# ') or linha.startswith('Manual de implantação'):
            i += 1; continue
        if linha.startswith('## '):
            story.append(Paragraph(inline(linha[3:]), styles['h2'])); i += 1; continue
        if linha.startswith('```'):
            codigo=[]; i += 1
            while i < len(linhas) and not linhas[i].startswith('```'):
                codigo.extend(textwrap.wrap(linhas[i], width=91, replace_whitespace=False, drop_whitespace=False) or ['']); i += 1
            story.append(Preformatted('\n'.join(codigo), styles['code'])); i += 1; continue
        if linha.startswith('|'):
            rows=[]
            while i < len(linhas) and linhas[i].startswith('|'):
                cells=[c.strip() for c in linhas[i].strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+', c) for c in cells): rows.append(cells)
                i += 1
            n=len(rows[0]); widths=[160,340] if n == 2 else [145,140,215]
            table=Table([[Paragraph(inline(c), styles['th' if r == 0 else 'table']) for c in row] for r,row in enumerate(rows)], colWidths=widths, repeatRows=1, hAlign='LEFT', splitByRow=1)
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),AZUL),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#EDF4F8'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),0.35,colors.HexColor('#D4E1E9'))]))
            story += [table, Spacer(1,10)]; continue
        partes=[linha]; i += 1
        while i < len(linhas) and linhas[i].strip() and not linhas[i].startswith(('## ', '|', '```')):
            if re.match(r'^(\d+\. |\- )', linhas[i]): break
            partes.append(linhas[i].strip()); i += 1
        texto=' '.join(partes)
        item=re.match(r'^(\d+\. |\- )(.+)',texto)
        if item:
            story.append(Paragraph(inline(item[2]), ParagraphStyle('Item', parent=styles['body'], leftIndent=14, firstLineIndent=0, bulletIndent=0), bulletText=item[1].strip()))
        else: story.append(Paragraph(inline(texto), styles['body']))
    doc=SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=46,leftMargin=46,topMargin=55,bottomMargin=58,
        title='Deméter - Manual de implantação dos servidores das unidades',author='Deméter | Tecnologia e Nutrição')
    doc.build(story,onFirstPage=rodape,onLaterPages=rodape)
    print(OUTPUT)


if __name__ == '__main__': gerar()
