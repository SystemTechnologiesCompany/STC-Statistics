import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from stc_statistics.theme import GlassButton, GlassComboBox, GlassTabBar, initialize_fonts


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        initialize_fonts(cls.app)

    def test_hover_animation_and_reduced_motion(self):
        host = QWidget()
        button = GlassButton('Test', host)
        host.show()
        host.setProperty('reduceMotion', False)
        point = QPointF(10, 10)
        QApplication.sendEvent(button, QEnterEvent(point, point, point))
        QTest.qWait(250)
        self.assertAlmostEqual(button.hover, 1.0)
        host.setProperty('reduceMotion', True)
        QApplication.sendEvent(button, QEvent(QEvent.Type.Leave))
        self.assertEqual(button.hover, 0.0)
        self.assertEqual(button.hover_animation.state(), button.hover_animation.State.Stopped)
        host.close()

    def test_dropdown_keyboard_and_tab_animation(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        combo = GlassComboBox()
        combo.addItems(['English', 'Français'])
        layout.addWidget(combo)
        tabs = GlassTabBar()
        tabs.addTab('Data')
        tabs.addTab('Python')
        layout.addWidget(tabs)
        host.show()
        combo.setFocus()
        combo.showPopup()
        QTest.qWait(350)
        self.assertAlmostEqual(combo.angle, 180.0)
        QTest.keyClick(combo, Qt.Key.Key_Down)
        QTest.keyClick(combo, Qt.Key.Key_Return)
        combo.hidePopup()
        QTest.qWait(250)
        self.assertEqual(combo.currentText(), 'Français')
        self.assertAlmostEqual(combo.angle, 0.0)
        tabs.setCurrentIndex(1)
        QTest.qWait(300)
        self.assertEqual(tabs.indicator, tabs.target_rect())
        host.close()


if __name__ == '__main__':
    unittest.main()
