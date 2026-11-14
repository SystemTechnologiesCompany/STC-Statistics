"""Qt download/progress controller. Installation runs after the app exits."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from PySide6.QtCore import QObject, QThread, Signal, QUrl, Qt, QTimer
from PySide6.QtNetwork import QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import QProgressDialog
from .update_installer import MAX_PACKAGE, atomic_json, validate_patch
from .version import APP_VERSION


def installed_runtime():
    runtime=Path(os.environ.get('STC_PORTABLE_ROOT','')).resolve()
    if (not os.environ.get('STC_PORTABLE_ROOT') or not (runtime/'.complete').is_file()
            or Path(__file__).resolve().parent.parent != runtime/'app'):
        raise ValueError('Use the installed EXE after enabling the updater / Utilisez le fichier EXE après activation des mises à jour')
    return runtime


class VerifyPatch(QThread):
    verified=Signal()
    failed=Signal(str)
    def __init__(self, package, manifest, parent=None):
        super().__init__(parent)
        self.package,self.manifest=package,manifest
    def run(self):
        try:
            validate_patch(self.package,self.manifest['sha256'],APP_VERSION,self.manifest['version'])
            self.verified.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateFlow(QObject):
    def __init__(self,page):
        super().__init__(page)
        self.page,self.app=page,page.app
        self.reply=self.file=self.worker=self.dialog=None
        self.cancelled=False
        self.error=''
        self.received=0
        self.installing=False
        self.installer_timer=QTimer(self)
        self.installer_timer.setInterval(100)
        self.installer_timer.timeout.connect(self.wait_for_installer)

    @property
    def busy(self):
        return self.reply is not None or (self.worker is not None and self.worker.isRunning()) or self.installing

    def start(self,manifest):
        if self.busy:
            return
        try:
            if self.app.active or (self.app.loader and self.app.loader.isRunning()):
                raise ValueError(self.app.t('update_wait_idle'))
            self.runtime=installed_runtime()
            if (self.runtime.parent/'updates/install.lock').exists():
                raise RuntimeError('Another update is already being installed / Une autre mise à jour est déjà en cours')
            if shutil.disk_usage(self.runtime).free < self.manifest_size(manifest):
                raise OSError('Not enough disk space to install and retain a rollback copy')
            self.folder=self.runtime.parent/'updates'/uuid.uuid4().hex
            self.folder.mkdir(parents=True)
            self.manifest=dict(manifest)
            self.file=(self.folder/'update.zip').open('xb')
            self.received=0
            self.error=''
            self.cancelled=False
            self.app.updating=True
            self.dialog=QProgressDialog(self.app.t('update_downloading'),self.app.t('cancel_update'),0,100,self.app)
            self.dialog.setWindowTitle('STC Statistics')
            self.dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            self.dialog.setMinimumDuration(0)
            self.dialog.setAutoClose(False)
            self.dialog.setAutoReset(False)
            self.dialog.setStyleSheet(self.page.progress.styleSheet())
            self.dialog.canceled.connect(self.cancel)
            self.page.state='update_downloading'
            self.page.progress.show()
            self.page.progress.setRange(0,100)
            self.page.progress.setValue(0)
            request=QNetworkRequest(QUrl(manifest['download_url']))
            request.setRawHeader(b'Accept',b'application/octet-stream')
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
            request.setTransferTimeout(60000)
            self.reply=self.page.network.get(request)
            self.reply.setReadBufferSize(1024**2)
            self.reply.readyRead.connect(self.read)
            self.reply.downloadProgress.connect(self.progress)
            self.reply.finished.connect(self.finish_download)
            self.dialog.show()
            self.page.translate()
        except Exception as exc:
            self.fail(str(exc))

    def read(self):
        if self.reply is None or self.file is None or self.error or self.cancelled:
            return
        try:
            raw=bytes(self.reply.readAll())
            self.received+=len(raw)
            if self.received>MAX_PACKAGE:
                raise ValueError('Update package exceeds 64 MiB')
            self.file.write(raw)
        except Exception as exc:
            self.error=str(exc)
            self.reply.abort()

    def progress(self,received,total):
        if self.reply is None:
            return
        if total>MAX_PACKAGE or received>MAX_PACKAGE:
            self.error='Update package exceeds 64 MiB'
            self.reply.abort()
            return
        value=min(90,int(received*90/total)) if total>0 else 0
        self.page.progress.setRange(0,100 if total>0 else 0)
        self.page.progress.setValue(value)
        if self.dialog:
            self.dialog.setRange(0,100 if total>0 else 0)
            self.dialog.setValue(value)
            self.dialog.setLabelText(self.app.t('update_downloading')+f'\n{received/1048576:.1f} / {total/1048576:.1f} MiB' if total>0 else self.app.t('update_downloading'))

    def finish_download(self):
        reply=self.reply
        if reply is None:
            return
        self.read()
        self.reply=None
        self.file.close()
        self.file=None
        try:
            if self.cancelled:
                self.fail(self.app.t('update_cancelled'))
                return
            if self.error or reply.error()!=QNetworkReply.NetworkError.NoError or reply.url().scheme()!='https':
                raise ValueError(self.error or reply.errorString())
            if self.received!=self.manifest['size_bytes']:
                raise ValueError('Incomplete update download')
            self.set_phase('update_verifying',93)
            self.worker=VerifyPatch(self.folder/'update.zip',self.manifest,self)
            self.worker.failed.connect(self.fail)
            self.worker.finished.connect(self.verification_finished)
            self.worker.start()
        except Exception as exc:
            self.fail(str(exc))
        finally:
            reply.deleteLater()

    def set_phase(self,key,value):
        self.page.state=key
        self.page.progress.setRange(0,100)
        self.page.progress.setValue(value)
        if self.dialog:
            self.dialog.setRange(0,100)
            self.dialog.setValue(value)
            self.dialog.setLabelText(self.app.t(key))
        self.page.translate()

    def verified(self):
        # finished is queued after failed, so a validation failure cannot install.
        if self.error or self.cancelled:
            self.app.updating=False
            self.page.translate()
            return
        try:
            self.installing=True
            self.set_phase('update_saving',96)
            from .workbench import project_save
            self.app._update_recovery={
                'project_path':self.app.project_path,'dirty':self.app.dirty,
                'file_path':self.app.file_path,'page':self.app.current_page,
                'cursors':[c.editor.textCursor().position() for c in self.app.cells],
                'report_flags':[self.app.report_tables.isChecked(),self.app.report_graphs.isChecked(),self.app.report_text.isChecked(),self.app.report_code.isChecked()]}
            try:
                project_save(self.app,path=str(self.folder/'workspace.stcproj'),set_current=False)
            finally:
                del self.app._update_recovery
            from . import update_installer
            shutil.copy2(update_installer.__file__,self.folder/'installer.py')
            job={'runtime':str(self.runtime),'pid':os.getpid(),'from_version':APP_VERSION,
                 'version':self.manifest['version'],'sha256':self.manifest['sha256']}
            atomic_json(self.folder/'job.json',job)
            self.set_phase('update_installing',99)
            if self.dialog:
                self.dialog.setCancelButton(None)
            self.process=subprocess.Popen([sys.executable,'-B',str(self.folder/'installer.py'),str(self.folder/'job.json')],
                             cwd=str(self.folder),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            self.installer_deadline=time.monotonic()+90
            self.installer_timer.start()
            self.wait_for_installer()
        except Exception as exc:
            self.installing=False
            self.fail(str(exc))

    def wait_for_installer(self):
        try:
            if self.process.poll() is not None:
                raise RuntimeError('The update installer could not prepare the update. Your app is still open.')
            ready=self.folder/'ready.json'
            if ready.is_file():
                state=json.loads(ready.read_text(encoding='utf-8'))
                if state.get('ready') is not True or state.get('version')!=self.manifest['version']:
                    raise ValueError('Invalid installer readiness acknowledgement')
                self.installer_timer.stop()
                self.app._update_exit=True
                # Only close after the separate helper has staged and validated the patch.
                self.app.dirty=False
                if self.dialog:
                    self.dialog.close()
                self.app.close()
            elif time.monotonic()>self.installer_deadline:
                raise TimeoutError('The installer is taking too long. Your current app remains open; retry after it finishes.')
        except Exception as exc:
            self.installer_timer.stop()
            self.installing=False
            self.fail(str(exc))

    def verification_finished(self):
        worker,self.worker=self.worker,None
        if worker:
            worker.deleteLater()
        self.verified()

    @staticmethod
    def manifest_size(manifest):
        from .update_installer import MAX_EXPANDED
        return MAX_EXPANDED+manifest['size_bytes']

    def cancel(self):
        if self.installing:
            return
        self.cancelled=True
        if self.reply is not None:
            self.reply.abort()
        else:
            self.fail(self.app.t('update_cancelled'))

    def fail(self,message):
        self.installer_timer.stop()
        self.error=message
        if self.file:
            self.file.close()
            self.file=None
        self.app.updating=False
        self.page.state='update_cancelled' if self.cancelled else 'updates_failed'
        self.page.progress.hide()
        if self.dialog:
            self.dialog.hide()
        self.page.translate()
