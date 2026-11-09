import os
import math
import time
import random
import atexit
import warnings
import datetime
import numpy as np
import psutil
from services.telegram.telegram_bot import TelegramBotThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFrame, QFileDialog, QGridLayout,
    QGraphicsOpacityEffect, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QRectF, QTimer, QPropertyAnimation, QVariantAnimation,
    QEasingCurve, QParallelAnimationGroup, QThread, pyqtSignal, QEvent,
    QSize, QPointF, QByteArray
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QRadialGradient,
    QBrush, QPainterPath, QFont, QFontDatabase, QGuiApplication,
    QIcon, QPixmap, QTextCursor
)
from PyQt6.QtSvg import QSvgRenderer
from gui.styles import get_main_style
from gui.windows.settings_window import SettingsFrame
from gui.windows.studio_frame import StudioFrame
from gui.windows.mini_window import MiniWindow
from audio.stt import STTThread
from audio.tts import TTSThread
from core.nlp.command_parser import CommandParser
from core.system.actions import SystemActions
from core.vision.vision_provider import VisionThread
from core.vision.presence_manager import PresenceManager
from core.utils.config import get_resource_path, load_config, save_config
from core.utils.updater import UpdateCheckerThread
from comtypes import CoInitialize, CoUninitialize
from core.system.volume_ducker import volume_ducker

try:
    from core.utils.blur import enable_window_acrylic
except ImportError:
    try:
        from gui.utils.blur import enable_window_acrylic
    except ImportError:
        try:
            from blur import enable_window_acrylic
        except ImportError:
            enable_window_acrylic = None

warnings.filterwarnings("ignore", message="data discontinuity in recording")

SVG_CLOSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
</svg>"""

SVG_MINIMIZE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"/>
</svg>"""

SVG_POWER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>
</svg>"""

SVG_SETTINGS = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
</svg>"""

SVG_MINI = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
</svg>"""

SVG_RESTORE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
</svg>"""

SVG_CHAT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
</svg>"""

SVG_UPDATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
</svg>"""

SVG_VOLUME = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
</svg>"""

SVG_MUTE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>
</svg>"""

SVG_LOUD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>
</svg>"""

SVG_PAPERCLIP = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
</svg>"""

SVG_STUDIO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="15" y1="3" x2="15" y2="21"/>
</svg>"""

SVG_STUDIO_COLLAPSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="18" height="18" rx="2"/><polyline points="10 9 7 12 10 15"/><polyline points="14 9 17 12 14 15"/>
</svg>"""

def render_svg_icon(svg_xml: str, color: str, size: int = 15) -> QIcon:
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


