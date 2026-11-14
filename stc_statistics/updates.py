"""Release checks plus verified in-app patch downloads and restart recovery."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTextBrowser, QProgressBar
from .theme import GlassButton
from .version import APP_VERSION

CONFIG_PATH = Path(__file__).resolve().parent / 'update_config.json'
MAX_FEED_BYTES = 256 * 1024

from .i18n import TEXT
for key,en,fr in [
    ('install_update','Update app','Mettre à jour l’application'),
    ('cancel_update','Cancel download','Annuler le téléchargement'),
    ('update_downloading','Downloading the update…','Téléchargement de la mise à jour…'),
    ('update_verifying','Verifying the update…','Vérification de la mise à jour…'),
    ('update_saving','Saving your workspace…','Enregistrement de votre espace de travail…'),
    ('update_installing','Installing and restarting…','Installation et redémarrage…'),
    ('update_cancelled','Update cancelled. Your app has not changed.','Mise à jour annulée. Votre application est inchangée.'),
    ('update_wait_idle','Finish the running calculation or import before updating.','Terminez le calcul ou l’importation avant la mise à jour.'),
    ('update_restored','Update finished. Your workspace has been restored.','Mise à jour terminée. Votre espace de travail a été restauré.'),
    ('update_rolled_back','The update failed. The previous app and your workspace have been restored.','La mise à jour a échoué. L’ancienne application et votre espace de travail ont été restaurés.')]:
    TEXT['en'][key],TEXT['fr'][key]=en,fr
TEXT['en']['update_instructions']='Click Check for updates, then Update app. The download runs here with progress. Your data, notebook cells, results and settings are saved before installation. The app restarts and restores the workspace. Failed startup triggers rollback. Legacy full releases open in your browser.'
TEXT['fr']['update_instructions']='Cliquez sur Vérifier les mises à jour, puis Mettre à jour l’application. Le téléchargement affiche sa progression ici. Les données, cellules, résultats et réglages sont enregistrés avant l’installation. L’application redémarre et restaure votre travail. Un échec au démarrage déclenche une restauration. Les anciennes versions complètes s’ouvrent dans le navigateur.'


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Expected a major.minor.patch version.')
    return tuple(int(part) for part in value.split('.'))


def valid_https_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        parsed.port
        return (parsed.scheme == 'https' and bool(parsed.hostname) and parsed.username is None
                and parsed.password is None and not any(c.isspace() for c in value))
    except ValueError:
        return False


def parse_manifest(payload):
    if not isinstance(payload, dict):
        raise ValueError('Invalid update feed.')
    version_tuple(payload.get('version'))
    if not valid_https_url(payload.get('download_url')):
        raise ValueError('The update download must use HTTPS.')
    notes = payload.get('release_notes', '')
    if not isinstance(notes, str):
        raise ValueError('Invalid release notes.')
    result={'version': payload['version'], 'download_url': payload['download_url'], 'release_notes': notes[:12000]}
    if payload.get('package_type') is not None:
        from .update_installer import FORMAT, MAX_PACKAGE
        url=urlsplit(payload['download_url'])
        if (payload['package_type']!=FORMAT or not isinstance(payload.get('sha256'),str) or not re.fullmatch(r'[a-fA-F0-9]{64}',payload.get('sha256',''))
                or type(payload.get('size_bytes')) is not int or not 0<payload['size_bytes']<=MAX_PACKAGE
                or url.hostname!='github.com'
                or not url.path.startswith('/SystemTechnologiesCompany/STC-Statistics/releases/download/')):
            raise ValueError('Invalid patch metadata or untrusted release URL')
        result.update(package_type=FORMAT,sha256=payload['sha256'].lower(),size_bytes=payload['size_bytes'])
    return result


def load_config(path=CONFIG_PATH):
    try:
        config = json.loads(Path(path).read_text(encoding='utf-8'))
        return {key: config.get(key, '') if valid_https_url(config.get(key, '')) else ''
                for key in ('manifest_url', 'download_url')}
    except (OSError, ValueError, AttributeError):
        return {'manifest_url': '', 'download_url': ''}


class UpdatesPage(QWidget):
    def __init__(self, app, config=None):
        super().__init__()
        self.app = app
        self.config = load_config() if config is None else config
        self.latest = None
        self.reply = None
        self.download_url = self.config.get('download_url', '')
        self.state = 'updates_unconfigured' if not any(self.config.values()) else 'updates_not_checked'
        self.network = QNetworkAccessManager(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        panel = QFrame()
        panel.setObjectName('pageCard')
        content = QVBoxLayout(panel)
        content.setContentsMargins(24, 24, 24, 24)
        content.setSpacing(18)
        self.installed = QLabel()
        self.installed.setObjectName('cardTitle')
        content.addWidget(self.installed)
        self.status = QLabel()
        self.status.setWordWrap(True)
        content.addWidget(self.status)
        controls = QHBoxLayout()
        self.check_button = GlassButton()
        self.check_button.clicked.connect(self.check)
        controls.addWidget(self.check_button)
        self.download_button = GlassButton()
        self.download_button.setObjectName('primary')
        self.download_button.clicked.connect(self.download)
        controls.addWidget(self.download_button)
        controls.addStretch()
        content.addLayout(controls)
        self.progress=QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setFormat('%p%')
        self.progress.setStyleSheet('QProgressBar {border:1px solid #8a968f; border-radius:7px; background:#121a17; min-height:18px; text-align:center; color:#e8ece9;} QProgressBar::chunk {background:#3fbf7f; border-radius:6px;}')
        self.progress.hide()
        content.addWidget(self.progress)
        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(False)
        self.notes.setMaximumHeight(140)
        self.notes.hide()
        content.addWidget(self.notes)
        layout.addWidget(panel)
        how = QFrame()
        how.setObjectName('pageCard')
        instructions = QVBoxLayout(how)
        instructions.setContentsMargins(24, 22, 24, 22)
        self.how_title = QLabel()
        self.how_title.setObjectName('cardTitle')
        self.how_text = QLabel()
        self.how_text.setWordWrap(True)
        instructions.addWidget(self.how_title)
        instructions.addWidget(self.how_text)
        self.website_button = GlassButton()
        self.website_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://stc-official.netlify.app/')))
        instructions.addWidget(self.website_button)
        layout.addWidget(how)
        layout.addStretch()
        from .update_flow import UpdateFlow
        self.flow=UpdateFlow(self)
        self.translate()

    def translate(self):
        self.installed.setText(f"{self.app.t('installed_version')}  {APP_VERSION}")
        self.check_button.setText(self.app.t('check_updates'))
        self.download_button.setText(self.app.t('install_update') if self.latest and self.latest.get('package_type') else self.app.t('download_update'))
        self.how_title.setText(self.app.t('how_update'))
        self.how_text.setText(self.app.t('update_instructions'))
        self.website_button.setText(self.app.t('visit_stc'))
        message = self.app.t(self.state)
        if self.latest:
            message += '\n' + self.app.t('latest_version') + ' ' + self.latest['version']
        if self.flow.error and self.state=='updates_failed':
            message += '\n' + self.flow.error
        self.status.setText(message)
        self.check_button.setEnabled(bool(self.config.get('manifest_url')) and self.reply is None and not self.flow.busy)
        self.download_button.setEnabled(valid_https_url(self.download_url) and self.reply is None and not self.flow.busy)

    def check(self):
        url = self.config.get('manifest_url', '')
        if self.reply is not None or self.flow.busy or not valid_https_url(url):
            return
        self.state = 'updates_checking'
        self.flow.error=''
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b'Accept', b'application/json')
        request.setRawHeader(b'User-Agent', f'STC-Statistics/{APP_VERSION}'.encode())
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        request.setTransferTimeout(15000)
        self.reply = self.network.get(request)
        self.reply.downloadProgress.connect(lambda received, total: self.reply.abort() if self.reply is not None and (received > MAX_FEED_BYTES or total > MAX_FEED_BYTES) else None)
        self.reply.finished.connect(self.receive)
        self.translate()

    def accept_manifest(self, payload):
        latest = parse_manifest(payload)
        self.latest = latest
        newer = version_tuple(latest['version']) > version_tuple(APP_VERSION)
        self.state = 'updates_available' if newer else 'updates_current'
        self.download_url = latest['download_url'] if newer else ''
        self.notes.setPlainText(latest['release_notes'])
        self.notes.setVisible(bool(latest['release_notes']))

    def receive(self):
        reply, self.reply = self.reply, None
        try:
            raw = bytes(reply.readAll())
            if reply.error() != QNetworkReply.NetworkError.NoError or len(raw) > MAX_FEED_BYTES or not valid_https_url(reply.url().toString()):
                raise ValueError('Update check failed.')
            self.accept_manifest(json.loads(raw))
        except (ValueError, TypeError, UnicodeError):
            self.state = 'updates_failed'
        finally:
            reply.deleteLater()
            self.translate()

    def download(self):
        if self.latest and self.latest.get('package_type'):
            self.flow.start(self.latest)
            return
        if valid_https_url(self.download_url):
            if not QDesktopServices.openUrl(QUrl(self.download_url)):
                self.state = 'updates_failed'
                self.translate()
