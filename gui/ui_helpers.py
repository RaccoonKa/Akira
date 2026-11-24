"""
Общие кроссплатформенные UI-помощники для PyQt6 (шрифты и перетаскивание окон на X11 / Wayland / Windows).
"""

import sys
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QFontDatabase
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
