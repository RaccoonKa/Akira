import os
import math
import random
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit
from PyQt6.QtCore import Qt, QPoint, QRectF, QTimer, QVariantAnimation, QEasingCurve, pyqtSignal, QSize, QByteArray, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QLinearGradient, QRadialGradient, QBrush, QPainterPath, QFont, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from core.utils.config import get_resource_path

try:
    from core.utils.blur import enable_window_acrylic
except ImportError:
    try:
        from gui.utils.blur import enable_window_acrylic
    except ImportError:
        enable_window_acrylic = None

SVG_POWER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>
</svg>"""

SVG_RESTORE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
</svg>"""

def _render_svg_icon(svg_xml: str, color: str, size: int = 15) -> QIcon:
    xml = svg_xml.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(xml.encode("utf-8")))
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)


class AkiraMiniMicWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMouseTracking(True)
        self.setFixedSize(40, 40)

        self.is_processing = False
        self.music_blend = 0.0
        self.current_theme = "dark"
        self.target_fps = 60
        self.speed_mult = 1.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

        self.pulse = 0.0
        self.boost = 0.0
        self.is_listening = False
        self.is_speaking = False
        self.beat_impulse = 0.0
        self.target_impulse = 0.0
        self.music_hue = 45.0
        self.listening_hue = 0.0
        self.music_flow_hue = 0.0
        self.sound_presence = 0.0

        self.dark_palette = {
            "happy": (45.0, 230.0, 255.0),
            "sad": (198.0, 220.0, 255.0),
            "angry": (352.0, 235.0, 255.0),
            "surprise": (280.0, 220.0, 255.0),
            "neutral": (42.0, 45.0, 250.0),
            "other": (280.0, 220.0, 255.0),
        }

        self.light_palette = {
            "happy": (35.0, 235.0, 115.0),
            "sad": (218.0, 220.0, 110.0),
            "angry": (352.0, 230.0, 110.0),
            "surprise": (282.0, 215.0, 100.0),
            "neutral": (215.0, 55.0, 42.0),
            "other": (282.0, 215.0, 100.0),
        }

        self.emotion_palette = self.dark_palette
        self.target_emotion = "neutral"
        self.current_color_hue, self.current_color_sat, self.current_color_val = self.emotion_palette["neutral"]

        self.reset_emotion_timer = QTimer(self)
        self.reset_emotion_timer.setSingleShot(True)
        self.reset_emotion_timer.timeout.connect(self._reset_to_neutral)

        self.intro_progress = 0.0
        self.morph_scale = 1.0
        self.particles = []
        self.total_particles = 90
        self._init_particles()

    def get_orb_center(self) -> QPointF:
        return QPointF(self.width() / 2.0, self.height() / 2.0)

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.emotion_palette = self.light_palette if theme == "light" else self.dark_palette
        if self.target_emotion in self.emotion_palette:
            self.current_color_hue, self.current_color_sat, self.current_color_val = self.emotion_palette[self.target_emotion]
        self.update()

    def set_framerate(self, fps: int):
        self.target_fps = fps
        self.speed_mult = 60.0 / fps
        self.timer.setInterval(max(1, int(1000 / fps)))

    def _init_particles(self):
        self.particles.clear()
        for i in range(self.total_particles):
            r_dist = random.gauss(11, 2.5)
            if r_dist < 5:
                r_dist = 5 + random.uniform(0, 2)
            self.particles.append({
                'r': r_dist,
                'accum_angle': random.uniform(0, math.pi * 2),
                'speed': random.uniform(0.0015, 0.005) * (1 if random.random() > 0.2 else -0.6),
                'x_start': -random.uniform(5, 20),
                'y_start_off': random.gauss(0, 8),
                'p1_x_off': -random.uniform(8, 20),
                'p1_y_off': -random.uniform(6, 15),
                'p2_x_off': random.uniform(6, 15),
                'p2_y_off': random.uniform(4, 10),
                'delay': (i / self.total_particles) * 0.55 + random.uniform(0, 0.04),
                'size': random.uniform(0.5, 1.2),
                'alpha': random.randint(140, 255)
            })

    def start_intro_animation(self, duration=3800):
        self.intro_progress = 0.0
        self._init_particles()
        self.intro_anim = QVariantAnimation(self)
        self.intro_anim.setDuration(duration)
        self.intro_anim.setStartValue(0.0)
        self.intro_anim.setEndValue(1.0)
        self.intro_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.intro_anim.valueChanged.connect(lambda v: (setattr(self, 'intro_progress', float(v)), self.update()))
        self.intro_anim.start()

    def trigger_morph_bloom(self, start_scale: float = 0.30, duration: int = 420):
        self.intro_progress = 1.0
        self.morph_scale = start_scale
        self.morph_anim = QVariantAnimation(self)
        self.morph_anim.setDuration(duration)
        self.morph_anim.setStartValue(start_scale)
        self.morph_anim.setEndValue(1.0)
        self.morph_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.morph_anim.valueChanged.connect(lambda v: (setattr(self, 'morph_scale', float(v)), self.update()))
        self.morph_anim.start()

    def set_listening(self, state: bool):
        self.is_listening = state
        if not state and self.target_emotion == "neutral":
            self.current_color_hue, self.current_color_sat, self.current_color_val = self.emotion_palette["neutral"]

    def set_processing(self, state: bool):
        self.is_processing = state
        if state:
            self.target_impulse = 0.0

    def set_speaking(self, state: bool):
        self.is_speaking = state
        if state:
            self.reset_emotion_timer.stop()
        elif self.target_emotion != "neutral":
            self.reset_emotion_timer.start(5000)

    def set_emotion(self, emotion: str):
        self.target_emotion = emotion if emotion in self.emotion_palette else "neutral"
        self.reset_emotion_timer.stop()
        if self.target_emotion != "neutral" and not self.is_speaking:
            self.reset_emotion_timer.start(5500)

    def _reset_to_neutral(self):
        self.target_emotion = "neutral"

    def trigger_wake_effect(self):
        self.boost = 2.2
        self.target_impulse = 0.6

    def on_audio_data(self, impulse: float, hue: float, is_music: bool):
        if self.is_speaking or self.is_listening or self.is_processing:
            self.target_impulse = 0.0
            return
        if is_music:
            scaled = impulse * self.music_blend
            if scaled > self.target_impulse:
                self.target_impulse = scaled
            self.music_hue = hue
            if impulse > 0.003:
                self.sound_presence = min(1.0, self.sound_presence + 0.12)
        else:
            self.target_impulse = 0.0
            self.sound_presence = max(0.0, self.sound_presence - 0.02)

    def animate(self):
        self.pulse += 0.015 * self.speed_mult
        self.beat_impulse += (self.target_impulse - self.beat_impulse) * 0.05 * self.speed_mult
        self.target_impulse *= math.pow(0.93, self.speed_mult)
        self.sound_presence = max(0.0, self.sound_presence - 0.003 * self.speed_mult)

        if self.is_listening:
            target_boost = 0.15
            self.music_blend = 0.0
        elif self.is_processing:
            target_boost = 1.6
            self.music_blend = 0.0
        elif self.is_speaking:
            target_boost = 1.3 + math.sin(self.pulse * 4.0) * 0.6
            self.music_blend = 0.0
        else:
            target_boost = 0.0
            self.music_blend = min(1.0, self.music_blend + 0.012 * self.speed_mult)

        self.boost += (target_boost - self.boost) * 0.08 * self.speed_mult
        effective_boost = self.boost if (self.is_listening or self.is_processing) else max(self.boost, self.beat_impulse * 2.8)
        self.music_flow_hue = (self.music_flow_hue + 0.20 * self.speed_mult) % 360.0

        if self.is_listening:
            self.listening_hue = (self.listening_hue + 0.9 * self.speed_mult) % 360.0
            target_h = self.listening_hue
            target_s = 220.0
            target_v = 110.0 if self.current_theme == "light" else 255.0
            color_rate = 0.08 * self.speed_mult
        elif self.target_emotion != "neutral":
            target_h, target_s, target_v = self.emotion_palette[self.target_emotion]
            color_rate = 0.045 * self.speed_mult
        elif self.is_processing:
            target_h = 42.0
            target_s = 180.0 if self.current_theme == "light" else 80.0
            target_v = 100.0 if self.current_theme == "light" else 255.0
            color_rate = 0.05 * self.speed_mult
        elif self.sound_presence > 0.05 or (self.beat_impulse > 0.01 and self.music_blend > 0.1):
            target_h = self.music_flow_hue
            if self.current_theme == "light":
                target_s = 220.0
                target_v = 110.0
            else:
                base_s = 45.0
                max_s = 225.0
                target_s = base_s + (max_s - base_s) * min(1.0, self.sound_presence * 1.5)
                target_v = 255.0
            color_rate = 0.035 * self.speed_mult
        else:
            target_h, target_s, target_v = self.emotion_palette["neutral"]
            color_rate = 0.03 * self.speed_mult

        h_diff = (target_h - self.current_color_hue + 180.0) % 360.0 - 180.0
        self.current_color_hue = (self.current_color_hue + h_diff * color_rate) % 360.0
        self.current_color_sat += (target_s - self.current_color_sat) * color_rate
        self.current_color_val += (target_v - self.current_color_val) * color_rate

        for p in self.particles:
            p['accum_angle'] = (p['accum_angle'] + p['speed'] * (1.0 + effective_boost) * self.speed_mult) % (math.pi * 2)
        self.update()

    def _get_bezier_pt(self, p0, p1, p2, p3, t):
        u = 1.0 - t
        tt = t * t
        uu = u * u
        return (
            uu * u * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + tt * t * p3[0],
            uu * u * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + tt * t * p3[1]
        )

    def paintEvent(self, event):
        T = self.intro_progress
        if T <= 0.001:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)

        p_val = math.sin(self.pulse * (2.5 if self.is_speaking else 1.0)) * (0.8 if self.is_speaking else 0.4)
        active_impulse = self.beat_impulse

        base_col = QColor.fromHsv(
            int(self.current_color_hue) % 360,
            int(max(0, min(255, self.current_color_sat))),
            int(max(0, min(255, self.current_color_val)))
        )

        for p in self.particles:
            if T < p['delay']:
                continue
            local_t = min(1.0, (T - p['delay']) / (1.0 - p['delay']))
            u = math.sin(local_t * (math.pi / 2))
            cur_angle = p['accum_angle']
            rad_focus = -3.0 if self.is_processing else 0.0
            target_rad = (p['r'] + rad_focus + p_val + (active_impulse * 5.0)) * self.morph_scale
            target_x = cx + math.cos(cur_angle) * target_rad
            target_y = cy + math.sin(cur_angle) * target_rad

            if u < 1.0:
                p0 = (p['x_start'], cy + p['y_start_off'])
                p1 = (cx + p['p1_x_off'], cy + p['p1_y_off'])
                p2 = (cx + p['p2_x_off'], cy + p['p2_y_off'])
                p3 = (target_x, target_y)
                px, py = self._get_bezier_pt(p0, p1, p2, p3, u)
            else:
                px, py = target_x, target_y

            col = QColor(base_col)
            base_alpha = p['alpha'] * (0.85 if self.boost < 0.6 and active_impulse < 0.01 else 1.0)
            col.setAlpha(int(min(255, base_alpha * min(1.0, local_t * 1.8))))

            painter.setBrush(QBrush(col))
            sz = p['size'] + (active_impulse * 1.0)
            painter.drawEllipse(QRectF(px - sz / 2.0, py - sz / 2.0, sz, sz))

    def mouseMoveEvent(self, event):
        orb_center = self.get_orb_center()
        dist = math.hypot(event.pos().x() - orb_center.x(), event.pos().y() - orb_center.y())
        if dist <= 20:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            orb_center = self.get_orb_center()
            dist = math.hypot(event.pos().x() - orb_center.x(), event.pos().y() - orb_center.y())
            if dist <= 20:
                self.clicked.emit()
                event.accept()
                return
        super().mousePressEvent(event)


