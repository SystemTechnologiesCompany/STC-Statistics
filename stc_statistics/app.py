import base64
import html
from pathlib import Path
import re
import sys

import nbformat
import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSettings, QThread, Signal, QUrl, QTranslator, QLibraryInfo
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QShortcut, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidgetItem,
    QMainWindow, QMessageBox, QPlainTextEdit, QTextBrowser, QVBoxLayout,
)

from .analysis import analysis_code, conversion_code, correlation_code
from .i18n import TEXT
from .kernel import Execution, Session
from .plot_code import histogram_code
from .theme import (
    STYLE, GlassButton as QPushButton,
    GlassComboBox as QComboBox, fade_in, initialize_fonts,
)


class PythonHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        patterns = [
            (r"\b(?:import|from|as|for|in|if|else|elif|def|return|class|try|except|with|while|True|False|None|and|or|not|print)\b", "#a9c9ff"),
            (r"\b\d+(?:\.\d+)?\b", "#e6c889"),
            (r"(['\"])(?:\\.|(?!\1).)*?\1", "#5fd9a0"),
            (r"#.*$", "#82988a"),
        ]
        for pattern, color in patterns:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class FrameModel(QAbstractTableModel):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame
        self.changed = None
        self.before_change = None

    def flags(self, index):
        return super().flags(index) | Qt.ItemFlag.ItemIsEditable

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        try:
            dtype = self.frame.dtypes.iloc[index.column()]
            nullable_dtype = None
            if value == '':
                value = pd.NA if pd.api.types.is_extension_array_dtype(dtype) else np.nan
                if pd.api.types.is_integer_dtype(dtype):
                    nullable_dtype = 'UInt64' if pd.api.types.is_unsigned_integer_dtype(dtype) else 'Int64'
                    value = pd.NA
            elif pd.api.types.is_numeric_dtype(dtype):
                if pd.api.types.is_integer_dtype(dtype):
                    from decimal import Decimal
                    decimal = Decimal(str(value).replace(',', '.'))
                    if not decimal.is_finite() or decimal != int(decimal):
                        return False
                    value = int(decimal)
                    limits = np.iinfo(dtype.numpy_dtype if hasattr(dtype,'numpy_dtype') else dtype)
                    if not limits.min <= value <= limits.max:
                        return False
                else:
                    value = float(str(value).replace(',', '.'))
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                value = pd.Timestamp(value)
            if self.before_change:
                self.before_change()
            if nullable_dtype:
                c = self.frame.columns[index.column()]
                self.frame[c] = self.frame[c].astype(nullable_dtype)
            self.frame.iat[index.row(),index.column()] = value
            self.dataChanged.emit(index,index)
            if self.changed:
                self.changed()
            return True
        except (ValueError, TypeError, ArithmeticError):
            return False

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            value = self.frame.iloc[index.row(), index.column()]
            return "" if pd.isna(value) else str(value)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self.frame.columns[section]) if orientation == Qt.Orientation.Horizontal else str(section + 1)


class FileLoader(QThread):
    loaded = Signal(object, object)
    failed = Signal(str)

    def __init__(self, path, sheet, header, separator, decimal, parent=None):
        super().__init__(parent)
        self.path, self.sheet, self.header = path, sheet, header
        self.separator, self.decimal = separator, decimal

    def run(self):
        try:
            if Path(self.path).suffix.lower() == ".csv":
                frame = pd.read_csv(self.path, sep=self.separator, decimal=self.decimal, header=self.header)
                sheets = []
                source = (f"df = pd.read_csv({self.path!r}, sep={self.separator!r}, "
                          f"decimal={self.decimal!r}, header={self.header})")
            else:
                with pd.ExcelFile(self.path) as workbook:
                    sheets = workbook.sheet_names
                    chosen = self.sheet if self.sheet in sheets else sheets[0]
                    frame = pd.read_excel(workbook, sheet_name=chosen, header=self.header)
                source = f"df = pd.read_excel({self.path!r}, sheet_name={chosen!r}, header={self.header})"
            self.loaded.emit(frame, {"sheets": sheets, "source": source})
        except Exception as exc:
            self.failed.emit(str(exc))


