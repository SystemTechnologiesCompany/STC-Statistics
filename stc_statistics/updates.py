"""Release checks plus verified in-app patch downloads and restart recovery."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTextBrowser, QProgressBar
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
    result={'version': payload['version'], 'download_url': payload['download_url'], 'release_notes': notes[:12000]}
    public=payload.get('user_notes',{})
    if not isinstance(public,dict) or any(k not in ('en','fr') or not isinstance(v,str) for k,v in public.items()):
        raise ValueError('Invalid public update notes.')
    result['user_notes']={k:v[:4000] for k,v in public.items()}
    if payload.get('package_type') is not None:
        from .update_installer import FORMAT, MAX_PACKAGE
        url=urlsplit(payload['download_url'])
        if (payload['package_type']!=FORMAT or not isinstance(payload.get('sha256'),str) or not re.fullmatch(r'[a-fA-F0-9]{64}',payload.get('sha256',''))
                or type(payload.get('size_bytes')) is not int or not 0<payload['size_bytes']<=MAX_PACKAGE
                or url.hostname!='github.com'
                or not url.path.startswith('/SystemTechnologiesCompany/STC-Statistics/releases/download/')):
            raise ValueError('Invalid patch metadata or untrusted release URL')
        result.update(package_type=FORMAT,sha256=payload['sha256'].lower(),size_bytes=payload['size_bytes'])
        if any(key in payload for key in ('cumulative','runtime_id','minimum_version','from_versions')):
            sources=payload.get('from_versions')
            if (payload.get('cumulative') is not True or not isinstance(payload.get('runtime_id'),str)
                    or not payload['runtime_id'] or not isinstance(sources,list) or not 0<len(sources)<=20000
                    or any(not isinstance(source,str) for source in sources)):
                raise ValueError('Invalid cumulative compatibility metadata')
            floor=version_tuple(payload.get('minimum_version'))
            if floor>=version_tuple(payload['version']): raise ValueError('Invalid update compatibility floor')
            if len(set(sources))!=len(sources): raise ValueError('Duplicate compatible source versions')
            for source in sources:
                if not floor<=version_tuple(source)<version_tuple(payload['version']): raise ValueError('Invalid compatible source version')
            result.update(cumulative=True,runtime_id=payload['runtime_id'],minimum_version=payload['minimum_version'],from_versions=list(sources))
    return result


def supports_installation(manifest,current=APP_VERSION):
    if not manifest.get('cumulative'): return True  # Legacy feeds are verified from their ZIP.
    from .update_installer import RUNTIME_ID
    try:
        return (manifest['runtime_id']==RUNTIME_ID and version_tuple(manifest['minimum_version'])<=version_tuple(current)
                <version_tuple(manifest['version']))
    except (ValueError,TypeError,KeyError): return False


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
        self.download_url = ''
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
        self.status.setTextFormat(Qt.TextFormat.PlainText)
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
        self.notes_title=QLabel()
        self.notes_title.setObjectName('section')
        self.notes_title.hide()
        content.addWidget(self.notes_title)
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
        self.how_title.setWordWrap(True)
        self.how_text = QLabel()
        self.how_text.setTextFormat(Qt.TextFormat.RichText)
        self.how_text.setWordWrap(True)
        instructions.addWidget(self.how_title)
        instructions.addWidget(self.how_text)
        self.session_note=QLabel()
        self.session_note.setObjectName('hint')
        self.session_note.setWordWrap(True)
        instructions.addWidget(self.session_note)
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
        legacy=self.latest and not self.latest.get('package_type')
        self.download_button.setText(self.app.t('legacy_download' if legacy else 'install_update'))
        self.how_title.setText(self.app.t('how_update'))
        self.how_text.setText(self.app.t('legacy_instructions' if legacy else 'update_instructions'))
        self.session_note.setText(self.app.t('update_session_note'))
        self.session_note.setVisible(not legacy)
        self.notes_title.setText(self.app.t('updates_highlights'))
        self.website_button.setText(self.app.t('visit_stc'))
        from .update_messages import friendly_error
        message = friendly_error(getattr(self.flow,'error_code','STC-U401'),self.app.language) if self.state=='updates_failed' else self.app.t(self.state)
        if legacy and self.state=='updates_available':
            message=self.app.t('legacy_available')
        if self.latest:
            message += '\n' + self.app.t('latest_version') + ' ' + self.latest['version']
        self.status.setText(message)
        if self.latest:
            self.notes.setPlainText(self.latest.get('user_notes',{}).get(self.app.language) or self.app.t('updates_public_summary'))
        self.check_button.setEnabled(bool(self.config.get('manifest_url')) and self.reply is None and not self.flow.busy)
        self.download_button.setEnabled(valid_https_url(self.download_url) and self.reply is None and not self.flow.busy)

    def check(self):
        url = self.config.get('manifest_url', '')
        if self.reply is not None or self.flow.busy or not valid_https_url(url):
            return
        self.state = 'updates_checking'
        self.flow.error=''
        self.flow.error_code=''
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b'Accept', b'application/json')
        request.setRawHeader(b'User-Agent', f'STC-Statistics/{APP_VERSION}'.encode())
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        request.setRawHeader(b'Cache-Control', b'no-cache')
        request.setTransferTimeout(60000)
        self.reply = self.network.get(request)
        self.reply.downloadProgress.connect(lambda received, total: self.reply.abort() if self.reply is not None and (received > MAX_FEED_BYTES or total > MAX_FEED_BYTES) else None)
        self.reply.finished.connect(self.receive)
        self.translate()

    def accept_manifest(self, payload):
        latest = parse_manifest(payload)
        self.latest = latest
        newer = version_tuple(latest['version']) > version_tuple(APP_VERSION)
        self.state = 'updates_available' if newer else 'updates_current'
        compatible=supports_installation(latest)
        if newer and not compatible: self.state='updates_incompatible'
        self.download_url = latest['download_url'] if newer and compatible else ''
        self.notes.setPlainText(latest.get('user_notes',{}).get(self.app.language) or self.app.t('updates_public_summary'))
        self.notes.show()
        self.notes_title.show()

    def receive(self):
        reply, self.reply = self.reply, None
        try:
            raw = bytes(reply.readAll())
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise ValueError(reply.errorString())
            if len(raw) > MAX_FEED_BYTES:
                raise ValueError('Update feed exceeds the size limit.')
            # GitHub redirects to signed asset URLs containing encoded spaces.
            # PrettyDecoded turns %20 into literal spaces, invalidating a valid URL.
            if not valid_https_url(reply.url().toString(QUrl.ComponentFormattingOption.FullyEncoded)):
                raise ValueError('The update feed redirected to an invalid or non-HTTPS URL.')
            self.accept_manifest(json.loads(raw))
        except (ValueError, TypeError, UnicodeError) as exc:
            self.state = 'updates_failed'
            self.flow.error = str(exc)
            from .update_messages import record_error
            self.flow.error_code='STC-U101' if reply.error()!=QNetworkReply.NetworkError.NoError else 'STC-U102'
            record_error(self.flow.error_code,exc,'check')
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
                from .update_messages import record_error
                self.flow.error_code='STC-U201'
                record_error('STC-U201','Browser download could not open','legacy_download')
                self.translate()