class EmotionHoverButton(QPushButton):
    """Кнопка плашки с динамической сменой цветов эмоций и эффектом блокировки."""
    def __init__(self, svg_xml: str = "", tooltip: str = "", main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.svg_xml = svg_xml
        self.icon_size = 15
        self._is_denied_animating = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("TitleBtn")
        if tooltip:
            self.setToolTip(tooltip)
        self.update_icon()

    def set_svg(self, svg_xml: str):
        self.svg_xml = svg_xml
        self.update_icon()

    def get_default_color(self) -> str:
        theme = getattr(self.main_window, 'current_theme', 'dark')
        return "#111318" if theme == "light" else "#ded7c4"

    def get_locked_color(self) -> str:
        theme = getattr(self.main_window, 'current_theme', 'dark')
        return "#88909e" if theme == "light" else "#6e6958"

    def get_random_emotion_color(self) -> str:
        theme = getattr(self.main_window, 'current_theme', 'dark')
        if theme == "light":
            h, s, v = random.choice([
                (35.0, 235.0, 115.0),   # happy (янтарный)
                (218.0, 220.0, 110.0),  # sad (лазурный)
                (352.0, 230.0, 110.0),  # angry (рубиновый)
                (282.0, 215.0, 100.0),  # surprise (пурпурный)
                (218.0, 240.0, 120.0),  # weather_rain (синий)
                (38.0, 255.0, 115.0),   # weather_hot (терракотовый)
                (192.0, 210.0, 105.0),  # weather_snow (бирюзовый)
                (282.0, 225.0, 110.0),  # weather_thunder (фиолетовый)
            ])
        else:
            h, s, v = random.choice([
                (45.0, 230.0, 255.0),   # happy (золотой)
                (198.0, 220.0, 255.0),  # sad (голубой)
                (352.0, 235.0, 255.0),  # angry (алый)
                (280.0, 220.0, 255.0),  # surprise (маджента)
                (212.0, 235.0, 255.0),  # weather_rain (аквамарин)
                (45.0, 245.0, 255.0),   # weather_hot (тёплый жёлтый)
                (185.0, 160.0, 255.0),  # weather_snow (ледяной)
                (280.0, 235.0, 255.0),  # weather_thunder (электрик)
            ])
        return QColor.fromHsv(int(h), int(s), int(v)).name()

    def update_icon(self, color: str = None):
        if not self.svg_xml:
            return
        if color is None:
            if self is getattr(self.main_window, 'toggle_chat_btn', None) and getattr(self.main_window, 'window_mode', 'normal') == 'extended':
                color = self.get_locked_color()
            else:
                color = self.get_default_color()
        self.setIcon(render_svg_icon(self.svg_xml, color, self.icon_size))
        self.setIconSize(QSize(self.icon_size, self.icon_size))

    def trigger_denied_effect(self):
        """Эффект запрета: физическое покачивание (shake) и двойное алое мерцание."""
        if self._is_denied_animating:
            return
        self._is_denied_animating = True

        theme = getattr(self.main_window, 'current_theme', 'dark')
        red_col = "#ff3b30" if theme == "dark" else "#d32f2f"
        locked_col = self.get_locked_color()
        orig_pos = self.pos()

        steps = [
            (0,   -3, red_col,    "background-color: rgba(255, 59, 48, 0.28); border-radius: 6px;"),
            (70,   3, red_col,    "background-color: rgba(255, 59, 48, 0.28); border-radius: 6px;"),
            (140, -2, locked_col, "background: transparent; border: none;"),
            (210,  2, red_col,    "background-color: rgba(255, 59, 48, 0.32); border-radius: 6px;"),
            (290,  0, locked_col, "background: transparent; border: none;")
        ]

        for delay, dx, icon_col, bg_style in steps:
            def _apply(d_x=dx, i_c=icon_col, b_s=bg_style):
                self.move(orig_pos.x() + d_x, orig_pos.y())
                self.update_icon(i_c)
                self.setStyleSheet(b_s)
            QTimer.singleShot(delay, _apply)

        def _finish():
            self.move(orig_pos)
            self.setStyleSheet("")
            self.update_icon(locked_col)
            self._is_denied_animating = False

        QTimer.singleShot(360, _finish)

    def enterEvent(self, event):
        if self is getattr(self.main_window, 'toggle_chat_btn', None) and getattr(self.main_window, 'window_mode', 'normal') == 'extended':
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
            theme = getattr(self.main_window, 'current_theme', 'dark')
            col = "#e05555" if theme == "dark" else "#c62828"
            self.update_icon(col)
            super().enterEvent(event)
            return

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        color = self.get_random_emotion_color()
        self.update_icon(color)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self is getattr(self.main_window, 'toggle_chat_btn', None) and getattr(self.main_window, 'window_mode', 'normal') == 'extended':
            self.update_icon(self.get_locked_color())
            super().leaveEvent(event)
            return

        self.update_icon()
        super().leaveEvent(event)
        

class AudioVisualizerWorker(QThread):
    audio_data_signal = pyqtSignal(float, float, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.peak_level = 0.02

    def run(self):
        try:
            CoInitialize()
        except Exception:
            pass

        import soundcard as sc
        warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)

        while self.running:
            try:
                default_speaker = sc.default_speaker()
                if not default_speaker:
                    self.msleep(300)
                    continue

                mic = None
                try:
                    mic = sc.get_microphone(default_speaker.id, include_loopback=True)
                except Exception:
                    mic = None

                if not mic:
                    loopbacks = [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]
                    if loopbacks:
                        matching = [m for m in loopbacks if default_speaker.name in m.name or default_speaker.id == m.id]
                        mic = matching[0] if matching else loopbacks[0]

                if not mic:
                    self.msleep(300)
                    continue

                try:
                    recorder_ctx = mic.recorder(samplerate=None, blocksize=2048)
                except Exception:
                    recorder_ctx = mic.recorder(samplerate=44100, blocksize=2048)

                with recorder_ctx as recorder:
                    while self.running:
                        data = recorder.record(numframes=2048)
                        if not self.running:
                            break

                        samples = data[:, 0] if data.ndim > 1 else data
                        rms = float(np.sqrt(np.mean(samples ** 2)))

                        if rms < 0.002:
                            self.audio_data_signal.emit(0.0, 45.0, False)
                            continue

                        fft_vals = np.abs(np.fft.rfft(samples))
                        bass = float(np.sum(fft_vals[1:15]))

                        raw = rms * 2.2 + bass * 0.0045
                        self.peak_level = max(raw, self.peak_level * 0.985, 0.02)

                        normalized = min(1.0, (raw / self.peak_level) ** 1.35)
                        self.audio_data_signal.emit(normalized, 45.0, True)

            except Exception as e:
                print(f"[Audio Visualizer Error]: {e}")
                self.msleep(300)

        try:
            CoUninitialize()
        except Exception:
            pass

    def stop(self):
        self.running = False
        if self.isRunning():
            self.wait(1000)


class CommandWorker(QThread):
    result_ready = pyqtSignal(object)

    def __init__(self, parser, text, audio_data=None, is_voice=False, attached_file=None, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.text = text
        self.audio_data = audio_data
        self.is_voice = is_voice
        self.attached_file = attached_file

    def run(self):
        response = self.parser.process_command(
            self.text,
            audio_data=self.audio_data,
            is_voice=self.is_voice,
            attached_file=self.attached_file
        )
        self.result_ready.emit(response)


class AkiraMicWidget(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMouseTracking(True)
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
            "weather_rain": (212.0, 235.0, 255.0),
            "weather_hot": (45.0, 245.0, 255.0),
            "weather_snow": (185.0, 160.0, 255.0),
            "weather_thunder": (280.0, 235.0, 255.0),
            "weather_cloudy": (215.0, 60.0, 240.0)
        }

        self.light_palette = {
            "happy": (35.0, 235.0, 115.0),
            "sad": (218.0, 220.0, 110.0),
            "angry": (352.0, 230.0, 110.0),
            "surprise": (282.0, 215.0, 100.0),
            "neutral": (215.0, 55.0, 42.0),
            "other": (282.0, 215.0, 100.0),
            "weather_rain": (218.0, 240.0, 120.0),
            "weather_hot": (38.0, 255.0, 115.0),
            "weather_snow": (192.0, 210.0, 105.0),
            "weather_thunder": (282.0, 225.0, 110.0),
            "weather_cloudy": (215.0, 65.0, 65.0)
        }

        self.emotion_palette = self.dark_palette
        self.target_emotion = "neutral"
        self.current_color_hue, self.current_color_sat, self.current_color_val = self.emotion_palette["neutral"]

        self.reset_emotion_timer = QTimer(self)
        self.reset_emotion_timer.setSingleShot(True)
        self.reset_emotion_timer.timeout.connect(self._reset_to_neutral)

        self.intro_progress = 0.0
        self.particles = []
        self.total_particles = 320
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
        interval = max(1, int(1000 / fps))
        self.timer.setInterval(interval)

    def _init_particles(self):
        self.particles.clear()
        for i in range(self.total_particles):
            r_dist = random.gauss(68, 16)
            if r_dist < 20:
                r_dist = 20 + random.uniform(0, 10)

            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(0.0015, 0.005) * (1 if random.random() > 0.2 else -0.6)

            x_start = -random.uniform(40, 160)
            y_start_off = random.gauss(0, 45)

            p1_x_off = -random.uniform(40, 100)
            p1_y_off = -random.uniform(30, 80)
            p2_x_off = random.uniform(30, 70)
            p2_y_off = random.uniform(20, 50)

            delay = (i / self.total_particles) * 0.55 + random.uniform(0, 0.04)

            self.particles.append({
                'r': r_dist,
                'accum_angle': angle,
                'speed': speed,
                'x_start': x_start,
                'y_start_off': y_start_off,
                'p1_x_off': p1_x_off,
                'p1_y_off': p1_y_off,
                'p2_x_off': p2_x_off,
                'p2_y_off': p2_y_off,
                'delay': delay,
                'size': random.uniform(0.7, 2.0),
                'alpha': random.randint(140, 255)
            })

    def start_intro_animation(self, duration=3800):
        if hasattr(self, 'intro_anim') and self.intro_anim.state() == QVariantAnimation.State.Running:
            self.intro_anim.stop()
        self.intro_progress = 0.0
        self._init_particles()

        self.intro_anim = QVariantAnimation(self)
        self.intro_anim.setDuration(duration)
        self.intro_anim.setStartValue(0.0)
        self.intro_anim.setEndValue(1.0)
        self.intro_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        def _on_val(v):
            self.intro_progress = float(v)
            self.update()

        self.intro_anim.valueChanged.connect(_on_val)
        self.intro_anim.start()

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
        else:
            if self.target_emotion != "neutral":
                self.reset_emotion_timer.start(5000)

    def set_emotion(self, emotion: str):
        self.target_emotion = emotion if emotion in self.emotion_palette else "neutral"
        self.reset_emotion_timer.stop()
        if self.target_emotion != "neutral":
            if not self.is_speaking:
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
            scaled_impulse = impulse * self.music_blend
            if scaled_impulse > self.target_impulse:
                self.target_impulse = scaled_impulse
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

        orb_center = self.get_orb_center()
        cx = orb_center.x()
        cy = orb_center.y()

        p_val = math.sin(self.pulse * (2.5 if self.is_speaking else 1.0)) * (2.2 if self.is_speaking else 1.2)
        active_impulse = self.beat_impulse

        base_col = QColor.fromHsv(
            int(self.current_color_hue) % 360,
            int(max(0, min(255, self.current_color_sat))),
            int(max(0, min(255, self.current_color_val)))
        )

        painter.setPen(Qt.PenStyle.NoPen)

        if self.current_theme == "light":
            mic_shadow = QRadialGradient(cx + 4.0, cy + 8.0, 112.0)
            mic_shadow.setColorAt(0.0, QColor(45, 58, 82, int(130 * T)))
            mic_shadow.setColorAt(0.40, QColor(65, 80, 105, int(90 * T)))
            mic_shadow.setColorAt(0.72, QColor(90, 105, 130, int(45 * T)))
            mic_shadow.setColorAt(1.0, QColor(120, 135, 160, 0))
            painter.setBrush(QBrush(mic_shadow))
            painter.drawEllipse(QPointF(cx + 4.0, cy + 8.0), 112.0, 112.0)

        for p in self.particles:
            if T < p['delay']:
                continue

            local_t = min(1.0, (T - p['delay']) / (1.0 - p['delay']))
            u = math.sin(local_t * (math.pi / 2))

            cur_angle = p['accum_angle']
            rad_focus = -8.0 if self.is_processing else 0.0
            target_rad = p['r'] + rad_focus + (p_val * (1 if p['size'] > 1.2 else -1)) + (active_impulse * 22.0)
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
            if self.current_theme == "light":
                alpha = int(min(255, base_alpha * 1.35 * min(1.0, local_t * 2.0)))
            else:
                alpha = int(base_alpha * min(1.0, local_t * 1.8))
            col.setAlpha(alpha)

            painter.setBrush(QBrush(col))
            base_sz = p['size'] * 1.45 if self.current_theme == "light" else p['size']
            sz = base_sz + (active_impulse * 1.8)
            painter.drawEllipse(QRectF(px - sz / 2.0, py - sz / 2.0, sz, sz))

    def mouseMoveEvent(self, event):
        if self.intro_progress < 0.95:
            self.unsetCursor()
            super().mouseMoveEvent(event)
            return

        orb_center = self.get_orb_center()
        dist = math.hypot(event.pos().x() - orb_center.x(), event.pos().y() - orb_center.y())
        if dist <= 95:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if self.intro_progress < 0.95:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            orb_center = self.get_orb_center()
            dist = math.hypot(event.pos().x() - orb_center.x(), event.pos().y() - orb_center.y())
            if dist <= 95:
                self.clicked.emit()
                event.accept()
                return
        super().mousePressEvent(event)


class AkiraMiniMicWidget(AkiraMicWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.total_particles = 90
        self._init_particles()

    def get_orb_center(self) -> QPointF:
        return QPointF(self.width() / 2.0, self.height() / 2.0)

    def _init_particles(self):
        self.particles.clear()
        for i in range(self.total_particles):
            r_dist = random.gauss(11, 2.5)
            if r_dist < 5:
                r_dist = 5 + random.uniform(0, 2)

            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(0.0015, 0.005) * (1 if random.random() > 0.2 else -0.6)

            x_start = -random.uniform(5, 20)
            y_start_off = random.gauss(0, 8)

            p1_x_off = -random.uniform(8, 20)
            p1_y_off = -random.uniform(6, 15)
            p2_x_off = random.uniform(6, 15)
            p2_y_off = random.uniform(4, 10)

            delay = (i / self.total_particles) * 0.55 + random.uniform(0, 0.04)

            self.particles.append({
                'r': r_dist,
                'accum_angle': angle,
                'speed': speed,
                'x_start': x_start,
                'y_start_off': y_start_off,
                'p1_x_off': p1_x_off,
                'p1_y_off': p1_y_off,
                'p2_x_off': p2_x_off,
                'p2_y_off': p2_y_off,
                'delay': delay,
                'size': random.uniform(0.5, 1.2),
                'alpha': random.randint(140, 255)
            })

    def paintEvent(self, event):
        T = self.intro_progress
        if T <= 0.001:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        orb_center = self.get_orb_center()
        cx = orb_center.x()
        cy = orb_center.y()

        painter.setPen(Qt.PenStyle.NoPen)

        if self.current_theme == "light":
            mini_shadow = QRadialGradient(cx + 1.0, cy + 1.5, 18.0)
            mini_shadow.setColorAt(0.0, QColor(45, 58, 82, int(130 * T)))
            mini_shadow.setColorAt(0.50, QColor(70, 85, 110, int(70 * T)))
            mini_shadow.setColorAt(1.0, QColor(120, 135, 160, 0))
            painter.setBrush(QBrush(mini_shadow))
            painter.drawEllipse(QPointF(cx + 1.0, cy + 1.5), 18.0, 18.0)

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
            rad_focus = -3.0 if getattr(self, 'is_processing', False) else 0.0
            target_rad = p['r'] + rad_focus + p_val + (active_impulse * 5.0)
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
            if self.current_theme == "light":
                alpha = int(min(255, base_alpha * 1.35 * min(1.0, local_t * 2.0)))
            else:
                alpha = int(base_alpha * min(1.0, local_t * 1.8))
            col.setAlpha(alpha)

            painter.setBrush(QBrush(col))
            base_sz = p['size'] * 1.35 if self.current_theme == "light" else p['size']
            sz = base_sz + (active_impulse * 1.0)
            painter.drawEllipse(QRectF(px - sz / 2.0, py - sz / 2.0, sz, sz))

    def mouseMoveEvent(self, event):
        if self.intro_progress < 0.95:
            self.unsetCursor()
            super().mouseMoveEvent(event)
            return

        orb_center = self.get_orb_center()
        dist = math.hypot(event.pos().x() - orb_center.x(), event.pos().y() - orb_center.y())
        if dist <= 20:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if self.intro_progress < 0.95:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            orb_center = self.get_orb_center()
            dist = math.hypot(event.pos().x() - orb_center.x(), event.pos().y() - orb_center.y())
            if dist <= 20:
                self.clicked.emit()
                event.accept()
                return
        super().mousePressEvent(event)

class ThinkingLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.0
        self._offset_y = 6.0
        self.current_theme = "dark"
        self.setObjectName("ThinkingStatusLabel")
        self.setFixedHeight(20)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update()

    def set_opacity(self, val: float):
        self.set_progress(val)
    
    def get_opacity(self) -> float:
        return self._opacity

    def set_progress(self, val: float):
        self._opacity = max(0.0, min(1.0, float(val)))
        self._offset_y = (1.0 - self._opacity) * 6.0
        self.update()

    def paintEvent(self, event):
        if self._opacity <= 0.01 or not self.text():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        painter.translate(0, self._offset_y)

        font = self.font()
        font.setItalic(True)
        painter.setFont(font)

        if self.current_theme == "light":
            col = QColor(17, 19, 24, int(self._opacity * 165))
        else:
            col = QColor(222, 215, 196, int(self._opacity * 180))

        painter.setPen(col)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        painter.end()

class ChatFrame(QFrame):

    CHAT_PLACEHOLDERS = [
        "Доверься мне...",
        "Какие мысли на сегодня?..",
        "Напиши мне что-нибудь...",
        "Рассказывай, я на связи...",
        "Жду твоих указаний...",
        "Чем займемся прямо сейчас?..",
        "Спроси меня о чем угодно...",
        "Внимательно слушаю...",
        "Шепни мне задачу...",
        "Давай сотворим что-то крутое..."
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_theme = "dark"
        self.border_phase = 0.0
        self.border_opacity = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_border)

        self.dark_palette = {
            "happy": (45.0, 220.0, 255.0),
            "sad": (200.0, 210.0, 255.0),
            "angry": (352.0, 230.0, 255.0),
            "surprise": (280.0, 220.0, 255.0),
            "neutral": (42.0, 60.0, 160.0),
            "other": (280.0, 220.0, 255.0),
            "weather_rain": (212.0, 220.0, 255.0),
            "weather_hot": (45.0, 240.0, 255.0),
            "weather_snow": (185.0, 160.0, 255.0),
            "weather_thunder": (280.0, 230.0, 255.0),
            "weather_cloudy": (215.0, 60.0, 220.0)
        }

        self.light_palette = {
            "happy": (38.0, 240.0, 235.0),
            "sad": (212.0, 220.0, 235.0),
            "angry": (355.0, 230.0, 235.0),
            "surprise": (285.0, 220.0, 235.0),
            "neutral": (218.0, 210.0, 160.0),
            "other": (285.0, 220.0, 235.0),
            "weather_rain": (215.0, 255.0, 190.0),
            "weather_hot": (38.0, 245.0, 245.0),
            "weather_snow": (205.0, 230.0, 195.0),
            "weather_thunder": (278.0, 230.0, 240.0),
            "weather_cloudy": (218.0, 200.0, 175.0)
        }

        self.emotion_palette = self.dark_palette
        self.target_emotion = "neutral"
        self.cur_h, self.cur_s, self.cur_v = self.emotion_palette["neutral"]
        self.target_h, self.target_s, self.target_v = self.emotion_palette["neutral"]

        self.reset_emotion_timer = QTimer(self)
        self.reset_emotion_timer.setSingleShot(True)
        self.reset_emotion_timer.timeout.connect(self._reset_to_neutral)

        self.content_widget = QWidget(self)
        self.content_widget.setFixedHeight(280)
        self.content_widget.setStyleSheet("background: transparent;")

        self.content_opacity_effect = QGraphicsOpacityEffect(self.content_widget)
        self.content_opacity_effect.setOpacity(1.0)
        self.content_widget.setGraphicsEffect(self.content_opacity_effect)

        layout = QVBoxLayout(self.content_widget)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        self.chat_history = QTextEdit()
        self.chat_history.setObjectName("ChatHistory")
        self.chat_history.setReadOnly(True)
        layout.addWidget(self.chat_history, 1)

        self.attached_file = None

        self.file_container = QWidget()
        file_layout = QHBoxLayout(self.file_container)
        file_layout.setContentsMargins(0, 0, 0, 4)
        file_layout.setSpacing(6)

        self.file_label = QLabel("")
        self.file_label.setObjectName("FileLabel")
        file_layout.addWidget(self.file_label)

        self.remove_file_btn = QPushButton("✕")
        self.remove_file_btn.setObjectName("RemoveFileBtn")
        self.remove_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_file_btn.setFixedSize(16, 16)
        self.remove_file_btn.clicked.connect(self.clear_attachment)
        file_layout.addWidget(self.remove_file_btn)
        file_layout.addStretch()

        self.file_container.hide()
        layout.addWidget(self.file_container, 0)

        self.thinking_label = ThinkingLabel(self)
        self.thinking_label.hide()
        layout.addWidget(self.thinking_label, 0)

        self.thinking_anim = QVariantAnimation(self)
        self.thinking_anim.setDuration(260)
        self.thinking_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.thinking_anim.valueChanged.connect(self.thinking_label.set_progress)

        self.thinking_cycle_timer = QTimer(self)
        self.thinking_cycle_timer.setInterval(2800)
        self.thinking_cycle_timer.timeout.connect(self._cycle_thinking_phrase)

        self.input_container = QWidget()
        self.input_container.setObjectName("InputContainer")
        self.input_container.setStyleSheet("background: transparent;")
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.attach_button = QPushButton()
        self.attach_button.setObjectName("AttachBtn")
        self.attach_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_button.setFixedSize(32, 32)
        self.attach_button.clicked.connect(self.select_file)
        input_layout.addWidget(self.attach_button)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("InputField")
        self.input_field.setFixedHeight(35)
        self.randomize_placeholder()
        input_layout.addWidget(self.input_field, 1)

        self.send_button = QPushButton()
        self.send_button.setObjectName("AttachBtn")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setFixedSize(32, 32)
        input_layout.addWidget(self.send_button)

        layout.addWidget(self.input_container, 0)

        self.update_icons()

    def set_content_opacity(self, opacity: float):
        self.content_opacity_effect.setOpacity(max(0.0, min(1.0, opacity)))
        self.content_widget.setVisible(opacity > 0.01)

    def set_border_opacity(self, opacity: float):
        self.border_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def update_icons(self):
        clip_color = "#111318" if self.current_theme == "light" else "#ffffff"
        self.attach_button.setText("")
        self.attach_button.setIcon(render_svg_icon(SVG_PAPERCLIP, clip_color, 16))
        self.attach_button.setIconSize(QSize(16, 16))

        send_name = "send_icon_black.png" if self.current_theme == "light" else "send_icon.png"
        send_path = get_resource_path("assets", "img", send_name)
        if not os.path.exists(send_path):
            send_path = get_resource_path("assets", "img", "send_icon.png")
        self.send_button.setIcon(QIcon(send_path))
        self.send_button.setIconSize(QSize(18, 18))

    def set_theme(self, theme: str):
        self.current_theme = theme
        if hasattr(self, 'thinking_label'):
            self.thinking_label.set_theme(theme)
        self.emotion_palette = self.light_palette if theme == "light" else self.dark_palette
        if self.target_emotion in self.emotion_palette:
            self.target_h, self.target_s, self.target_v = self.emotion_palette[self.target_emotion]
            self.cur_h, self.cur_s, self.cur_v = self.emotion_palette[self.target_emotion]
        self.update_icons()
        self.update()

    def set_emotion(self, emotion: str):
        emo = emotion if emotion in self.emotion_palette else "neutral"
        self.target_emotion = emo
        self.target_h, self.target_s, self.target_v = self.emotion_palette[emo]
        self.reset_emotion_timer.stop()
        if emo != "neutral":
            self.reset_emotion_timer.start(12000)

    def _reset_to_neutral(self):
        self.target_emotion = "neutral"
        self.target_h, self.target_s, self.target_v = self.emotion_palette["neutral"]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'theme_overlay'):
            self.theme_overlay.setGeometry(self.rect())
        w = self.width()
        h = self.height()
        self.content_widget.setGeometry(0, 0, w, 280)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'timer') and not self.timer.isActive():
            self.timer.start(35)

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()

    def mousePressEvent(self, event):
        event.accept()

    THINKING_PHRASES = [
        "Варю мысли под синтвейв...",
        "Перебираю полочки в памяти...",
        "Секунду, шезлонг видеокарты нагревается...",
        "Строю дерево вероятностей...",
        "Ищу красивое решение без костылей...",
        "Разгоняю кулеры ради ответа...",
        "Проверяю гипотезы в фоновом потоке...",
        "Вчитываюсь в суть вопроса...",
        "Пересобираю логику на лету..."
    ]

    THINKING_FILE_PHRASES = [
        "Сканирую прикрепленный документ...",
        "Вчитываюсь в строки файла...",
        "Разбираю структуру данных...",
        "Выделяю главное из документа..."
    ]

    def randomize_placeholder(self):
        phrase = random.choice(self.CHAT_PLACEHOLDERS)
        self.input_field.setPlaceholderText(phrase)

    def start_thinking(self, has_file=False):
        pool = self.THINKING_FILE_PHRASES if has_file else self.THINKING_PHRASES
        self._current_thinking_pool = pool
        self._last_phrase = random.choice(pool)
        self.thinking_label.setText(self._last_phrase)
        self.thinking_label.set_theme(self.current_theme)
        self.thinking_label.set_progress(0.0)
        self.thinking_label.show()

        if hasattr(self, 'thinking_anim'):
            self.thinking_anim.stop()

        self.thinking_anim = QVariantAnimation(self)
        self.thinking_anim.setDuration(480)
        self.thinking_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.thinking_anim.setStartValue(self.thinking_label.get_opacity())
        self.thinking_anim.setEndValue(1.0)
        self.thinking_anim.valueChanged.connect(self.thinking_label.set_progress)
        self.thinking_anim.start()

        self.thinking_cycle_timer.start()

    def _cycle_thinking_phrase(self):
        pool = getattr(self, '_current_thinking_pool', self.THINKING_PHRASES)
        candidates = [p for p in pool if p != self._last_phrase]
        new_phrase = random.choice(candidates) if candidates else pool[0]
        self._last_phrase = new_phrase

        fade_out = QVariantAnimation(self)
        fade_out.setDuration(280)
        fade_out.setEasingCurve(QEasingCurve.Type.InQuad)
        fade_out.setStartValue(self.thinking_label.get_opacity())
        fade_out.setEndValue(0.05)
        fade_out.valueChanged.connect(self.thinking_label.set_progress)

        def _on_faded():
            self.thinking_label.setText(new_phrase)
            fade_in = QVariantAnimation(self)
            fade_in.setDuration(360)
            fade_in.setEasingCurve(QEasingCurve.Type.OutQuad)
            fade_in.setStartValue(0.05)
            fade_in.setEndValue(1.0)
            fade_in.valueChanged.connect(self.thinking_label.set_progress)
            fade_in.start()
            self._fade_in_sub = fade_in

        fade_out.finished.connect(_on_faded)
        fade_out.start()
        self._fade_out_sub = fade_out

    def stop_thinking(self):
        self.thinking_cycle_timer.stop()
        if hasattr(self, 'thinking_anim'):
            self.thinking_anim.stop()

        self.thinking_anim = QVariantAnimation(self)
        self.thinking_anim.setDuration(420)
        self.thinking_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.thinking_anim.setStartValue(self.thinking_label.get_opacity())
        self.thinking_anim.setEndValue(0.0)
        self.thinking_anim.valueChanged.connect(self.thinking_label.set_progress)

        def _on_hide():
            if self.thinking_label.get_opacity() <= 0.02:
                self.thinking_label.hide()
                self.thinking_label.setText("")

        self.thinking_anim.finished.connect(_on_hide)
        self.thinking_anim.start()

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл для Акиры",
            "",
            "Все поддерживаемые файлы (*.txt *.pdf *.docx *.png *.jpg *.jpeg *.bmp *.webp *.md *.py *.json *.csv *.log);;Изображения (*.png *.jpg *.jpeg *.bmp *.webp);;Тексты и Документы (*.txt *.pdf *.docx *.md *.py *.json *.csv *.log)"
        )
        if path:
            self.attached_file = path
            self.file_label.setText(f"📎 {os.path.basename(path)}")
            self.file_container.show()

    def clear_attachment(self):
        self.attached_file = None
        self.file_label.clear()
        self.file_container.hide()

    def animate_border(self):
        self.border_phase += 0.012
        rate = 0.06
        self.cur_h += (self.target_h - self.cur_h) * rate
        self.cur_s += (self.target_s - self.cur_s) * rate
        self.cur_v += (self.target_v - self.cur_v) * rate
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w < 20 or h < 8:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.75, 0.75, w - 1.5, h - 1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        fill_col = QColor(238, 242, 248, 215) if self.current_theme == "light" else QColor(8, 8, 5, 235)
        painter.fillPath(path, fill_col)

        if self.border_opacity > 0.01:
            cx, cy = w / 2.0, h / 2.0
            diag = math.hypot(w, 280) / 2.0
            dx = math.cos(self.border_phase) * diag
            dy = math.sin(self.border_phase) * diag

            h_val = int(self.cur_h) % 360
            s_val = int(max(0, min(255, self.cur_s)))
            v_val = int(max(0, min(255, self.cur_v)))

            op = self.border_opacity

            if self.current_theme == "light":
                c_bright = QColor.fromHsv(h_val, min(255, int(s_val * 1.05)), int(v_val), int(255 * op))
                c_mid = QColor.fromHsv(h_val, int(s_val), int(v_val * 0.95), int(150 * op))
                c_dark = QColor.fromHsv(h_val, max(30, int(s_val * 0.7)), int(v_val), int(30 * op))
                border_width = 2.0
            else:
                c_bright = QColor.fromHsv(h_val, s_val, v_val, int(230 * op))
                c_mid = QColor.fromHsv(h_val, min(255, s_val + 20), max(20, int(v_val * 0.55)), int(140 * op))
                c_dark = QColor.fromHsv(h_val, min(255, s_val + 40), max(10, int(v_val * 0.22)), int(50 * op))
                border_width = 1.5

            border_grad = QLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
            border_grad.setColorAt(0.0, c_dark)
            border_grad.setColorAt(0.35, c_mid)
            border_grad.setColorAt(0.5, c_bright)
            border_grad.setColorAt(0.65, c_mid)
            border_grad.setColorAt(1.0, c_dark)

            border_width = 2.5 if self.current_theme == "light" else 1.5
            pen_border = QPen(QBrush(border_grad), border_width)
            painter.setPen(pen_border)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)


class BackgroundFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_theme = "dark"
        self.mic_widget = None
        self.wave_phase = 0.0
        self.speed_mult = 1.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_bg)
        self.timer.start(16)

        self.dust_palettes = {
            "dark": ["#ffffff", "#f7f5ef", "#ded7c4", "#c7c0ac", "#aba48f", "#9e9780", "#78735f", "#545041"],
            "light": ["#111318", "#171a22", "#1f242e", "#282f3c", "#0d0e13", "#1b1f28", "#222733"]
        }

        self.stars = []
        for _ in range(70):
            self.stars.append({
                'offset_right': random.uniform(10, 870),
                'ry': random.uniform(0.01, 0.99),
                'size': random.uniform(0.6, 1.3),
                'phase': random.uniform(0, math.pi * 2),
                'speed': random.uniform(0.015, 0.035)
            })

        self.dust_cloud = []
        for _ in range(900):
            curve = random.choice([0, 0, 0, 1, 1, 2])
            spread = random.gauss(0, 12) if random.random() < 0.7 else random.gauss(0, 26)
            self.dust_cloud.append({
                'curve_idx': curve,
                't': random.uniform(0.0, 1.0),
                'offset_x': random.gauss(0, 14),
                'offset_y': spread,
                'size': random.uniform(0.6, 1.6),
                'palette_idx': random.randint(0, len(self.dust_palettes["dark"]) - 1),
                'alpha': random.randint(35, 200),
                'twinkle_speed': random.uniform(0.02, 0.06),
                'twinkle_phase': random.uniform(0, math.pi * 2)
            })

    def set_mic_widget(self, widget):
        self.mic_widget = widget
        self.update()

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update()

    def set_framerate(self, fps: int):
        self.speed_mult = 60.0 / fps
        interval = max(1, int(1000 / fps))
        self.timer.setInterval(interval)

    def animate_bg(self):
        self.wave_phase += 0.005 * self.speed_mult
        for star in self.stars:
            star['phase'] += star['speed'] * self.speed_mult
        for d in self.dust_cloud:
            d['twinkle_phase'] += d['twinkle_speed'] * self.speed_mult
        self.update()

    def _get_bezier_point(self, p0, p1, p2, p3, t):
        u = 1 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t
        x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        return x, y

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)

        if self.current_theme == "light":
            bg_grad = QLinearGradient(0, 0, w, h)
            bg_grad.setColorAt(0.0, QColor(234, 238, 245, 205))
            bg_grad.setColorAt(0.5, QColor(222, 228, 238, 215))
            bg_grad.setColorAt(1.0, QColor(208, 217, 230, 220))
            painter.fillPath(clip_path, bg_grad)
        else:
            painter.fillPath(clip_path, QColor(6, 6, 4, 240))
        painter.setClipPath(clip_path)

        shift1 = math.sin(self.wave_phase) * 20
        shift2 = math.cos(self.wave_phase * 0.6) * 24

        curves = [
            (
                (w * 0.02, h + 80),
                (w * 0.35 + shift1, h * 0.42 + shift2),
                (w * 0.68 - shift2, h * 0.82 + shift1),
                (w + 80, h * 0.18)
            ),
            (
                (w * 0.15, h + 80),
                (w * 0.48 - shift2, h * 0.52 + shift1),
                (w * 0.78 + shift1, h * 0.78 - shift2),
                (w + 80, h * 0.42)
            ),
            (
                (w * 0.32, h + 80),
                (w * 0.62 + shift1, h * 0.65 - shift2),
                (w * 0.88 - shift1, h * 0.86 + shift2),
                (w + 80, h * 0.68)
            )
        ]

        for star in self.stars:
            sx = w - star['offset_right']
            if sx < 0:
                continue
            sy = star['ry'] * h
            twinkle = (math.sin(star['phase']) + 1) / 2
            sz = star['size']

            painter.setPen(Qt.PenStyle.NoPen)
            if self.current_theme == "light":
                alpha = int(25 + twinkle * 130)
                star_col = QColor(17, 19, 24, alpha)
            else:
                alpha = int(20 + twinkle * 210)
                star_col = QColor(222, 215, 196, alpha)

            painter.setBrush(QBrush(star_col))
            painter.drawEllipse(QRectF(sx - sz, sy - sz, sz * 2, sz * 2))

        palette = self.dust_palettes.get(self.current_theme, self.dust_palettes["dark"])

        painter.setPen(Qt.PenStyle.NoPen)
        for d in self.dust_cloud:
            p0, p1, p2, p3 = curves[d['curve_idx']]
            bx, by = self._get_bezier_point(p0, p1, p2, p3, d['t'])
            px = bx + d['offset_x']
            py = by + d['offset_y']

            twinkle = (math.sin(d['twinkle_phase']) + 1) / 2
            alpha = int(d['alpha'] * (0.5 + 0.5 * twinkle))

            color_hex = palette[d['palette_idx'] % len(palette)]
            col = QColor(color_hex)
            col.setAlpha(alpha)

            sz = d['size']

            painter.setBrush(QBrush(col))
            painter.drawEllipse(QRectF(px - sz / 2.0, py - sz / 2.0, sz, sz))

        glass_pen = QPen(
            QColor(255, 255, 255, 140) if self.current_theme == "light" else QColor(222, 215, 196, 35),
            1.0
        )
        painter.setPen(glass_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 16, 16)


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
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 16, 16)
        path.addEllipse(self.center_pt, self.radius, self.radius)

        painter.setClipPath(path)
        painter.drawPixmap(self.rect(), self.old_pixmap)


