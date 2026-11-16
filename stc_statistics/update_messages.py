"""Public update messages and private, bounded diagnostic logs."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import threading
from .version import APP_VERSION

MESSAGES = {
    'STC-U203': ('This update needs a different installation. Please contact STC support.', 'Cette mise à jour nécessite une autre installation. Contactez le support STC.'),
    'STC-U101': ('We couldn’t check for updates. Please try again.', 'Impossible de vérifier les mises à jour. Veuillez réessayer.'),
    'STC-U102': ('Update information is temporarily unavailable. Please try again later.', 'Les informations de mise à jour sont temporairement indisponibles. Réessayez plus tard.'),
    'STC-U201': ('The download couldn’t finish. Please try again.', 'Le téléchargement n’a pas pu se terminer. Veuillez réessayer.'),
    'STC-U202': ('We couldn’t verify this update. Please download it again.', 'Impossible de vérifier cette mise à jour. Veuillez la télécharger à nouveau.'),
    'STC-U301': ('We couldn’t save your workspace. Your work is still open. Please save it and try again.', 'Impossible d’enregistrer votre espace de travail. Votre travail reste ouvert. Enregistrez-le puis réessayez.'),
    'STC-U401': ('The update couldn’t start. Your current app is still open. Please try again.', 'La mise à jour n’a pas pu démarrer. Votre application reste ouverte. Veuillez réessayer.'),
    'STC-U402': ('This app isn’t ready to update yet. Please finish any running task and try again.', 'L’application n’est pas encore prête pour la mise à jour. Terminez les tâches en cours puis réessayez.'),
}
PHASE_CODES = {'update_downloading':'STC-U201','update_verifying':'STC-U202',
               'update_saving':'STC-U301','update_installing':'STC-U401'}
_lock = threading.Lock()


def friendly_error(code, language):
    code = code if code in MESSAGES else 'STC-U401'
    return MESSAGES[code][language == 'fr'] + '\n' + code


def diagnostic_path():
    runtime = os.environ.get('STC_PORTABLE_ROOT')
    base = Path(runtime).resolve().parent if runtime else Path(__file__).resolve().parent.parent / '.tmp'
    return base / 'logs' / 'update-diagnostics.log'


def record_error(code, detail, phase):
    """Diagnostics must never replace the friendly message if the log is unwritable."""
    try:
        with _lock:
            path = diagnostic_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(path,maxBytes=1024*1024,backupCount=2,encoding='utf-8')
            try:
                import datetime
                payload = {'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                           'version':APP_VERSION,'code':code,'phase':phase,'detail':str(detail)}
                handler.emit(logging.makeLogRecord({'msg':json.dumps(payload,ensure_ascii=True),'levelno':logging.ERROR,'levelname':'ERROR'}))
            finally:
                handler.close()
    except OSError:
        pass
