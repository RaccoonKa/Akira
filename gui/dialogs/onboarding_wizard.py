import os
import sys
import math
import random
import shutil
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QStackedWidget, QFrame,
    QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPoint, QPointF,
    QEasingCurve, QVariantAnimation
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QRadialGradient,
    QBrush, QPainterPath, QFont, QFontDatabase, QIcon, QPixmap
)

from core.utils.config import save_config, load_config, get_user_data_path, get_resource_path
from gui.windows.settings_window import ModernToggle, NoScrollComboBox
from gui.styles import get_main_style
from gui.ui_helpers import handle_drag_press, handle_drag_move, handle_drag_release, open_files_dialog

try:
    from gui.components.blur import enable_window_acrylic
except ImportError:
    try:
        from core.utils.blur import enable_window_acrylic
    except ImportError:
        try:
            from gui.utils.blur import enable_window_acrylic
        except ImportError:
            enable_window_acrylic = None

WIZARD_DARK_EXTRA = """
QFrame#WizardCard {
    background-color: rgba(14, 13, 9, 0.86);
    border: 1px solid rgba(120, 115, 95, 0.35);
    border-radius: 12px;
}

QFrame#WizardSubCell {
    background-color: rgba(8, 8, 6, 0.68);
    border: 1px solid rgba(120, 115, 95, 0.24);
    border-radius: 9px;
}

QFrame#WizardSubCell:hover {
    background-color: rgba(22, 20, 15, 0.78);
    border: 1px solid rgba(158, 151, 128, 0.42);
}

QFrame#WizardDivider {
    background-color: rgba(120, 115, 95, 0.32);
    border: none;
}

QLabel#WizardHeaderTitle {
    color: #ded7c4;
    letter-spacing: 1px;
    text-transform: uppercase;
    background: transparent;
}

QLabel#WizardStepCounter {
    background-color: rgba(222, 215, 196, 0.12);
    color: #ded7c4;
    border: 1px solid rgba(120, 115, 95, 0.45);
    border-radius: 6px;
    padding: 2px 8px;
    letter-spacing: 0.8px;
}

QLabel#WizardSectionTitle {
    color: #ded7c4;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    background: transparent;
}

QLabel#WizardFieldLabel {
    color: #fffde7;
    letter-spacing: 0.2px;
    background: transparent;
}

QLabel#WizardSubDesc {
    color: rgba(255, 253, 231, 0.55);
    background: transparent;
}

QLabel#WizardDescText {
    color: rgba(255, 253, 231, 0.88);
    background: transparent;
}

QLabel#WizardStepBadge {
    background-color: rgba(222, 215, 196, 0.14);
    color: #ded7c4;
    border: 1px solid rgba(120, 115, 95, 0.55);
    border-radius: 6px;
}

QLineEdit#WizardInput {
    background-color: rgba(7, 7, 5, 0.92);
    color: #fffde7;
    border: 1px solid #78735f;
    border-radius: 7px;
    padding: 4px 12px;
}

QLineEdit#WizardInput:hover {
    border: 1px solid #9e9780;
    background-color: #12110d;
}

QLineEdit#WizardInput:focus {
    border: 1px solid #ded7c4;
    background-color: #15130f;
    color: #ffffff;
}

QComboBox#WizardCombo {
    background-color: rgba(7, 7, 5, 0.92);
    color: #ded7c4;
    border: 1px solid #78735f;
    border-radius: 7px;
    padding: 4px 28px 4px 12px;
}

QComboBox#WizardCombo:hover {
    border: 1px solid #9e9780;
    background-color: #12110d;
}

QComboBox#WizardCombo:focus {
    border: 1px solid #ded7c4;
}

QComboBox#WizardCombo::drop-down {
    border: none;
    background: transparent;
    width: 0px;
}

QComboBox#WizardCombo::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}

QPushButton#WizardPrimaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #121008;
    border: none;
    border-radius: 7px;
    padding: 6px 18px;
    letter-spacing: 0.8px;
}

QPushButton#WizardPrimaryBtn:hover {
    background: #ffffff;
    color: #121008;
}

QPushButton#WizardActionBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #121008;
    border: none;
    border-radius: 7px;
    padding: 5px 12px;
    letter-spacing: 0.6px;
}

QPushButton#WizardActionBtn:hover {
    background: #ffffff;
    color: #121008;
}

QPushButton#WizardSecondaryBtn {
    background-color: #0e0d0a;
    color: #ded7c4;
    border: 1px solid #78735f;
    border-radius: 7px;
    padding: 5px 12px;
    letter-spacing: 0.6px;
}

QPushButton#WizardSecondaryBtn:hover {
    background-color: #1e1b14;
    border-color: #9e9780;
    color: #ffffff;
}

QPushButton#CloseBtn {
    background-color: transparent;
    color: #ded7c4;
    font-size: 13px;
    border-radius: 6px;
    border: none;
}

QPushButton#CloseBtn:hover {
    background-color: #ff5252;
    color: #ffffff;
}
"""

