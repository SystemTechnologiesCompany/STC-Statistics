"""Run with QT_QPA_PLATFORM=offscreen for unattended checks."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from stc_statistics.app import MainWindow
from stc_statistics.i18n import TEXT
from stc_statistics.kernel import Execution, Session


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_translations_and_editable_cells(self):
        self.assertEqual(set(TEXT['en']), set(TEXT['fr']))
        window = MainWindow()
        window.language_picker.setCurrentIndex(1)
        self.assertEqual(window.open_button.text(), TEXT['fr']['import'])
        cell = window.add_cell('1 + 2')
        self.assertEqual(cell.editor.toPlainText(), '1 + 2')
        self.assertEqual(cell.run_button.text(), 'Exécuter  ▶')
        window.language_picker.setCurrentIndex(0)
        self.assertEqual(cell.run_button.text(), 'Run cell  ▶')
        window.remove_cell(cell)
        self.assertFalse(window.cells)
        window.dirty = False
        window.close()

    def execute(self, session, code):
        messages, result = [], []
        worker = Execution(session, code)
        loop = QEventLoop()
        worker.output.connect(messages.append)
        worker.completed.connect(lambda success, count: result.append((success, count)))
        worker.finished.connect(loop.quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(session.interrupt)
        timer.start(60000)
        worker.start()
        loop.exec()
        worker.wait()
        timer.stop()
        self.assertTrue(result)
        return messages, result[0]

    def test_pages_preserve_data_selection_and_notebook(self):
        import pandas as pd
        from stc_statistics.pages import PAGE_KEYS
        window = MainWindow()
        window.use_frame(pd.DataFrame({'a': [1, 2], 'b': [3, 4]}))
        window.navigate('analysis')
        selected = window.selected_columns()
        window.generate('stats')
        self.assertEqual(window.current_page, 'notebook')
        cell = window.cells[-1]
        cell.editor.setPlainText('retained_value = 42')
        for key in PAGE_KEYS:
            window.navigate(key, animate=False)
            self.assertEqual(window.pages.currentIndex(), PAGE_KEYS.index(key))
            self.assertTrue(window.nav_buttons[key].isChecked())
            self.assertEqual(window.selected_columns(), selected)
            self.assertEqual(cell.editor.toPlainText(), 'retained_value = 42')
        window.navigate('charts')
        self.assertEqual(window.column_hosts['charts'].count(), 1)
        self.assertEqual(window.column_hosts['analysis'].count(), 0)
        window.language_picker.setCurrentIndex(1)
        self.assertEqual(window.page_title.text(), 'Graphiques')
        window.dirty = False
        window.close()

    def test_real_kernel_variables_output_error_and_plot(self):
        session = Session()
        try:
            _, result = self.execute(session, 'x = 41')
            self.assertTrue(result[0])
            messages, result = self.execute(session, 'print(x + 1)\nx + 2')
            self.assertTrue(result[0])
            self.assertTrue(any(m['msg_type'] == 'stream' and '42' in m['content']['text'] for m in messages))
            self.assertTrue(any(m['msg_type'] == 'execute_result' for m in messages))
            messages, result = self.execute(session, "raise ValueError('test error')")
            self.assertFalse(result[0])
            self.assertTrue(any(m['msg_type'] == 'error' for m in messages))
            messages, result = self.execute(session, '%matplotlib inline\nimport matplotlib.pyplot as plt\nplt.plot([1, 2, 3]); plt.show()')
            self.assertTrue(result[0])
            self.assertTrue(any('image/png' in m['content'].get('data', {}) for m in messages))
        finally:
            session.close()


if __name__ == '__main__':
    unittest.main()
