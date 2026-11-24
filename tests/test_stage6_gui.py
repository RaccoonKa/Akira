import os
import py_compile
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt6.QtCore import QPoint, QPointF, QPropertyAnimation, QParallelAnimationGroup, Qt  # noqa: E402
from PyQt6.QtGui import QFont, QMouseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QWidget  # noqa: E402


STAGE6_FILES = [
    "gui/ui_helpers.py",
    "gui/components/blur.py",
    "gui/components/tray.py",
    "gui/styles.py",
    "gui/widgets/code_formatter.py",
    "gui/windows/mini_window.py",
    "gui/windows/chat_window.py",
    "gui/windows/settings_window.py",
    "gui/windows/studio_frame.py",
    "gui/dialogs/onboarding_wizard.py",
    "gui/dialogs/face_manager_dialog.py",
    "gui/dialogs/voice_enrollment_dialog.py",
    "gui/dialogs/mode_config_dialog.py",
    "gui/dialogs/spotify_auth_dialog.py",
    "gui/dialogs/yandex_auth_dialog.py",
    "gui/dialogs/gigachat_auth_dialog.py",
    "gui/dialogs/telegram_pair_dialog.py",
    "gui/dialogs/routerai_auth_dialog.py",
    "gui/dialogs/yandex_iot_auth_dialog.py",
]


class _TrayHostWindow(QWidget):
    """Minimal host window exposing methods expected by SystemTray."""

    def __init__(self):
        super().__init__()
        self.resize(300, 300)
        self.exit_called = False
        self.bring_called = False

    def exit_app(self):
        self.exit_called = True

    def bring_to_front(self):
        self.bring_called = True
        self.raise_()


