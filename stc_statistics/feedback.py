"""Friendly file/action feedback; Python cell tracebacks remain in the notebook."""
from PySide6.QtWidgets import QMessageBox
from .update_messages import record_error

OPERATIONS={
    'input':('STC-A101','input_error'), 'import':('STC-F101','import_error'),
    'project':('STC-F102','project_error'), 'notebook':('STC-F103','notebook_error'),
    'export':('STC-F104','export_error'), 'session':('STC-A102','session_error'),
    'sync':('STC-D101','sync_error'),
}


def show_error(app,operation,error):
    code,key=OPERATIONS[operation]
    record_error(code,error,operation)
    QMessageBox.warning(app,app.t('action_failed'),app.t(key)+'\n'+code)