WIZARD_LIGHT_EXTRA = """
QFrame#WizardCard {
    background-color: rgba(255, 255, 255, 0.90);
    border: 1.5px solid rgba(17, 19, 24, 0.20);
    border-radius: 12px;
}

QFrame#WizardSubCell {
    background-color: rgba(238, 242, 248, 0.92);
    border: 1.2px solid rgba(17, 19, 24, 0.18);
    border-radius: 9px;
}

QFrame#WizardSubCell:hover {
    background-color: #ffffff;
    border: 1.2px solid #111318;
}

QFrame#WizardDivider {
    background-color: rgba(17, 19, 24, 0.14);
    border: none;
}

QLabel#WizardHeaderTitle {
    color: #111318;
    letter-spacing: 1px;
    text-transform: uppercase;
    background: transparent;
}

QLabel#WizardStepCounter {
    background-color: rgba(17, 19, 24, 0.08);
    color: #111318;
    border: 1px solid rgba(17, 19, 24, 0.22);
    border-radius: 6px;
    padding: 2px 8px;
    letter-spacing: 0.8px;
}

QLabel#WizardSectionTitle {
    color: #111318;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    background: transparent;
}

QLabel#WizardFieldLabel {
    color: #111318;
    letter-spacing: 0.2px;
    background: transparent;
}

QLabel#WizardSubDesc {
    color: #555e6d;
    background: transparent;
}

QLabel#WizardDescText {
    color: #1e232d;
    background: transparent;
}

QLabel#WizardStepBadge {
    background-color: #111318;
    color: #ffffff;
    border: none;
    border-radius: 6px;
}

QLineEdit#WizardInput {
    background-color: #ffffff;
    color: #111318;
    border: 1.5px solid #111318;
    border-radius: 7px;
    padding: 4px 12px;
}

QLineEdit#WizardInput:hover {
    background-color: #ffffff;
    border: 1.5px solid #000000;
}

QLineEdit#WizardInput:focus {
    border: 2px solid #000000;
    background-color: #ffffff;
}

QComboBox#WizardCombo {
    background-color: #ffffff;
    color: #111318;
    border: 1.5px solid #111318;
    border-radius: 7px;
    padding: 4px 28px 4px 12px;
}

QComboBox#WizardCombo:hover {
    background-color: #f4f6fa;
    border: 1.5px solid #000000;
}

QComboBox#WizardCombo:focus {
    border: 2px solid #000000;
}

QComboBox#WizardCombo::drop-down {
    border: none;
    background: transparent;
    width: 0px;
}

QComboBox#WizardCombo::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}

QPushButton#WizardPrimaryBtn {
    background-color: #111318;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 6px 18px;
    letter-spacing: 0.8px;
}

QPushButton#WizardPrimaryBtn:hover {
    background-color: #2b313d;
}

QPushButton#WizardActionBtn {
    background-color: #111318;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 5px 12px;
    letter-spacing: 0.6px;
}

QPushButton#WizardActionBtn:hover {
    background-color: #2b313d;
}

QPushButton#WizardSecondaryBtn {
    background-color: #ffffff;
    color: #111318;
    border: 1.5px solid #111318;
    border-radius: 7px;
    padding: 5px 12px;
    letter-spacing: 0.6px;
}

QPushButton#WizardSecondaryBtn:hover {
    background-color: #111318;
    color: #ffffff;
}

QPushButton#CloseBtn {
    background-color: transparent;
    color: #111318;
    font-size: 13px;
    border-radius: 6px;
    border: none;
}

QPushButton#CloseBtn:hover {
    background-color: #e53935;
    color: #ffffff;
}
"""


def get_wizard_style(theme="dark"):
    base = get_main_style(theme)
    extra = WIZARD_LIGHT_EXTRA if theme == "light" else WIZARD_DARK_EXTRA
    return base + "\n" + extra


class WizardBackground(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.border_phase = 0.0
        self.current_theme = "dark"

        self.stars = []
        for _ in range(50):
            self.stars.append({
                'rx': random.uniform(0.01, 0.99),
                'ry': random.uniform(0.01, 0.99),
                'size': random.uniform(0.6, 1.3),
                'phase': random.uniform(0, math.pi * 2),
                'speed': random.uniform(0.015, 0.035)
            })

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_bg)
        self.timer.start(25)

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update()

    def animate_bg(self):
        self.border_phase += 0.010
        for star in self.stars:
            star['phase'] += star['speed']
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), 14, 14)

        if self.current_theme == "light":
            bg_grad = QLinearGradient(0, 0, w, h)
            bg_grad.setColorAt(0.0, QColor(234, 238, 245, 240))
            bg_grad.setColorAt(0.5, QColor(222, 228, 238, 245))
            bg_grad.setColorAt(1.0, QColor(208, 217, 230, 248))
            painter.fillPath(clip_path, bg_grad)
        else:
            painter.fillPath(clip_path, QColor(6, 6, 4, 250))

        painter.setClipPath(clip_path)

        for star in self.stars:
            sx = star['rx'] * w
            sy = star['ry'] * h
            twinkle = (math.sin(star['phase']) + 1) / 2

            painter.setPen(Qt.PenStyle.NoPen)
            if self.current_theme == "light":
                alpha = int(25 + twinkle * 120)
                star_col = QColor(17, 19, 24, alpha)
            else:
                alpha = int(25 + twinkle * 180)
                star_col = QColor(222, 215, 196, alpha)

            painter.setBrush(QBrush(star_col))
            painter.drawEllipse(QRectF(sx - star['size'], sy - star['size'], star['size'] * 2, star['size'] * 2))

        cx, cy = w / 2, h / 2
        dx = math.cos(self.border_phase) * w
        dy = math.sin(self.border_phase) * h

        border_grad = QLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
        if self.current_theme == "light":
            border_width = 1.6
            border_grad.setColorAt(0.0, QColor(17, 19, 24, 75))
            border_grad.setColorAt(0.35, QColor(17, 19, 24, 185))
            border_grad.setColorAt(0.5, QColor(17, 19, 24, 255))
            border_grad.setColorAt(0.65, QColor(17, 19, 24, 185))
            border_grad.setColorAt(1.0, QColor(17, 19, 24, 75))
        else:
            border_width = 1.2
            border_grad.setColorAt(0.0, QColor("#141310"))
            border_grad.setColorAt(0.35, QColor("#38352b"))
            border_grad.setColorAt(0.5, QColor("#78735f"))
            border_grad.setColorAt(0.65, QColor("#38352b"))
            border_grad.setColorAt(1.0, QColor("#141310"))

        painter.setPen(QPen(QBrush(border_grad), border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.6, 0.6, w - 1.2, h - 1.2), 14, 14)