class TestStage6GuiCrossplatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_01_py_compile_all_stage6_files(self):
        for rel_path in STAGE6_FILES:
            abs_path = ROOT_DIR / rel_path
            self.assertTrue(abs_path.is_file(), f"Missing file: {rel_path}")
            py_compile.compile(str(abs_path), doraise=True)

    def test_02_no_bare_consolas_or_legacy_inline_css_in_gui(self):
        gui_dir = ROOT_DIR / "gui"
        bare_qfont_re = re.compile(r"""QFont\(\s*['"]Consolas['"]""")
        bare_inline_css_re = re.compile(r"""font-family\s*:\s*Consolas\s*,\s*monospace""")

        for py_file in gui_dir.rglob("*.py"):
            rel = py_file.relative_to(ROOT_DIR).as_posix()
            if rel == "gui/ui_helpers.py":
                continue
            text = py_file.read_text(encoding="utf-8")
            self.assertIsNone(
                bare_qfont_re.search(text),
                f"Bare QFont('Consolas', ...) still present in {rel}",
            )
            self.assertIsNone(
                bare_inline_css_re.search(text),
                f"Bare 'font-family: Consolas, monospace' still present in {rel}",
            )

        from gui.styles import get_main_style

        style_text = get_main_style("dark")
        self.assertIn("JetBrains Mono", style_text)
        self.assertIn("DejaVu Sans Mono", style_text)
        self.assertIn("Liberation Mono", style_text)

    def test_03_ui_helpers_fonts_and_drag(self):
        from gui import ui_helpers

        mono = ui_helpers.get_monospace_font(11)
        self.assertIsInstance(mono, QFont)
        self.assertEqual(mono.pointSize(), 11)

        linux_ui_font = ui_helpers.get_ui_fallback_font()
        self.assertIsInstance(linux_ui_font, str)
        self.assertTrue(bool(linux_ui_font.strip()))

        with patch.object(ui_helpers.sys, "platform", "win32"):
            self.assertEqual(ui_helpers.get_ui_fallback_font(), "Arial")

        w = QWidget()
        w.resize(200, 120)
        w.move(50, 60)

        press_right = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(100, 100),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(ui_helpers, "is_wayland", return_value=False):
            self.assertFalse(ui_helpers.handle_drag_press(w, press_right))

        press_left = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        move_left = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(30, 40),
            QPointF(140, 150),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        release_left = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(30, 40),
            QPointF(140, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(ui_helpers, "is_wayland", return_value=False):
            self.assertTrue(ui_helpers.handle_drag_press(w, press_left))
            self.assertFalse(w.drag_position.isNull())
            self.assertTrue(ui_helpers.handle_drag_move(w, move_left))
            self.assertEqual(w.pos(), QPoint(90, 110))
            self.assertTrue(ui_helpers.handle_drag_release(w, release_left))
            self.assertTrue(w.drag_position.isNull())

        fake_handle = MagicMock()
        fake_handle.startSystemMove.return_value = True
        with patch.object(ui_helpers, "is_wayland", return_value=True), \
                patch.object(w, "windowHandle", return_value=fake_handle):
            self.assertTrue(ui_helpers.handle_drag_press(w, press_left))
            fake_handle.startSystemMove.assert_called_once()
        w.close()

    def test_04_blur_cinnamon_noop_and_kde_guard(self):
        from gui.components import blur

        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "X-Cinnamon"}, clear=False):
            blur.enable_window_acrylic(0)
            blur.disable_window_acrylic(0)

        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}, clear=False):
            blur.enable_window_acrylic(0)
            blur.disable_window_acrylic(0)

    def test_05_system_tray_linux_cinnamon(self):
        from gui.components.tray import SystemTray

        win = _TrayHostWindow()
        tray = SystemTray(win, self.app)

        self.assertFalse(tray.icon().isNull())
        menu = tray.contextMenu()
        self.assertIsNotNone(menu)
        action_texts = [a.text() for a in menu.actions() if a.text()]
        self.assertIn("Открыть окно", action_texts)
        self.assertIn("Свернуть", action_texts)
        self.assertIn("Выход", action_texts)

        tray.hide_window()
        self.assertFalse(win.isVisible())

        tray.show_window()
        self.assertTrue(win.isVisible())
        self.assertFalse(bool(win.windowState() & Qt.WindowState.WindowMinimized))
        self.assertEqual(win.windowOpacity(), 1.0)
        self.assertTrue(win.bring_called)

        tray.on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
        self.assertFalse(win.isVisible())
        tray.on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
        self.assertTrue(win.isVisible())

        tray.hide()
        win.close()

    def test_06_code_formatter_uses_crossplatform_monospace(self):
        from gui.widgets.code_formatter import CodeBlockWidget, markdown_to_rich_html
        from gui.ui_helpers import MONO_CSS_FAMILY

        block = CodeBlockWidget("python", "print('akira')", theme="dark")
        self.assertTrue(bool(block.lang_label.font().family()))
        self.assertTrue(bool(block.code_edit.font().family()))
        self.assertEqual(block.code_edit.font().pointSize(), 10)
        block.close()

        rendered = markdown_to_rich_html("Use `sudo apt update` now", theme="dark")
        self.assertIn(MONO_CSS_FAMILY, rendered)
        self.assertIn("DejaVu Sans Mono", rendered)

    def test_07_mini_window_show_at_x11_and_wayland(self):
        from core.utils import platform_utils
        from gui.windows.mini_window import MiniWindow

        mini = MiniWindow(theme="dark")
        try:
            with patch.object(platform_utils, "is_wayland", return_value=False), \
                    patch.object(mini, "move") as mock_move, \
                    patch.object(mini, "show") as mock_show, \
                    patch.object(mini, "raise_") as mock_raise, \
                    patch.object(mini, "activateWindow"):
                mini.show_at(150, 220)
                mock_move.assert_called_once_with(150, 220)
                mock_show.assert_called_once()
                mock_raise.assert_called_once()

            with patch.object(platform_utils, "is_wayland", return_value=True), \
                    patch.object(mini, "move") as mock_move, \
                    patch.object(mini, "show") as mock_show, \
                    patch.object(mini, "raise_") as mock_raise, \
                    patch.object(mini, "activateWindow"):
                mini.show_at(150, 220)
                mock_move.assert_not_called()
                mock_show.assert_called_once()
                mock_raise.assert_called_once()
        finally:
            mini.close()

    def test_08_main_window_native_event_and_animations(self):
        from gui.windows import chat_window as cw_mod

        class _MainWindowAnimProbe(cw_mod.MainWindow):
            def __init__(self):
                QWidget.__init__(self)
                self.NORMAL_WIDTH = 380
                self.EXTENDED_WIDTH = 880
                self.WINDOW_HEIGHT = 560
                self.window_mode = "normal"
                self.resize(self.NORMAL_WIDTH, self.WINDOW_HEIGHT)
                self._is_animating_window = False
                self._window_ready = True
                self.mini_window = None

            def _check_and_reveal(self):
                pass

            def bring_to_front(self):
                self.raise_()

        host = _MainWindowAnimProbe()
        try:
            self.assertEqual(
                host.nativeEvent(b"xcb_generic_event_t", 0),
                (False, 0),
            )

            with patch.object(cw_mod, "is_wayland", return_value=False):
                host.show_animated()
                self.assertIsInstance(host.opening_anim, QParallelAnimationGroup)
                avail = self.app.primaryScreen().availableGeometry()
                self.assertLessEqual(host.y(), avail.y() + avail.height())
                self.assertEqual(host.opening_anim.animationAt(0).endValue().x(), avail.x() + avail.width() - 380 - 20)
                host.opening_anim.stop()

                done_called = []
                host._animate_down_and_do(lambda: done_called.append(True))
                self.assertIsInstance(host.closing_anim, QParallelAnimationGroup)
                host.closing_anim.stop()

            with patch.object(cw_mod, "is_wayland", return_value=True):
                host.show_animated()
                self.assertIsInstance(host.opening_anim, QPropertyAnimation)
                self.assertEqual(host.opening_anim.propertyName(), b"windowOpacity")
                host.opening_anim.stop()

                done_called = []
                host._animate_down_and_do(lambda: done_called.append(True))
                self.assertIsInstance(host.closing_anim, QPropertyAnimation)
                self.assertEqual(host.closing_anim.propertyName(), b"windowOpacity")
                host.closing_anim.stop()
        finally:
            host.close()

    def test_09_linux_window_width_matches_visible_body_no_void(self):
        from core.database import chat_db as cdb
        from core.utils.config import DEFAULT_CONFIG
        from gui.windows import chat_window as cw_mod
        import tempfile

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(cdb, "get_db_path", return_value=os.path.join(tmp, "s6_w.db")):
            test_db = cdb.StudioChatDatabase()
            with patch.object(cw_mod, "STTThread", return_value=MagicMock()), \
                    patch.object(cw_mod, "TTSThread", return_value=MagicMock()), \
                    patch.object(cw_mod, "VisionThread"), \
                    patch.object(cw_mod, "UpdateCheckerThread"), \
                    patch("gui.windows.studio_frame.studio_db", test_db), \
                    patch("core.utils.config.get_user_data_path", side_effect=lambda *p: os.path.join(tmp, *p)):
                mw = cw_mod.MainWindow(dict(DEFAULT_CONFIG))
                try:
                    # Normal mode on Linux: OS window width == NORMAL_WIDTH (380), no transparent void left side
                    self.assertEqual(mw.width(), mw.NORMAL_WIDTH)
                    self.assertEqual(mw.bg_frame.x(), 0)
                    self.assertEqual(mw.bg_frame.width(), mw.NORMAL_WIDTH)

                    # Expand & collapse keep right edge anchored cleanly
                    mw.move(400, 100)
                    right_before = mw.x() + mw.width()
                    mw._sync_linux_geometry(mw.EXTENDED_WIDTH, anchor_right=right_before)
                    self.assertEqual(mw.width(), mw.EXTENDED_WIDTH)
                    self.assertEqual(mw.x() + mw.width(), right_before)
                    self.assertEqual(mw.bg_frame.geometry().width(), mw.EXTENDED_WIDTH)

                    mw._sync_linux_geometry(mw.NORMAL_WIDTH, anchor_right=right_before)
                    self.assertEqual(mw.width(), mw.NORMAL_WIDTH)
                    self.assertEqual(mw.x() + mw.width(), right_before)
                    self.assertEqual(mw.bg_frame.geometry().x(), 0)
                finally:
                    mw.shutdown()
                    mw.close()


if __name__ == "__main__":
    unittest.main()
