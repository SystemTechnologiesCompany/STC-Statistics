"""Export notebook results without recalculating them or needing a running kernel."""
import base64
from datetime import datetime
from html.parser import HTMLParser
import io
import json
import re
from pathlib import Path
import zipfile
from xml.sax.saxutils import escape

from .analysis import TABLE_MIME


class TableParser(HTMLParser):
    """Fallback for ordinary pandas HTML output from user-written notebook code."""
    def __init__(self):
        super().__init__()
        self.tables, self.rows, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and self.rows is None:
            self.rows = []
        elif tag == 'tr' and self.rows is not None:
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []
        elif tag == 'br' and self.cell is not None:
            self.cell.append('\n')

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == 'table' and self.rows is not None:
            if self.rows:
                self.tables.append(self.rows)
            self.rows = None


def _numeric_html_rows(rows):
    converted = []
    pattern = re.compile(r'[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\Z')
    for r, row in enumerate(rows):
        values = []
        for c, value in enumerate(row):
            if r and c and pattern.fullmatch(value):
                value = float(value) if any(mark in value.lower() for mark in ('.', 'e')) else int(value)
            values.append(value)
        converted.append(values)
    return converted


def collect_results(cells, tables=True, graphs=True, text=True, code=False, language='en'):
    items = []
    cell_name = 'Cell' if language == 'en' else 'Cellule'
    for index, cell in enumerate(cells, 1):
        if not cell.outputs:
            continue
        title = f'{cell_name} {index}'
        cell_items = []
        for output in cell.outputs:
            kind = output['output_type']
            data = output.get('data', {})
            if graphs and 'image/png' in data:
                cell_items.append({'kind': 'image', 'title': title, 'png': base64.b64decode(data['image/png'])})
            elif tables and TABLE_MIME in data:
                payload = data[TABLE_MIME]
                payload = json.loads(payload) if isinstance(payload, str) else payload
                rows = [[''] + payload['columns']]
                rows += [[label] + values for label, values in zip(payload['index'], payload['data'])]
                label = output.get('metadata', {}).get('stc', {}).get('title', '')
                cell_items.append({'kind': 'table', 'title': title + (f' · {label}' if label else ''), 'rows': rows})
            elif tables and 'text/html' in data:
                parser = TableParser()
                parser.feed(data['text/html'])
                cell_items += [{'kind': 'table', 'title': title, 'rows': _numeric_html_rows(rows)} for rows in parser.tables]
                if not parser.tables and text and 'text/plain' in data:
                    cell_items.append({'kind': 'text', 'title': title, 'text': data['text/plain']})
            elif text and kind == 'stream':
                cell_items.append({'kind': 'text', 'title': title, 'text': output['text']})
            elif text and 'text/plain' in data and 'image/png' not in data and TABLE_MIME not in data and '<table' not in data.get('text/html', ''):
                cell_items.append({'kind': 'text', 'title': title, 'text': data['text/plain']})
            elif kind == 'error':
                cell_items.append({'kind': 'text', 'title': title, 'text': f"{output['ename']}: {output['evalue']}"})
        if cell_items and code:
            source = getattr(cell, 'executed_source', None) or cell.editor.toPlainText()
            items.append({'kind': 'code', 'title': title, 'text': source})
        items.extend(cell_items)
    return items


def _literal(cell, value):
    # Preserve formulas/identifiers as literal content, and long integers as exact text.
    if isinstance(value, (dict, list, tuple)):
        value = str(value)
    if isinstance(value, int) and abs(value) >= 10 ** 15:
        value = str(value)
    cell.value = value
    if isinstance(value, str):
        cell.data_type = 's'


