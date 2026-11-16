import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from make_patch import build_patch
from stc_statistics.update_installer import validate_patch,RUNTIME_ID,file_hash
from stc_statistics.updates import parse_manifest,supports_installation
from stc_statistics.app import MainWindow
from stc_statistics.version import APP_VERSION

ROOT=Path(__file__).resolve().parent.parent


class CumulativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.destination=Path(self.temp.name)

    def test_future_release_can_skip_missing_intermediate_patch_with_old_validator(self):
        # This is a temporary future-version fixture, never a published release.
        package,feed=build_patch(ROOT,self.destination,'1.0.3',['1.0.2'])
        manifest=parse_manifest(json.loads(feed.read_text(encoding='utf-8')))
        self.assertTrue(manifest['cumulative'])
        for previous in ('0.5.6','1.0.0','1.0.1','1.0.2'):
            validate_patch(package,manifest['sha256'],previous,'1.0.3')
            self.assertTrue(supports_installation(manifest,previous))
        # Exercise the exact validator shipped before these changes.
        with zipfile.ZipFile(ROOT/'releases/1.0.1/STC_Statistics_1.0.1_Update.zip') as old:
            namespace={'__name__':'old_validator'}
            exec(compile(old.read('stc_statistics/update_installer.py'),'old_validator','exec'),namespace)
        namespace['validate_patch'](package,manifest['sha256'],'1.0.1','1.0.3')
        with zipfile.ZipFile(package) as archive:
            self.assertIn('main.py',archive.namelist())
            self.assertIn('stc_statistics/scene_view.py',archive.namelist())
            self.assertIn('stc_statistics/science.py',archive.namelist())
        self.assertFalse(supports_installation(manifest,'0.5.0'))

    def test_default_builder_includes_history_and_runtime_floor(self):
        package,feed=build_patch(ROOT,self.destination,'1.0.3')
        item=json.loads(feed.read_text())
        self.assertIn('1.0.1',item['from_versions']); self.assertIn('1.0.2',item['from_versions'])
        self.assertNotIn('0.5.0',item['from_versions'])
        self.assertEqual(item['runtime_id'],RUNTIME_ID)
        with self.assertRaises(ValueError): build_patch(ROOT,self.destination/'bad','1.0.3',['1.0.3'])

    def test_range_aware_updater_also_skips_releases_across_minor_versions(self):
        package,feed=build_patch(ROOT,self.destination,'1.1.0')
        manifest=parse_manifest(json.loads(feed.read_text()))
        self.assertTrue(supports_installation(manifest,'1.0.2'))
        validate_patch(package,manifest['sha256'],'1.0.2','1.1.0')
        self.assertFalse(supports_installation(manifest,'1.1.0'))

    def test_unrelated_runtime_or_invalid_compatibility_is_rejected(self):
        package,feed=build_patch(ROOT,self.destination,'99.0.0')
        item=json.loads(feed.read_text())
        incompatible=parse_manifest(dict(item,runtime_id='another-runtime'))
        self.assertFalse(supports_installation(incompatible,APP_VERSION))
        for changes in ({'from_versions':[{}]},{'minimum_version':'99.0.0'},{'cumulative':False}):
            with self.assertRaises(ValueError): parse_manifest(dict(item,**changes))
        with zipfile.ZipFile(package) as archive: content={n:archive.read(n) for n in archive.namelist()}
        meta=json.loads(content['patch.json']); meta['runtime_id']='another-runtime'
        content['patch.json']=json.dumps(meta).encode()
        bad=self.destination/'different-runtime.zip'
        with zipfile.ZipFile(bad,'w') as archive:
            for name,raw in content.items(): archive.writestr(name,raw)
        with self.assertRaises(ValueError): validate_patch(bad,file_hash(bad),APP_VERSION,'99.0.0')

    def test_incompatible_feed_does_not_offer_or_start_download_in_either_language(self):
        app=QApplication.instance() or QApplication([])
        settings=QSettings(str(self.destination/'settings.ini'),QSettings.Format.IniFormat)
        with patch('stc_statistics.app.QSettings',return_value=settings): window=MainWindow()
        self.addCleanup(lambda:(setattr(window,'dirty',False),window.close(),app.processEvents()))
        _,feed=build_patch(ROOT,self.destination,'99.0.0')
        item=json.loads(feed.read_text()); item['runtime_id']='another-runtime'
        page=window.updates_page; page.accept_manifest(item); page.translate()
        self.assertEqual(page.state,'updates_incompatible')
        self.assertFalse(page.download_button.isEnabled())
        window.language_picker.setCurrentIndex(1)
        self.assertIn('STC-U203',page.status.text())
        with patch.object(page.network,'get') as download:
            page.flow.start(parse_manifest(item))
            download.assert_not_called()
