import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import pandas as pd
from PySide6.QtCore import QObject,Signal,QByteArray,QUrl,QEventLoop,QTimer
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkReply
from PySide6.QtWidgets import QApplication
from stc_statistics.app import MainWindow
from stc_statistics import update_installer as installer
from stc_statistics.projects import load_project
from stc_statistics.updates import parse_manifest
from stc_statistics.version import APP_VERSION
from make_patch import build_patch

ROOT=Path(__file__).resolve().parent.parent
TARGET='99.0.0'


class PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        provisioning=patch('stc_statistics.licensing.require_configured_release')
        provisioning.start()
        self.addCleanup(provisioning.stop)
        self.package,self.feed=build_patch(ROOT,self.root/'release',TARGET,[APP_VERSION],'Test patch')
        self.manifest=json.loads(self.feed.read_text())

    def fixture(self):
        runtime=self.root/'runtime-test'
        app=runtime/'app'
        (app/'stc_statistics').mkdir(parents=True)
        (runtime/'.complete').write_text('fixture')
        (app/'main.py').write_text('# previous app')
        (app/'stc_statistics/version.py').write_text(f'APP_VERSION = {APP_VERSION!r}\n')
        (app/'previous.txt').write_text('Keep rollback bytes')
        folder=self.root/'updates'/'job1'
        folder.mkdir(parents=True)
        (folder/'update.zip').write_bytes(self.package.read_bytes())
        (folder/'workspace.stcproj').write_bytes(b'checkpoint')
        job={'runtime':str(runtime),'pid':0,'from_version':APP_VERSION,'version':TARGET,'sha256':self.manifest['sha256']}
        installer.atomic_json(folder/'job.json',job)
        return runtime,folder

    def test_patch_validation_and_tampering(self):
        manifest=installer.validate_patch(self.package,self.manifest['sha256'],APP_VERSION,TARGET)
        self.assertEqual(manifest['format'],installer.FORMAT)
        with self.assertRaises(ValueError):
            installer.validate_patch(self.package,'0'*64,APP_VERSION,TARGET)
        with self.assertRaises(ValueError):
            installer.validate_patch(self.package,self.manifest['sha256'],'99.0.0',TARGET)
        for name in ('../evil.py','stc_statistics/../evil.py','/main.py','stc_statistics\\evil.py','stc_statistics/CON.py','stc_statistics/e.exe','stc_statistics/file.py:evil'):
            try:
                allowed=installer.safe_name(name)
            except ValueError:
                allowed=False
            self.assertFalse(allowed,name)
        with zipfile.ZipFile(self.package,'a') as z:
            z.writestr('../evil.py','print(1)')
        with self.assertRaises(ValueError):
            installer.validate_patch(self.package,installer.file_hash(self.package),APP_VERSION,TARGET)

    def test_manifest_requires_hash_size_and_official_asset(self):
        self.assertEqual(parse_manifest(self.manifest)['sha256'],self.manifest['sha256'])
        for field,value in [('sha256',None),('sha256','abc'),('size_bytes',True),('size_bytes',installer.MAX_PACKAGE+1),('download_url','https://evil.test/update.zip')]:
            bad=dict(self.manifest,**{field:value})
            with self.assertRaises(ValueError):
                parse_manifest(bad)

    def test_install_success_keeps_backup_and_workspace(self):
        runtime,folder=self.fixture()
        calls=[]
        class Child:
            def poll(self): return None
        def launch(runtime,workspace,health,reverted=False):
            calls.append((workspace,reverted))
            if health:
                installer.atomic_json(health,{'version':TARGET,'workspace_restored':True})
            return Child()
        self.assertTrue(installer.install_job(folder/'job.json',launcher=launch,health_timeout=1))
        self.assertEqual(installer.app_version(runtime/'app'),TARGET)
        self.assertEqual((runtime/'app-backup-job1/previous.txt').read_text(),'Keep rollback bytes')
        self.assertEqual((folder/'workspace.stcproj').read_bytes(),b'checkpoint')
        self.assertEqual(json.loads((folder/'status.json').read_text())['state'],'installed')
        self.assertFalse((self.root/'updates/install.lock').exists())

    def test_failed_startup_rolls_back_and_reopens_checkpoint(self):
        runtime,folder=self.fixture()
        calls=[]
        class Child:
            def poll(self): return 1
        def launch(runtime,workspace,health,reverted=False):
            calls.append((workspace,reverted))
            return Child()
        self.assertFalse(installer.install_job(folder/'job.json',launcher=launch,health_timeout=.1))
        self.assertEqual(installer.app_version(runtime/'app'),APP_VERSION)
        self.assertEqual((runtime/'app/previous.txt').read_text(),'Keep rollback bytes')
        self.assertEqual(calls[-1],(folder/'workspace.stcproj',True))
        self.assertEqual(json.loads((folder/'status.json').read_text())['state'],'rolled_back')

    def test_failed_directory_swap_restores_original(self):
        runtime,folder=self.fixture()
        real=installer.os.replace
        def replace(source,destination):
            if Path(source).name=='staged-app':
                raise PermissionError('Simulated locked directory')
            return real(source,destination)
        with patch.object(installer.os,'replace',side_effect=replace),patch.object(installer.time,'sleep'):
            self.assertFalse(installer.install_job(folder/'job.json',launcher=lambda *args:None))
        self.assertTrue((runtime/'app/previous.txt').is_file())
        self.assertEqual(installer.app_version(runtime/'app'),APP_VERSION)

    def test_existing_install_lock_is_respected(self):
        runtime,folder=self.fixture()
        lock=self.root/'updates/install.lock'
        lock.write_text('another installer')
        with self.assertRaises(FileExistsError):
            installer.install_job(folder/'job.json',launcher=lambda *args:None)
        self.assertEqual(lock.read_text(),'another installer')

    @unittest.skipUnless(os.name=='nt','Windows file sharing behavior')
    def test_status_write_retries_transient_windows_lock(self):
        real=installer.os.replace
        attempts=[]
        def replace(source,destination):
            attempts.append(destination)
            if len(attempts)==1:
                raise PermissionError('Simulated transient reader lock')
            return real(source,destination)
        path=self.root/'status.json'
        with patch.object(installer.os,'replace',side_effect=replace),patch.object(installer.time,'sleep'):
            installer.atomic_json(path,{'state':'installed'})
        self.assertEqual(json.loads(path.read_text())['state'],'installed')
        self.assertEqual(len(attempts),2)

    def make_reply(self,raw):
        class Reply(QObject):
            readyRead=Signal()
            downloadProgress=Signal(int,int)
            finished=Signal()
            def __init__(self):
                super().__init__()
                self.raw=raw
                self.aborted=False
            def setReadBufferSize(self,size): pass
            def readAll(self):
                value,self.raw=self.raw,b''
                return QByteArray(value)
            def url(self): return QUrl('https://release-assets.githubusercontent.com/asset.zip')
            def error(self): return QNetworkReply.NetworkError.OperationCanceledError if self.aborted else QNetworkReply.NetworkError.NoError
            def errorString(self): return 'Cancelled' if self.aborted else ''
            def abort(self):
                self.aborted=True
                self.finished.emit()
        return Reply()

    def window(self):
        window=MainWindow()
        window.language_picker.setCurrentIndex(0)
        window.use_frame(pd.DataFrame({'x':[1.5,2.5]}))
        window.add_cell('important_code = 42')
        window.navigate('updates')
        self.addCleanup(lambda:(setattr(window,'dirty',False),window.close()))
        return window

    def test_in_app_download_progress_checkpoint_and_restart_dispatch(self):
        window=self.window()
        page=window.updates_page
        runtime=self.root/'runtime-test'
        runtime.mkdir()
        reply=self.make_reply(self.package.read_bytes())
        page.accept_manifest(self.manifest)
        loop=QEventLoop()
        with patch('stc_statistics.update_flow.installed_runtime',return_value=runtime),patch.object(QNetworkAccessManager,'get',return_value=reply),patch('stc_statistics.update_flow.subprocess.Popen') as launch:
            launch.return_value.poll.return_value=None
            def ready(*args,**kwargs):
                installer.atomic_json(page.flow.folder/'ready.json',{'ready':True,'version':TARGET})
                return launch.return_value
            launch.side_effect=ready
            page.download()
            reply.downloadProgress.emit(len(reply.raw)//2,len(reply.raw))
            self.assertEqual(page.progress.value(),(len(reply.raw)//2)*90//len(reply.raw))
            reply.readyRead.emit()
            reply.finished.emit()
            page.flow.worker.finished.connect(loop.quit)
            QTimer.singleShot(5000,loop.quit)
            loop.exec()
            QApplication.processEvents()
            self.assertEqual(launch.call_count,1,page.status.text())
        frame,notebook,settings=load_project(page.flow.folder/'workspace.stcproj')
        self.assertEqual(frame.x.tolist(),[1.5,2.5])
        self.assertEqual(notebook.cells[0].source,'important_code = 42')
        self.assertTrue(settings['_update_recovery']['dirty'])
        self.assertTrue((page.flow.folder/'installer.py').is_file())
        self.assertEqual(page.state,'update_installing')

    def test_cancel_preserves_app_and_workspace(self):
        window=self.window()
        page=window.updates_page
        runtime=self.root/'runtime-test'
        runtime.mkdir()
        reply=self.make_reply(self.package.read_bytes())
        page.accept_manifest(self.manifest)
        with patch('stc_statistics.update_flow.installed_runtime',return_value=runtime),patch.object(QNetworkAccessManager,'get',return_value=reply),patch('stc_statistics.update_flow.subprocess.Popen') as launch:
            page.download()
            page.flow.cancel()
            self.assertEqual(page.state,'update_cancelled')
            self.assertFalse(window.updating)
            self.assertTrue(window.dirty)
            launch.assert_not_called()

    def test_hash_failure_does_not_close_or_install(self):
        window=self.window()
        page=window.updates_page
        runtime=self.root/'runtime-test'
        runtime.mkdir()
        reply=self.make_reply(self.package.read_bytes()+b'changed')
        manifest=dict(self.manifest,size_bytes=len(reply.raw))
        page.accept_manifest(manifest)
        loop=QEventLoop()
        with patch('stc_statistics.update_flow.installed_runtime',return_value=runtime),patch.object(QNetworkAccessManager,'get',return_value=reply),patch('stc_statistics.update_flow.subprocess.Popen') as launch:
            page.download()
            reply.readyRead.emit()
            reply.finished.emit()
            page.flow.worker.finished.connect(loop.quit)
            QTimer.singleShot(5000,loop.quit)
            loop.exec()
            QApplication.processEvents()
            self.assertEqual(page.state,'updates_failed')
            self.assertIn('STC-U202',page.status.text())
            self.assertNotIn('checksum',page.status.text())
            self.assertTrue(window.dirty)
            launch.assert_not_called()

    def test_checkpoint_failure_aborts_install_without_losing_edits(self):
        window=self.window()
        page=window.updates_page
        runtime=self.root/'runtime-test'
        runtime.mkdir()
        reply=self.make_reply(self.package.read_bytes())
        page.accept_manifest(self.manifest)
        loop=QEventLoop()
        with patch('stc_statistics.update_flow.installed_runtime',return_value=runtime),patch.object(QNetworkAccessManager,'get',return_value=reply),patch('stc_statistics.update_flow.subprocess.Popen') as launch,patch('stc_statistics.workbench.project_save',side_effect=OSError('Disk write failed')):
            page.download()
            reply.readyRead.emit()
            reply.finished.emit()
            page.flow.worker.finished.connect(loop.quit)
            QTimer.singleShot(5000,loop.quit)
            loop.exec()
            QApplication.processEvents()
            self.assertEqual(page.state,'updates_failed')
            self.assertIn('STC-U301',page.status.text())
            self.assertNotIn('Disk write failed',page.status.text())
            self.assertTrue(window.dirty)
            self.assertEqual(window.frame.x.tolist(),[1.5,2.5])
            self.assertFalse(window.updating)
            launch.assert_not_called()

    def test_installer_start_failure_keeps_unsaved_app_open(self):
        window=self.window()
        page=window.updates_page
        runtime=self.root/'runtime-test'
        runtime.mkdir()
        reply=self.make_reply(self.package.read_bytes())
        page.accept_manifest(self.manifest)
        loop=QEventLoop()
        with patch('stc_statistics.update_flow.installed_runtime',return_value=runtime),patch.object(QNetworkAccessManager,'get',return_value=reply),patch('stc_statistics.update_flow.subprocess.Popen') as launch:
            launch.return_value.poll.return_value=1
            page.download()
            reply.readyRead.emit()
            reply.finished.emit()
            page.flow.worker.finished.connect(loop.quit)
            QTimer.singleShot(5000,loop.quit)
            loop.exec()
            QApplication.processEvents()
            self.assertEqual(page.state,'updates_failed')
            self.assertTrue(window.dirty)
            self.assertFalse(getattr(window,'_update_exit',False))
            self.assertTrue((page.flow.folder/'workspace.stcproj').is_file())


if __name__=='__main__':
    unittest.main()
