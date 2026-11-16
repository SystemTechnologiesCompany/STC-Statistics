"""Chart presentation independent of the notebook's text-output layout."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QFileDialog, QDialog, QLabel, QMessageBox,
)
from .theme import GlassButton, GlassComboBox


class ChartCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setStyleSheet('QGraphicsView {background:#f5f7f6;border:1px solid rgba(255,255,255,145);border-radius:10px;}')
        self.fitting = True
        self.fit_mode = 'all'
        self.item = None

    def set_pixmap(self, pixmap):
        self.scene().clear()
        self.item = self.scene().addPixmap(pixmap)
        self.setSceneRect(self.item.boundingRect())
        if pixmap.height() > pixmap.width() * .65:
            self.fit_width()
        else:
            self.fit()

    def fit(self):
        self.fitting = True
        self.fit_mode = 'all'
        if self.item:
            self.fitInView(self.item, Qt.AspectRatioMode.KeepAspectRatio)

    def fit_width(self):
        self.fitting = True
        self.fit_mode = 'width'
        if self.item:
            self.resetTransform()
            factor = max(1, self.viewport().width() - 8) / self.item.pixmap().width()
            self.scale(factor, factor)
            self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    def zoom(self, factor):
        scale = self.transform().m11()
        if .03 <= scale * factor <= 16:
            self.fitting = False
            self.scale(factor, factor)

    def wheelEvent(self, event):
        self.zoom(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fitting:
            self.fit_width() if self.fit_mode == 'width' else self.fit()


class ChartViewer(QWidget):
    def __init__(self, app, fullscreen=False):
        super().__init__()
        self.app, self.images, self.fullscreen = app, [], fullscreen
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.picker = GlassComboBox()
        self.picker.currentIndexChanged.connect(self.select_image)
        toolbar.addWidget(self.picker)
        self.buttons = {}
        for key, action in [('fit_chart', lambda: self.canvas.fit()),
                            ('fit_width', lambda: self.canvas.fit_width()),
                            ('zoom_out', lambda: self.canvas.zoom(1 / 1.25)),
                            ('zoom_in', lambda: self.canvas.zoom(1.25)),
                            ('fullscreen_chart', self.open_fullscreen),
                            ('save_chart', self.save)]:
            button = GlassButton()
            button.clicked.connect(action)
            toolbar.addWidget(button)
            self.buttons[key] = button
        self.buttons['fullscreen_chart'].setVisible(not fullscreen)
        layout.addLayout(toolbar)
        self.empty = QLabel()
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        self.canvas = ChartCanvas()
        self.canvas.setMinimumHeight(180)
        layout.addWidget(self.canvas, 1)
        self.hint = QLabel()
        self.hint.setObjectName('hint')
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.translate()
        self.set_images([])

    def translate(self):
        for key, button in self.buttons.items():
            button.setText(self.app.t(key))
        self.empty.setText(self.app.t('chart_empty'))
        self.hint.setText(self.app.t('chart_zoom_hint'))
        current = self.picker.currentIndex()
        self.picker.blockSignals(True)
        self.picker.clear()
        for i in range(len(self.images)):
            self.picker.addItem(f"{self.app.t('chart_image')} {i + 1}")
        self.picker.setCurrentIndex(current if current >= 0 else 0)
        self.picker.blockSignals(False)

    def set_images(self, images):
        self.images = images
        self.translate()
        has_images = bool(images)
        self.empty.setVisible(not has_images)
        self.canvas.setVisible(has_images)
        self.picker.setEnabled(has_images)
        for button in self.buttons.values():
            button.setEnabled(has_images)
        if has_images:
            self.picker.setCurrentIndex(len(images) - 1)
            self.select_image(len(images) - 1)
        else:
            self.canvas.scene().clear()
            self.canvas.item = None

    def select_image(self, index):
        if 0 <= index < len(self.images):
            pixmap = QPixmap()
            pixmap.loadFromData(self.images[index], 'PNG')
            self.canvas.set_pixmap(pixmap)

    def open_fullscreen(self):
        if not self.images:
            return
        dialog = QDialog(self.app)
        dialog.setProperty('reduceMotion', self.app.property('reduceMotion'))
        dialog.setWindowTitle(self.app.t('charts'))
        layout = QVBoxLayout(dialog)
        viewer = ChartViewer(self.app, fullscreen=True)
        viewer.set_images(list(self.images))
        viewer.picker.setCurrentIndex(self.picker.currentIndex())
        layout.addWidget(viewer)
        close = GlassButton(self.app.t('close_chart'))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.showFullScreen()
        dialog.exec()

    def save(self):
        index = self.picker.currentIndex()
        if not 0 <= index < len(self.images):
            return
        path, _ = QFileDialog.getSaveFileName(self, self.app.t('save_chart'), 'STC_Chart.png', 'PNG (*.png)')
        if path:
            if not path.lower().endswith('.png'):
                path += '.png'
            try:
                with open(path, 'wb') as target:
                    target.write(self.images[index])
            except OSError as exc:
                from .feedback import show_error
                show_error(self.app,'export',exc)
