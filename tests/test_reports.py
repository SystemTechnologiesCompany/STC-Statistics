import base64
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
from PIL import Image
from openpyxl import load_workbook

from stc_statistics.analysis import TABLE_MIME, analysis_code, correlation_code
from stc_statistics.reports import collect_results, export_excel, export_word


def sample_results():
    buffer = io.BytesIO()
    Image.new('RGB', (1200, 700), 'white').save(buffer, format='PNG')
    png = buffer.getvalue()
    payload = {'columns': ['Porosity', 'Permeability'], 'index': ['Mean', 'Median', 'Missing'],
               'data': [[18.125, 41.5], [18.0, 32.0], [0, None]]}
    outputs = [
        {'output_type': 'display_data', 'data': {TABLE_MIME: json.dumps(payload), 'text/html': '<table><tr><td>do not duplicate</td></tr></table>'}},
        {'output_type': 'display_data', 'data': {'image/png': base64.b64encode(png).decode()}},
        {'output_type': 'stream', 'text': 'Mean = 18.125', 'name': 'stdout'},
    ]
    cell = SimpleNamespace(outputs=outputs, executed_source='summary = df.mean()', editor=SimpleNamespace(toPlainText=lambda: 'modified_after_execution = True'))
    return cell, png


class ReportTests(unittest.TestCase):
    def test_collection_filters_and_executed_code(self):
        cell, png = sample_results()
        items = collect_results([cell], code=True)
        self.assertEqual([i['kind'] for i in items], ['code', 'table', 'image', 'text'])
        self.assertEqual(items[0]['text'], 'summary = df.mean()')
        self.assertEqual(items[1]['rows'][1][1], 18.125)
        self.assertEqual(items[2]['png'], png)
        self.assertEqual([i['kind'] for i in collect_results([cell], tables=False, text=False)], ['image'])

    def test_excel_numeric_values_and_original_embedded_graph(self):
        cell, png = sample_results()
        items = collect_results([cell])
        items.append({'kind': 'table', 'title': 'Literal strings', 'rows': [['Label', 'Value'], ['Formula', '=2+2']]})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.xlsx'
            export_excel(path, items, source='sample.xlsx')
            with zipfile.ZipFile(path) as archive:
                images = [name for name in archive.namelist() if name.startswith('xl/media/')]
                self.assertEqual(len(images), 1)
                self.assertEqual(archive.read(images[0]), png)
            workbook = load_workbook(path)
            self.assertEqual(workbook['Table 1']['B2'].value, 18.125)
            self.assertEqual(workbook['Table 1']['B2'].data_type, 'n')
            self.assertEqual(workbook['Table 2']['B2'].value, '=2+2')
            self.assertEqual(workbook['Table 2']['B2'].data_type, 's')
            self.assertEqual(len(workbook['Graph 1']._images), 1)
            workbook.close()

    def test_word_editable_tables_valid_xml_and_original_graph(self):
        cell, png = sample_results()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.docx'
            export_word(path, collect_results([cell]), language='fr', source='sample.xlsx')
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.endswith(('.xml', '.rels')):
                        ET.fromstring(archive.read(name))
                document = ET.fromstring(archive.read('word/document.xml'))
                namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                self.assertTrue(document.findall('.//w:tbl', namespace))
                text = ' '.join(t.text or '' for t in document.findall('.//w:t', namespace))
                self.assertIn('18.125', text)
                self.assertIn('Résultats statistiques', text)
                self.assertEqual(archive.read('word/media/image1.png'), png)

    def test_html_fallback_table(self):
        cell = SimpleNamespace(outputs=[{'output_type': 'display_data', 'data': {'text/html': pd.DataFrame({'a': [1, 2]}).to_html()}}])
        items = collect_results([cell])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['rows'][0], ['', 'a'])
        self.assertEqual(items[0]['rows'][1][1], 1)

    def test_statistic_selection_population_and_percentiles(self):
        namespace = {'df': pd.DataFrame({'x': [1, 2, 3, 4]})}
        displayed = []
        with patch('IPython.display.display', side_effect=lambda data, **kw: displayed.append(data)):
            exec(analysis_code(['x'], 'en', [2, 3, 8], ddof=0, percentiles=[5, 95]), namespace)
        summary = namespace['summary']
        self.assertEqual(list(summary.index), ['Mean', 'Median', 'Population variance', 'Percentile 5%', 'Percentile 95%'])
        self.assertEqual(summary.loc['Population variance', 'x'], 1.25)
        self.assertAlmostEqual(summary.loc['Percentile 5%', 'x'], 1.15)
        self.assertIn(TABLE_MIME, displayed[0])

    def test_spearman_uses_pairwise_complete_ranks(self):
        namespace = {'pd': pd, 'np': np, 'numeric': pd.DataFrame({'x': [1, 2, 3, np.nan, 4], 'y': [4, np.nan, 2, 1, 1]})}
        with patch('IPython.display.display'):
            exec(correlation_code('spearman'), namespace)
        self.assertAlmostEqual(namespace['correlation'].loc['x', 'y'], -1)


if __name__ == '__main__':
    unittest.main()
