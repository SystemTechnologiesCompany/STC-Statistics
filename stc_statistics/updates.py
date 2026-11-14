"""Version checks and browser downloads. Never installs or replaces running code."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTextBrowser
from .theme import GlassButton
from .version import APP_VERSION

CONFIG_PATH = Path(__file__).resolve().parent / 'update_config.json'
MAX_FEED_BYTES = 256 * 1024


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
    return {'version': payload['version'], 'download_url': payload['download_url'], 'release_notes': notes[:12000]}


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
        self.translate()

    def translate(self):
        self.installed.setText(f"{self.app.t('installed_version')}  {APP_VERSION}")
        self.check_button.setText(self.app.t('check_updates'))
        self.download_button.setText(self.app.t('download_update'))
        self.how_title.setText(self.app.t('how_update'))
        self.how_text.setText(self.app.t('update_instructions'))
        self.website_button.setText(self.app.t('visit_stc'))
        message = self.app.t(self.state)
        if self.latest:
            message += '\n' + self.app.t('latest_version') + ' ' + self.latest['version']
        self.status.setText(message)
        self.check_button.setEnabled(bool(self.config.get('manifest_url')) and self.reply is None)
        self.download_button.setEnabled(valid_https_url(self.download_url) and self.reply is None)

    def check(self):
        url = self.config.get('manifest_url', '')
        if self.reply is not None or not valid_https_url(url):
            return
        self.state = 'updates_checking'
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
        if valid_https_url(self.download_url):
            if not QDesktopServices.openUrl(QUrl(self.download_url)):
                self.state = 'updates_failed'
                self.translate()
