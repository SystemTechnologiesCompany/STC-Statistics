from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QLineEdit, QMessageBox
from .analysis import METRICS
from .theme import GlassComboBox


def choose_statistics(app):
    dialog = QDialog(app)
    dialog.setWindowTitle(app.t('statistics_options'))
    dialog.resize(520, 640)
    layout = QVBoxLayout(dialog)
    # Dialog labels are snapshots, so opening/closing does not retain dead widgets in bindings.
    from PySide6.QtWidgets import QLabel
    layout.addWidget(QLabel(app.t('select_measures')))
    measures = QListWidget()
    names = list(METRICS[app.language])
    names[8:10] = ['Variance', 'Standard deviation'] if app.language == 'en' else ['Variance', 'Écart-type']
    for index, name in enumerate(names):
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if index in app.stats_metrics else Qt.CheckState.Unchecked)
        measures.addItem(item)
    layout.addWidget(measures, 1)
    layout.addWidget(QLabel(app.t('variance_convention')))
    convention = GlassComboBox()
    convention.addItem(app.t('sample_variance'), 1)
    convention.addItem(app.t('population_variance'), 0)
    convention.setCurrentIndex(0 if app.stats_ddof == 1 else 1)
    layout.addWidget(convention)
    layout.addWidget(QLabel(app.t('custom_percentiles')))
    percentiles = QLineEdit('; '.join(f'{p:g}' for p in app.stats_percentiles))
    percentiles.setPlaceholderText('5; 95')
    layout.addWidget(percentiles)
    buttons = QHBoxLayout()
    from .theme import GlassButton
    apply = GlassButton(app.t('apply_options'))
    cancel = GlassButton(app.t('cancel_options'))
    buttons.addWidget(apply)
    buttons.addWidget(cancel)
    layout.addLayout(buttons)
    cancel.clicked.connect(dialog.reject)

    def commit():
        try:
            values = sorted(set(float(value.strip().replace(',', '.')) for value in percentiles.text().split(';') if value.strip()))
            if any(not 0 <= p <= 100 for p in values):
                raise ValueError()
            chosen = [i for i in range(measures.count()) if measures.item(i).checkState() == Qt.CheckState.Checked]
            if not chosen and not values:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(dialog, app.t('error'), app.t('invalid_percentiles'))
            return
        app.stats_metrics, app.stats_ddof, app.stats_percentiles = chosen, convention.currentData(), values
        dialog.accept()

    apply.clicked.connect(commit)
    dialog.exec()