class Cell(QFrame):
    def __init__(self, app, code="", title=""):
        super().__init__()
        self.app, self.outputs, self.execution_count = app, [], None
        self.executed_source = None
        self.chart_started = False
        self.setObjectName("cell")
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.prompt = QLabel(title or "In [ ]")
        toolbar.addWidget(self.prompt)
        toolbar.addStretch()
        self.actions = QComboBox()
        self.actions.setMaximumWidth(180)
        self.actions.currentIndexChanged.connect(self.apply_action)
        toolbar.addWidget(self.actions)
        self.chart_button = QPushButton()
        self.chart_button.clicked.connect(lambda: app.show_cell_charts(self))
        self.chart_button.hide()
        toolbar.addWidget(self.chart_button)
        self.run_button = QPushButton()
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(lambda: app.run_cell(self))
        toolbar.addWidget(self.run_button)
        self.remove_button = QPushButton()
        self.remove_button.clicked.connect(lambda: app.remove_cell(self))
        toolbar.addWidget(self.remove_button)
        layout.addLayout(toolbar)
        self.editor = QPlainTextEdit(code)
        self.editor.setFont(QFont("Consolas", 11))
        self.editor.setTabStopDistance(32)
        self.editor.setMinimumHeight(130)
        self.editor.setMaximumHeight(420)
        self.editor.textChanged.connect(self.resize_editor)
        self.editor.textChanged.connect(app.mark_dirty)
        self.highlighter = PythonHighlighter(self.editor.document())
        layout.addWidget(self.editor)
        self.output = QTextBrowser()
        self.output.setOpenExternalLinks(False)
        self.output.setMinimumHeight(90)
        self.output.setMaximumHeight(650)
        self.output.hide()
        layout.addWidget(self.output)
        self.shortcut = QShortcut(QKeySequence("Shift+Return"), self.editor)
        self.shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.shortcut.activated.connect(lambda: app.run_cell(self))
        self.ctrl_enter = QShortcut(QKeySequence('Ctrl+Return'), self.editor)
        self.ctrl_enter.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.ctrl_enter.activated.connect(lambda: app.run_cell(self))
        self.resize_editor()
        self.translate()

    def translate(self):
        self.actions.blockSignals(True)
        self.actions.clear()
        for key in ('cell_actions', 'duplicate_cell', 'move_up', 'move_down', 'clear_output'):
            self.actions.addItem(self.app.t(key), key)
        self.actions.blockSignals(False)
        self.chart_button.setText(self.app.t('view_chart'))
        self.run_button.setText(self.app.t("run") + "  ▶")
        self.remove_button.setText(self.app.t("remove"))

    def apply_action(self, index):
        if index > 0:
            self.app.cell_action(self, self.actions.itemData(index))
            self.actions.setCurrentIndex(0)

    def resize_editor(self):
        height = min(420, max(130, self.editor.document().blockCount() * 20 + 24))
        self.editor.setFixedHeight(height)

    def receive(self, msg):
        kind, content = msg["msg_type"], msg["content"]
        if kind == "clear_output":
            self.outputs.clear()
            if self.chart_started:
                self.app.chart_viewer.set_images([])
                self.app.chart_view_page_button.setEnabled(False)
            self.chart_button.hide()
        elif kind == "stream":
            self.outputs.append(nbformat.v4.new_output("stream", name=content["name"], text=content["text"]))
        elif kind == "error":
            self.outputs.append(nbformat.v4.new_output("error", ename=content["ename"],
                                                       evalue=content["evalue"], traceback=content.get("traceback", [])))
        else:
            args = {"data": content["data"], "metadata": content.get("metadata", {})}
            if kind == "execute_result":
                args["execution_count"] = content["execution_count"]
            self.outputs.append(nbformat.v4.new_output(kind, **args))
            if 'image/png' in content['data']:
                image_bytes = base64.b64decode(content['data']['image/png'])
                if not self.chart_started:
                    self.app.chart_viewer.set_images([])
                    self.chart_started = True
                self.app.chart_viewer.set_images(self.app.chart_viewer.images + [image_bytes])
                self.app.chart_view_page_button.setEnabled(True)
                self.chart_button.show()
        self.render()

    def render(self):
        fragments = ["<style>body {font-family:Segoe UI;color:#e8ece9;background:#101b14;} table {border-collapse:collapse;color:#e8ece9;} td,th {padding:7px 12px;border:1px solid #2c4234;} th {background:#1d3023;color:#5fd9a0;} pre {white-space:pre-wrap;}</style>"]
        ansi = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
        for item in self.outputs:
            kind = item["output_type"]
            if kind == "stream":
                fragments.append("<pre>" + html.escape(item["text"]) + "</pre>")
            elif kind == "error":
                trace = "\n".join(item["traceback"]) or f"{item['ename']}: {item['evalue']}"
                fragments.append('<pre style="color:#ff9b9b">' + html.escape(ansi.sub("", trace)) + "</pre>")
            else:
                data = item["data"]
                if "image/png" in data:
                    image = QImage.fromData(base64.b64decode(data["image/png"]))
                    url = QUrl(f"stc-image:{len(fragments)}")
                    self.output.document().addResource(QTextDocument.ResourceType.ImageResource, url, image)
                    width = max(300, self.width() - 60)
                    fragments.append(f'<img src="{url.toString()}" width="{width}">')
                elif "text/html" in data:
                    fragments.append(data["text/html"])
                else:
                    fragments.append("<pre>" + html.escape(data.get("text/plain", "")) + "</pre>")
        self.output.setHtml("\n".join(fragments))
        self.output.setVisible(bool(self.outputs))
        self.output.setFixedHeight(min(650, max(100, int(self.output.document().size().height()) + 40)))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("STC", "Statistics")
        self.language = self.settings.value("language", "en")
        if self.language not in TEXT:
            self.language = "en"
        self.frame, self.file_path = None, None
        self.session, self.worker, self.loader = Session(), None, None
        self.cells, self.pending, self.active = [], [], None
        self.stats_metrics, self.stats_ddof, self.stats_percentiles = list(range(16)), 1, []
        self.dirty = False
        self.bound_labels = []
        self.qt_translator = QTranslator(self)
        self.setProperty("reduceMotion", self.settings.value("reduceMotion", False, type=bool))
        from .pages import build_workspace
        build_workspace(self)
        from .workbench import install
        install(self)
        import tempfile
        self.bridge_dir = tempfile.TemporaryDirectory(prefix='stc-data-')
        self.bridge_path = str(Path(self.bridge_dir.name) / 'frame.parquet')
        self.data_pending = False
        self.data_sync_error = False
        self.translate()
        self.save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        self.save_shortcut.activated.connect(self.save_project)
        self.dirty = False

    def t(self, key):
        return TEXT[self.language][key]

    def label(self, key, wrap=False):
        label = QLabel()
        label.setWordWrap(wrap)
        if wrap:
            label.setObjectName("hint")
        self.bound_labels.append((label, key))
        return label

    def button(self, key, callback, layout, primary=False):
        button = QPushButton()
        button.clicked.connect(callback)
        if primary:
            button.setObjectName("primary")
        layout.addWidget(button)
        self.bound_labels.append((button, key))
        return button

    def change_language(self, index):
        self.language = "en" if index == 0 else "fr"
        self.settings.setValue("language", self.language)
        self.translate()

    def navigate(self, key, animate=True):
        from .pages import PAGE_KEYS
        changed = key != self.current_page
        self.current_page = key
        if key in self.column_hosts:
            self.column_hosts[key].addWidget(self.column_panel)
        index = PAGE_KEYS.index(key)
        self.pages.setCurrentIndex(index)
        self.page_title.setText(self.t(key))
        self.page_description.setText(self.t(key + "_description"))
        self.page_number.setText("STC STATISTICS")
        for name, button in self.nav_buttons.items():
            button.setText(self.t(name))
            button.setChecked(name == key)
        if changed and animate:
            fade_in(self.pages.currentWidget(), duration=180)

    def set_reduce_motion(self, reduced):
        self.setProperty("reduceMotion", reduced)
        self.settings.setValue("reduceMotion", reduced)
        if reduced:
            for button in self.findChildren(QPushButton):
                button.hover_animation.stop()
                button.hover = 1.0 if button.underMouse() else 0.0
            for combo in self.findChildren(QComboBox):
                combo.hover_animation.stop()
                combo.arrow_animation.stop()
                combo.hover = 0.0
                combo.angle = 180.0 if combo.view().isVisible() else 0.0
                if combo.popup_animation is not None:
                    combo.popup_animation.stop()
                    combo.view().window().setWindowOpacity(1.0)
            for cell in self.cells:
                if cell.graphicsEffect() is not None:
                    cell._fade.stop()
                    cell.setGraphicsEffect(None)

    def translate(self):
        QApplication.instance().removeTranslator(self.qt_translator)
        if self.language == "fr":
            translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            if self.qt_translator.load("qtbase_fr", translations):
                QApplication.instance().installTranslator(self.qt_translator)
        for widget, key in self.bound_labels:
            widget.setText(self.t(key))
        self.motion_toggle.setText(self.t("motion"))
        self.chart_viewer.translate()
        self.updates_page.translate()
        self.navigate(self.current_page, animate=False)
        self.decimal_comma.setText(self.t("comma"))
        current = self.chart_picker.currentData()
        self.chart_picker.clear()
        for key in ("histogram", "box", "scatter"):
            self.chart_picker.addItem(self.t(key), key)
        if current:
            self.chart_picker.setCurrentIndex(self.chart_picker.findData(current))
        self.update_info()
        for cell in self.cells:
            cell.translate()
        self.statusBar().showMessage(self.t("running") if self.active else self.t("ready"))
        self.set_busy(bool(self.active))

    def mark_dirty(self):
        self.dirty = True

    def save_project(self):
        from .workbench import guard, project_save
        return guard(self, lambda: project_save(self))

    def data_edited(self):
        self.data_pending = True
        self.mark_dirty()
        self.update_info()
        for label, value in zip(self.metric_values, (len(self.frame), len(self.frame.columns), int(self.frame.isna().sum().sum()))):
            label.setText(f'{value:,}')

    def receive_frame(self, path):
        if Path(path).exists():
            try:
                selected = self.selected_columns()
                self.use_frame(pd.read_parquet(path))
                for i in range(self.column_list.count()):
                    item = self.column_list.item(i)
                    item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in selected else Qt.CheckState.Unchecked)
                self.data_pending = False
                self.data_sync_error = False
            except Exception as exc:
                self.statusBar().showMessage(str(exc))

    def update_info(self):
        if self.frame is None:
            self.data_info.setText(self.t("no_data"))
            self.dataset_badge.setText(self.t("no_dataset"))
        else:
            self.dataset_badge.setText(f"{len(self.frame):,} × {len(self.frame.columns)}\n" + (Path(self.file_path).name if self.file_path else "STC sample"))
            self.data_info.setText((self.file_path or "STC sample / exemple") + "\n" +
                                   self.t("preview").format(shown=len(self.frame),
                                                            rows=len(self.frame), cols=len(self.frame.columns)))

    def set_busy(self, busy):
        loading = self.loader is not None and self.loader.isRunning()
        self.table.setEnabled(not busy and not loading)
        for button in [self.open_button, self.demo_button, self.stats_button, self.correlation_button,
                       self.chart_button, self.convert_button, self.all_button, self.result_button,
                       self.restart_button, self.open_notebook_button, self.word_button]:
            button.setEnabled(not busy and not loading)
        self.stop_button.setEnabled(busy)
        for cell in self.cells:
            cell.run_button.setEnabled(not busy and not loading)
            cell.remove_button.setEnabled(not busy)
            cell.editor.setReadOnly(cell is self.active)
            cell.actions.setEnabled(not busy)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, self.t("import"), "", "Excel / CSV (*.xlsx *.xls *.xlsm *.csv)")
        if path:
            self.file_path = path
            self.header_row.setValue(1)
            self.sheet.clear()
            self.reload_file()

    def reload_file(self):
        if not self.file_path or self.active or (self.loader and self.loader.isRunning()):
            return
        self.loader = FileLoader(self.file_path, self.sheet.currentText(), self.header_row.value() - 1,
                                 self.csv_separator.currentData(), self.csv_decimal.currentText(), self)
        self.loader.loaded.connect(self.file_loaded)
        self.loader.failed.connect(lambda error: QMessageBox.warning(self, self.t("error"), error))
        self.loader.finished.connect(lambda: self.set_busy(bool(self.active)))
        self.loader.start()
        self.set_busy(False)

    def file_loaded(self, frame, metadata):
        current = self.sheet.currentText()
        self.sheet.clear()
        self.sheet.addItems(metadata["sheets"])
        if current in metadata["sheets"]:
            self.sheet.setCurrentText(current)
        self.use_frame(frame)
        code = "import pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\n%matplotlib inline\n\n" + metadata["source"] + "\ndf.head()"
        cell = self.add_cell(code)
        self.run_cell(cell)
        self.navigate("data")

    def use_frame(self, frame):
        self.frame = frame
        self.welcome.hide()
        self.table.show()
        for label, value in zip(self.metric_values, (len(frame), len(frame.columns), int(frame.isna().sum().sum()))):
            label.setText(f"{value:,}")
        self.model = FrameModel(frame)
        self.model.changed = self.data_edited
        self.model.before_change = lambda: setattr(self, 'data_undo', self.frame.copy(deep=True))
        self.table.setModel(self.model)
        self.data_pending = True
        self.column_list.clear()
        numeric = frame.select_dtypes(include="number").columns
        for column in frame.columns:
            item = QListWidgetItem(f"{column}  [{frame[column].dtype}]")
            item.setData(Qt.ItemDataRole.UserRole, column)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if column in numeric else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
        self.update_info()

    def demo(self):
        self.file_path = None
        self.sheet.clear()
        rng = np.random.default_rng(42)
        frame = pd.DataFrame({"Sample": [f"S{i:03}" for i in range(1, 61)],
                              "Porosity_pct": rng.normal(18, 4, 60).round(2),
                              "Permeability_mD": rng.lognormal(3.5, 0.7, 60).round(2),
                              "Depth_m": np.arange(2200, 2800, 10)})
        frame.loc[[4, 18, 40], "Porosity_pct"] = np.nan
        self.use_frame(frame)
        code = ("import pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\n%matplotlib inline\n"
                "\nrng = np.random.default_rng(42)\ndf = pd.DataFrame({\n"
                "    'Sample': [f'S{i:03}' for i in range(1, 61)],\n"
                "    'Porosity_pct': rng.normal(18, 4, 60).round(2),\n"
                "    'Permeability_mD': rng.lognormal(3.5, 0.7, 60).round(2),\n"
                "    'Depth_m': np.arange(2200, 2800, 10)\n})\n"
                "df.loc[[4, 18, 40], 'Porosity_pct'] = np.nan\ndf.head()")
        self.run_cell(self.add_cell(code))
        self.navigate("data")

    def select_columns(self, checked):
        for i in range(self.column_list.count()):
            self.column_list.item(i).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def selected_columns(self):
        return [self.column_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.column_list.count())
                if self.column_list.item(i).checkState() == Qt.CheckState.Checked]

    def add_cell(self, code=""):
        cell = Cell(self, code)
        self.cells.append(cell)
        self.cell_layout.addWidget(cell)
        self.navigate("notebook")
        self.mark_dirty()
        fade_in(cell)
        return cell

    def remove_cell(self, cell):
        if self.active:
            return
        self.cells.remove(cell)
        self.cell_layout.removeWidget(cell)
        cell.deleteLater()
        self.mark_dirty()

    def cell_action(self, cell, action):
        if self.active:
            return
        index = self.cells.index(cell)
        if action == 'clear_output':
            cell.outputs.clear()
            cell.execution_count = None
            cell.executed_source = None
            cell.prompt.setText('In [ ]')
            cell.chart_button.hide()
            cell.render()
        elif action == 'duplicate_cell':
            duplicate = self.add_cell(cell.editor.toPlainText())
            self.cells.remove(duplicate)
            self.cells.insert(index + 1, duplicate)
            self.cell_layout.removeWidget(duplicate)
            self.cell_layout.insertWidget(index + 1, duplicate)
        elif action in ('move_up', 'move_down'):
            target = index + (-1 if action == 'move_up' else 1)
            if 0 <= target < len(self.cells):
                self.cells.pop(index)
                self.cells.insert(target, cell)
                self.cell_layout.removeWidget(cell)
                self.cell_layout.insertWidget(target, cell)
        self.mark_dirty()

    def generate(self, kind):
        columns = self.selected_columns()
        if not columns:
            QMessageBox.information(self, "STC Statistics", self.t("choose"))
            return
        if kind in ("scatter", "correlation") and len(columns) < 2:
            QMessageBox.information(self, "STC Statistics", self.t("need_two"))
            return
        if kind == "stats":
            code = analysis_code(columns, self.language, self.stats_metrics, self.stats_ddof, self.stats_percentiles)
        else:
            code = ("import pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\n%matplotlib inline\n"
                    "plt.style.use('default')\n"
                    "plt.rcParams.update({'figure.facecolor': 'white', 'axes.facecolor': 'white', 'text.color': '#172a20', 'axes.labelcolor': '#172a20', 'xtick.color': '#172a20', 'ytick.color': '#172a20', 'axes.edgecolor': '#52665a', 'grid.color': '#d9e3dc', 'font.size': 16, 'axes.labelsize': 16, 'axes.titlesize': 18, 'xtick.labelsize': 14, 'ytick.labelsize': 14, 'figure.dpi': 160, 'savefig.dpi': 200})\n"
                    f"selected_columns = {columns!r}\n"
                    "numeric = df[selected_columns].select_dtypes(include='number').replace([np.inf, -np.inf], np.nan)\n")
            if kind == "correlation":
                code += correlation_code(self.correlation_method.currentData())
            elif kind == "histogram":
                code += histogram_code()
            elif kind == "box":
                code += "numeric.plot.box(figsize=(10, 6), grid=True, color='#188650')\nplt.xticks(rotation=20, ha='right')\nplt.tight_layout(pad=2)\nplt.show()"
            else:
                code += ("if len(numeric.columns) < 2:\n    raise ValueError('Select two numeric columns / Sélectionnez deux colonnes numériques')\n"
                         "x, y = numeric.columns[:2]\nnumeric.plot.scatter(x=x, y=y, color='#188650', figsize=(10, 6), s=70, alpha=0.9)\nplt.tight_layout(pad=2)\nplt.show()")
        if kind in ('histogram', 'box', 'scatter') and self.chart_options:
            from .plot_code import customize_code
            code = customize_code(code, self.chart_options)
        # Generated analysis remains editable before the user chooses Run.
        self.add_cell(code)

    def convert(self):
        columns = self.selected_columns()
        if columns:
            self.add_cell(conversion_code(columns, self.decimal_comma.isChecked()))
            self.statusBar().showMessage(self.t("conversion"))

    def show_cell_charts(self, cell):
        images = [base64.b64decode(output.get('data', {})['image/png'])
                  for output in cell.outputs if 'image/png' in output.get('data', {})]
        if images:
            self.chart_viewer.set_images(images)
            self.chart_view_page_button.setEnabled(True)
            self.navigate('charts')
            self.chart_stack.setCurrentIndex(1)

    def run_cell(self, cell):
        if self.active or (self.loader and self.loader.isRunning()):
            # A loader's final signal may arrive before QThread has fully exited.
            if not self.active and self.loader and self.loader.isRunning():
                self.loader.wait(1000)
            else:
                return
        self.active = cell
        cell.executed_source = cell.editor.toPlainText()
        cell.chart_started = False
        cell.chart_button.hide()
        cell.outputs.clear()
        cell.output.clear()
        cell.output.hide()
        cell.prompt.setText("In [*]")
        self.statusBar().showMessage(self.t("running"))
        try:
            if self.frame is not None and self.data_pending:
                self.frame.to_parquet(self.bridge_path, index=True)
        except Exception as exc:
            self.active = None
            QMessageBox.warning(self, self.t('error'), str(exc))
            return
        self.worker = Execution(self.session, cell.editor.toPlainText(), self,
                                load_path=self.bridge_path if self.frame is not None and self.data_pending else None,
                                snapshot_path=self.bridge_path)
        self.worker.data_ready.connect(self.receive_frame)
        self.data_pending = False
        self.worker.output.connect(cell.receive)
        self.worker.completed.connect(self.execution_complete)
        self.worker.finished.connect(self.advance_queue)
        self.set_busy(True)
        self.worker.start()

    def execution_complete(self, success, count):
        cell = self.active
        cell.execution_count = count or None
        cell.prompt.setText(f"In [{count or ' '}]  {'✓' if success else '✕'}")
        self.last_success = success
        self.data_sync_error = any(o.get('ename')=='DataSyncError' for o in cell.outputs)
        if not success:
            self.pending.clear()
        self.mark_dirty()
        self.statusBar().showMessage(self.t("done") if success else self.t("error"))
        if success and cell.chart_started and not self.pending:
            self.show_cell_charts(cell)

    def advance_queue(self):
        self.active = None
        old_worker = self.worker
        self.worker = None
        old_worker.deleteLater()
        self.set_busy(False)
        if self.pending:
            self.run_cell(self.pending.pop(0))

    def run_all(self):
        if self.active or not self.cells:
            return
        self.pending = list(self.cells)
        self.run_cell(self.pending.pop(0))

    def stop(self):
        self.pending.clear()
        try:
            self.session.interrupt()
        except Exception as exc:
            QMessageBox.warning(self, self.t("error"), str(exc))

    def restart(self):
        if self.active:
            return
        if QMessageBox.question(self, self.t("restart"), self.t("restart_note")) == QMessageBox.StandardButton.Yes:
            self.session.close()
            self.session = Session()
            self.data_pending = self.frame is not None
            for cell in self.cells:
                cell.prompt.setText("In [ ]")

    def save_notebook(self):
        path, _ = QFileDialog.getSaveFileName(self, self.t("export"), "STC_Statistics.ipynb", "Jupyter (*.ipynb)")
        if not path:
            return False
        if not path.lower().endswith(".ipynb"):
            path += ".ipynb"
        notebook = nbformat.v4.new_notebook()
        notebook.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
        notebook.metadata["language_info"] = {"name": "python"}
        notebook.cells = [nbformat.v4.new_code_cell(cell.editor.toPlainText(), outputs=cell.outputs,
                                                   execution_count=cell.execution_count) for cell in self.cells]
        try:
            nbformat.write(notebook, path)
            self.statusBar().showMessage(self.t("saved") + ": " + path)
            return True
        except Exception as exc:
            QMessageBox.warning(self, self.t("error"), str(exc))
            return False

    def open_notebook(self):
        if self.dirty and not self.confirm_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Jupyter", "", "Jupyter (*.ipynb)")
        if not path:
            return
        try:
            notebook = nbformat.read(path, as_version=4)
            nbformat.validate(notebook)
            # A notebook is opened for review; code is never run on open.
            for entry in notebook.cells:
                if entry.cell_type == "code":
                    cell = self.add_cell(entry.source)
                    cell.execution_count = entry.execution_count
                    # Do not render saved rich output from imported notebooks.
            self.statusBar().showMessage(path)
        except Exception as exc:
            QMessageBox.warning(self, self.t("error"), str(exc))

    def export_results(self):
        self.export_report('xlsx')

    def export_word_report(self):
        self.export_report('docx')

    def export_report(self, extension):
        if self.active:
            return
        from .reports import collect_results, export_excel, export_word
        from .pages import LOGO_PATH
        import tempfile
        import os
        items = collect_results(self.cells, tables=self.report_tables.isChecked(),
                                graphs=self.report_graphs.isChecked(), text=self.report_text.isChecked(),
                                code=self.report_code.isChecked(), language=self.language)
        if self.report_plan:
            plan = self.report_plan[0]
            from .workbench import report_signature
            if plan.get('signature') == report_signature(items):
                selected = []
                for i in plan['indices']:
                    if 0 <= i < len(items):
                        selected.append(items[i])
                        if plan.get('annotations',{}).get(str(i)):
                            selected.append({'kind':'text','title':items[i]['title'],'text':plan['annotations'][str(i)]})
                items = selected
                if plan.get('intro'):
                    items.insert(0, {'kind':'text', 'title':'Introduction', 'text':plan['intro']})
            else:
                QMessageBox.information(self, 'STC Statistics', 'Results changed. Rebuild the report selection. / Résultats modifiés. Recomposez le rapport.')
                return
        if not items:
            QMessageBox.information(self, 'STC Statistics', self.t('no_report_results'))
            return
        label = 'Word' if extension == 'docx' else 'Excel'
        path, _ = QFileDialog.getSaveFileName(self, self.t('export_word' if extension == 'docx' else 'export_results'),
                                             f'STC_Results.{extension}', f'{label} (*.{extension})')
        if not path:
            return
        if not path.lower().endswith('.' + extension):
            path += '.' + extension
        temporary = None
        try:
            # Replace the selected file only after a complete report has been written.
            with tempfile.NamedTemporaryFile(dir=Path(path).parent, suffix='.' + extension, delete=False) as target:
                temporary = Path(target.name)
            source = Path(self.file_path).name if self.file_path else 'STC dataset'
            if extension == 'docx':
                export_word(temporary, items, self.language, source=source, logo=LOGO_PATH)
            else:
                export_excel(temporary, items, self.language, source=source)
            os.replace(temporary, path)
            self.statusBar().showMessage(self.t('saved') + ': ' + path)
        except Exception as exc:
            QMessageBox.warning(self, self.t('error'), str(exc))
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def confirm_save(self):
        answer = QMessageBox.question(self, "STC Statistics", self.t("unsaved"),
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_project() if answer == QMessageBox.StandardButton.Save else True

    def closeEvent(self, event):
        if self.active or (self.loader and self.loader.isRunning()):
            self.stop()
            event.ignore()
            return
        if self.dirty and not self.confirm_save():
            event.ignore()
            return
        self.session.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    initialize_fonts(app)
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
