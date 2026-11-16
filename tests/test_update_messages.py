import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from stc_statistics.app import MainWindow
from stc_statistics.update_messages import friendly_error,record_error


class UpdateMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def window(self):
        window=MainWindow()
        window.language_picker.setCurrentIndex(0)
        self.addCleanup(lambda:(setattr(window,'dirty',False),window.close()))
        return window

    def test_legacy_technical_release_notes_never_appear(self):
        window=self.window()
        page=window.updates_page
        detail='Fix GitHub redirected feeds, timeout exceptions and C:/private/path'
        page.accept_manifest({'version':'99.0.0','download_url':'https://example.test/update.zip','release_notes':detail})
        page.translate()
        self.assertNotIn(detail,page.notes.toPlainText())
        self.assertIn('STC Statistics',page.notes.toPlainText())

    def test_public_notes_follow_selected_language(self):
        window=self.window()
        page=window.updates_page
        page.accept_manifest({'version':'99.0.0','download_url':'https://example.test/update.zip',
                              'release_notes':'Internal exception details',
                              'user_notes':{'en':'A smoother update experience.','fr':'Une mise à jour plus fluide.'}})
        window.language_picker.setCurrentIndex(1)
        self.assertEqual(page.notes.toPlainText(),'Une mise à jour plus fluide.')
        window.language_picker.setCurrentIndex(0)
        self.assertEqual(page.notes.toPlainText(),'A smoother update experience.')

    def test_failure_codes_hide_details_and_keep_diagnostics(self):
        window=self.window()
        page=window.updates_page
        detail='PermissionError C:/Users/private/file.py https://private.test/?token=internal'
        with tempfile.TemporaryDirectory() as folder,patch('stc_statistics.update_messages.diagnostic_path',return_value=Path(folder)/'diagnostics.log'):
            for phase,code in [('update_downloading','STC-U201'),('update_verifying','STC-U202'),('update_saving','STC-U301'),('update_installing','STC-U401')]:
                page.state=phase
                page.flow.fail(detail)
                self.assertIn(code,page.status.text())
                self.assertNotIn('private',page.status.text())
                self.assertNotIn('PermissionError',page.status.text())
            entries=[json.loads(line) for line in (Path(folder)/'diagnostics.log').read_text().splitlines()]
            self.assertEqual(len(entries),4)
            self.assertEqual(entries[0]['detail'],detail)
            self.assertEqual(entries[-1]['code'],'STC-U401')

    def test_bilingual_friendly_error_and_logging_failure(self):
        self.assertIn('STC-U101',friendly_error('STC-U101','en'))
        self.assertIn('Impossible',friendly_error('STC-U101','fr'))
        with patch('stc_statistics.update_messages.RotatingFileHandler',side_effect=OSError('Log unavailable')):
            record_error('STC-U101','Internal error','check')


if __name__=='__main__':
    unittest.main()