class MiniWindow(QWidget):
    message_sent = pyqtSignal(str)
    restore_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    MINI_PLACEHOLDERS = [
        "слушаю...", "команда...", "я на связи...",
        "жду команду...", "что делаем?..", "слушаю тебя...",
        "я рядом...", "наготове...", "готова..."
    ]

    def __init__(self, theme: str = "dark", font_family: str = "Arial"):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(460, 56)
        self.setObjectName("AkiraMiniWindow")

        self.current_theme = theme
        self.font_family = font_family
        self.drag_position = QPoint()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.exit_btn = QPushButton()
        self.exit_btn.setObjectName("TitleBtn")
        self.exit_btn.setFixedSize(28, 28)
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.setToolTip("Закрыть Акиру")
        self.exit_btn.clicked.connect(self.exit_requested.emit)
        layout.addWidget(self.exit_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.restore_btn = QPushButton()
        self.restore_btn.setObjectName("TitleBtn")
        self.restore_btn.setFixedSize(28, 28)
        self.restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_btn.setToolTip("Вернуться в полный режим")
        self.restore_btn.clicked.connect(self.restore_requested.emit)
        layout.addWidget(self.restore_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.mini_mic = AkiraMiniMicWidget(self)
        layout.addWidget(self.mini_mic, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("InputField")
        self.input_field.setFixedHeight(34)
        self.input_field.setFont(QFont(self.font_family, 12))
        self.input_field.returnPressed.connect(self._on_send)
        layout.addWidget(self.input_field, 1, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.send_button = QPushButton()
        self.send_button.setObjectName("AttachBtn")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setFixedSize(30, 30)
        self.send_button.clicked.connect(self._on_send)
        layout.addWidget(self.send_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.randomize_placeholder()
        self.update_icons()

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.mini_mic.set_theme(theme)
        self.update_icons()
        self.update()

    def set_framerate(self, fps: int):
        self.mini_mic.set_framerate(fps)

    def randomize_placeholder(self):
        self.input_field.setPlaceholderText(random.choice(self.MINI_PLACEHOLDERS))

    def update_icons(self):
        icon_color = "#ded7c4" if self.current_theme == "dark" else "#111318"
        self.exit_btn.setIcon(_render_svg_icon(SVG_POWER, icon_color, 15))
        self.restore_btn.setIcon(_render_svg_icon(SVG_RESTORE, icon_color, 15))

        send_name = "send_icon_black.png" if self.current_theme == "light" else "send_icon.png"
        send_path = get_resource_path("assets", "img", send_name)
        if not os.path.exists(send_path):
            send_path = get_resource_path("assets", "img", "send_icon.png")
        self.send_button.setIcon(QIcon(send_path))
        self.send_button.setIconSize(QSize(16, 16))

    def _on_send(self):
        text = self.input_field.text().strip()
        if text:
            self.message_sent.emit(text)

    def set_input_enabled(self, enabled: bool):
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        if enabled:
            self.input_field.setFocus()

    def clear_input(self):
        self.input_field.clear()

    def show_at(self, x: int, y: int):
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def showEvent(self, event):
        super().showEvent(event)
        if enable_window_acrylic:
            try:
                tint = "20E8EEF5" if self.current_theme == "light" else "25080805"
                enable_window_acrylic(int(self.winId()), tint)
            except Exception:
                pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 16, 16)

        if self.current_theme == "light":
            bg_grad = QLinearGradient(0, 0, w, h)
            bg_grad.setColorAt(0.0, QColor(234, 238, 245, 235))
            bg_grad.setColorAt(0.5, QColor(222, 228, 238, 240))
            bg_grad.setColorAt(1.0, QColor(208, 217, 230, 245))
            painter.fillPath(clip_path, bg_grad)
            painter.setPen(QPen(QColor(255, 255, 255, 160), 1.0))
        else:
            painter.fillPath(clip_path, QColor(8, 8, 6, 242))
            painter.setPen(QPen(QColor(222, 215, 196, 40), 1.0))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(clip_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = QPoint()
            event.accept()