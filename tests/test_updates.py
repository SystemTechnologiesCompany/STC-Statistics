import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, QByteArray, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply
from stc_statistics.app import MainWindow
from stc_statistics.updates import parse_manifest, valid_https_url, version_tuple, UpdatesPage
from stc_statistics.version import APP_VERSION


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_version_order_and_invalid_sources(self):
        self.assertGreater(version_tuple('0.10.0'), version_tuple('0.3.0'))
        for version in ('', 'latest', '1.2', 'v1.2.3', None):
            with self.assertRaises(ValueError):
                version_tuple(version)
        for url in ('http://example.test/file.zip', 'file:///setup.exe', 'https://user:secret@example.test/a', 'https://example.test:bad/a'):
            self.assertFalse(valid_https_url(url))
            with self.assertRaises(ValueError):
                parse_manifest({'version': '1.0.0', 'download_url': url})

    def test_update_state_and_download_opens_only_configured_link(self):
        window = MainWindow()
        page = UpdatesPage(window, config={'manifest_url': '', 'download_url': ''})
        self.assertFalse(page.check_button.isEnabled())
        self.assertFalse(page.download_button.isEnabled())
        page.accept_manifest({'version': '99.0.0', 'download_url': 'https://downloads.example.test/stc.zip', 'release_notes': 'New statistics'})
        page.translate()
        self.assertEqual(page.state, 'updates_available')
        self.assertTrue(page.download_button.isEnabled())
        with patch('stc_statistics.updates.QDesktopServices.openUrl', return_value=True) as browser:
            page.download_button.click()
            self.assertEqual(browser.call_args.args[0].toString(), 'https://downloads.example.test/stc.zip')
        page.accept_manifest({'version': APP_VERSION, 'download_url': 'https://downloads.example.test/stc.zip'})
        page.translate()
        self.assertEqual(page.state, 'updates_current')
        self.assertFalse(page.download_button.isEnabled())
        window.navigate('updates')
        self.assertEqual(window.current_page, 'updates')
        window.language_picker.setCurrentIndex(1)
        self.assertEqual(window.page_title.text(), 'Mises à jour')
        page.deleteLater()
        window.dirty = False
        window.close()

    def test_release_package_has_feed_settings_and_matching_hash(self):
        project = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(project / 'stc_statistics', root / 'stc_statistics', ignore=shutil.ignore_patterns('__pycache__'))
            # Public-only test fixture; no operational service or signing secrets.
            (root/'stc_statistics/license_config.json').write_text(json.dumps({'server_url':'https://license.example.test'}))
            key={'n':format((1<<3071)+1,'x'),'e':65537,'key_id':'a'*24}
            (root/'stc_statistics/license_trust.py').write_text('PUBLIC_KEY = '+repr(key))
            for name in ('main.py', 'make_release.py', 'requirements.txt', 'README.md', 'Setup.cmd', 'Setup.ps1', 'Start.cmd'):
                shutil.copy2(project / name, root / name)
            subprocess.run([sys.executable, str(root / 'make_release.py'), '--download-url', 'https://downloads.example.test/stc.zip',
                            '--feed-url', 'https://downloads.example.test/update.json', '--notes', 'Release test'], check=True, capture_output=True)
            archive = root / 'releases' / f'STC_Statistics_{APP_VERSION}.zip'
            manifest = json.loads((root / 'releases' / 'update.json').read_text())
            self.assertEqual(manifest['sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as package:
                config = json.loads(package.read('stc_statistics/update_config.json'))
                self.assertEqual(config['manifest_url'], 'https://downloads.example.test/update.json')
                self.assertIn('stc_statistics/assets/stc-logo.png', package.namelist())
                self.assertFalse(any('.venv' in name for name in package.namelist()))

    def test_check_processes_a_feed_without_installing_or_running_files(self):
        class Reply(QObject):
            downloadProgress = Signal(int, int)
            finished = Signal()
            def readAll(self):
                return QByteArray(json.dumps({'version': '99.1.0', 'download_url': 'https://downloads.example.test/new.zip'}).encode())
            def error(self):
                return QNetworkReply.NetworkError.NoError
            def url(self):
                return QUrl('https://downloads.example.test/update.json')
        window = MainWindow()
        page = UpdatesPage(window, config={'manifest_url': 'https://downloads.example.test/update.json', 'download_url': ''})
        reply = Reply()
        with patch.object(QNetworkAccessManager, 'get', return_value=reply) as request:
            page.check_button.click()
            self.assertEqual(page.state, 'updates_checking')
            self.assertFalse(page.check_button.isEnabled())
            self.assertEqual(request.call_args.args[0].transferTimeout(), 60000)
            reply.finished.emit()
        self.assertEqual(page.state, 'updates_available')
        self.assertTrue(page.download_button.isEnabled())
        self.assertEqual(page.download_url, 'https://downloads.example.test/new.zip')
        page.deleteLater()
        window.dirty = False
        window.close()

    def test_github_asset_redirect_with_encoded_spaces_is_accepted(self):
        class Reply(QObject):
            def readAll(self):
                return QByteArray(json.dumps({'version':'99.1.0','download_url':'https://downloads.example.test/new.zip'}).encode())
            def error(self): return QNetworkReply.NetworkError.NoError
            def url(self):
                return QUrl('https://release-assets.githubusercontent.com/asset?response-content-disposition=attachment%3B%20filename%3Dupdate.json')
        window=MainWindow()
        page=window.updates_page
        reply=Reply()
        self.assertFalse(valid_https_url(reply.url().toString()))
        page.reply=reply
        page.receive()
        self.assertEqual(page.state,'updates_available')
        self.assertTrue(page.download_button.isEnabled())
        window.dirty=False
        window.close()

    def test_network_error_has_friendly_message_and_support_code(self):
        class Reply(QObject):
            def readAll(self): return QByteArray()
            def error(self): return QNetworkReply.NetworkError.TimeoutError
            def errorString(self): return 'Operation timed out (test detail)'
        window=MainWindow()
        page=window.updates_page
        page.reply=Reply()
        page.receive()
        self.assertEqual(page.state,'updates_failed')
        self.assertIn('STC-U101',page.status.text())
        self.assertNotIn('Operation timed out (test detail)',page.status.text())
        window.dirty=False
        window.close()


if __name__ == '__main__':
    unittest.main()
