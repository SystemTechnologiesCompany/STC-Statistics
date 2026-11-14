"""STC brand palette and animated native Qt controls.

Colors taken from :root on https://stc-official.netlify.app/.
Glass is rendered inside the application; it does not blur other desktop windows.
"""
import os
from pathlib import Path

from PySide6.QtCore import Qt, Property, QEasingCurve, QPropertyAnimation, QRectF, QPointF, QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import (
    QWidget, QPushButton, QComboBox, QListView, QStyledItemDelegate,
    QStyle, QTabBar, QGraphicsOpacityEffect,
)

BG = "#0a0f0d"
SURFACE = "#121a17"
GREEN = "#3fbf7f"
MINT = "#5fd9a0"
TEXT = "#e8ece9"
MUTED = "#8a968f"


def initialize_fonts(app):
    # Qt's offscreen Windows platform may not enumerate installed fonts.
    # Load the system's own fonts directly; no font files are redistributed.
    font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    if "Segoe UI" not in QFontDatabase.families():
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf", "consola.ttf"):
            path = font_dir / name
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont("Segoe UI", 10))


def motion_enabled(widget):
    return not bool(widget.window().property("reduceMotion"))


def animate(widget, animation, value):
    animation.stop()
    if motion_enabled(widget):
        animation.setStartValue(widget.property(bytes(animation.propertyName()).decode()))
        animation.setEndValue(value)
        animation.start()
    else:
        widget.setProperty(bytes(animation.propertyName()).decode(), value)


class GlassBackground(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(BG))
        for center, radius, color in [
            (QPointF(self.width() * .83, -30), self.width() * .65, QColor(38, 143, 95, 43)),
            (QPointF(-40, self.height() * .77), self.width() * .52, QColor(37, 115, 92, 30)),
        ]:
            gradient = QRadialGradient(center, radius)
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(10, 15, 13, 0))
            painter.fillRect(self.rect(), gradient)
        painter.setPen(QColor(232, 236, 233, 9))
        for x in range(24, self.width(), 32):
            for y in range(24, self.height(), 32):
                painter.drawPoint(x, y)


class GlassButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._hover = 0.0
        self._point = QPointF(20, 20)
        self.hover_animation = QPropertyAnimation(self, b"hover", self)
        self.hover_animation.setDuration(190)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setMinimumHeight(38)

    def sizeHint(self):
        size = super().sizeHint()
        return QSize(min(size.width(), 290), max(size.height(), 38))

    def minimumSizeHint(self):
        return QSize(min(self.sizeHint().width(), 120), 38)

    def event(self, event):
        # Elided labels always retain their complete accessible name and tooltip.
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.ToolTip:
            self.setToolTip(self.text())
        return super().event(event)

    @Property(float)
    def hover(self):
        return self._hover

    @hover.setter
    def hover(self, value):
        self._hover = value
        self.update()

    def enterEvent(self, event):
        animate(self, self.hover_animation, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate(self, self.hover_animation, 0.0)
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        self._point = event.position()
        self.update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(bounds, 11, 11)
        primary = self.objectName() == "primary"
        navigation = self.objectName() == "navigation"
        enabled = self.isEnabled()
        hover = self._hover if enabled else 0
        gradient = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        if primary and enabled:
            gradient.setColorAt(0, QColor(MINT).lighter(int(100 + hover * 8)))
            gradient.setColorAt(1, QColor(GREEN).darker(110 if self.isDown() else 100))
        else:
            gradient.setColorAt(0, QColor(63, 191, 127, 35) if navigation and self.isChecked() else QColor(232, 236, 233, int(15 + hover * 11)))
            gradient.setColorAt(1, QColor(63, 191, 127, 20) if navigation and self.isChecked() else QColor(63, 191, 127, int(6 + hover * 18)))
        p.fillPath(path, gradient)
        if hover:
            highlight = QRadialGradient(self._point, max(90, self.width() * .7))
            highlight.setColorAt(0, QColor(174, 255, 214, int(hover * (45 if primary else 22))))
            highlight.setColorAt(1, QColor(174, 255, 214, 0))
            p.fillPath(path, highlight)
        p.setPen(QPen(QColor(172, 246, 207, int(30 + hover * 65)), 1))
        p.drawPath(path)
        p.setPen(QColor(MINT if navigation and self.isChecked() else BG if primary and enabled else TEXT if enabled else MUTED))
        font = self.font()
        font.setWeight(QFont.Weight.DemiBold if primary else QFont.Weight.Normal)
        p.setFont(font)
        text_rect = bounds.adjusted(12, 0, -12, 0)
        if self.isDown():
            text_rect.translate(0, 1)
        p.drawText(text_rect, (Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft) if navigation else Qt.AlignmentFlag.AlignCenter,
                   p.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, int(text_rect.width())))
        if self.hasFocus():
            p.setPen(QPen(QColor(MINT), 1.5, Qt.PenStyle.DotLine))
            p.drawRoundedRect(bounds.adjusted(3, 3, -3, -3), 8, 8)


class GlassDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(5, 2, -5, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            painter.setPen(QPen(QColor(63, 191, 127, 65 if selected else 30)))
            painter.setBrush(QColor(63, 191, 127, 36 if selected else 18))
            painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(QColor(TEXT))
        painter.setFont(option.font)
        text = str(index.data() or "")
        text = option.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width()) - 44)
        painter.drawText(rect.adjusted(12, 0, -28, 0), Qt.AlignmentFlag.AlignVCenter, text)
        if index.row() == self.parent().currentIndex():
            painter.setPen(QColor(MINT))
            painter.drawText(rect.adjusted(0, 0, -12, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "✓")
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(40)
        return size


class GlassComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = 0.0
        self._angle = 0.0
        self.hover_animation = QPropertyAnimation(self, b"hover", self)
        self.hover_animation.setDuration(170)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.arrow_animation = QPropertyAnimation(self, b"angle", self)
        self.arrow_animation.setDuration(220)
        self.arrow_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.popup_animation = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setMinimumContentsLength(7)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        view = QListView()
        view.setMouseTracking(True)
        view.setSpacing(1)
        self.setView(view)
        view.setItemDelegate(GlassDelegate(self))
        view.setStyleSheet("QListView {background:#121a17;color:#e8ece9;border:1px solid #345044;border-radius:12px;padding:6px;outline:0;}")

    @Property(float)
    def hover(self):
        return self._hover

    @hover.setter
    def hover(self, value):
        self._hover = value
        self.update()

    @Property(float)
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._angle = value
        self.update()

    def enterEvent(self, event):
        animate(self, self.hover_animation, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate(self, self.hover_animation, 0.0)
        super().leaveEvent(event)

    def showPopup(self):
        super().showPopup()
        animate(self, self.arrow_animation, 180.0)
        popup = self.view().window()
        if motion_enabled(self):
            popup.setWindowOpacity(0.0)
            self.popup_animation = QPropertyAnimation(popup, b"windowOpacity", self)
            self.popup_animation.setDuration(160)
            self.popup_animation.setStartValue(0.0)
            self.popup_animation.setEndValue(1.0)
            self.popup_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.popup_animation.start()

    def hidePopup(self):
        if self.popup_animation is not None:
            self.popup_animation.stop()
        self.view().window().setWindowOpacity(1.0)
        super().hidePopup()
        animate(self, self.arrow_animation, 0.0)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        gradient.setColorAt(0, QColor(232, 236, 233, int(14 + self.hover * 9)))
        gradient.setColorAt(1, QColor(63, 191, 127, int(8 + self.hover * 16)))
        p.setBrush(gradient)
        p.setPen(QPen(QColor(148, 218, 177, 95 if self.hasFocus() else int(32 + self.hover * 48))))
        p.drawRoundedRect(bounds, 11, 11)
        p.setPen(QColor(TEXT if self.isEnabled() else MUTED))
        p.setFont(self.font())
        text = self.fontMetrics().elidedText(self.currentText(), Qt.TextElideMode.ElideRight, max(0, self.width() - 50))
        p.drawText(bounds.adjusted(13, 0, -35, 0), Qt.AlignmentFlag.AlignVCenter, text)
        p.translate(self.width() - 20, self.height() / 2)
        p.rotate(self._angle)
        p.setPen(QPen(QColor(MINT), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-4, -2), QPointF(0, 2))
        p.drawLine(QPointF(0, 2), QPointF(4, -2))


class GlassTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._indicator = QRectF()
        self.animation = QPropertyAnimation(self, b"indicator", self)
        self.animation.setDuration(240)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.currentChanged.connect(self.move_indicator)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @Property(QRectF)
    def indicator(self):
        return self._indicator

    @indicator.setter
    def indicator(self, value):
        self._indicator = value
        self.update()

    def target_rect(self):
        return QRectF(self.tabRect(self.currentIndex())).adjusted(3, 4, -3, -4)

    def move_indicator(self, index):
        if index < 0:
            return
        if self._indicator.isNull():
            self.indicator = self.target_rect()
        else:
            animate(self, self.animation, self.target_rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.animation.stop()
        self.indicator = self.target_rect()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(63, 191, 127, 65)))
        p.setBrush(QColor(63, 191, 127, 28))
        p.drawRoundedRect(self._indicator, 10, 10)
        p.end()
        super().paintEvent(event)


def fade_in(widget, duration=240):
    if not motion_enabled(widget):
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._fade = animation
    animation.start()


STYLE = """
QMainWindow {background:#0a0f0d;}
QWidget {background:transparent;color:#e8ece9;font-family:'Segoe UI';font-size:10pt;}
QFrame#header {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(34,57,45,190),stop:0.6 rgba(18,30,23,205),stop:1 rgba(26,64,44,175));border:1px solid rgba(197,242,211,35);border-radius:20px;}
QLabel#brand {font-size:24pt;font-weight:650;letter-spacing:-1px;color:#e8ece9;}
QLabel#wordmark {font-size:17pt;font-weight:800;color:#5fd9a0;letter-spacing:3px;background:rgba(63,191,127,22);border:1px solid rgba(63,191,127,60);border-radius:15px;padding:14px;}
QLabel#eyebrow {font-size:8pt;font-weight:600;letter-spacing:2px;color:#5fd9a0;}
QLabel#hint {color:#8a968f;font-size:9pt;}
QLabel#section {font-size:9pt;font-weight:600;color:#a9beb1;letter-spacing:1px;}
QPushButton {border:0;padding:8px 15px;background:transparent;}
QPushButton#primary {font-weight:600;}
QComboBox {border:0;padding:7px 34px 7px 12px;background:transparent;}
QComboBox::drop-down {border:0;width:0;}
QSpinBox {background:rgba(232,236,233,8);border:1px solid rgba(197,242,211,30);border-radius:10px;padding:8px 10px;selection-background-color:#286947;}
QSpinBox:focus {border-color:#3fbf7f;}
QFrame#sidebar {background:rgba(18,26,23,185);border:1px solid rgba(255,255,255,105);border-radius:18px;}
QFrame#pageCard {background:rgba(18,26,23,175);border:1px solid rgba(255,255,255,145);border-radius:16px;}
QLabel#navBrand {font-size:24pt;font-weight:800;color:#5fd9a0;letter-spacing:3px;}
QLabel#navProduct {font-size:18pt;font-weight:600;color:#e8ece9;}
QLabel#pageTitle {font-size:28pt;font-weight:650;color:#e8ece9;letter-spacing:-1px;}
QLabel#cardTitle {font-size:17pt;font-weight:600;color:#e8ece9;}
QFrame#metric {background:rgba(22,31,27,175);border:1px solid rgba(255,255,255,145);border-radius:13px;}
QLabel#metricValue {font-size:20pt;font-weight:600;color:#5fd9a0;}
QFrame#welcome {background:rgba(10,15,13,95);border:1px solid rgba(255,255,255,105);border-radius:14px;}
QLabel#welcomeTitle {font-size:24pt;font-weight:600;color:#e8ece9;letter-spacing:-1px;}
QLabel#welcomeMark {font-size:64pt;color:#3fbf7f;}
QListWidget {background:rgba(10,15,13,115);border:1px solid rgba(197,242,211,18);border-radius:12px;padding:6px;outline:0;}
QListWidget::item {padding:9px 6px;border-radius:7px;}
QListWidget::item:hover {background:rgba(63,191,127,18);}
QListWidget::item:selected {background:rgba(63,191,127,30);color:#e8ece9;}
QListWidget::indicator,QCheckBox::indicator {width:15px;height:15px;border:1px solid #466052;border-radius:4px;background:rgba(10,15,13,150);}
QListWidget::indicator:checked,QCheckBox::indicator:checked {background:#3fbf7f;border:3px solid #23543b;}
QCheckBox {spacing:8px;color:#a9beb1;padding:5px 0;}
QCheckBox:hover {color:#e8ece9;}
QTabWidget::pane {background:rgba(18,26,23,165);border:1px solid rgba(255,255,255,145);border-radius:17px;top:7px;}
QTabBar::tab {padding:13px 24px;color:#8a968f;background:transparent;border:0;}
QTabBar::tab:selected {color:#5fd9a0;font-weight:600;}
QTabBar::tab:hover {color:#e8ece9;}
QTableView {background:rgba(10,15,13,160);alternate-background-color:rgba(232,236,233,5);border:1px solid rgba(197,242,211,20);border-radius:11px;gridline-color:#213129;selection-background-color:#24563c;selection-color:#e8ece9;}
QHeaderView::section {background:#16231b;color:#a9beb1;border:0;border-bottom:1px solid #2a3c31;border-right:1px solid #213129;padding:10px;}
QTableCornerButton::section {background:#16231b;border:0;}
QFrame#cell {background:rgba(22,31,27,210);border:1px solid rgba(255,255,255,145);border-radius:15px;}
QPlainTextEdit {font-family:Consolas;font-size:10pt;background:#0d1510;color:#d5e5da;border:1px solid #25372c;border-radius:10px;padding:10px;selection-background-color:#28553d;}
QPlainTextEdit:focus {border:1px solid #3c7353;}
QTextBrowser {background:#101b14;color:#e8ece9;border:1px solid #25372c;border-radius:10px;padding:10px;selection-background-color:#28553d;}
QScrollArea {border:0;background:transparent;}
QScrollBar:vertical {width:8px;background:transparent;margin:4px 0;}
QScrollBar::handle:vertical {background:#344d3e;border-radius:4px;min-height:35px;}
QScrollBar::handle:vertical:hover {background:#3fbf7f;}
QScrollBar:horizontal {height:8px;background:transparent;}
QScrollBar::handle:horizontal {background:#344d3e;border-radius:4px;min-width:35px;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QScrollBar::add-page,QScrollBar::sub-page {background:transparent;}
QSplitter::handle {background:transparent;width:14px;}
QSplitter::handle:hover {background:rgba(63,191,127,20);border-radius:4px;}
QStatusBar {background:rgba(10,15,13,180);color:#8a968f;border-top:1px solid #213129;padding:5px 14px;font-size:9pt;}
QToolTip {background:#18271e;color:#e8ece9;border:1px solid #3c7353;padding:8px;}
QMessageBox,QFileDialog,QDialog {background:#121a17;}
QMessageBox QPushButton,QFileDialog QPushButton {background:#203d2d;color:#e8ece9;border:1px solid #3c7353;border-radius:8px;min-width:70px;}
QLineEdit {background:#0d1510;color:#e8ece9;border:1px solid #344d3e;border-radius:6px;padding:6px;}
"""