class StepIndicator(QWidget):
    def __init__(self, total_steps=4, current_step=0, font_family="Arial", parent=None):
        super().__init__(parent)
        self.total_steps = total_steps
        self.current_step = current_step
        self.font_family = font_family
        self._visual_pos = float(current_step)
        self.current_theme = "dark"
        self.step_labels = ["01 ПРОФИЛЬ", "02 ИНТЕЛЛЕКТ", "03 СЕНСОРЫ", "04 ЗАПУСК"]
        self.setFixedHeight(44)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(360)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._on_anim_step)

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update()

    def _on_anim_step(self, val):
        self._visual_pos = float(val)
        self.update()

    def set_step(self, step):
        self.current_step = step
        self._anim.stop()
        self._anim.setStartValue(self._visual_pos)
        self._anim.setEndValue(float(step))
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        spacing = 135.0
        start_x = (self.width() - (self.total_steps - 1) * spacing) / 2.0
        cy = 13.0

        end_x = start_x + (self.total_steps - 1) * spacing
        inactive_line_col = QColor(17, 19, 24, 40) if self.current_theme == "light" else QColor(55, 51, 42, 150)
        painter.setPen(QPen(inactive_line_col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(int(start_x), int(cy), int(end_x), int(cy))

        current_orb_x = start_x + self._visual_pos * spacing
        if current_orb_x > start_x:
            active_line_col = QColor("#111318") if self.current_theme == "light" else QColor("#ded7c4")
            painter.setPen(QPen(active_line_col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(start_x), int(cy), int(current_orb_x), int(cy))

        painter.setFont(QFont(self.font_family, 8))

        for i in range(self.total_steps):
            cx = start_x + i * spacing
            is_passed = i <= self._visual_pos + 0.05
            is_active = abs(i - self._visual_pos) < 0.45

            if self.current_theme == "light":
                node_col = QColor("#111318") if is_passed else QColor(218, 224, 233)
                border_col = QColor("#111318") if is_passed else QColor(170, 178, 192)
                text_col = QColor("#111318") if is_active else (QColor("#333a48") if is_passed else QColor("#7a8494"))
            else:
                node_col = QColor("#9e9780") if is_passed else QColor(24, 22, 18)
                border_col = QColor("#ded7c4") if is_passed else QColor(65, 60, 48)
                text_col = QColor("#fffde7") if is_active else (QColor("#ded7c4") if is_passed else QColor(120, 115, 95, 160))

            painter.setPen(QPen(border_col, 1.0))
            painter.setBrush(QBrush(node_col))
            painter.drawEllipse(QPointF(cx, cy), 3.8, 3.8)

            if i < len(self.step_labels):
                painter.setPen(text_col)
                lbl_rect = QRectF(cx - 58, cy + 9, 116, 18)
                painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, self.step_labels[i])

        halo = QRadialGradient(current_orb_x, cy, 13)
        if self.current_theme == "light":
            halo.setColorAt(0.0, QColor(17, 19, 24, 70))
            halo.setColorAt(0.6, QColor(17, 19, 24, 20))
            halo.setColorAt(1.0, QColor(17, 19, 24, 0))
        else:
            halo.setColorAt(0.0, QColor(222, 215, 196, 140))
            halo.setColorAt(0.6, QColor(222, 215, 196, 30))
            halo.setColorAt(1.0, QColor(222, 215, 196, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QPointF(current_orb_x, cy), 13, 13)

        core_grad = QLinearGradient(current_orb_x - 5, cy - 5, current_orb_x + 5, cy + 5)
        if self.current_theme == "light":
            core_grad.setColorAt(0.0, QColor("#ffffff"))
            core_grad.setColorAt(0.6, QColor("#2b313d"))
            core_grad.setColorAt(1.0, QColor("#111318"))
            border_core = QColor("#111318")
        else:
            core_grad.setColorAt(0.0, QColor("#ffffff"))
            core_grad.setColorAt(0.6, QColor("#ded7c4"))
            core_grad.setColorAt(1.0, QColor("#78735f"))
            border_core = QColor("#ffffff")

        painter.setPen(QPen(border_core, 1.0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPointF(current_orb_x, cy), 5.2, 5.2)


class ThemeRevealOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.old_pixmap = None
        self.radius = 0.0
        self.center_pt = QPointF(0, 0)
        self.max_radius = 1.0

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(420)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._on_anim_step)
        self.anim.finished.connect(self._on_anim_finished)
        self.hide()

    def start_reveal(self, old_pixmap: QPixmap, center: QPoint):
        self.old_pixmap = old_pixmap
        self.center_pt = QPointF(center)
        w, h = self.parent().width(), self.parent().height()
        self.setGeometry(0, 0, w, h)

        corners = [QPointF(0, 0), QPointF(w, 0), QPointF(0, h), QPointF(w, h)]
        self.max_radius = max(math.hypot(c.x() - self.center_pt.x(), c.y() - self.center_pt.y()) for c in corners) + 20.0

        self.radius = 0.0
        self.show()
        self.raise_()

        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(self.max_radius)
        self.anim.start()

    def _on_anim_step(self, val):
        self.radius = float(val)
        self.update()

    def _on_anim_finished(self):
        self.hide()
        self.old_pixmap = None

    def paintEvent(self, event):
        if not self.old_pixmap or self.radius >= self.max_radius:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 14, 14)
        path.addEllipse(self.center_pt, self.radius, self.radius)

        painter.setClipPath(path)
        painter.drawPixmap(self.rect(), self.old_pixmap)


class OnboardingWizard(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.drag_position = QPoint()
        self.current_theme = self.config.get("theme", "dark").lower() if isinstance(self.config, dict) else "dark"

        self._init_window_icon()
        self.setWindowTitle("Akira")

        from gui.ui_helpers import get_ui_fallback_font
        font_path = get_resource_path("assets", "fonts", "Arian_normal.otf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            self.font_family = families[0] if families else get_ui_fallback_font()
        else:
            self.font_family = get_ui_fallback_font()

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(660, 580)

        self.init_ui()
        self.apply_theme(self.current_theme, initial=True)

    def _init_window_icon(self):
        ico_path = get_resource_path("assets", "icon", "ico", "akira_icon.ico")
        png_path = get_resource_path("assets", "icon", "png", "akira_icon.png")

        app_icon = None
        if sys.platform == "win32":
            if os.path.exists(ico_path):
                app_icon = QIcon(ico_path)
            elif os.path.exists(png_path):
                app_icon = QIcon(png_path)
        else:
            if os.path.exists(png_path):
                app_icon = QIcon(png_path)
            elif os.path.exists(ico_path):
                app_icon = QIcon(ico_path)

        if app_icon and not app_icon.isNull():
            self.setWindowIcon(app_icon)

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.bg = WizardBackground(self)
        bg_layout = QVBoxLayout(self.bg)
        bg_layout.setContentsMargins(24, 18, 24, 18)
        bg_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        self.header_title = QLabel("ИНИЦИАЛИЗАЦИЯ // СИСТЕМА АКИРА")
        self.header_title.setObjectName("WizardHeaderTitle")
        self.header_title.setFont(QFont(self.font_family, 11))
        header_layout.addWidget(self.header_title)

        self.step_counter_lbl = QLabel("ШАГ 1 / 4")
        self.step_counter_lbl.setObjectName("WizardStepCounter")
        self.step_counter_lbl.setFont(QFont(self.font_family, 8))
        header_layout.addWidget(self.step_counter_lbl)

        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        bg_layout.addLayout(header_layout)

        top_divider = QFrame()
        top_divider.setObjectName("WizardDivider")
        top_divider.setFixedHeight(1)
        bg_layout.addWidget(top_divider)

        self.step_indicator = StepIndicator(total_steps=4, current_step=0, font_family=self.font_family)
        bg_layout.addWidget(self.step_indicator)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent; border: none;")

        self.step1_widget = self._create_step1()
        self.step2_widget = self._create_step2()
        self.step3_widget = self._create_step3()
        self.step4_widget = self._create_step4()

        self.stack.addWidget(self.step1_widget)
        self.stack.addWidget(self.step2_widget)
        self.stack.addWidget(self.step3_widget)
        self.stack.addWidget(self.step4_widget)

        bg_layout.addWidget(self.stack, 1)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 0)

        self.back_btn = QPushButton("← НАЗАД")
        self.back_btn.setObjectName("WizardSecondaryBtn")
        self.back_btn.setFont(QFont(self.font_family, 10))
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setFixedSize(120, 34)
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.hide()
        btn_row.addWidget(self.back_btn)

        btn_row.addStretch()

        self.next_btn = QPushButton("ДАЛЕЕ →")
        self.next_btn.setObjectName("WizardPrimaryBtn")
        self.next_btn.setFont(QFont(self.font_family, 10))
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFixedSize(145, 34)
        self.next_btn.clicked.connect(self._go_next)
        btn_row.addWidget(self.next_btn)

        bg_layout.addLayout(btn_row)
        root_layout.addWidget(self.bg)

        self.theme_overlay = ThemeRevealOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'theme_overlay'):
            self.theme_overlay.setGeometry(self.rect())

    def _style_combo_view(self, combo: NoScrollComboBox, theme: str):
        if combo is None or combo.view() is None:
            return

        if theme == "light":
            combo.view().setStyleSheet("""
                QListView {
                    background-color: #ffffff;
                    color: #111318;
                    selection-background-color: #e2e8f0;
                    selection-color: #000000;
                    border: 1.5px solid #111318;
                    border-radius: 7px;
                    padding: 3px;
                    outline: none;
                    font-size: 11px;
                }
                QListView::item {
                    min-height: 24px;
                    padding: 3px 10px;
                    color: #111318;
                    border-radius: 5px;
                }
                QListView::item:hover, QListView::item:selected {
                    background-color: #e2e8f0;
                    color: #000000;
                }
            """)
        else:
            combo.view().setStyleSheet("""
                QListView {
                    background-color: #12110d;
                    color: #ded7c4;
                    selection-background-color: #2b2820;
                    selection-color: #ffffff;
                    border: 1px solid #78735f;
                    border-radius: 7px;
                    padding: 3px;
                    outline: none;
                    font-size: 11px;
                }
                QListView::item {
                    min-height: 24px;
                    padding: 3px 10px;
                    color: #ded7c4;
                    border-radius: 5px;
                }
                QListView::item:hover, QListView::item:selected {
                    background-color: #2b2820;
                    color: #ffffff;
                }
            """)

    def apply_theme(self, theme: str, initial: bool = False):
        if not initial and hasattr(self, 'theme_overlay'):
            old_pixmap = self.grab()
            if hasattr(self, 'theme_combo') and self.theme_combo.isVisible():
                center = self.theme_combo.mapTo(self, self.theme_combo.rect().center())
            else:
                center = QPoint(self.width() // 2, self.height() // 2)

        self.current_theme = theme
        self.setStyleSheet(get_wizard_style(theme))

        if hasattr(self, 'bg'):
            self.bg.set_theme(theme)
        if hasattr(self, 'step_indicator'):
            self.step_indicator.set_theme(theme)

        for combo in (getattr(self, 'theme_combo', None), getattr(self, 'gender_combo', None)):
            if combo is not None:
                combo.set_theme(theme)
                self._style_combo_view(combo, theme)

        for tog in (getattr(self, 'face_toggle', None), getattr(self, 'gest_toggle', None), getattr(self, 'eye_toggle', None), getattr(self, 'auto_toggle', None)):
            if tog is not None:
                tog.set_theme(theme)

        if hasattr(self, 'lbl_giga_status'):
            c = "#111318" if theme == "light" else "#ded7c4"
            self.lbl_giga_status.setStyleSheet(f"color: {c}; background: transparent;")

        if hasattr(self, '_rebuild_step4_cards'):
            self._rebuild_step4_cards()

        if enable_window_acrylic:
            try:
                tint = "20E8EEF5" if theme == "light" else "25080805"
                enable_window_acrylic(int(self.winId()), tint)
            except Exception:
                pass

        self.update()

        if not initial and hasattr(self, 'theme_overlay'):
            self.theme_overlay.start_reveal(old_pixmap, center)

    def _on_theme_changed(self, index):
        new_theme = self.theme_combo.currentData()
        if new_theme and new_theme != self.current_theme:
            self.apply_theme(new_theme)

    def _create_card(self, title_text=""):
        card = QFrame()
        card.setObjectName("WizardCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        if title_text:
            lbl = QLabel(title_text)
            lbl.setObjectName("WizardSectionTitle")
            lbl.setFont(QFont(self.font_family, 9))
            layout.addWidget(lbl)

            div = QFrame()
            div.setObjectName("WizardDivider")
            div.setFixedHeight(1)
            layout.addWidget(div)

        return card, layout

    def _make_sub_cell(self, padding=(12, 9, 12, 9), spacing=8):
        cell = QFrame()
        cell.setObjectName("WizardSubCell")
        row = QHBoxLayout(cell)
        row.setContentsMargins(*padding)
        row.setSpacing(spacing)
        return cell, row

    def _create_step1(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(10)

        desc = QLabel(
            "Выбери комфортное оформление интерфейса и укажи своё имя, чтобы Акира правильно обращалась к тебе в диалоге."
        )
        desc.setObjectName("WizardDescText")
        desc.setFont(QFont(self.font_family, 10))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        card, card_layout = self._create_card("ОФОРМЛЕНИЕ И ПРОФИЛЬ")

        cell_theme, row_theme = self._make_sub_cell()
        col_theme = QVBoxLayout()
        col_theme.setSpacing(1)
        lbl_theme = QLabel("Тема оформления")
        lbl_theme.setObjectName("WizardFieldLabel")
        lbl_theme.setFont(QFont(self.font_family, 10))
        sub_theme = QLabel("Тёмная ночь или светлый шёлковый фарфор")
        sub_theme.setObjectName("WizardSubDesc")
        sub_theme.setFont(QFont(self.font_family, 8))
        col_theme.addWidget(lbl_theme)
        col_theme.addWidget(sub_theme)
        row_theme.addLayout(col_theme)
        row_theme.addStretch()

        self.theme_combo = NoScrollComboBox()
        self.theme_combo.setObjectName("WizardCombo")
        self.theme_combo.setFont(QFont(self.font_family, 10))
        self.theme_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_combo.addItem("Тёмная", "dark")
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.setFixedSize(185, 32)
        idx_t = self.theme_combo.findData(self.current_theme)
        if idx_t != -1:
            self.theme_combo.setCurrentIndex(idx_t)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        row_theme.addWidget(self.theme_combo)
        card_layout.addWidget(cell_theme)

        cell_name, row_name = self._make_sub_cell()
        col_name = QVBoxLayout()
        col_name.setSpacing(1)
        lbl_name = QLabel("Имя пользователя")
        lbl_name.setObjectName("WizardFieldLabel")
        lbl_name.setFont(QFont(self.font_family, 10))
        sub_name = QLabel("Как Акира будет обращаться к тебе")
        sub_name.setObjectName("WizardSubDesc")
        sub_name.setFont(QFont(self.font_family, 8))
        col_name.addWidget(lbl_name)
        col_name.addWidget(sub_name)
        row_name.addLayout(col_name)
        row_name.addStretch()

        self.name_input = QLineEdit()
        self.name_input.setObjectName("WizardInput")
        self.name_input.setFont(QFont(self.font_family, 10))
        self.name_input.setText(self.config.get("user_name", "") if isinstance(self.config, dict) else "")
        self.name_input.setPlaceholderText("Например: Светозар...")
        self.name_input.setFixedSize(185, 32)
        row_name.addWidget(self.name_input)
        card_layout.addWidget(cell_name)

        cell_gender, row_gender = self._make_sub_cell()
        col_gender = QVBoxLayout()
        col_gender.setSpacing(1)
        lbl_gender = QLabel("Пол")
        lbl_gender.setObjectName("WizardFieldLabel")
        lbl_gender.setFont(QFont(self.font_family, 10))
        sub_gender = QLabel("Для корректных окончаний в речи")
        sub_gender.setObjectName("WizardSubDesc")
        sub_gender.setFont(QFont(self.font_family, 8))
        col_gender.addWidget(lbl_gender)
        col_gender.addWidget(sub_gender)
        row_gender.addLayout(col_gender)
        row_gender.addStretch()

        self.gender_combo = NoScrollComboBox()
        self.gender_combo.setObjectName("WizardCombo")
        self.gender_combo.setFont(QFont(self.font_family, 10))
        self.gender_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gender_combo.addItem("Мужской", "male")
        self.gender_combo.addItem("Женский", "female")
        self.gender_combo.setFixedSize(185, 32)
        saved_gender = self.config.get("user_gender", "male") if isinstance(self.config, dict) else "male"
        idx_g = self.gender_combo.findData(saved_gender)
        if idx_g != -1:
            self.gender_combo.setCurrentIndex(idx_g)
        row_gender.addWidget(self.gender_combo)
        card_layout.addWidget(cell_gender)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _create_step2(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(10)

        desc = QLabel(
            "Подключи ключ GigaChat API для живого диалога и долговременной памяти. "
            "Медиа-плеер, YouTube и прогноз погоды работают автономно без ключей."
        )
        desc.setObjectName("WizardDescText")
        desc.setFont(QFont(self.font_family, 10))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        card, card_layout = self._create_card("НЕЙРОСЕТЕВОЙ ИНТЕЛЛЕКТ (GIGACHAT)")

        cell_key = QFrame()
        cell_key.setObjectName("WizardSubCell")
        cell_key_l = QVBoxLayout(cell_key)
        cell_key_l.setContentsMargins(12, 10, 12, 10)
        cell_key_l.setSpacing(8)

        row_head = QHBoxLayout()
        row_head.setSpacing(6)
        lbl_giga = QLabel("Client Secret (Base64)")
        lbl_giga.setObjectName("WizardFieldLabel")
        lbl_giga.setFont(QFont(self.font_family, 10))
        row_head.addWidget(lbl_giga)
        row_head.addStretch()

        btn_portal = QPushButton("ПОРТАЛ SBER")
        btn_portal.setObjectName("WizardSecondaryBtn")
        btn_portal.setFixedHeight(26)
        btn_portal.setFont(QFont(self.font_family, 8))
        btn_portal.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_portal.clicked.connect(lambda: webbrowser.open("https://developers.sber.ru/studio/workspaces"))
        row_head.addWidget(btn_portal)

        btn_paste = QPushButton("ВСТАВИТЬ")
        btn_paste.setObjectName("WizardActionBtn")
        btn_paste.setFixedHeight(26)
        btn_paste.setFont(QFont(self.font_family, 8))
        btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_paste.clicked.connect(self._paste_giga_token)
        row_head.addWidget(btn_paste)
        cell_key_l.addLayout(row_head)

        from gui.ui_helpers import get_monospace_font
        self.giga_input = QLineEdit()
        self.giga_input.setObjectName("WizardInput")
        self.giga_input.setFont(get_monospace_font(10))
        initial_key = self.config.get("api_keys", {}).get("gigachat", "") if isinstance(self.config, dict) else ""
        self.giga_input.setText(initial_key)
        self.giga_input.setPlaceholderText("Вставь строку авторизационных данных Base64...")
        self.giga_input.setFixedHeight(34)
        cell_key_l.addWidget(self.giga_input)

        self.lbl_giga_status = QLabel("")
        self.lbl_giga_status.setFont(QFont(self.font_family, 8))
        self.lbl_giga_status.hide()
        cell_key_l.addWidget(self.lbl_giga_status)

        card_layout.addWidget(cell_key)

        cell_hint, row_hint = self._make_sub_cell(padding=(12, 9, 12, 9), spacing=10)
        badge_info = QLabel("INFO")
        badge_info.setObjectName("WizardStepBadge")
        badge_info.setFont(QFont(self.font_family, 8))
        badge_info.setFixedSize(36, 20)
        badge_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_hint.addWidget(badge_info, 0, Qt.AlignmentFlag.AlignTop)

        self.step2_hint = QLabel(
            "Этот шаг можно пропустить — подключить GigaChat или модели RouterAI (DeepSeek, Gemini Neon, Gemini Carbon) "
            "можно в любой момент в параметрах системы."
        )
        self.step2_hint.setObjectName("WizardSubDesc")
        self.step2_hint.setFont(QFont(self.font_family, 9))
        self.step2_hint.setWordWrap(True)
        row_hint.addWidget(self.step2_hint, 1)
        card_layout.addWidget(cell_hint)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _paste_giga_token(self):
        clip = QApplication.clipboard().text().strip()
        if clip:
            self.giga_input.setText(clip)
            self.lbl_giga_status.setText("✓ ТОКЕН ВСТАВЛЕН ИЗ БУФЕРА ОБМЕНА")
            self.lbl_giga_status.show()
            QTimer.singleShot(1800, self.lbl_giga_status.hide)

    def _create_step3(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(10)

        desc = QLabel("Настрой биометрические модули компьютерного зрения и системные параметры Акиры.")
        desc.setObjectName("WizardDescText")
        desc.setFont(QFont(self.font_family, 10))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        card, card_layout = self._create_card("МОДУЛИ И СЕНСОРЫ")
        mods = self.config.get("modules", {}) if isinstance(self.config, dict) else {}

        # 1. Полноширинная Bento-ячейка Face ID с кнопками базы снимков
        cell_face = QFrame()
        cell_face.setObjectName("WizardSubCell")
        cell_face_l = QVBoxLayout(cell_face)
        cell_face_l.setContentsMargins(12, 9, 12, 9)
        cell_face_l.setSpacing(8)

        row_face_top = QHBoxLayout()
        col_face_lbl = QVBoxLayout()
        col_face_lbl.setSpacing(1)
        lbl_face = QLabel("Face ID (Распознавание владельца)")
        lbl_face.setObjectName("WizardFieldLabel")
        lbl_face.setFont(QFont(self.font_family, 10))
        sub_face = QLabel("Биометрическая идентификация по веб-камере")
        sub_face.setObjectName("WizardSubDesc")
        sub_face.setFont(QFont(self.font_family, 8))
        col_face_lbl.addWidget(lbl_face)
        col_face_lbl.addWidget(sub_face)
        row_face_top.addLayout(col_face_lbl)
        row_face_top.addStretch()

        self.face_toggle = ModernToggle(checked=mods.get("face_recognition", False))
        row_face_top.addWidget(self.face_toggle)
        cell_face_l.addLayout(row_face_top)

        row_face_btns = QHBoxLayout()
        row_face_btns.setSpacing(8)

        self.btn_manage_faces = QPushButton("БАЗА ФОТО (0)")
        self.btn_manage_faces.setObjectName("WizardActionBtn")
        self.btn_manage_faces.setFixedHeight(26)
        self.btn_manage_faces.setFont(QFont(self.font_family, 8))
        self.btn_manage_faces.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_manage_faces.clicked.connect(self._open_face_manager)
        row_face_btns.addWidget(self.btn_manage_faces, 1)

        self.btn_add_face = QPushButton("+ ДОБАВИТЬ СНИМОК")
        self.btn_add_face.setObjectName("WizardSecondaryBtn")
        self.btn_add_face.setFixedHeight(26)
        self.btn_add_face.setFont(QFont(self.font_family, 8))
        self.btn_add_face.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_face.clicked.connect(self._add_owner_face)
        row_face_btns.addWidget(self.btn_add_face, 1)

        cell_face_l.addLayout(row_face_btns)
        card_layout.addWidget(cell_face)

        # 2. Bento-сетка 2x2 для остальных сенсоров и параметров
        grid = QGridLayout()
        grid.setSpacing(8)

        def _make_toggle_cell(title_text, sub_text, checked_val, right_pad=11):
            c, r = self._make_sub_cell(padding=(11, 8, right_pad, 8), spacing=6)
            col = QVBoxLayout()
            col.setSpacing(1)
            lbl = QLabel(title_text)
            lbl.setObjectName("WizardFieldLabel")
            lbl.setFont(QFont(self.font_family, 9))
            sub = QLabel(sub_text)
            sub.setObjectName("WizardSubDesc")
            sub.setFont(QFont(self.font_family, 8))
            col.addWidget(lbl)
            col.addWidget(sub)
            r.addLayout(col, 1)
            tog = ModernToggle(checked=checked_val)
            r.addWidget(tog)
            return c, tog

        cell_gest, self.gest_toggle = _make_toggle_cell(
            "Жесты рук", "Блокировка и пауза", mods.get("gestures", False)
        )
        cell_eye, self.eye_toggle = _make_toggle_cell(
            "Трекинг глаз", "Контроль усталости", mods.get("eye_tracking", False)
        )
        cell_auto, self.auto_toggle = _make_toggle_cell(
            "Автозапуск", "Автоматический запуск вместе с системой",
            self.config.get("autostart", False) if isinstance(self.config, dict) else False,
            right_pad=26
        )

        grid.addWidget(cell_gest, 0, 0)
        grid.addWidget(cell_eye, 0, 1)
        grid.addWidget(cell_auto, 1, 0, 1, 2)

        card_layout.addLayout(grid)
        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _open_face_manager(self):
        from gui.dialogs.face_manager_dialog import FaceManagerDialog
        dialog = FaceManagerDialog(font_family=self.font_family, parent=self, theme=self.current_theme)
        dialog.exec()
        self._update_face_count_btn()

    def _update_face_count_btn(self):
        face_dir = os.path.normpath(get_user_data_path("owner_face"))
        count = 0
        if os.path.exists(face_dir):
            valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
            count = len([f for f in os.listdir(face_dir) if f.lower().endswith(valid_exts)])
        self.btn_manage_faces.setText(f"БАЗА ФОТО ({count})")

    def _add_owner_face(self):
        files = open_files_dialog(self, "Выбор фотографий владельца", "", "Images (*.png *.jpg *.jpeg)")
        if files:
            face_dir = os.path.normpath(get_user_data_path("owner_face"))
            os.makedirs(face_dir, exist_ok=True)
            for f in files:
                try:
                    shutil.copy(f, os.path.join(face_dir, os.path.basename(f)))
                except Exception:
                    pass
            self._update_face_count_btn()

    def _create_step4(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(10)

        card, card_layout = self._create_card("СИСТЕМА ГОТОВА К РАБОТЕ")
        self._step4_card_layout = card_layout

        self.step4_title = QLabel("КАЛИБРОВКА ЗАВЕРШЕНА")
        self.step4_title.setObjectName("WizardHeaderTitle")
        self.step4_title.setFont(QFont(self.font_family, 13))
        card_layout.addWidget(self.step4_title)

        sub_intro = QLabel("Акира успешно интегрирована в систему и готова к выполнению команд:")
        sub_intro.setObjectName("WizardSubDesc")
        sub_intro.setFont(QFont(self.font_family, 9))
        card_layout.addWidget(sub_intro)

        self._step4_tips_container = QVBoxLayout()
        self._step4_tips_container.setSpacing(8)
        card_layout.addLayout(self._step4_tips_container)

        self._rebuild_step4_cards()

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _rebuild_step4_cards(self):
        if not hasattr(self, '_step4_tips_container'):
            return

        while self._step4_tips_container.count():
            item = self._step4_tips_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        is_light = self.current_theme == "light"
        hl_bg = "rgba(17, 19, 24, 0.07)" if is_light else "rgba(222, 215, 196, 0.12)"
        hl_fg = "#000000" if is_light else "#ffffff"
        text_col = "#111318" if is_light else "#fffde7"

        def _hl(word):
            return f'<span style="background-color: {hl_bg}; color: {hl_fg};">{word}</span>'

        tips = [
            ("01", f"Кликни по ядру микрофона или обратись по имени {_hl('«Акира»')}, чтобы отдать голосовую команду."),
            ("02", f"В параметрах системы можно подключить {_hl('Яндекс Музыку')}, {_hl('Spotify')}, {_hl('Дом с Алисой')} и {_hl('Telegram Remote')}."),
            ("03", f"Сценарии быстрого запуска {_hl('«Работа»')} и {_hl('«Отдых»')} настраиваются в дашборде профилей."),
        ]

        for num, rich_html in tips:
            tip_cell, tip_row = self._make_sub_cell(padding=(11, 9, 12, 9), spacing=10)

            badge = QLabel(num)
            badge.setObjectName("WizardStepBadge")
            badge.setFont(QFont(self.font_family, 9))
            badge.setFixedSize(24, 22)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tip_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

            lbl = QLabel()
            lbl.setFont(QFont(self.font_family, 10))
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setText(f'<div style="line-height: 142%;">{rich_html}</div>')
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {text_col}; background: transparent; border: none;")
            tip_row.addWidget(lbl, 1)

            self._step4_tips_container.addWidget(tip_cell)

    def _save_current_data(self):
        cfg = load_config()
        if "api_keys" not in cfg or not isinstance(cfg["api_keys"], dict):
            cfg["api_keys"] = {}
        if "modules" not in cfg or not isinstance(cfg["modules"], dict):
            cfg["modules"] = {}

        cfg["theme"] = self.theme_combo.currentData()
        cfg["user_name"] = self.name_input.text().strip() or "друг"
        cfg["user_gender"] = self.gender_combo.currentData()

        giga_key = self.giga_input.text().strip()
        cfg["api_keys"]["gigachat"] = giga_key
        cfg["modules"]["gigachat"] = bool(giga_key)

        face_on = self.face_toggle.isChecked()
        gest_on = self.gest_toggle.isChecked()
        eye_on = self.eye_toggle.isChecked()

        cfg["modules"]["face_recognition"] = face_on
        cfg["modules"]["gestures"] = gest_on
        cfg["modules"]["eye_tracking"] = eye_on
        cfg["modules"]["vision"] = face_on or gest_on or eye_on
        cfg["autostart"] = self.auto_toggle.isChecked()

        cfg["first_run"] = False
        cfg["is_configured"] = True
        save_config(cfg)
        self.config = cfg

    def _go_next(self):
        cur_idx = self.stack.currentIndex()
        if cur_idx < self.stack.count() - 1:
            self._save_current_data()
            next_idx = cur_idx + 1
            self.stack.setCurrentIndex(next_idx)
            self.step_indicator.set_step(next_idx)
            self.step_counter_lbl.setText(f"ШАГ {next_idx + 1} / 4")
            self.back_btn.show()

            if next_idx == 2:
                self._update_face_count_btn()

            if next_idx == self.stack.count() - 1:
                self.next_btn.setText("ЗАВЕРШИТЬ ✓")
        else:
            self._save_current_data()
            self.accept()

    def _go_back(self):
        cur_idx = self.stack.currentIndex()
        if cur_idx > 0:
            next_idx = cur_idx - 1
            self.stack.setCurrentIndex(next_idx)
            self.step_indicator.set_step(next_idx)
            self.step_counter_lbl.setText(f"ШАГ {next_idx + 1} / 4")
            self.next_btn.setText("ДАЛЕЕ →")
            if next_idx == 0:
                self.back_btn.hide()

    def mousePressEvent(self, event):
        if handle_drag_press(self, event):
            event.accept()

    def mouseMoveEvent(self, event):
        if handle_drag_move(self, event):
            event.accept()

    def mouseReleaseEvent(self, event):
        if handle_drag_release(self, event):
            event.accept()