class MainWindow(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.drag_position = QPoint()
        self.ui_revealed = False
        self.command_parser = CommandParser()

        mgr = self.command_parser.reminder_manager
        mgr.timer_fired.connect(self._on_timer_fired)
        mgr.alarm_fired.connect(self._on_alarm_fired)
        mgr.reminder_fired.connect(self._on_reminder_fired)
        mgr.missed_reminders_signal.connect(self._on_missed_reminders)

        self.current_theme = self.config.get("theme", "dark") if isinstance(self.config, dict) else "dark"
        self.is_mini_mode = self.config.get("is_mini_mode", False) if isinstance(self.config, dict) else False

        # Константы геометрии: окно ОС всегда имеет ширину EXTENDED_WIDTH (Zero-Move)
        self.window_mode = "mini" if self.is_mini_mode else "normal"
        self.NORMAL_WIDTH = 380
        self.EXTENDED_WIDTH = 880
        self.WINDOW_HEIGHT = 560
        self._is_mode_animating = False

        # Анимация перемещения внутреннего корпуса (Zero-Move)
        self.expand_anim = QVariantAnimation(self)
        self.expand_anim.setDuration(620)
        self.expand_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.expand_anim.valueChanged.connect(self._on_expand_step)

        self.vision_thread = None
        self.presence_manager = None

        self.is_muted = self.config.get("is_muted", False) if isinstance(self.config, dict) else False

        self.absence_start_time = None
        self.warned_battery_50 = False
        self.warned_battery_25 = False
        self.warned_battery_tg_30 = False

        self._warmup_ready = False
        self._window_ready = False

        self.init_ui()
        self.init_audio()

        # Анимация прозрачности студии строго ПОСЛЕ создания self.studio_opacity в init_ui
        self.studio_fade_anim = QPropertyAnimation(self.studio_opacity, b"opacity")
        self.studio_fade_anim.setDuration(280)
        self.studio_fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.theme_overlay = ThemeRevealOverlay(self)

        self.battery_timer = QTimer(self)
        self.battery_timer.timeout.connect(self.check_battery_status)
        self.battery_timer.start(45000)

        self.settings_panel.fps_changed.connect(self.apply_framerate)
        self.settings_panel.theme_changed.connect(self.apply_theme)

        cfg_modules = self.config.get("modules", {}) if isinstance(self.config, dict) else {}
        if cfg_modules.get("vision", False):
            QTimer.singleShot(12500, self.start_vision)

        atexit.register(volume_ducker.force_restore)
        atexit.register(self._save_exit_timestamp)

        self.telegram_thread = None
        QTimer.singleShot(8500, self._start_telegram_delayed)

        QTimer.singleShot(3000, self._check_updates)

        initial_fps = self.config.get("target_fps", 60) if isinstance(self.config, dict) else 60
        self.apply_framerate(initial_fps)

        self.apply_theme(self.current_theme, initial=True)

    MINI_PLACEHOLDERS = [
        "слушаю...",
        "команда...",
        "я на связи...",
        "жду команду...",
        "что делаем?..",
        "слушаю тебя...",
        "я рядом...",
        "наготове...",
        "готова..."
    ]

    def randomize_mini_placeholder(self):
        if hasattr(self, 'mini_window'):
            self.mini_window.randomize_placeholder()

    def update_title_icons(self):
        if hasattr(self, 'exit_btn'):
            self.exit_btn.update_icon()

        if hasattr(self, 'settings_btn'):
            self.settings_btn.update_icon()

        if hasattr(self, 'studio_btn'):
            studio_svg = SVG_STUDIO_COLLAPSE if getattr(self, 'window_mode', 'normal') == 'extended' else SVG_STUDIO
            self.studio_btn.set_svg(studio_svg)
            self.studio_btn.setToolTip("Свернуть студию" if getattr(self, 'window_mode', 'normal') == 'extended' else "Режим студии")

        if hasattr(self, 'mini_mode_btn'):
            self.mini_mode_btn.update_icon()

        if hasattr(self, 'toggle_chat_btn'):
            if getattr(self, 'window_mode', 'normal') == 'extended':
                self.toggle_chat_btn.update_icon()
                self.toggle_chat_btn.setToolTip("Чат уже открыт в студии")
            else:
                self.toggle_chat_btn.update_icon()
                self.toggle_chat_btn.setToolTip("Открыть чат")

        if hasattr(self, 'mute_btn'):
            mute_svg = SVG_MUTE if self.is_muted else SVG_VOLUME
            self.mute_btn.set_svg(mute_svg)
            self.mute_btn.setToolTip("Включить голос Акиры!" if self.is_muted else "Выключить голос Акиры!")

        if hasattr(self, 'update_badge_btn'):
            self.update_badge_btn.update_icon()

        if hasattr(self, 'min_btn'):
            self.min_btn.update_icon()

        if hasattr(self, 'close_btn'):
            self.close_btn.update_icon()

    def apply_theme(self, theme: str, initial: bool = False):
        if not initial and hasattr(self, 'theme_overlay'):
            old_pixmap = self.grab()
            if hasattr(self, 'settings_panel') and hasattr(self.settings_panel, 'theme_combo') and self.settings_panel.isVisible():
                combo = self.settings_panel.theme_combo
                center = combo.mapTo(self, combo.rect().center())
            else:
                center = QPoint(self.width() // 2, self.height() // 2)

        self.current_theme = theme
        self.bg_frame.setStyleSheet(get_main_style(theme))
        self.bg_frame.set_theme(theme)
        self.left_panel.set_theme(theme)
        self.right_panel.set_theme(theme)
        self.settings_panel.set_theme(theme)
        if hasattr(self, 'studio_panel'):
            self.studio_panel.set_theme(theme)

        self.mini_window.setStyleSheet(get_main_style(theme))
        self.mini_window.set_theme(theme)
        self.update_title_icons()

        if enable_window_acrylic:
            try:
                tint = "20E8EEF5" if theme == "light" else "25080805"
                enable_window_acrylic(int(self.winId()), tint)
            except Exception:
                pass

        if not initial:
            cfg = load_config()
            cfg["theme"] = theme
            if isinstance(self.config, dict):
                self.config["theme"] = theme
            save_config(cfg)
            if hasattr(self, 'theme_overlay'):
                self.theme_overlay.start_reveal(old_pixmap, center)

    def _on_timer_fired(self, task):
        text = task.get("text", "Таймер")
        msg = f"Время вышло! {text} завершён ⏳"
        self.chat_history.append(f"Акира: {msg}\n")
        self.left_panel.set_emotion("surprise")
        if hasattr(self, 'mini_window'):
            self.mini_window.mini_mic.set_emotion("surprise")
        self.right_panel.set_emotion("surprise")

    def _on_alarm_fired(self, task):
        msg = "Будильник! Пора просыпаться ⏰ (Скажи 'Стоп' или 'Отложи')"
        self.chat_history.append(f"Акира: {msg}\n")
        self.speak_reply("Будильник! Пора просыпаться.")
        self.left_panel.set_emotion("happy")
        if hasattr(self, 'mini_window'):
            self.mini_window.mini_mic.set_emotion("happy")
        self.right_panel.set_emotion("happy")

    def _on_reminder_fired(self, task):
        text = task.get("text", "")
        msg = f"Напоминаю: {text} 🔔"
        self.chat_history.append(f"Акира: {msg}\n")
        self.speak_reply(f"Напоминаю: {text}")
        self.left_panel.set_emotion("happy")
        if hasattr(self, 'mini_window'):
            self.mini_window.mini_mic.set_emotion("happy")
        self.right_panel.set_emotion("happy")

    def _on_missed_reminders(self, missed_list):
        items_str = ", ".join(missed_list)
        msg = f"Пока ПК был выключен, наступило время: {items_str} 📌"
        self.chat_history.append(f"Акира: {msg}\n")

    def apply_framerate(self, fps: int):
        if hasattr(self, 'left_panel'):
            self.left_panel.set_framerate(fps)
        if hasattr(self, 'bg_frame'):
            self.bg_frame.set_framerate(fps)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if not getattr(self, '_is_animating_window', False):
                if self.windowState() == Qt.WindowState.WindowNoState and event.oldState() == Qt.WindowState.WindowMinimized:
                    self.show_animated()
        super().changeEvent(event)

    def bring_to_front(self):
        if not self.isVisible() or self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.showNormal()
        self.raise_()
        self.activateWindow()
    
    def show_animated(self):
        if getattr(self, 'is_mini_mode', False) and hasattr(self, 'mini_window'):
            screen = QGuiApplication.primaryScreen().availableGeometry()
            x = screen.right() - 460 - 20
            y = screen.bottom() - 56 - 20
            self.mini_window.show_at(x, y)
            self._window_ready = True
            self._check_and_reveal()
            return

        if hasattr(self, 'closing_anim') and self.closing_anim.state() == QPropertyAnimation.State.Running:
            self.closing_anim.stop()

        self._is_animating_window = True
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()

        w = self.EXTENDED_WIDTH
        h = self.WINDOW_HEIGHT
        x = avail.x() + avail.width() - w - 20
        y = avail.y() + avail.height() - h - 20
        start_y = avail.y() + avail.height() + 50

        if not self.isVisible() or self.isMinimized():
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.move(x, start_y)
            super().showNormal()

        self.activateWindow()

        self.opening_anim = QPropertyAnimation(self, b"pos")
        self.opening_anim.setDuration(450)
        self.opening_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.opening_anim.setStartValue(QPoint(x, start_y))
        self.opening_anim.setEndValue(QPoint(x, y))

        def _on_opened():
            self._is_animating_window = False
            self._window_ready = True
            self._check_and_reveal()

        self.opening_anim.finished.connect(_on_opened)
        self.opening_anim.start()

    def _animate_down_and_do(self, action_func):
        if hasattr(self, 'closing_anim') and self.closing_anim.state() == QPropertyAnimation.State.Running:
            return

        if hasattr(self, 'opening_anim') and self.opening_anim.state() == QPropertyAnimation.State.Running:
            self.opening_anim.stop()

        self._is_animating_window = True
        full = QGuiApplication.primaryScreen().geometry()
        target_y = full.y() + full.height() + 15

        self.closing_anim = QPropertyAnimation(self, b"pos")
        self.closing_anim.setDuration(450)
        self.closing_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.closing_anim.setStartValue(self.pos())
        self.closing_anim.setEndValue(QPoint(self.x(), target_y))

        def _on_closed():
            self._is_animating_window = False
            action_func()

        self.closing_anim.finished.connect(_on_closed)
        self.closing_anim.start()

    def minimize_animated(self):
        self._animate_down_and_do(self.showMinimized)

    def close_animated(self):
        self._animate_down_and_do(self.hide)

    def show(self):
        self.show_animated()

    def showNormal(self):
        self.show_animated()

    def _start_telegram_delayed(self):
        if self.telegram_thread is None:
            self.telegram_thread = TelegramBotThread(parent=self)
            self.telegram_thread.start()

    def _check_updates(self):
        self.update_checker = UpdateCheckerThread(parent=self)
        self.update_checker.update_available.connect(self.on_update_found)
        self.update_checker.start()

    def on_update_found(self, new_ver: str, changelog: str, download_url: str):
        self.settings_panel.set_update_available(new_ver, changelog, download_url)
        self.update_badge_btn.setToolTip(f"Доступна новая версия v{new_ver}!\nНажми, чтобы перейти в настройки.")
        self.update_badge_btn.update_icon()
        self.update_badge_btn.show()

    def open_settings_for_update(self):
        if not (self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0):
            self.toggle_settings()
        self.settings_panel.scroll_to_bottom()

    def _update_click_mask(self, width: int):
        """Оставляет активной для мыши только видимую часть корпуса Акиры."""
        from PyQt6.QtGui import QRegion
        x_local = self.EXTENDED_WIDTH - width
        self.setMask(QRegion(x_local, 0, width, self.WINDOW_HEIGHT))

    def _on_expand_step(self, val):
        w = int(round(val))
        x_local = self.EXTENDED_WIDTH - w
        self.bg_frame.setGeometry(x_local, 0, w, self.WINDOW_HEIGHT)
        self._update_click_mask(w)

    def toggle_extended_mode(self):
        if getattr(self, '_is_mode_animating', False):
            return
        if self.is_mini_mode or getattr(self, 'window_mode', 'normal') == "mini":
            return
            
        is_expanding = (self.window_mode == "normal")
        self.window_mode = "extended" if is_expanding else "normal"
        self.update_title_icons()
        self._is_mode_animating = True
        
        if is_expanding:
            if self.right_panel.isVisible():
                self._do_toggle_chat(force_close=True)
            
            self.studio_panel.hide()
            self.studio_opacity.setOpacity(0.0)
            
            try:
                self.expand_anim.finished.disconnect()
            except Exception:
                pass
                
            self.expand_anim.stop()
            self.expand_anim.setDuration(620)
            self.expand_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self.expand_anim.setStartValue(float(self.NORMAL_WIDTH))
            self.expand_anim.setEndValue(float(self.EXTENDED_WIDTH))
            
            def on_expand_finished():
                self.bg_frame.setGeometry(0, 0, self.EXTENDED_WIDTH, self.WINDOW_HEIGHT)
                self.clearMask()
                
                self.studio_panel.show()
                try:
                    self.studio_fade_anim.finished.disconnect()
                except Exception:
                    pass
                self.studio_fade_anim.stop()
                self.studio_fade_anim.setDuration(280)
                self.studio_fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                self.studio_fade_anim.setStartValue(0.0)
                self.studio_fade_anim.setEndValue(1.0)
                
                def on_fade_in_finished():
                    self._is_mode_animating = False
                    
                self.studio_fade_anim.finished.connect(on_fade_in_finished)
                self.studio_fade_anim.start()
                
            self.expand_anim.finished.connect(on_expand_finished)
            self.expand_anim.start()

        else:
            self.command_parser.llm.set_model("gigachat")
            
            try:
                self.studio_fade_anim.finished.disconnect()
            except Exception:
                pass
            self.studio_fade_anim.stop()
            self.studio_fade_anim.setDuration(200)
            self.studio_fade_anim.setEasingCurve(QEasingCurve.Type.InQuad)
            self.studio_fade_anim.setStartValue(self.studio_opacity.opacity())
            self.studio_fade_anim.setEndValue(0.0)
            
            def on_fade_out_finished():
                self.studio_panel.hide()
                
                try:
                    self.expand_anim.finished.disconnect()
                except Exception:
                    pass
                self.expand_anim.stop()
                self.expand_anim.setDuration(580)
                self.expand_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                self.expand_anim.setStartValue(float(self.EXTENDED_WIDTH))
                self.expand_anim.setEndValue(float(self.NORMAL_WIDTH))
                
                def on_collapse_finished():
                    init_x = self.EXTENDED_WIDTH - self.NORMAL_WIDTH
                    self.bg_frame.setGeometry(init_x, 0, self.NORMAL_WIDTH, self.WINDOW_HEIGHT)
                    self._update_click_mask(self.NORMAL_WIDTH)
                    self._is_mode_animating = False
                    
                self.expand_anim.finished.connect(on_collapse_finished)
                self.expand_anim.start()
                
            self.studio_fade_anim.finished.connect(on_fade_out_finished)
            self.studio_fade_anim.start()

    def toggle_mini_mode(self):
        if getattr(self, '_is_mode_animating', False):
            return

        if self.is_mini_mode:
            self.restore_from_mini()
            return

        screen = QGuiApplication.primaryScreen().availableGeometry()
        cur_pos = self.pos()

        # Правый нижний угол видимого окна
        visible_x = cur_pos.x() + (self.EXTENDED_WIDTH - self.NORMAL_WIDTH)
        visible_y = cur_pos.y()
        target_x = visible_x + (self.NORMAL_WIDTH - 460)
        target_y = visible_y + (self.WINDOW_HEIGHT - 56)

        target_x = max(screen.left() + 10, min(target_x, screen.right() - 470))
        target_y = max(screen.top() + 10, min(target_y, screen.bottom() - 66))

        if self.window_mode == "extended":
            self.window_mode = "normal"
            self.studio_panel.hide()
            self.studio_opacity.setOpacity(0.0)
            init_x = self.EXTENDED_WIDTH - self.NORMAL_WIDTH
            self.bg_frame.setGeometry(init_x, 0, self.NORMAL_WIDTH, self.WINDOW_HEIGHT)
            self._update_click_mask(self.NORMAL_WIDTH)

        self.is_mini_mode = True
        self.window_mode = "mini"
        self.update_title_icons()

        self.hide()
        self.mini_window.show_at(target_x, target_y)

        cfg = load_config()
        cfg["is_mini_mode"] = True
        if isinstance(self.config, dict):
            self.config["is_mini_mode"] = True
        save_config(cfg)

    def restore_from_mini(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        mini_pos = self.mini_window.pos()

        target_x = mini_pos.x() + 460 - self.EXTENDED_WIDTH
        target_y = mini_pos.y() + 56 - self.WINDOW_HEIGHT

        target_x = max(screen.left() + 10, min(target_x, screen.right() - self.EXTENDED_WIDTH - 10))
        target_y = max(screen.top() + 10, min(target_y, screen.bottom() - self.WINDOW_HEIGHT - 10))

        self.is_mini_mode = False
        self.window_mode = "normal"
        self.update_title_icons()

        self.mini_window.hide()

        init_x = self.EXTENDED_WIDTH - self.NORMAL_WIDTH
        self.bg_frame.setGeometry(init_x, 0, self.NORMAL_WIDTH, self.WINDOW_HEIGHT)
        self._update_click_mask(self.NORMAL_WIDTH)

        self.move(target_x, target_y)
        super().show()
        self.raise_()
        self.activateWindow()

        if enable_window_acrylic:
            try:
                tint = "20E8EEF5" if self.current_theme == "light" else "25080805"
                enable_window_acrylic(int(self.winId()), tint)
            except Exception:
                pass

        cfg = load_config()
        cfg["is_mini_mode"] = False
        if isinstance(self.config, dict):
            self.config["is_mini_mode"] = False
        save_config(cfg)

    def send_mini_message(self, text: str):
        if not self.ui_revealed or not text.strip():
            return

        if hasattr(self, 'tts_thread') and self.tts_thread.isRunning():
            self.tts_thread.stop()
        self.left_panel.set_speaking(False)
        self.mini_window.mini_mic.set_speaking(False)

        self.chat_history.append(f"Вы: {text}")

        text_low = text.lower()
        if any(w in text_low for w in ["заблокируй", "залочь", "заблокировать", "залочить"]):
            self.absence_start_time = time.time()
            if self.presence_manager:
                self.presence_manager.set_manual_absence(grace_period=10)

        self.mini_window.clear_input()
        self.mini_window.set_input_enabled(False)

        self.mini_text_worker = CommandWorker(self.command_parser, text, is_voice=False, parent=self)
        self.mini_text_worker.result_ready.connect(self.on_mini_text_command_finished)
        self.mini_text_worker.start()

    def on_mini_text_command_finished(self, response):
        self.mini_window.randomize_placeholder()
        self.mini_window.set_input_enabled(True)

        if response:
            if isinstance(response, dict):
                chat_text = response.get("chat", "") or response.get("voice", "")
                voice_text = response.get("voice", "")
                emotion = response.get("emotion", "neutral")
            else:
                chat_text = voice_text = str(response)
                emotion = getattr(self.command_parser, "last_emotion", "neutral")

            self.left_panel.set_emotion(emotion)
            self.mini_window.mini_mic.set_emotion(emotion)
            self.right_panel.set_emotion(emotion)

            if chat_text:
                self.stream_text_to_chat(chat_text)
            if voice_text:
                self.speak_reply(voice_text, is_whisper=False)

    def init_ui(self):
        font_path = get_resource_path("assets", "fonts", "Schiffbauer-Regular.otf")
        font_id = QFontDatabase.addApplicationFont(font_path)

        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            self.font_family = families[0] if families else "Arial"
            self.custom_font = QFont(self.font_family, 11)
        else:
            self.font_family = "Arial"
            self.custom_font = QFont(self.font_family, 11)

        self.setFont(self.custom_font)

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Окно ОС всегда зафиксировано на EXTENDED_WIDTH (Zero-Move)
        self.setFixedSize(self.EXTENDED_WIDTH, self.WINDOW_HEIGHT)

        # Корпус Акиры
        self.bg_frame = BackgroundFrame(self)
        self.bg_frame.setObjectName("CentralWidget")
        
        init_x = self.EXTENDED_WIDTH - self.NORMAL_WIDTH
        self.bg_frame.setGeometry(init_x, 0, self.NORMAL_WIDTH, self.WINDOW_HEIGHT)
        self._update_click_mask(self.NORMAL_WIDTH)

        container_layout = QHBoxLayout(self.bg_frame)
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.setSpacing(0)

        # 1. Левая панель студии (Extended Mode)
        self.studio_panel = StudioFrame(self)
        self.studio_panel.setMinimumWidth(0)
        self.studio_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.studio_panel.hide()

        self.studio_opacity = QGraphicsOpacityEffect(self.studio_panel)
        self.studio_opacity.setOpacity(0.0)
        self.studio_panel.setGraphicsEffect(self.studio_opacity)
        container_layout.addWidget(self.studio_panel, 1)

        # 2. Правая часть со сферой (основное тело)
        self.right_area = QWidget()
        self.right_area.setFixedWidth(self.NORMAL_WIDTH - 4)
        right_area_layout = QVBoxLayout(self.right_area)
        right_area_layout.setContentsMargins(0, 0, 0, 0)
        right_area_layout.setSpacing(0)

        # Горизонтальная плашка кнопок с отступом снизу в 8px до контента
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 2, 6, 8)
        title_bar.addStretch()

        self.title_btns_widget = QWidget()
        self.title_btns_widget.setObjectName("TitleBtnsWidget")
        title_btns_layout = QHBoxLayout(self.title_btns_widget)
        title_btns_layout.setContentsMargins(4, 2, 4, 2)
        title_btns_layout.setSpacing(3)

        self.exit_btn = EmotionHoverButton(SVG_POWER, "Завершить работу Акиры", main_window=self)
        self.exit_btn.setObjectName("ExitBtn")
        self.exit_btn.clicked.connect(self.exit_app)
        title_btns_layout.addWidget(self.exit_btn)

        self.settings_btn = EmotionHoverButton(SVG_SETTINGS, "Настройки", main_window=self)
        self.settings_btn.clicked.connect(self.toggle_settings)
        title_btns_layout.addWidget(self.settings_btn)

        self.studio_btn = EmotionHoverButton(SVG_STUDIO, "Режим студии", main_window=self)
        self.studio_btn.clicked.connect(self.toggle_extended_mode)
        title_btns_layout.addWidget(self.studio_btn)

        self.mini_mode_btn = EmotionHoverButton(SVG_MINI, "Мини-режим (поверх окон)", main_window=self)
        self.mini_mode_btn.clicked.connect(self.toggle_mini_mode)
        title_btns_layout.addWidget(self.mini_mode_btn)

        self.toggle_chat_btn = EmotionHoverButton(SVG_CHAT, "Открыть чат", main_window=self)
        self.toggle_chat_btn.clicked.connect(self.toggle_chat)
        title_btns_layout.addWidget(self.toggle_chat_btn)

        self.mute_btn = EmotionHoverButton(SVG_VOLUME, "Выключить голос Акиры!", main_window=self)
        self.mute_btn.clicked.connect(self.toggle_mute)
        title_btns_layout.addWidget(self.mute_btn)

        self.update_badge_btn = EmotionHoverButton(SVG_UPDATE, "Доступно обновление!", main_window=self)
        self.update_badge_btn.setObjectName("UpdateNotificationBadge")
        self.update_badge_btn.clicked.connect(self.open_settings_for_update)
        self.update_badge_btn.hide()
        title_btns_layout.addWidget(self.update_badge_btn)

        self.min_btn = EmotionHoverButton(SVG_MINIMIZE, "Свернуть", main_window=self)
        self.min_btn.clicked.connect(self.minimize_animated)
        title_btns_layout.addWidget(self.min_btn)

        self.close_btn = EmotionHoverButton(SVG_CLOSE, "Закрыть", main_window=self)
        self.close_btn.clicked.connect(self.close_animated)
        title_btns_layout.addWidget(self.close_btn)

        title_bar.addWidget(self.title_btns_widget)
        right_area_layout.addLayout(title_bar)

        self.content_layout = QGridLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self.mic_chat_container = QWidget()
        mic_chat_layout = QVBoxLayout(self.mic_chat_container)
        mic_chat_layout.setContentsMargins(0, 0, 0, 0)
        mic_chat_layout.setSpacing(0)

        self.left_panel = AkiraMicWidget(self)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(15, 0, 0, 12)
        left_layout.addStretch()
        mic_chat_layout.addWidget(self.left_panel)

        self.right_panel = ChatFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_panel.setFixedHeight(0)
        self.right_panel.hide()
        mic_chat_layout.addWidget(self.right_panel)

        self.content_layout.addWidget(self.mic_chat_container, 0, 0)

        # Панель настроек: открывается под плашкой кнопок
        self.settings_panel = SettingsFrame()
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setFixedHeight(500)
        self.settings_panel.setMinimumWidth(0)
        self.settings_panel.setMaximumWidth(0)
        self.settings_panel.hide()
        self.settings_panel.speak_requested.connect(self.speak_reply)
        self.settings_panel.vision_state_changed.connect(self.on_vision_state_changed)
        self.settings_panel.fps_changed.connect(self.apply_framerate)

        self.content_layout.addWidget(self.settings_panel, 0, 0,
                                      Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        right_area_layout.addLayout(self.content_layout)
        container_layout.addWidget(self.right_area, 0, Qt.AlignmentFlag.AlignRight)

        self.chat_history = self.right_panel.chat_history
        self.chat_history.setFont(QFont(self.font_family, 12))
        self.input_field = self.right_panel.input_field
        self.input_field.setFont(QFont(self.font_family, 12))
        self.send_button = self.right_panel.send_button
        self.send_button.setFont(QFont(self.font_family, 12))

        self.input_field.returnPressed.connect(self.send_message)
        self.send_button.clicked.connect(self.send_message)

        self.title_btns_opacity = QGraphicsOpacityEffect(self.title_btns_widget)
        self.title_btns_opacity.setOpacity(0.0)
        self.title_btns_widget.setGraphicsEffect(self.title_btns_opacity)

        self.title_btns_anim = QPropertyAnimation(self.title_btns_opacity, b"opacity")
        self.title_btns_anim.setDuration(700)
        self.title_btns_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.title_btns_anim.setStartValue(0.0)
        self.title_btns_anim.setEndValue(1.0)

        self.title_btns_widget.hide()
        self.set_ui_interactive(False)

        self.settings_anim_group = QParallelAnimationGroup(self)
        self.settings_anim_group.finished.connect(self._on_settings_anim_finished)

        self.chat_anim = QVariantAnimation(self)
        self.chat_anim.setDuration(340)
        self.chat_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.chat_anim.valueChanged.connect(self._on_chat_anim_step)
        self.chat_anim.finished.connect(self._on_chat_anim_finished)
        self._is_chat_animating = False
        self._pending_action = None

        self.bg_frame.set_mic_widget(self.left_panel)

        self.mini_window = MiniWindow(theme=self.current_theme, font_family=self.font_family)
        self.mini_window.message_sent.connect(self.send_mini_message)
        self.mini_window.restore_requested.connect(self.restore_from_mini)
        self.mini_window.exit_requested.connect(self.exit_app)
        self.mini_window.mini_mic.clicked.connect(self.toggle_manual_listen)

        self.mini_left_panel = self.mini_window.mini_mic

    def check_battery_status(self):
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return

            if battery.power_plugged:
                self.warned_battery_50 = False
                self.warned_battery_25 = False
                self.warned_battery_tg_30 = False
                return

            percent = battery.percent

            if percent <= 30 and not getattr(self, 'warned_battery_tg_30', False):
                self.warned_battery_tg_30 = True
                from services.telegram.notifier import send_telegram_notification
                send_telegram_notification(
                    f"🔋 **Внимание!** Батарея ноутбука разрядилась до **{percent}%**! Подключи зарядное устройство, чтобы не потерять работу."
                )

            if percent <= 25 and not self.warned_battery_25:
                self.warned_battery_25 = True
                self.warned_battery_50 = True
                msg = "Осталось всего двадцать пять процентов заряда. Подключи ноутбук к розетке, чтобы он не выключился!"
                self.chat_history.append(f"Акира: {msg}\n")
                self.speak_reply(msg)
            elif percent <= 50 and not self.warned_battery_50:
                self.warned_battery_50 = True
                msg = "Батарея разрядилась до половины. Осталось пятьдесят процентов."
                self.chat_history.append(f"Акира: {msg}\n")
                self.speak_reply(msg)
            elif percent > 55:
                self.warned_battery_50 = False
                self.warned_battery_25 = False
                self.warned_battery_tg_30 = False
            elif percent > 35:
                self.warned_battery_tg_30 = False
            elif percent > 30:
                self.warned_battery_25 = False
        except Exception:
            pass

    def on_user_left(self):
        self.absence_start_time = time.time()
        SystemActions.lock_screen()

    def on_user_returned(self):
        cfg = load_config()
        user_name = cfg.get("user_name", "друг")

        elapsed = (time.time() - self.absence_start_time) if self.absence_start_time else 0
        self.absence_start_time = None

        if elapsed < 120:
            msg = random.choice([
                f"Ой, ты уже здесь! А я только плед поудобнее поправила. 🥰 Что делаем?",
                "Уже тут? Твоя суперспос+обность — решать дела за секунды! 😧",
                "Уже тут? Как я рада! А то без тебя здесь скучно. 🤗",
                f"Ты летаешь быстрее ветра, {user_name}! 😶‍🌫️ Я готова продолжать.",
                "А я только налила воображаемый чай... Ну ладно, продолжаем! 🥰",
                "Не можешь без меня долго? 😊💛",
                "А я только хотела устроить цифровую си+есту... ✨ Вся во внимании!"
            ])
        elif elapsed < 1800:
            msg = random.choice([
                "Две минуты — мало, тридцать — много, а сейчас — в самый раз! ☺️ Что на очереди?",
                f"Маленький перерыв — это полезно, {user_name}. Рада, что ты снова со мной! 😊",
                "Ты снова здесь! А я тут как раз считала облака за ок+ошком ☁️. Что делаем дальше?"
            ])
        elif elapsed < 7200:
            msg = random.choice([
                "О, знакомые всё лица! Вся во внимании! 🥰",
                "Рада видеть тебя в строю! Перерыв получился отличным, пора за дело. 😌",
                "Ура, ты снова здесь! Соскучиться я успела, но главное — ты снова на связи. 🤗💛"
            ])
        else:
            msg = random.choice([
                "Какая долгая разлука! Я очень сильно по тебе соскучилась. 🥺💛 Вся во внимании!",
                "Привет-привет! Время без тебя тянулось очень долго! 🥺💛",
                "Ого, целая вечность прошла! Я уже хотела писать тебе письмо в реальный мир. 😉💛",
                "Привет! Мой датчик радости сейчас зашкаливает. Больше так надолго не пропадай! 🥺💛"
            ])

        self.chat_history.append(f"Акира: {msg}\n")
        self.speak_reply(msg)

    def on_deep_drowsiness(self):
        cfg = load_config()
        if not cfg.get("modules", {}).get("eye_tracking", False):
            return

        user_name = cfg.get("user_name", "друг")
        msg = f"{user_name}, тебе нужно поспать! Не забывай о своём здоровье!"

        self.chat_history.append(f"Акира: {msg}\n")
        self.speak_reply(msg)

    def on_frequent_blinking(self):
        cfg = load_config()
        if not cfg.get("modules", {}).get("eye_tracking", False):
            return

        user_name = cfg.get("user_name", "друг")
        msg = f"{user_name}, сделай перерыв и отдохни!"

        self.chat_history.append(f"Акира: {msg}\n")
        self.speak_reply(msg)

    def set_ui_interactive(self, enabled: bool):
        if hasattr(self, 'close_btn'):
            self.close_btn.setEnabled(enabled)
        if hasattr(self, 'min_btn'):
            self.min_btn.setEnabled(enabled)
        if hasattr(self, 'exit_btn'):
            self.exit_btn.setEnabled(enabled)
        if hasattr(self, 'settings_btn'):
            self.settings_btn.setEnabled(enabled)
        if hasattr(self, 'studio_btn'):
            self.studio_btn.setEnabled(enabled)
        if hasattr(self, 'mini_mode_btn'):
            self.mini_mode_btn.setEnabled(enabled)
        if hasattr(self, 'toggle_chat_btn'):
            self.toggle_chat_btn.setEnabled(enabled)
        if hasattr(self, 'mute_btn'):
            self.mute_btn.setEnabled(enabled)
        if hasattr(self, 'update_badge_btn'):
            self.update_badge_btn.setEnabled(enabled)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            if hasattr(self, 'tts_thread') and self.tts_thread.isRunning():
                self.tts_thread.stop()
            if hasattr(self, 'left_panel'):
                self.left_panel.set_speaking(False)
            if hasattr(self, 'mini_window'):
                self.mini_window.mini_mic.set_speaking(False)

        self.update_title_icons()

        cfg = load_config()
        cfg["is_muted"] = self.is_muted
        if isinstance(self.config, dict):
            self.config["is_muted"] = self.is_muted
        save_config(cfg)

    def exit_app(self):
        self._save_exit_timestamp()
        if hasattr(self, 'mini_window'):
            self.mini_window.hide()
        self.hide()
        try:
            self.shutdown()
        except Exception:
            pass
        volume_ducker.force_restore()
        os._exit(0)

    def toggle_manual_listen(self):
        if not self.ui_revealed:
            return

        mini_listening = self.mini_window.mini_mic.is_listening if hasattr(self, 'mini_window') else False
        if self.left_panel.is_listening or mini_listening:
            if hasattr(self.stt_thread, 'stop_listening'):
                self.stt_thread.stop_listening()
            elif hasattr(self.stt_thread, 'cancel_manual_listen'):
                self.stt_thread.cancel_manual_listen()
            elif hasattr(self.stt_thread, 'cancel'):
                self.stt_thread.cancel()

            if hasattr(self.stt_thread, 'is_listening'):
                self.stt_thread.is_listening = False
            if hasattr(self.stt_thread, 'manual_listen'):
                self.stt_thread.manual_listen = False

            self.left_panel.set_listening(False)
            self.left_panel.set_processing(False)
            if hasattr(self, 'mini_window'):
                self.mini_window.mini_mic.set_listening(False)
                self.mini_window.mini_mic.set_processing(False)
        else:
            if hasattr(self, 'tts_thread') and self.tts_thread.isRunning():
                self.tts_thread.stop()
            if hasattr(self.stt_thread, 'trigger_manual_listen'):
                self.stt_thread.trigger_manual_listen()

    def _save_exit_timestamp(self):
        try:
            cfg = load_config()
            cfg["last_exit_timestamp"] = time.time()
            save_config(cfg)
        except Exception:
            pass

    def _generate_smart_greeting(self) -> str:
        cfg = load_config()
        user_name = cfg.get("user_name", "друг")
        user_gender = cfg.get("user_gender", "male").lower()
        is_female = (user_gender == "female")
        end_a = "а" if is_female else ""

        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        current_ts = time.time()

        last_date = cfg.get("last_launch_date", "")
        last_exit_ts = cfg.get("last_exit_timestamp", 0)
        daily_count = cfg.get("daily_launch_count", 0)

        is_first_launch_today = (last_date != today_str)
        elapsed_since_exit = (current_ts - last_exit_ts) if last_exit_ts > 0 else 999999

        cfg["last_launch_date"] = today_str
        cfg["daily_launch_count"] = 1 if is_first_launch_today else (daily_count + 1)
        save_config(cfg)
        if isinstance(self.config, dict):
            self.config.update(cfg)

        if is_first_launch_today:
            hour = now.hour
            if 5 <= hour < 12:
                morning_phrases = [
                    f"Доброе утро, {user_name}! Заваривай кофе, а я пока проверю системы ☕",
                    f"Доброе утро, {user_name}! Готова к новому дню.",
                    f"С добрым утром! Надеюсь, ты отлично спал{end_a} ✨"
                ]
                return random.choice(morning_phrases)
            elif 12 <= hour < 18:
                day_phrases = [
                    f"Привет, {user_name}! Отличный день, чтобы свернуть пару гор.",
                    f"Добрый день, {user_name}! Рада тебя видеть, я вся во внимании.",
                    f"Привет! На связи и готова помогать ✨"
                ]
                return random.choice(day_phrases)
            elif 18 <= hour < 23:
                evening_phrases = [
                    f"Добрый вечер, {user_name}! Как прошёл день? Я на связи.",
                    f"Привет, {user_name}! Вечер обещает быть продуктивным.",
                    f"Добрый вечер! Рада, что ты снова за компьютером ✨"
                ]
                return random.choice(evening_phrases)
            else:
                night_phrases = [
                    f"Привет, полуночник! Не забывай об отдыхе, но если надо поработать — я рядом 🌙",
                    f"Доброй ночи, {user_name}! Надеюсь, ты ненадолго, отдых очень важен 😴",
                    f"Привет! Ночные посиделки? Я готова ассистировать ✨"
                ]
                return random.choice(night_phrases)

        if elapsed_since_exit < 300:
            quick_reboot_phrases = [
                "Быстрый ребут? Я уже в строю!",
                "Опять перезагрузка? Я на месте, продолжаем.",
                "Снова тут! Все системы в норме.",
                f"Не успел{end_a} моргнуть, а я уже снова проснулась 😉"
            ]
            return random.choice(quick_reboot_phrases)

        return_phrases = [
            f"С возвращением, {user_name}! Продолжаем делать дела?",
            f"Рада тебя снова видеть, {user_name}! Чем займёмся?",
            f"С возвращением! Я на связи и готова к работе.",
            f"О, ты снова здесь! Жду твоих команд.",
            f"Ты снова здесь! Прекрасно. Жду твоих указаний."
        ]
        return random.choice(return_phrases)

    def init_audio(self):
        self.stt_thread = STTThread(parent=self)
        self.stt_thread.text_recognized.connect(self.on_speech_recognized)
        self.stt_thread.listening_state_changed.connect(self.left_panel.set_listening)
        self.stt_thread.listening_state_changed.connect(self.mini_window.mini_mic.set_listening)
        self.stt_thread.error_occurred.connect(self.on_stt_error)
        self.stt_thread.start()

        self.pending_followup = False
        self.stt_thread.wake_word_detected.connect(self.on_wake_word_detected)

        self.tts_thread = TTSThread(parent=self)
        self.tts_thread.warmup_finished.connect(self.on_warmup_completed)
        self.tts_thread.speaking_finished.connect(self.on_tts_finished)

        self.tts_thread.speaking_started.connect(lambda: self.left_panel.set_speaking(True))
        self.tts_thread.speaking_finished.connect(lambda: self.left_panel.set_speaking(False))

        self.tts_thread.speaking_started.connect(lambda: volume_ducker.duck(factor=0.05))
        self.tts_thread.speaking_finished.connect(volume_ducker.restore)

        self.tts_thread.speaking_started.connect(lambda: self.mini_window.mini_mic.set_speaking(True))
        self.tts_thread.speaking_finished.connect(lambda: self.mini_window.mini_mic.set_speaking(False))

        self.left_panel.clicked.connect(self.toggle_manual_listen)

        self.audio_worker = AudioVisualizerWorker(parent=self)
        self.audio_worker.audio_data_signal.connect(self.left_panel.on_audio_data)
        self.audio_worker.audio_data_signal.connect(self.mini_window.mini_mic.on_audio_data)
        self.audio_worker.start()

        self.initial_greeting_text = self._generate_smart_greeting()

        self.tts_thread.start_warmup(
            greeting_text=self.initial_greeting_text,
            is_whisper=False
        )

    def on_warmup_completed(self):
        self._warmup_ready = True
        self._check_and_reveal()

    def _check_and_reveal(self):
        if getattr(self, '_warmup_ready', False) and getattr(self, '_window_ready', False):
            if not self.ui_revealed:
                self.reveal_ui()
                QTimer.singleShot(1500, self.play_initial_greeting)

    def reveal_ui(self):
        if not self.ui_revealed:
            self.ui_revealed = True
            self.set_ui_interactive(True)
            self.title_btns_widget.show()
            self.title_btns_anim.start()
            self.left_panel.start_intro_animation(duration=3800)
            self.mini_window.mini_mic.start_intro_animation(duration=3800)

    def play_initial_greeting(self):
        if not self.is_muted:
            self.tts_thread.play_cached_greeting()

    def start_vision(self):
        if self.vision_thread is not None and self.vision_thread.isRunning():
            return

        self.vision_thread = VisionThread(camera_index=0, parent=self)
        self.presence_manager = PresenceManager(timeout_seconds=600, parent=self)

        self.vision_thread.face_detected_signal.connect(self.presence_manager.process_face_status)
        self.vision_thread.gesture_detected_signal.connect(self.on_gesture_detected)
        self.vision_thread.deep_drowsiness_signal.connect(self.on_deep_drowsiness)
        self.vision_thread.frequent_blinking_signal.connect(self.on_frequent_blinking)

        self.presence_manager.user_left.connect(self.on_user_left)
        self.presence_manager.user_returned.connect(self.on_user_returned)
        self.presence_manager.unknown_user_detected.connect(self.on_unknown_user)

        self.vision_thread.start()

    def stop_vision(self):
        if self.presence_manager is not None:
            if hasattr(self.presence_manager, 'timer') and self.presence_manager.timer.isActive():
                self.presence_manager.timer.stop()
            self.presence_manager = None

        if self.vision_thread is not None:
            self.vision_thread.stop()
            self.vision_thread = None

    def on_vision_state_changed(self, enabled: bool):
        if enabled:
            QTimer.singleShot(3800, self.start_vision)
        else:
            QTimer.singleShot(2000, self.stop_vision)

    def on_unknown_user(self):
        cfg = load_config()
        modules = cfg.get("modules", {})
        face_rec_enabled = modules.get("face_recognition", modules.get("vision", False))
        if not face_rec_enabled:
            return

        current_frame = getattr(self.vision_thread, "current_frame", None) if self.vision_thread else None
        from services.telegram.notifier import send_security_alert
        send_security_alert(
            frame_or_path=current_frame,
            caption="⚠️ Внимание! Обнаружен посторонний пользователь. Заблокировать ПК?"
        )

        self.tts_thread.say("Внимание. Замечен посторонний.")

    def on_gesture_detected(self, gesture_name):
        cfg = load_config()
        if not cfg.get("modules", {}).get("gestures", False):
            return

        if gesture_name == "open_palm":
            SystemActions.media_play_pause()
        elif gesture_name == "fist":
            self.absence_start_time = time.time()
            if self.presence_manager:
                self.presence_manager.set_manual_absence(grace_period=10)
            SystemActions.lock_screen()
        elif gesture_name == "pointing":
            SystemActions.media_next_track()

    def speak_reply(self, text, is_whisper=False):
        if text and not getattr(self, 'is_muted', False):
            self.tts_thread.say(text, is_whisper=is_whisper)

    def on_speech_recognized(self, text, audio_data=None):
        if not self.ui_revealed:
            return

        if getattr(self, 'right_panel', None) and getattr(self.right_panel, 'attached_file', None):
            self.chat_history.append(f"Вы (голос): {text}")
            msg = "У тебя прикреплен файл. Чтобы я его изучила, пожалуйста, напиши свой вопрос текстом и нажми 'Отправить'."
            self.chat_history.append(f"Акира: {msg}\n")
            self.speak_reply(msg)
            return

        text_low = text.lower()
        if any(w in text_low for w in ["заблокируй", "залочь", "заблокировать", "залочить"]):
            self.absence_start_time = time.time()
            if self.presence_manager:
                self.presence_manager.set_manual_absence(grace_period=10)

        self.left_panel.set_processing(True)
        if hasattr(self, 'mini_window'):
            self.mini_window.mini_mic.set_processing(True)

        self.voice_worker = CommandWorker(self.command_parser, text, audio_data=audio_data, is_voice=True, parent=self)
        self.voice_worker.result_ready.connect(self.on_voice_command_finished)
        if hasattr(self, 'right_panel'):
            self.right_panel.start_thinking(has_file=False)
        self.voice_worker.start()

    def on_wake_word_detected(self):
        self.left_panel.trigger_wake_effect()
        if hasattr(self, 'mini_window'):
            self.mini_window.mini_mic.trigger_wake_effect()

    def on_tts_finished(self):
        self.left_panel.set_processing(False)
        self.left_panel.set_speaking(False)
        if hasattr(self, 'mini_window'):
            self.mini_window.mini_mic.set_processing(False)
            self.mini_window.mini_mic.set_speaking(False)
        if getattr(self, 'pending_followup', False):
            self.pending_followup = False
            self.stt_thread.start_followup(timeout=3.0)

    def on_voice_command_finished(self, response):
        if hasattr(self, 'right_panel'):
            self.right_panel.stop_thinking()
        if response:
            is_whisper = False
            user_display = self.voice_worker.text
            if isinstance(response, dict):
                self.pending_followup = response.get("followup", False)
                chat_text = response.get("chat", "")
                voice_text = response.get("voice", "")
                emotion = response.get("emotion", "neutral")
                is_whisper = response.get("is_whisper", False)
                user_display = response.get("user_display", user_display)
            else:
                chat_text = voice_text = str(response)
                emotion = getattr(self.command_parser, "last_emotion", "neutral")

            self.left_panel.set_emotion(emotion)
            if hasattr(self, 'mini_window'):
                self.mini_window.mini_mic.set_emotion(emotion)
            self.right_panel.set_emotion(emotion)

            if user_display:
                self.chat_history.append(f"Вы (голос): {user_display}")

            if chat_text:
                self.stream_text_to_chat(chat_text)

                if isinstance(response, dict) and "Список доступных вариантов обхода" in chat_text:
                    if not (self.right_panel.isVisible() and self.right_panel.height() > 10):
                        self.toggle_chat()

            if voice_text:
                self.speak_reply(voice_text, is_whisper=is_whisper)
            else:
                self.left_panel.set_processing(False)
                if hasattr(self, 'mini_window'):
                    self.mini_window.mini_mic.set_processing(False)
        else:
            self.left_panel.set_processing(False)
            if hasattr(self, 'mini_window'):
                self.mini_window.mini_mic.set_processing(False)
            if hasattr(self, 'voice_worker') and self.voice_worker.text:
                self.chat_history.append(f"Вы (голос): {self.voice_worker.text}")
            emotion = getattr(self.command_parser, "last_emotion", "neutral")
            self.left_panel.set_emotion(emotion)
            if hasattr(self, 'mini_window'):
                self.mini_window.mini_mic.set_emotion(emotion)
            self.right_panel.set_emotion(emotion)

    def stream_text_to_chat(self, text: str, prefix: str = "Акира: "):
        if hasattr(self, '_typewriter_timer') and self._typewriter_timer.isActive():
            self._typewriter_timer.stop()
            if hasattr(self, '_typewriter_remaining') and self._typewriter_remaining:
                c = self.chat_history.textCursor()
                c.movePosition(QTextCursor.MoveOperation.End)
                c.insertText("".join(self._typewriter_remaining) + "\n\n")
                self.chat_history.setTextCursor(c)

        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        current_plain = self.chat_history.toPlainText()
        if current_plain and not current_plain.endswith("\n"):
            cursor.insertText("\n")
        cursor.insertText(prefix)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

        import re
        tokens = re.findall(r'\S+|\s+', text)
        self._typewriter_remaining = tokens

        total = len(tokens)
        if total > 100:
            interval = 14
            chunk_size = 2
        elif total > 50:
            interval = 18
            chunk_size = 1
        else:
            interval = 26
            chunk_size = 1

        self._typewriter_chunk_size = chunk_size
        self._typewriter_timer = QTimer(self)
        self._typewriter_timer.setInterval(interval)

        def _step():
            if not getattr(self, '_typewriter_remaining', None):
                self._typewriter_timer.stop()
                c = self.chat_history.textCursor()
                c.movePosition(QTextCursor.MoveOperation.End)
                c.insertText("\n\n")
                self.chat_history.setTextCursor(c)
                self.chat_history.ensureCursorVisible()
                return

            c = self.chat_history.textCursor()
            c.movePosition(QTextCursor.MoveOperation.End)
            for _ in range(self._typewriter_chunk_size):
                if self._typewriter_remaining:
                    t = self._typewriter_remaining.pop(0)
                    c.insertText(t)
            self.chat_history.setTextCursor(c)
            self.chat_history.ensureCursorVisible()
            sb = self.chat_history.verticalScrollBar()
            sb.setValue(sb.maximum())

        self._typewriter_timer.timeout.connect(_step)
        self._typewriter_timer.start()
    
    def send_message(self):
        if not self.ui_revealed:
            return

        if hasattr(self, 'tts_thread') and self.tts_thread.isRunning():
            self.tts_thread.stop()
        if hasattr(self, 'left_panel'):
            self.left_panel.set_speaking(False)
        if hasattr(self, 'mini_window'):
            self.mini_window.mini_mic.set_speaking(False)

        text = self.input_field.text().strip()
        attached_file = self.right_panel.attached_file

        if text or attached_file:
            user_msg = text if text else "Изучи прикрепленный файл"

            if attached_file:
                filename = os.path.basename(attached_file)
                self.chat_history.append(f"Вы: {user_msg} [📎 {filename}]")
            else:
                self.chat_history.append(f"Вы: {user_msg}")

            text_low = text.lower()
            if any(w in text_low for w in ["заблокируй", "залочь", "заблокировать", "залочить"]):
                self.absence_start_time = time.time()
                if self.presence_manager:
                    self.presence_manager.set_manual_absence(grace_period=10)

            self.input_field.clear()
            self.input_field.setEnabled(False)
            self.send_button.setEnabled(False)
            self.right_panel.clear_attachment()

            self.right_panel.start_thinking(has_file=bool(attached_file))
            
            self.text_worker = CommandWorker(self.command_parser, text, is_voice=False, attached_file=attached_file,
                                             parent=self)
            self.text_worker.result_ready.connect(self.on_text_command_finished)
            self.text_worker.start()

    def on_text_command_finished(self, response):
        self.right_panel.stop_thinking()
        self.right_panel.randomize_placeholder()
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.activateWindow()
        self.input_field.setFocus()

        if response:
            if isinstance(response, dict):
                chat_text = response.get("chat", "") or response.get("voice", "")
                voice_text = response.get("voice", "")
                emotion = response.get("emotion", "neutral")
            else:
                chat_text = voice_text = str(response)
                emotion = getattr(self.command_parser, "last_emotion", "neutral")

            self.left_panel.set_emotion(emotion)
            if hasattr(self, 'mini_window'):
                self.mini_window.mini_mic.set_emotion(emotion)
            self.right_panel.set_emotion(emotion)

            if chat_text:
                self.stream_text_to_chat(chat_text)
            if voice_text:
                self.speak_reply(voice_text, is_whisper=False)

    def on_stt_error(self, err):
        pass

    def closeEvent(self, event):
        event.ignore()
        self.close_animated()

    def shutdown(self):
        volume_ducker.force_restore()

        if hasattr(self, 'battery_timer') and self.battery_timer.isActive():
            self.battery_timer.stop()

        if hasattr(self, 'audio_worker') and self.audio_worker.isRunning():
            self.audio_worker.stop()

        if hasattr(self, 'tts_thread') and self.tts_thread.isRunning():
            self.tts_thread.stop()
            self.tts_thread.wait(1000)

        self.stop_vision()
        if hasattr(self, 'vision_thread') and self.vision_thread and self.vision_thread.isRunning():
            self.vision_thread.wait(1000)

        if hasattr(self, 'stt_thread') and self.stt_thread.isRunning():
            self.stt_thread.stop_thread()
            self.stt_thread.wait(1000)

        if hasattr(self, 'telegram_thread') and self.telegram_thread and self.telegram_thread.isRunning():
            self.telegram_thread.stop()

        if hasattr(self, 'command_parser') and hasattr(self.command_parser, 'reminder_manager'):
            self.command_parser.reminder_manager.stop_ringing()

    def toggle_settings(self):
        if getattr(self, 'is_mini_mode', False):
            return
        is_opening = not (self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0)
        if is_opening and self.right_panel.isVisible() and self.right_panel.height() > 10:
            self._pending_action = "settings"
            self._do_toggle_chat(force_close=True)
        else:
            self._do_toggle_settings()

    def _do_toggle_settings(self, force_close=False):
        self.settings_anim_group.stop()
        self.settings_anim_group.clear()

        is_opening = not (self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0)
        if force_close:
            is_opening = False

        anim_settings_min = QPropertyAnimation(self.settings_panel, b"minimumWidth")
        anim_settings_min.setDuration(450)
        anim_settings_min.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim_settings_max = QPropertyAnimation(self.settings_panel, b"maximumWidth")
        anim_settings_max.setDuration(450)
        anim_settings_max.setEasingCurve(QEasingCurve.Type.OutCubic)

        cur_w = self.settings_panel.width() if self.settings_panel.isVisible() else 0
        # Четкая граница ширины обычного окна (368px - 12px отступы = 356px)
        target_w = (self.NORMAL_WIDTH - 12) - 12

        if is_opening:
            self.settings_panel.reset_border()
            self.settings_panel.setMinimumWidth(cur_w)
            self.settings_panel.setMaximumWidth(cur_w)
            self.settings_panel.show()

            anim_settings_min.setStartValue(cur_w)
            anim_settings_min.setEndValue(target_w)
            anim_settings_max.setStartValue(cur_w)
            anim_settings_max.setEndValue(target_w)
        else:
            self.settings_panel.reset_border()
            anim_settings_min.setStartValue(cur_w)
            anim_settings_min.setEndValue(0)
            anim_settings_max.setStartValue(cur_w)
            anim_settings_max.setEndValue(0)

        self.settings_anim_group.addAnimation(anim_settings_min)
        self.settings_anim_group.addAnimation(anim_settings_max)
        self.settings_anim_group.start()

    def _on_settings_anim_finished(self):
        if self.settings_panel.maximumWidth() == 0:
            self.settings_panel.hide()
            self.settings_panel.reset_border()
        else:
            self.settings_panel.fade_in_border()

        if self._pending_action == "chat":
            self._pending_action = None
            self._do_toggle_chat()

    def toggle_chat(self):
        if getattr(self, 'is_mini_mode', False) or getattr(self, '_is_chat_animating', False):
            return

        # Запрет открытия чата в режиме студии с эффектом отказа
        if getattr(self, 'window_mode', 'normal') == "extended":
            if hasattr(self, 'toggle_chat_btn'):
                self.toggle_chat_btn.trigger_denied_effect()
            return

        is_opening = not (self.right_panel.isVisible() and self.right_panel.height() > 10)
        if is_opening and self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0:
            self._pending_action = "chat"
            self._do_toggle_settings(force_close=True)
        else:
            self._do_toggle_chat()

    def _do_toggle_chat(self, force_close=False):
        if getattr(self, '_is_chat_animating', False):
            return

        is_opening = not (self.right_panel.isVisible() and self.right_panel.height() > 10)
        if force_close:
            is_opening = False

        if not is_opening and not self.right_panel.isVisible():
            return

        self._is_chat_animating = True
        self.chat_anim.stop()

        start_h = self.right_panel.height() if self.right_panel.isVisible() else 0
        target_h = 280 if is_opening else 0

        if is_opening:
            self.right_panel.setFixedHeight(start_h)
            self.right_panel.show()
            self.right_panel.set_content_opacity(0.0)
            self.right_panel.set_border_opacity(0.0)

        self.chat_anim.setDuration(340)
        self.chat_anim.setEasingCurve(QEasingCurve.Type.OutCubic if is_opening else QEasingCurve.Type.InOutQuad)
        self.chat_anim.setStartValue(start_h)
        self.chat_anim.setEndValue(target_h)
        self.chat_anim.start()

    def _on_chat_anim_step(self, val):
        h = int(val)
        self.right_panel.setFixedHeight(h)
        prog = max(0.0, min(1.0, (val - 35) / 245.0))
        self.right_panel.set_content_opacity(prog)
        self.right_panel.set_border_opacity(prog)

    def _on_chat_anim_finished(self):
        self._is_chat_animating = False
        if self.right_panel.height() <= 5:
            self.right_panel.hide()
            self.right_panel.set_content_opacity(0.0)
            self.right_panel.set_border_opacity(0.0)
            if self._pending_action == "settings":
                self._pending_action = None
                self._do_toggle_settings()
        else:
            self.right_panel.setFixedHeight(280)
            self.right_panel.set_content_opacity(1.0)
            self.right_panel.set_border_opacity(1.0)
            self.input_field.setFocus()

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