def export_excel(path, items, language='en', source=''):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.drawing.image import Image as SheetImage
    from openpyxl.utils import get_column_letter
    book = Workbook()
    overview = book.active
    overview.title = 'STC Statistics'
    overview.append(['STC Statistics', 'Results' if language == 'en' else 'Résultats'])
    overview.append(['Source', source])
    overview.append(['Created' if language == 'en' else 'Création', datetime.now().isoformat(timespec='minutes')])
    overview.append(['Note', 'Saved notebook outputs; no recalculation.' if language == 'en' else 'Sorties enregistrées du notebook ; aucun recalcul.'])
    overview.append(['Missing' if language == 'en' else 'Valeurs manquantes', 'Blank numeric cells indicate missing or undefined values.' if language == 'en' else 'Les cellules numériques vides indiquent des valeurs manquantes ou indéfinies.'])
    overview.append([])
    overview.append(['Sheet' if language == 'en' else 'Feuille', 'Cell' if language == 'en' else 'Cellule', 'Type'])
    counts = {'table': 0, 'image': 0, 'text': 0, 'code': 0}
    image_buffers = []
    for item in items:
        kind = item['kind']
        counts[kind] += 1
        prefix = {'table': 'Table', 'image': 'Graph', 'text': 'Output', 'code': 'Python'}[kind]
        sheet = book.create_sheet(f'{prefix} {counts[kind]}')
        overview.append([sheet.title, item['title'], kind])
        if kind == 'table':
            for r, row in enumerate(item['rows'], 1):
                for c, value in enumerate(row, 1):
                    target = sheet.cell(r, c)
                    _literal(target, value)
                    target.alignment = Alignment(vertical='top', wrap_text=True)
                    if isinstance(value, float):
                        target.number_format = '0.###############'
                    if r == 1 or c == 1:
                        target.font = Font(bold=True, color='FFFFFF' if r == 1 else '183D29')
                        target.fill = PatternFill('solid', fgColor='216444' if r == 1 else 'E8F3ED')
            sheet.freeze_panes = 'B2'
            sheet.auto_filter.ref = sheet.dimensions
            for c in range(1, sheet.max_column + 1):
                sheet.column_dimensions[get_column_letter(c)].width = 30 if c == 1 else 21
        elif kind == 'image':
            sheet['A1'] = item['title']
            buffer = io.BytesIO(item['png'])
            image_buffers.append(buffer)
            image = SheetImage(buffer)
            scale = min(1, 1150 / image.width)
            image.width, image.height = image.width * scale, image.height * scale
            sheet.add_image(image, 'A3')
            sheet.sheet_view.showGridLines = False
        else:
            sheet['A1'] = item['title']
            for r, line in enumerate(item['text'].splitlines(), 3):
                _literal(sheet.cell(r, 1), line)
            sheet.column_dimensions['A'].width = 115
    overview.column_dimensions['A'].width = 26
    overview.column_dimensions['B'].width = 70
    overview.column_dimensions['C'].width = 18
    for row in overview:
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = 's'
    for cell in overview[1]:
        cell.font = Font(size=16, bold=True, color='216444')
    book.save(path)


def _clean(value):
    text = '' if value is None else str(value)
    return ''.join(c for c in text if ord(c) >= 32 or c in '\n\t')


def _p(text, style=None):
    prop = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    runs = '<w:br/>'.join(f'<w:t xml:space="preserve">{escape(line)}</w:t>' for line in _clean(text).split('\n'))
    return f'<w:p>{prop}<w:r>{runs}</w:r></w:p>'


