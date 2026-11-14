import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QListWidget, QLineEdit
from stc_statistics.app import MainWindow
from stc_statistics.analysis import TABLE_MIME
from stc_statistics.stat_options import choose_statistics
from stc_statistics.theme import GlassButton, GlassComboBox


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_statistics_dialog_commits_selection_and_percentiles(self):
        window = MainWindow()
        window.language_picker.setCurrentIndex(0)
        def select_options():
            dialog = QApplication.activeModalWidget()
            measures = dialog.findChild(QListWidget)
            for index in range(measures.count()):
                measures.item(index).setCheckState(Qt.CheckState.Checked if index in [2, 3, 8] else Qt.CheckState.Unchecked)
            dialog.findChild(GlassComboBox).setCurrentIndex(1)
            dialog.findChild(QLineEdit).setText('5; 95')
            next(button for button in dialog.findChildren(GlassButton) if button.text() == 'Apply').click()
        QTimer.singleShot(50, select_options)
        choose_statistics(window)
        self.assertEqual(window.stats_metrics, [2, 3, 8])
        self.assertEqual(window.stats_ddof, 0)
        self.assertEqual(window.stats_percentiles, [5, 95])
        window.dirty = False
        window.close()

    def test_export_buttons_create_reports_without_kernel_or_recalculation(self):
        window = MainWindow()
        cell = window.add_cell('a = 2.5')
        cell.executed_source = 'a = 2.5'
        cell.receive({'msg_type': 'display_data', 'content': {'data': {TABLE_MIME: json.dumps({'columns': ['A'], 'index': ['Mean'], 'data': [[2.5]]}), 'text/html': '<table></table>'}, 'metadata': {}}})
        with tempfile.TemporaryDirectory() as directory:
            for extension, action in [('xlsx', window.export_results), ('docx', window.export_word_report)]:
                path = Path(directory) / ('report.' + extension)
                with patch('stc_statistics.app.QFileDialog.getSaveFileName', return_value=(str(path), '')):
                    action()
                self.assertTrue(zipfile.is_zipfile(path))
        self.assertIsNone(window.session.manager)
        window.dirty = False
        window.close()

    def test_cell_duplicate_move_and_clear(self):
        window = MainWindow()
        first, second = window.add_cell('x = 1'), window.add_cell('x + 1')
        first.receive({'msg_type': 'stream', 'content': {'name': 'stdout', 'text': 'result'}})
        window.cell_action(first, 'duplicate_cell')
        duplicate = window.cells[1]
        self.assertEqual(duplicate.editor.toPlainText(), 'x = 1')
        self.assertFalse(duplicate.outputs)
        window.cell_action(second, 'move_up')
        self.assertEqual(window.cells, [first, second, duplicate])
        window.cell_action(first, 'clear_output')
        self.assertFalse(first.outputs)
        self.assertTrue(first.output.isHidden())
        window.dirty = False
        window.close()


if __name__ == '__main__':
    unittest.main()
