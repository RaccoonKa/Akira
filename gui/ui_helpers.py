"""
Общие кроссплатформенные UI-помощники для PyQt6 (шрифты и перетаскивание окон на X11 / Wayland / Windows).
"""

import os
import sys
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import QDialog, QFileDialog, QWidget
from core.utils.platform_utils import is_wayland

MONO_CSS_FAMILY = "'JetBrains Mono', 'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono', 'Ubuntu Mono', 'Consolas', monospace"
_MONO_CANDIDATES = (
    "JetBrains Mono",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Noto Sans Mono",
    "Ubuntu Mono",
    "Consolas",
)
_UI_LINUX_CANDIDATES = ("Noto Sans", "Ubuntu", "DejaVu Sans", "Liberation Sans")


def get_ui_fallback_font() -> str:
    """Возвращает базовый системный шрифт интерфейса, если кастомный шрифт не загружен."""
    if sys.platform == "win32":
        return "Arial"
    try:
        available = set(QFontDatabase.families())
        for fam in _UI_LINUX_CANDIDATES:
            if fam in available:
                return fam
    except Exception:
        pass
    return "Sans Serif"


def get_monospace_font(point_size: int = 10) -> QFont:
    """Возвращает моноширинный шрифт с корректным fallback на Linux и Windows."""
    if sys.platform == "win32":
        font = QFont("Consolas", point_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        return font

    try:
        available = set(QFontDatabase.families())
        for fam in _MONO_CANDIDATES:
            if fam in available:
                font = QFont(fam, point_size)
                font.setStyleHint(QFont.StyleHint.Monospace)
                return font
    except Exception:
        pass

    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(point_size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def handle_drag_press(widget, event) -> bool:
    """Обработчик нажатия мыши для перемещения безрамочного окна (Wayland startSystemMove / X11 & Win move)."""
    if event.button() != Qt.MouseButton.LeftButton:
        return False
    if is_wayland():
        try:
            wh = widget.windowHandle()
            if wh is not None and wh.startSystemMove():
                widget.drag_position = QPoint()
                event.accept()
                return True
        except Exception:
            pass
    widget.drag_position = event.globalPosition().toPoint() - widget.frameGeometry().topLeft()
    event.accept()
    return True


def handle_drag_move(widget, event) -> bool:
    """Обработчик перемещения мыши для X11/Windows."""
    if is_wayland():
        return False
    drag_pos = getattr(widget, "drag_position", QPoint())
    if event.buttons() == Qt.MouseButton.LeftButton and not drag_pos.isNull():
        widget.move(event.globalPosition().toPoint() - drag_pos)
        event.accept()
        return True
    return False


def handle_drag_release(widget, event) -> bool:
    if event.button() == Qt.MouseButton.LeftButton:
        widget.drag_position = QPoint()
        event.accept()
        return True
    return False


def _resolve_dialog_parent(parent):
    if isinstance(parent, QWidget):
        top = parent.window()
        if top is not None:
            return top
    return parent if isinstance(parent, QWidget) else None


def _detect_dialog_theme(parent) -> str:
    for obj in (parent, _resolve_dialog_parent(parent)):
        if obj is not None:
            theme = getattr(obj, "current_theme", None)
            if theme in ("dark", "light"):
                return theme
    return "dark"


def _build_qt_file_dialog_stylesheet(theme: str) -> str:
    if theme == "light":
        bg = "#f8fafc"
        panel = "#ffffff"
        fg = "#0f172a"
        muted = "#475569"
        border = "#cbd5e1"
        sel_bg = "#e0e7ff"
        sel_fg = "#1e1b4b"
        btn_bg = "#e2e8f0"
        btn_hover = "#cbd5e1"
    else:
        bg = "#101114"
        panel = "#17181c"
        fg = "#ebe6d8"
        muted = "#a39e8e"
        border = "#3a3830"
        sel_bg = "#2f2c22"
        sel_fg = "#ffffff"
        btn_bg = "#202228"
        btn_hover = "#2c2f38"

    return f"""
QFileDialog {{
    background-color: {bg};
    color: {fg};
}}
QFileDialog QWidget {{
    background-color: {bg};
    color: {fg};
}}
QFileDialog QLineEdit,
QFileDialog QComboBox {{
    background-color: {panel};
    color: {fg};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px 8px;
}}
QFileDialog QTreeView,
QFileDialog QListView,
QFileDialog QTableView {{
    background-color: {panel};
    color: {fg};
    alternate-background-color: {bg};
    border: 1px solid {border};
    border-radius: 6px;
    selection-background-color: {sel_bg};
    selection-color: {sel_fg};
}}
QFileDialog QHeaderView::section {{
    background-color: {bg};
    color: {muted};
    border: none;
    border-bottom: 1px solid {border};
    padding: 4px 6px;
}}
QFileDialog QPushButton {{
    background-color: {btn_bg};
    color: {fg};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 5px 14px;
    min-width: 72px;
}}
QFileDialog QPushButton:hover {{
    background-color: {btn_hover};
}}
"""


def _prepare_linux_file_dialog(
    parent,
    caption: str,
    directory: str,
    file_filter: str,
    accept_mode: QFileDialog.AcceptMode,
    file_mode: QFileDialog.FileMode,
) -> QFileDialog:
    parent_win = _resolve_dialog_parent(parent)
    theme = _detect_dialog_theme(parent)

    start_dir = directory or ""
    if not start_dir:
        home_dir = os.path.expanduser("~")
        if os.path.isdir(home_dir):
            start_dir = home_dir
    elif (
        accept_mode == QFileDialog.AcceptMode.AcceptSave
        and not os.path.isabs(start_dir)
        and os.sep not in start_dir
        and "/" not in start_dir
    ):
        home_dir = os.path.expanduser("~")
        if os.path.isdir(home_dir):
            start_dir = os.path.join(home_dir, start_dir)

    dlg = QFileDialog(parent_win, caption, start_dir, file_filter)
    # На Linux нативный GTK3/Portal QFileDialog внутри безрамочного WA_TranslucentBackground
    # окна может зависать без отображения окна — используем автономный Qt-диалог.
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setAcceptMode(accept_mode)
    dlg.setFileMode(file_mode)
    dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    dlg.setAutoFillBackground(True)
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.setStyleSheet(_build_qt_file_dialog_stylesheet(theme))
    dlg.resize(740, 470)

    screen = None
    if parent_win is not None and hasattr(parent_win, "screen"):
        screen = parent_win.screen()
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is not None:
        avail = screen.availableGeometry()
        if parent_win is not None and parent_win.isVisible():
            center = parent_win.frameGeometry().center()
        else:
            center = avail.center()
        x = max(avail.left() + 12, min(center.x() - dlg.width() // 2, avail.right() - dlg.width() - 12))
        y = max(avail.top() + 12, min(center.y() - dlg.height() // 2, avail.bottom() - dlg.height() - 12))
        dlg.move(x, y)

    return dlg


def open_file_dialog(parent=None, caption: str = "", directory: str = "", file_filter: str = "") -> str:
    """Кроссплатформенно открывает диалог выбора одного файла без зависания на Linux."""
    if sys.platform == "win32":
        path, _ = QFileDialog.getOpenFileName(_resolve_dialog_parent(parent), caption, directory, file_filter)
        return path or ""

    dlg = _prepare_linux_file_dialog(
        parent,
        caption,
        directory,
        file_filter,
        QFileDialog.AcceptMode.AcceptOpen,
        QFileDialog.FileMode.ExistingFile,
    )
    if dlg.exec() == QDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""


def open_files_dialog(parent=None, caption: str = "", directory: str = "", file_filter: str = "") -> list[str]:
    """Кроссплатформенно открывает диалог множественного выбора файлов без зависания на Linux."""
    if sys.platform == "win32":
        files, _ = QFileDialog.getOpenFileNames(_resolve_dialog_parent(parent), caption, directory, file_filter)
        return list(files or [])

    dlg = _prepare_linux_file_dialog(
        parent,
        caption,
        directory,
        file_filter,
        QFileDialog.AcceptMode.AcceptOpen,
        QFileDialog.FileMode.ExistingFiles,
    )
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return list(dlg.selectedFiles() or [])
    return []


def save_file_dialog(parent=None, caption: str = "", directory: str = "", file_filter: str = "") -> str:
    """Кроссплатформенно открывает диалог сохранения файла без зависания на Linux."""
    if sys.platform == "win32":
        path, _ = QFileDialog.getSaveFileName(_resolve_dialog_parent(parent), caption, directory, file_filter)
        return path or ""

    dlg = _prepare_linux_file_dialog(
        parent,
        caption,
        directory,
        file_filter,
        QFileDialog.AcceptMode.AcceptSave,
        QFileDialog.FileMode.AnyFile,
    )
    if dlg.exec() == QDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""