def export_word(path, items, language='en', source='', logo=None):
    """Native .docx OOXML; no additional application dependency is required."""
    from PIL import Image
    body, relationships, media = [], [], []
    body += [_p('STC Statistics', 'Title'), _p('Statistical results' if language == 'en' else 'Résultats statistiques', 'Subtitle')]
    body.append(_p(f"Source : {source}\n{datetime.now().strftime('%Y-%m-%d %H:%M')}"))
    body.append(_p('Saved notebook results. Tables remain editable; figures use the original PNG images.' if language == 'en'
                   else 'Résultats enregistrés du notebook. Les tableaux sont modifiables ; les figures utilisent les images PNG originales.'))
    body.append(_p('Blank numeric cells indicate missing or undefined values.' if language == 'en' else 'Les cellules numériques vides indiquent des valeurs manquantes ou indéfinies.'))

    def picture(png, max_width=9.9, max_height=5.6):
        with Image.open(io.BytesIO(png)) as image:
            width, height = image.size
        scale = min(max_width / width, max_height / height)
        cx, cy = int(width * scale * 914400), int(height * scale * 914400)
        number = len(media) + 1
        rid = f'rIdImage{number}'
        media.append((f'word/media/image{number}.png', png))
        relationships.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{number}.png"/>')
        return f'''<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{number}" name="STC figure {number}"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="{number}" name="Figure {number}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''

    if logo and Path(logo).is_file():
        body.insert(0, picture(Path(logo).read_bytes(), .48, .58))
    for item in items:
        if item['kind'] == 'image':
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        body.append(_p(item['title'], 'Heading1'))
        if item['kind'] == 'image':
            body.append(picture(item['png']))
        elif item['kind'] == 'table':
            rows = item['rows']
            width = max(map(len, rows), default=1)
            # Split very wide tables into readable blocks, repeating the row labels.
            groups = [list(range(width))] if width <= 7 else [[0] + list(range(start, min(width, start + 6))) for start in range(1, width, 6)]
            for group in groups:
                table = ['<w:tbl><w:tblPr><w:tblW w:w="14900" w:type="dxa"/><w:tblBorders><w:top w:val="single" w:sz="4" w:color="CBDCD0"/><w:left w:val="single" w:sz="4" w:color="CBDCD0"/><w:bottom w:val="single" w:sz="4" w:color="CBDCD0"/><w:right w:val="single" w:sz="4" w:color="CBDCD0"/><w:insideH w:val="single" w:sz="4" w:color="CBDCD0"/><w:insideV w:val="single" w:sz="4" w:color="CBDCD0"/></w:tblBorders><w:tblLayout w:type="fixed"/></w:tblPr>']
                cell_width = 14900 // len(group)
                table.append('<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{cell_width}"/>' for _ in group) + '</w:tblGrid>')
                for r, row in enumerate(rows):
                    table.append('<w:tr><w:trPr><w:cantSplit/>' + ('<w:tblHeader/>' if r == 0 else '') + '</w:trPr>')
                    for c in group:
                        value = row[c] if c < len(row) else ''
                        color, fill = ('FFFFFF', '216444') if r == 0 else ('172A20', 'EDF5EF' if c == 0 else 'FFFFFF')
                        table.append(f'<w:tc><w:tcPr><w:tcW w:w="{cell_width}" w:type="dxa"/><w:shd w:fill="{fill}"/></w:tcPr><w:p><w:r><w:rPr><w:color w:val="{color}"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">{escape(_clean(value))}</w:t></w:r></w:p></w:tc>')
                    table.append('</w:tr>')
                table.append('</w:tbl>')
                body.extend(table)
                body.append(_p(''))
        else:
            body.append(_p(item['text'], 'Code' if item['kind'] == 'code' else None))
    body.append('<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/><w:pgMar w:top="720" w:right="936" w:bottom="720" w:left="936" w:header="360" w:footer="360"/></w:sectPr>')
    namespaces = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {namespaces}><w:body>{"".join(body)}</w:body></w:document>'
    styles = '''<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:color w:val="216444"/><w:sz w:val="42"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:rPr><w:sz w:val="28"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:color w:val="216444"/><w:sz w:val="27"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr></w:style></w:styles>'''
    relationships.insert(0, '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr('word/document.xml', document)
        archive.writestr('word/styles.xml', styles)
        archive.writestr('word/_rels/document.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(relationships) + '</Relationships>')
        for name, png in media:
            archive.writestr(name, png)
