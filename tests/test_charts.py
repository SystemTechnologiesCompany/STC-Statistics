import base64
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from stc_statistics.app import MainWindow
from stc_statistics.theme import initialize_fonts, STYLE


class ChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        initialize_fonts(cls.app)
        cls.app.setStyleSheet(STYLE)

    def test_plot_output_opens_large_viewer_and_can_zoom_fit_export(self):
        window = MainWindow()
        window.setProperty('reduceMotion', True)
        window.show()
        fig, ax = plt.subplots(figsize=(12, 7), dpi=160)
        ax.plot([1, 2, 3], [4, 8, 5], color='#188650')
        ax.set_xlabel('Porosity (%)')
        ax.set_ylabel('Permeability (mD)')
        raw = io.BytesIO()
        fig.savefig(raw, format='png', facecolor='white')
        plt.close(fig)
        png = raw.getvalue()
        cell = window.add_cell('plt.show()')
        cell.receive({'msg_type': 'display_data', 'content': {'data': {'image/png': base64.b64encode(png).decode()}, 'metadata': {}}})
        window.active = cell
        window.execution_complete(True, 1)
        window.active = None
        QTest.qWait(100)
        self.assertEqual(window.current_page, 'charts')
        self.assertEqual(window.chart_stack.currentIndex(), 1)
        canvas = window.chart_viewer.canvas
        self.assertEqual(canvas.item.pixmap().width(), QImage.fromData(png).width())
        self.assertGreater(canvas.viewport().width(), 800)
        before = canvas.transform().m11()
        canvas.zoom(1.5)
        self.assertGreater(canvas.transform().m11(), before)
        canvas.fit()
        self.assertAlmostEqual(canvas.transform().m11(), before, places=2)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'chart.png'
            with patch('stc_statistics.charts.QFileDialog.getSaveFileName', return_value=(str(target), 'PNG')):
                window.chart_viewer.save()
            self.assertEqual(target.read_bytes(), png)
        self.assertFalse(cell.chart_button.isHidden())
        window.dirty = False
        window.close()

    def test_all_generated_charts_render_with_readable_plot_background(self):
        window = MainWindow()
        window.setProperty('reduceMotion', True)
        window.use_frame(pd.DataFrame({'Porosity': [10, 12, 16, 18], 'Permeability': [4, 8, 16, 32]}))
        for kind in ('histogram', 'box', 'scatter'):
            window.generate(kind)
            code = window.cells[-1].editor.toPlainText().replace('%matplotlib inline', '')
            with patch('matplotlib.pyplot.show'):
                exec(code, {'df': window.frame})
            figure = plt.gcf()
            self.assertEqual(figure.get_facecolor(), (1.0, 1.0, 1.0, 1.0))
            self.assertGreaterEqual(figure.dpi, 160)
            self.assertTrue(figure.axes)
            plt.close('all')
        window.dirty = False
        window.close()

    def test_histogram_large_coordinates_have_no_overlapping_ticks(self):
        import numpy as np
        from stc_statistics.plot_code import histogram_code
        rng = np.random.default_rng(42)
        frame = pd.DataFrame({
            'X': rng.uniform(530000, 580000, 200),
            'Y': rng.normal(258000, 14000, 200),
            'Top Absolue': rng.normal(-1490, 45, 200),
        })
        with patch('matplotlib.pyplot.show'):
            exec(histogram_code(), {'numeric': frame, 'plt': plt})
        fig = plt.gcf()
        self.assertEqual(len(fig.axes), 3)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for ax, column in zip(fig.axes, frame.columns):
            boxes = [tick.get_window_extent(renderer) for tick in ax.get_xticklabels() if tick.get_visible()]
            for left, right in zip(boxes, boxes[1:]):
                self.assertLess(left.x1 + 2, right.x0)
            expected, _ = np.histogram(frame[column].dropna(), bins=15)
            np.testing.assert_array_equal([patch.get_height() for patch in ax.patches], expected)
        plt.close('all')

    def test_histograms_split_large_selections_into_figures(self):
        from stc_statistics.plot_code import histogram_code
        plt.close('all')
        frame = pd.DataFrame({f'C{i}': [1, 2, 3, 4] for i in range(7)})
        with patch('matplotlib.pyplot.show'):
            exec(histogram_code(), {'numeric': frame, 'plt': plt})
        self.assertEqual([len(plt.figure(number).axes) for number in plt.get_fignums()], [4, 3])
        plt.close('all')


if __name__ == '__main__':
    unittest.main()
