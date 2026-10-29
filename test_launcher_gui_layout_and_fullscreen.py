import os
import sys
import unittest

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

# Initialize single QApplication instance for tests
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from launcher_gui import MainWindow


class TestLauncherGuiLayoutAndFullscreen(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()

    def test_top_bar_dimensions_within_display_bounds(self):
        """Verify MainWindow and top_bar min width are well under high-DPI display constraints (e.g. 1620 logical points for Surface Book 3)."""
        min_size = self.window.minimumSizeHint()
        # Surface Book 3 is 3240x2160 device px with 200% scaling = 1620 logical points wide.
        # min_size width MUST be substantially under 1620 to never trigger mintrack overflow.
        self.assertLess(min_size.width(), 1300, f"MainWindow minimum width {min_size.width()} is too wide and will overflow high-DPI displays!")
        self.assertLessEqual(min_size.height(), 400, f"MainWindow minimum height {min_size.height()} is too tall!")

    def test_fullscreen_and_maximized_toggle(self):
        """Verify window can show maximized and toggle fullscreen seamlessly without geometry errors."""
        self.window.showMaximized()
        self.assertTrue(self.window.isMaximized(), "MainWindow should be maximized on launch")

        # Toggle to Fullscreen
        self.window.toggle_fullscreen()
        self.assertTrue(self.window.isFullScreen(), "MainWindow should be fullscreen after toggle")
        self.assertIn("Exit", self.window.btn_fullscreen.text())

        # Toggle back to Maximized
        self.window.toggle_fullscreen()
        self.assertFalse(self.window.isFullScreen(), "MainWindow should exit fullscreen")
        self.assertIn("Fullscreen", self.window.btn_fullscreen.text())

    def test_keyboard_shortcuts_f11_and_escape(self):
        """Verify F11 toggles fullscreen and Escape exits fullscreen."""
        # Press F11 -> enter fullscreen
        f11_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F11, Qt.KeyboardModifier.NoModifier)
        self.window.keyPressEvent(f11_event)
        self.assertTrue(self.window.isFullScreen(), "F11 should enter fullscreen")

        # Press Esc -> exit fullscreen
        esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        self.window.keyPressEvent(esc_event)
        self.assertFalse(self.window.isFullScreen(), "Escape should exit fullscreen")


if __name__ == "__main__":
    unittest.main()
