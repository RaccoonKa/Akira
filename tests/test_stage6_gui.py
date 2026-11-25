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

    def test_09_linux_window_no_void_and_jitter_free_studio_expand(self):
        from core.database import chat_db as cdb
        from core.utils.config import DEFAULT_CONFIG
        from gui.windows import chat_window as cw_mod
        from PyQt6.QtCore import QPoint, QRect
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
                    # 1. Linux X11 Normal mode: single unified MainWindow stays compact at NORMAL_WIDTH (no void in preview)
                    self.assertEqual(mw.width(), mw.NORMAL_WIDTH)
                    self.assertEqual(mw.bg_frame.geometry(), QRect(0, 0, mw.NORMAL_WIDTH, mw.WINDOW_HEIGHT))
                    self.assertIsNone(mw.bg_frame._reveal_width)
                    self.assertIsNone(getattr(mw, "studio_wing", None))
                    self.assertIs(mw.studio_panel.parent(), mw.bg_frame)
                    self.assertIs(mw.right_area.parent(), mw.bg_frame)
                    self.assertIs(mw.studio_panel.main_window, mw)

                    # 2. Single-window expand & collapse on Linux X11: stationary OS frame & right_area during animation
                    mw.move(1000, 120)
                    expected_right_edge = mw.x() + mw.width()

                    mw._prepare_linux_expand_window()
                    anchor_pos = QPoint(mw.pos())
                    anchor_size = mw.size()
                    expected_right_geo = QRect(
                        mw.EXTENDED_WIDTH - mw.NORMAL_WIDTH + 2,
                        2,
                        mw.NORMAL_WIDTH - 4,
                        mw.WINDOW_HEIGHT - 4,
                    )
                    self.assertEqual(anchor_size.width(), mw.EXTENDED_WIDTH)
                    self.assertEqual(mw.x() + mw.width(), expected_right_edge)
                    self.assertEqual(mw.right_area.geometry(), expected_right_geo)

                    start_w, end_w = mw._expand_anim_bounds()
                    self.assertEqual((start_w, end_w), (float(mw.NORMAL_WIDTH), float(mw.EXTENDED_WIDTH)))
                    for step_w in (mw.NORMAL_WIDTH, 520, 700, mw.EXTENDED_WIDTH, 700, 520, mw.NORMAL_WIDTH):
                        mw._on_expand_step(step_w)
                        self.assertEqual(mw.pos(), anchor_pos)
                        self.assertEqual(mw.size(), anchor_size)
                        self.assertEqual(mw.right_area.geometry(), expected_right_geo)
                        self.assertEqual(mw.bg_frame.visible_rect().width(), step_w)

                    mw._apply_expanded_geometry()
                    self.assertEqual(mw.width(), mw.EXTENDED_WIDTH)
                    self.assertEqual(mw.bg_frame.visible_rect().width(), mw.EXTENDED_WIDTH)

                    mw._apply_collapsed_geometry()
                    self.assertEqual(mw.width(), mw.NORMAL_WIDTH)
                    self.assertEqual(mw.x() + mw.width(), expected_right_edge)
                    self.assertEqual(mw.y(), 120)
                    self.assertEqual(mw.bg_frame.geometry(), QRect(0, 0, mw.NORMAL_WIDTH, mw.WINDOW_HEIGHT))
                    self.assertEqual(mw.right_area.geometry(), QRect(2, 2, mw.NORMAL_WIDTH - 4, mw.WINDOW_HEIGHT - 4))
                    self.assertIsNone(mw.bg_frame._reveal_width)

                    # 3. Wayland keeps single-window resize expand/collapse without move()
                    with patch.object(cw_mod, "is_wayland", return_value=True):
                        mw._on_expand_step(640)
                        self.assertEqual(mw.width(), 640)
                        self.assertIsNone(mw.bg_frame._reveal_width)
                        mw._apply_collapsed_geometry()
                        self.assertEqual(mw.width(), mw.NORMAL_WIDTH)

                    # 4. X11 ConfigureNotify handoff defers child shifts & repaints cleanly on match
                    import ctypes
                    import struct
                    from PyQt6.QtGui import QGuiApplication

                    QWidget.show(mw)
                    mw.move(1000, 120)
                    self.app.processEvents()
                    wid = int(mw.winId())
                    ready_calls = []

                    with patch.dict(os.environ, {"DISPLAY": ":0"}), \
                            patch.object(QGuiApplication, "platformName", return_value="xcb"), \
                            patch.object(mw, "_apply_x11_northeast_gravity"):
                        mw._prepare_linux_expand_window(on_ready=lambda: ready_calls.append("expanded"))
                        self.assertFalse(mw.updatesEnabled())
                        self.assertEqual(mw.right_area.geometry().x(), 2)
                        self.assertIsNotNone(mw._x11_handoff_filter)

                        # Wrong width event must not trigger early unlock
                        wrong_pkt = (ctypes.c_ubyte * 24).from_buffer_copy(
                            struct.pack("<BBHIIIhhHH", 22, 0, 1, wid, wid, 0, 500, 120, 640, 560)
                        )
                        mw._x11_handoff_filter.nativeEventFilter(b"xcb_generic_event_t", ctypes.addressof(wrong_pkt))
                        self.app.processEvents()
                        self.assertFalse(mw.updatesEnabled())

                        # Exact ConfigureNotify(880) unlocks & moves right_area synchronously
                        ok_pkt = (ctypes.c_ubyte * 24).from_buffer_copy(
                            struct.pack("<BBHIIIhhHH", 22, 0, 2, wid, wid, 0, 500, 120, mw.EXTENDED_WIDTH, mw.WINDOW_HEIGHT)
                        )
                        mw._x11_handoff_filter.nativeEventFilter(b"xcb_generic_event_t", ctypes.addressof(ok_pkt))
                        self.app.processEvents()
                        self.assertTrue(mw.updatesEnabled())
                        self.assertEqual(mw.right_area.geometry(), expected_right_geo)
                        self.assertEqual(ready_calls, ["expanded"])

                        # Collapse handoff awaits ConfigureNotify(380) before moving right_area back to x=2
                        collapse_done = []
                        mw._apply_collapsed_geometry(on_done=lambda: collapse_done.append("collapsed"))
                        self.assertFalse(mw.updatesEnabled())
                        self.assertEqual(mw.right_area.geometry(), expected_right_geo)

                        ok_col_pkt = (ctypes.c_ubyte * 24).from_buffer_copy(
                            struct.pack("<BBHIIIhhHH", 22, 0, 3, wid, wid, 0, 1000, 120, mw.NORMAL_WIDTH, mw.WINDOW_HEIGHT)
                        )
                        mw._x11_handoff_filter.nativeEventFilter(b"xcb_generic_event_t", ctypes.addressof(ok_col_pkt))
                        self.app.processEvents()
                        self.assertTrue(mw.updatesEnabled())
                        self.assertEqual(mw.right_area.geometry(), QRect(2, 2, mw.NORMAL_WIDTH - 4, mw.WINDOW_HEIGHT - 4))
                        self.assertEqual(collapse_done, ["collapsed"])

                    # 5. Windows Zero-Move + stationary right_area inside fixed EXTENDED_WIDTH bg_frame
                    with patch.object(cw_mod, "CommandParser", return_value=MagicMock()), \
                            patch.object(cw_mod.sys, "platform", "win32"):
                        win_mw = cw_mod.MainWindow(dict(DEFAULT_CONFIG))
                        try:
                            expected_right_geo = QRect(
                                win_mw.EXTENDED_WIDTH - win_mw.NORMAL_WIDTH + 2,
                                2,
                                win_mw.NORMAL_WIDTH - 4,
                                win_mw.WINDOW_HEIGHT - 4,
                            )
                            self.assertEqual(win_mw.width(), win_mw.EXTENDED_WIDTH)
                            self.assertEqual(win_mw.bg_frame.geometry(), QRect(0, 0, win_mw.EXTENDED_WIDTH, win_mw.WINDOW_HEIGHT))
                            self.assertEqual(win_mw.bg_frame.visible_rect().width(), win_mw.NORMAL_WIDTH)
                            self.assertEqual(win_mw.right_area.geometry(), expected_right_geo)

                            for w_step in (win_mw.NORMAL_WIDTH, 550, 720, win_mw.EXTENDED_WIDTH):
                                win_mw._on_expand_step(w_step)
                                self.assertEqual(win_mw.bg_frame.geometry(), QRect(0, 0, win_mw.EXTENDED_WIDTH, win_mw.WINDOW_HEIGHT))
                                self.assertEqual(win_mw.right_area.geometry(), expected_right_geo)
                                self.assertEqual(win_mw.bg_frame.visible_rect().width(), w_step)
                        finally:
                            win_mw.shutdown()
                            win_mw.close()
                finally:
                    mw.shutdown()
                    mw.close()

    def test_10_game_mode_persists_across_restart_and_pauses_stt(self):
        import json
        import tempfile
        from core.database import chat_db as cdb
        from core.utils import config as cfg_mod
        from gui.windows import chat_window as cw_mod

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(cdb, "get_db_path", return_value=os.path.join(tmp, "s6_gm.db")):
            cfg_file = Path(tmp) / "config.json"
            cfg_file.write_text(json.dumps(dict(cfg_mod.DEFAULT_CONFIG)), encoding="utf-8")

            def _load():
                return json.loads(cfg_file.read_text(encoding="utf-8"))

            def _save(data):
                cfg_file.write_text(json.dumps(data), encoding="utf-8")

            test_db = cdb.StudioChatDatabase()
            stt1 = MagicMock()
            stt2 = MagicMock()

            with patch.object(cw_mod, "load_config", side_effect=_load), \
                    patch.object(cw_mod, "save_config", side_effect=_save), \
                    patch("gui.windows.studio_frame.load_config", side_effect=_load), \
                    patch("gui.windows.settings_window.load_config", side_effect=_load), \
                    patch("gui.windows.studio_frame.studio_db", test_db), \
                    patch.object(cw_mod, "TTSThread", return_value=MagicMock()), \
                    patch.object(cw_mod, "VisionThread"), \
                    patch.object(cw_mod, "UpdateCheckerThread"), \
                    patch("core.utils.config.get_user_data_path", side_effect=lambda *p: os.path.join(tmp, *p)):
                with patch.object(cw_mod, "STTThread", return_value=stt1):
                    mw1 = cw_mod.MainWindow(_load())
                    try:
                        self.assertFalse(mw1.is_game_mode)
                        mw1.toggle_game_mode(enable=True, announce=False)
                        self.assertTrue(mw1.is_game_mode)
                        self.assertTrue(_load()["is_game_mode"])
                        stt1.set_paused.assert_called_with(True)
                    finally:
                        mw1.shutdown()
                        mw1.close()

                # Simulated full close & reopen reads saved is_game_mode=True
                with patch.object(cw_mod, "STTThread", return_value=stt2):
                    mw2 = cw_mod.MainWindow(_load())
                    try:
                        self.assertTrue(mw2.is_game_mode)
                        self.assertTrue(stt2.is_paused)
                        self.assertIn("активен", mw2.game_mode_btn.toolTip())

                        # Explicit turn off persists False
                        mw2.toggle_game_mode(enable=False, announce=False)
                        self.assertFalse(mw2.is_game_mode)
                        self.assertFalse(_load()["is_game_mode"])
                    finally:
                        mw2.shutdown()
                        mw2.close()

    def test_11_main_chat_smooth_scroll_and_studio_styling(self):
        import tempfile
        from PyQt6.QtGui import QWheelEvent
        from core.database import chat_db as cdb
        from core.utils.config import DEFAULT_CONFIG
        from gui.styles import get_main_style
        from gui.widgets.code_formatter import CodeBlockWidget
        from gui.windows import chat_window as cw_mod
        from gui.windows.studio_frame import SmoothScrollArea, StudioAkiraStream, StudioUserMessage

        self.assertIn("QScrollArea#ChatHistory", get_main_style("dark"))
        self.assertIn("QScrollArea#ChatHistory", get_main_style("light"))

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(cdb, "get_db_path", return_value=os.path.join(tmp, "s6_chat.db")):
            test_db = cdb.StudioChatDatabase()
            with patch.object(cw_mod, "STTThread", return_value=MagicMock()), \
                    patch.object(cw_mod, "TTSThread", return_value=MagicMock()), \
                    patch.object(cw_mod, "VisionThread"), \
                    patch.object(cw_mod, "UpdateCheckerThread"), \
                    patch("gui.windows.studio_frame.studio_db", test_db), \
                    patch("core.utils.config.get_user_data_path", side_effect=lambda *p: os.path.join(tmp, *p)):
                mw = cw_mod.MainWindow(dict(DEFAULT_CONFIG))
                try:
                    feed = mw.chat_history
                    self.assertIsInstance(feed, cw_mod.ChatHistoryFeed)
                    self.assertIsInstance(feed, SmoothScrollArea)

                    mw.right_panel.set_emotion("happy")
                    feed.append("Вы: Покажи код на Python")
                    mw.stream_text_to_chat("Лови пример:\n```python\nprint('hello')\n```")
                    feed.finish_active_stream()

                    items = [
                        feed.feed_layout.itemAt(i).widget()
                        for i in range(feed.feed_layout.count())
                    ]
                    self.assertEqual(len(items), 2)
                    self.assertIsInstance(items[0], StudioUserMessage)
                    self.assertIsNotNone(items[0].rail)
                    self.assertIsInstance(items[1], StudioAkiraStream)
                    self.assertIsNotNone(items[1].rail)
                    self.assertTrue(any(isinstance(cb, CodeBlockWidget) for cb in items[1].code_blocks))

                    # Show panel to verify real layout & smooth wheel scroll momentum timer
                    QWidget.show(mw)
                    mw.right_panel.setFixedHeight(280)
                    mw.right_panel.show()
                    for idx in range(12):
                        feed.append(f"Вы: Сообщение #{idx}")
                        feed.append(f"Акира: Длинный ответ номер {idx} для проверки прокрутки чата в основном окне.")

                    self.app.processEvents()
                    self.app.processEvents()
                    self.assertGreater(feed.verticalScrollBar().maximum(), 0)

                    wheel_ev = QWheelEvent(
                        QPointF(100, 100),
                        QPointF(100, 100),
                        QPoint(0, 0),
                        QPoint(0, 120),
                        Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase,
                        False,
                    )
                    feed.wheelEvent(wheel_ev)
                    self.assertTrue(feed._timer.isActive())

                    # Switching theme propagates to all Studio-styled widgets in main chat
                    mw.apply_theme("light")
                    self.assertEqual(items[0].current_theme, "light")
                    self.assertEqual(items[1].current_theme, "light")
                finally:
                    mw.shutdown()
                    mw.close()


if __name__ == "__main__":
    unittest.main()
