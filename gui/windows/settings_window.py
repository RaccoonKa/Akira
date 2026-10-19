import os
import sys
import math
import winreg
import shutil
import wave
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QComboBox, QDialog,
    QFileDialog, QSlider, QProgressBar, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPoint, QPointF, pyqtSignal,
    QVariantAnimation, QEasingCurve, QUrl, QSize, QByteArray,
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QBrush, QPainterPath,
    QFont, QFontDatabase, QGuiApplication, QIcon, QPixmap
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtMultimedia import QSoundEffect
from core.utils.config import load_config, save_config, get_user_data_path, get_resource_path
from core.utils.updater import CURRENT_VERSION, DownloaderThread, apply_update_and_restart
from gui.dialogs.voice_enrollment_dialog import VoiceEnrollmentDialog
from core.nlp.speaker_verifier import SpeakerVerifier
from gui.dialogs.yandex_auth_dialog import YandexAuthDialog
from gui.dialogs.yandex_iot_auth_dialog import YandexIotAuthDialog
from gui.dialogs.spotify_auth_dialog import SpotifyAuthDialog
from gui.dialogs.gigachat_auth_dialog import GigaChatAuthDialog
from services.spotify.spotify_manager import SpotifyManager
from gui.dialogs.mode_config_dialog import ModeConfigDialog
from gui.dialogs.face_manager_dialog import FaceManagerDialog


def is_valid_wav(path: str) -> bool:
    if not path or not os.path.isfile(path) or os.path.getsize(path) < 44:
        return False
    try:
        with wave.open(path, "rb") as w:
            channels = w.getnchannels()
            sample_width = w.getsampwidth()
            framerate = w.getframerate()
            frames = w.getnframes()
            if channels <= 0 or sample_width <= 0 or framerate <= 0 or frames <= 0:
                return False
            data = w.readframes(min(frames, 1024))
            if not data:
                return False
            return True
    except Exception:
        return False


def convert_audio_to_wav(src_path: str, dst_path: str) -> bool:
    if not src_path or not os.path.isfile(src_path) or os.path.getsize(src_path) < 100:
        return False

    if src_path.lower().endswith(".wav") and is_valid_wav(src_path):
        try:
            shutil.copy(src_path, dst_path)
            if is_valid_wav(dst_path):
                return True
        except Exception:
            pass

    try:
        import soundfile as sf
        data, sr = sf.read(src_path)
        if len(data) > 0 and sr > 0:
            sf.write(dst_path, data, sr, format="WAV")
            if is_valid_wav(dst_path):
                return True
    except Exception:
        pass

    try:
        from pydub import AudioSegment
        sound = AudioSegment.from_file(src_path)
        if len(sound) > 0:
            sound.export(dst_path, format="wav")
            if is_valid_wav(dst_path):
                return True
    except Exception:
        pass

    try:
        import torchaudio
        waveform, sr = torchaudio.load(src_path)
        if waveform.numel() > 0 and sr > 0:
            torchaudio.save(dst_path, waveform, sr)
            if is_valid_wav(dst_path):
                return True
    except Exception:
        pass

    try:
        import subprocess
        res = subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, dst_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if res.returncode == 0 and is_valid_wav(dst_path):
            return True
    except Exception:
        pass

    if os.path.exists(dst_path):
        try:
            os.remove(dst_path)
        except Exception:
            pass

    return False


SPEECH_HINTS = {
    "autostart": "Включив автозапуск, я буду просыпаться одновременно с твоим компьютером. Тебе даже не придётся искать мою иконку — я сразу буду тут, готова помогать.",
    "theme": "Выбирай комфортное оформление интерфейса: тёплая тёмная ночь или светлый шёлковый фарфор.",
    "framerate": "Выбирай частоту кадров, сбалансированный режим на шестьдесят кадров подходит для слабого компьютера, а ультра-режим на сто двадцать кадров делает частицы и анимации идеально мягкими.",
    "voice_volume": "Ползунок регулирует громкость моей речи относительно системного звука!",
    "alarm_sound": "Здесь ты можешь выбрать одну из трёх моих мелодий для будильника или загрузить свой собственный трек с компьютера. Кнопкой рядом можно сразу послушать, как он звучит!",
    "user_gender": "Выбери свой пол, чтобы я правильно обращалась к тебе и никогда не путала окончания слов!",
    "city": "Укажи свой город, чтобы я могла точно сообщать текущую погоду и прогноз без лишних уточнений.",
    "vpn_service": "Выбери, какую виртуальную сеть ты используешь. Я смогу автоматически запускать и переключать её по голосовой команде.",
    "telegram_pair": "Включив эту функцию, я смогу дистанционно управлять твоим компьютером или просто общаться с тобой прямо в телеграме. Смогу управлять твоей камерой, питанием, статусом компьютера.",
    "voice_id": "Здесь ты можешь записать слепок своего голоса, чтобы я откликалась только на тебя и не реагировала на чужие голоса, стримы или телевизор. А после верификации создателя сюда можно добавить и профили друзей!",
    "face_recognition": "Если включишь эту функцию, я буду узнавать тебя в лицо. Смогу радостно здороваться при твоем возвращении и защищать систему от чужих глаз.",
    "eye_tracking": "С этой функцией, я смогу следить за твоими глазками. Если замечу, что часто моргаешь или долго сидишь с закрытыми глазами — я заботливо предложу отдохнуть!",
    "gestures": "С жестами я смогу понимать тебя без слов. Покажешь кулак — заблокирую твой компьютер, чтобы никто не получил к нему доступ кроме тебя. Покажешь ладонь — поставлю музыку на паузу. Почти магия!",
    "music_service": "Выбери, где мне включать музыку! Если переключатель включен — я буду ставить треки и запускать твою волну рекомендаций в Спотике, а если выключен — в Яндексе.",
    "gigachat": "Это мой главный ум и вдохновение! Подключив GigaChat, ты дашь мне возможность болтать с тобой обо всём на свете, шутить и отвечать на любые вопросы.",
    "yandex": "Доверь мне свой плейлист! Я смогу запускать твою волну, включать треки под настроение и ставить лайки.",
    "yandex_iot": "Подключив Умный дом, я смогу управлять твоим освещением, розетками и сценариями Дома с Алисой.",
    "spotify": "С этой кнопкой я смогу подключиться к твоему Спотифаю, включать любимые треки и запускать рекомендации!"
}

API_GUIDES = {
    "telegram_pair": {
        "title": "Привязка Telegram-бота",
        "text": "1. Нажми кнопку 'QR-КОД' в настройках системы.\n"
                "2. Отсканируй появившийся QR-код камерой телефона или нажми 'Открыть в Telegram'.\n"
                "3. В открывшемся диалоге нажми кнопку 'Старт' (Start).\n"
                "4. Акира автоматически сохранит профиль и привяжет удалённый пульт управления к твоему аккаунту!"
    },
    "gigachat": {
        "title": "Подключение GigaChat API",
        "text": "1. Нажми 'НАСТРОИТЬ' и перейди на портал developers.sber.ru по кнопке.\n"
                "2. Войди через Сбер ID и создай проект с типом GigaChat API (тариф Freemium).\n"
                "3. В карточке проекта сгенерируй Client Secret.\n"
                "4. Скопируй строку 'Авторизационные данные' (Base64) и нажми 'Вставить' в окне Акиры."
    },
    "yandex": {
        "title": "Привязка Яндекс Музыки",
        "text": "1. Нажми кнопку 'АВТОРИЗОВАТЬ'.\n"
                "2. В появившемся окне отобразится одноразовый код, а в браузере откроется страница входа.\n"
                "3. Введи код на сайте и нажми 'Разрешить'.\n"
                "4. Акира сохранит токен и сразу сможет воспроизводить треки и Мою волну."
    },
    "yandex_iot": {
        "title": "Подключение Дома с Алисой",
        "text": "1. Перейди на oauth.yandex.ru/client/new\n"
                "2. Укажи название (например, Akira Smart Home), выбери платформу 'Веб-сервисы' и добавь Redirect URI: http://localhost:8585/callback\n"
                "3. В правах доступа отметь 'Умный дом' (iot:view и iot:control).\n"
                "4. Скопируй полученный Client ID в окно подключения Акиры и нажми 'Войти через браузер'.\n"
                "5. На открывшейся странице нажми 'Разрешить' — Акира сама получит токен и сможет управлять светом и приборами."
    },
    "spotify": {
        "title": "Подключение Spotify",
        "text": "1. Перейди на developer.spotify.com/dashboard и авторизуйся.\n"
                "2. Нажми 'Create App', укажи название (например, Akira Music).\n"
                "3. В настройках приложения (Settings) найди раздел Redirect URIs и добавь адрес: http://127.0.0.1:8888/callback\n"
                "4. Скопируй Client ID, вставь его в окно авторизации и нажми 'Войти через браузер'.\n"
                "5. В браузере нажми 'Agree' — Акира подключится к твоему Спотифаю без секретных ключей."
    }
}

SVG_CHEVRON_DOWN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<polyline points="6 9 12 15 18 9"/>
</svg>"""

SVG_CHEVRON_RIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<polyline points="9 18 15 12 9 6"/>
</svg>"""


def render_svg_icon(svg_xml: str, color: str, size: int = 14) -> QIcon:
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


class BentoCard(QFrame):
    def __init__(self, title_text: str, font_family: str, parent=None, expanded: bool = False):
        super().__init__(parent)
        self.setObjectName("BentoCard")
        self.font_family = font_family
        self.is_expanded = expanded
        self.current_theme = "dark"
        self.target_height = 0
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(10, 8, 10, 8)
        self.card_layout.setSpacing(0)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        if title_text:
            self.header_widget = QWidget(self)
            self.header_widget.setFixedHeight(24)
            self.header_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            self.header_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            h_layout = QHBoxLayout(self.header_widget)
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(6)

            self.header_lbl = QLabel(title_text, self.header_widget)
            self.header_lbl.setObjectName("BentoSectionTitle")
            self.header_lbl.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
            self.header_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            h_layout.addWidget(self.header_lbl)
            h_layout.addStretch()

            self.arrow_btn = QPushButton(self.header_widget)
            self.arrow_btn.setFixedSize(20, 20)
            self.arrow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.arrow_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.arrow_btn.setStyleSheet("background: transparent; border: none; padding: 0px;")
            self.arrow_btn.clicked.connect(self.toggle_expanded)
            h_layout.addWidget(self.arrow_btn)

            self.card_layout.addWidget(self.header_widget)
            self.header_widget.mousePressEvent = self._on_header_clicked

        self.content_widget = QWidget(self)
        self.content_widget.setObjectName("BentoContentWidget")
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        self.content_layout.setSpacing(6)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.card_layout.addWidget(self.content_widget)

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(320)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.valueChanged.connect(self._on_anim_step)
        self.anim.finished.connect(self._on_anim_finished)

        if not self.is_expanded:
            self.content_widget.setFixedHeight(0)
            self.content_widget.setVisible(False)
        else:
            self.content_widget.setVisible(True)

        self.update_arrow()

    def _on_header_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_expanded()
            event.accept()

    def toggle_expanded(self):
        self.set_expanded(not self.is_expanded)

    def _sync_target_height(self):
        if self.is_expanded and self.anim.state() != QVariantAnimation.State.Running:
            self.content_layout.activate()
            h = self.content_layout.sizeHint().height()
            if h > 0:
                self.target_height = h
                self.content_widget.setFixedHeight(h)
                self.updateGeometry()

    def set_expanded(self, state: bool):
        if self.is_expanded == state and self.content_widget.isVisible() == state:
            return

        self.is_expanded = state
        self.update_arrow()
        self.anim.stop()

        if state:
            self.content_widget.setVisible(True)
            self.content_widget.setMinimumHeight(0)
            self.content_widget.setMaximumHeight(16777215)
            self.content_layout.activate()
            target_h = self.content_layout.sizeHint().height()
            if target_h <= 0:
                target_h = 240
            self.target_height = target_h

            self.content_widget.setFixedHeight(0)
            self.anim.setStartValue(0)
            self.anim.setEndValue(target_h)
            self.anim.start()
        else:
            current_h = self.content_widget.height()
            if current_h <= 0:
                current_h = self.content_layout.sizeHint().height()
            self.target_height = current_h
            self.anim.setStartValue(current_h)
            self.anim.setEndValue(0)
            self.anim.start()

    def _on_anim_step(self, val):
        self.content_widget.setFixedHeight(int(val))
        self.updateGeometry()

    def _on_anim_finished(self):
        if self.is_expanded:
            self.content_widget.setFixedHeight(self.target_height)
        else:
            self.content_widget.setFixedHeight(0)
            self.content_widget.setVisible(False)
        self.updateGeometry()

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update_arrow()

    def update_arrow(self):
        if hasattr(self, 'arrow_btn'):
            color = "#111318" if self.current_theme == "light" else "#ded7c4"
            svg = SVG_CHEVRON_DOWN if self.is_expanded else SVG_CHEVRON_RIGHT
            self.arrow_btn.setIcon(render_svg_icon(svg, color, 14))
            self.arrow_btn.setIconSize(QSize(14, 14))

    def add_widget(self, widget):
        widget.setParent(self.content_widget)
        self.content_layout.addWidget(widget)
        if self.is_expanded and self.anim.state() != QVariantAnimation.State.Running:
            QTimer.singleShot(0, self._sync_target_height)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)
        if self.is_expanded and self.anim.state() != QVariantAnimation.State.Running:
            QTimer.singleShot(0, self._sync_target_height)


class ApiGuideDialog(QDialog):
    def __init__(self, title, text, font_family, parent=None, width=480, height=390, theme: str = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(width, height)
        self.font_family = font_family
        self.drag_position = QPoint()

        if theme:
            self.current_theme = theme
        elif parent and hasattr(parent, 'current_theme'):
            self.current_theme = parent.current_theme
        elif parent and hasattr(parent, 'window') and hasattr(parent.window(), 'current_theme'):
            self.current_theme = parent.window().current_theme
        else:
            self.current_theme = "dark"

        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - width) // 2
        y = screen.y() + (screen.height() - height) // 2
        self.move(x, y)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        title_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        title_lbl.setStyleSheet(f"color: {title_color}; letter-spacing: 1px; text-transform: uppercase;")
        header_row.addWidget(title_lbl)
        header_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        header_row.addWidget(close_btn)

        layout.addLayout(header_row)

        guide_card = QFrame()
        if self.current_theme == "light":
            guide_card.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 255, 255, 0.85);
                    border: 1.5px solid rgba(17, 19, 24, 0.22);
                    border-radius: 8px;
                }
            """)
        else:
            guide_card.setStyleSheet("""
                QFrame {
                    background-color: rgba(14, 12, 7, 0.70);
                    border: 1px solid #78735f;
                    border-radius: 8px;
                }
            """)
        card_layout = QVBoxLayout(guide_card)
        card_layout.setContentsMargins(4, 4, 4, 4)

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(8, 8, 10, 8)
        scroll_layout.setSpacing(0)

        self.content_lbl = QLabel(text)
        self.content_lbl.setFont(QFont(self.font_family, 11))
        self.content_lbl.setWordWrap(True)
        self.content_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_color = "#111318" if self.current_theme == "light" else "#fffde7"
        self.content_lbl.setStyleSheet(f"color: {content_color}; background: transparent; border: none; line-height: 1.5;")
        scroll_layout.addWidget(self.content_lbl)

        self.scroll.setWidget(scroll_widget)
        card_layout.addWidget(self.scroll)

        layout.addWidget(guide_card, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        ok_btn = QPushButton("ПОНЯТНО")
        ok_btn.setObjectName("GuideCloseBtn")
        ok_btn.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.current_theme == "light":
            ok_btn.setStyleSheet("""
                QPushButton#GuideCloseBtn {
                    background-color: #111318;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 5px 14px;
                }
                QPushButton#GuideCloseBtn:hover {
                    background-color: #2b313d;
                }
            """)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        rect = QRectF(0.75, 0.75, w - 1.5, h - 1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        if self.current_theme == "light":
            painter.fillPath(path, QColor(238, 242, 248, 252))
            pen_border = QPen(QColor("#111318"), 1.5)
        else:
            painter.fillPath(path, QColor(8, 8, 5, 248))
            pen_border = QPen(QColor("#78735f"), 1.4)

        painter.setPen(pen_border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class NoScrollComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.current_theme = "dark"

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update()

    def wheelEvent(self, event):
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        arrow_x = w - 14
        arrow_y = h / 2.0

        is_hovered = self.underMouse()
        if self.current_theme == "light":
            pen_color = QColor("#000000") if is_hovered else QColor("#111318")
        else:
            pen_color = QColor("#ded7c4") if is_hovered else QColor("#78735f")

        pen = QPen(pen_color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        path = QPainterPath()
        path.moveTo(arrow_x - 3.5, arrow_y - 2)
        path.lineTo(arrow_x, arrow_y + 2)
        path.lineTo(arrow_x + 3.5, arrow_y - 2)
        painter.drawPath(path)


class SmoothScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._target_pos = None
        self._current_pos = 0.0
        self._velocity = 0.0
        self._friction = 0.935
        self._timer = QTimer(self)
        self._timer.setInterval(14)
        self._timer.timeout.connect(self._on_smooth_step)

        v_bar = self.verticalScrollBar()
        v_bar.sliderPressed.connect(self._on_slider_pressed)

    def _on_slider_pressed(self):
        self._timer.stop()
        self._velocity = 0.0
        self._target_pos = None
        self._current_pos = float(self.verticalScrollBar().value())

    def wheelEvent(self, event):
        v_bar = self.verticalScrollBar()
        min_val = float(v_bar.minimum())
        max_val = float(v_bar.maximum())

        if min_val >= max_val:
            super().wheelEvent(event)
            return

        if not self._timer.isActive():
            self._current_pos = float(v_bar.value())
            self._velocity = 0.0

        p_delta = event.pixelDelta().y()
        a_delta = event.angleDelta().y()

        if p_delta != 0:
            impulse = -p_delta * 0.45
        elif a_delta != 0:
            impulse = -(a_delta / 120.0) * 7.5
        else:
            super().wheelEvent(event)
            return

        self._velocity += impulse
        self._velocity = max(-35.0, min(35.0, self._velocity))

        if not self._timer.isActive():
            self._timer.start()

        event.accept()

    def _on_smooth_step(self):
        v_bar = self.verticalScrollBar()
        min_val = float(v_bar.minimum())
        max_val = float(v_bar.maximum())

        self._current_pos += self._velocity
        self._velocity *= self._friction

        if self._current_pos <= min_val:
            self._current_pos = min_val
            self._velocity = 0.0
        elif self._current_pos >= max_val:
            self._current_pos = max_val
            self._velocity = 0.0

        v_bar.setValue(int(round(self._current_pos)))

        if abs(self._velocity) < 0.2:
            self._velocity = 0.0
            self._timer.stop()


class ModernToggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = checked
        self._thumb_pos = 1.0 if checked else 0.0
        self.theme = "dark"

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.valueChanged.connect(self._on_anim_step)

    def set_theme(self, theme: str):
        self.theme = theme
        self.update()

    def _on_anim_step(self, val):
        self._thumb_pos = float(val)
        self.update()

    def isChecked(self):
        return self._checked

    def setChecked(self, state: bool):
        if self._checked != state:
            self._checked = state
            self._anim.stop()
            self._anim.setStartValue(self._thumb_pos)
            self._anim.setEndValue(1.0 if state else 0.0)
            self._anim.start()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = h / 2.0

        if self.theme == "light":
            bg_alpha = int(40 + self._thumb_pos * 215)
            bg_color = QColor(17, 19, 24, bg_alpha) if self._thumb_pos > 0.01 else QColor(218, 224, 233, 230)
            pen_color = QColor(17, 19, 24, int(130 + self._thumb_pos * 125))
            thumb_color = QColor(255, 255, 255) if self._thumb_pos > 0.5 else QColor(17, 19, 24)
        else:
            bg_alpha = int(35 + self._thumb_pos * 180)
            bg_color = QColor(120, 115, 95, bg_alpha) if self._thumb_pos > 0.01 else QColor(22, 20, 16, 180)
            pen_color = QColor(158, 151, 128, int(50 + self._thumb_pos * 190))
            thumb_color = QColor(255, 255, 255) if self._thumb_pos > 0.5 else QColor(120, 115, 95)

        painter.setPen(QPen(pen_color, 1.3))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(QRectF(0.6, 0.6, w - 1.2, h - 1.2), r, r)

        thumb_radius = r - 2.5
        thumb_min_x = 2.5 + thumb_radius
        thumb_max_x = w - 2.5 - thumb_radius
        thumb_cx = thumb_min_x + self._thumb_pos * (thumb_max_x - thumb_min_x)
        thumb_cy = h / 2.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(thumb_color))
        painter.drawEllipse(QPointF(thumb_cx, thumb_cy), thumb_radius, thumb_radius)


class SettingsFrame(QFrame):
    speak_requested = pyqtSignal(str)
    vision_state_changed = pyqtSignal(bool)
    fps_changed = pyqtSignal(int)
    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_theme = "dark"
        self.border_phase = 0.0
        self.border_opacity = 0.0
        self.border_anim = QVariantAnimation(self)
        self.border_anim.setDuration(350)
        self.border_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.border_anim.valueChanged.connect(self._on_border_anim_step)
        self.speaker_verifier = SpeakerVerifier(threshold=0.70)
        self.spotify_manager = SpotifyManager()
        self.saved_vision_state = False
        self.update_download_url = None
        self.downloader_thread = None
        self.preview_sound = QSoundEffect(self)
        self.preview_sound.playingChanged.connect(self._on_preview_playing_changed)
        self.custom_alarm_path = ""
        self.work_apps = []
        self.rest_apps = []
        self.gigachat_key = ""
        self.yandex_music_token = ""
        self.yandex_iot_token = ""
        self._is_loading = True

        font_path = get_resource_path("assets", "fonts", "Schiffbauer-Regular.otf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            self.font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        else:
            self.font_family = "Arial"

        self.custom_font = QFont(self.font_family, 11)
        self.setFont(self.custom_font)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_border)
        self.timer.start(20)

        self.init_ui()
        self.load_settings()
        self._is_loading = False
        self._connect_auto_save()

    def mousePressEvent(self, event):
        event.accept()

    def _create_hint_button(self, hint_key):
        btn = QPushButton("?")
        btn.setObjectName("HintCircleBtn")
        btn.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        btn.setFixedSize(16, 16)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.speak_requested.emit(SPEECH_HINTS[hint_key]))
        return btn

    def _create_guide_button(self, guide_key):
        btn = QPushButton("INFO")
        btn.setObjectName("GuideCircleBtn")
        btn.setFixedSize(32, 16)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._show_guide(guide_key))
        return btn

    def _show_guide(self, guide_key):
        guide = API_GUIDES.get(guide_key)
        if guide:
            dialog = ApiGuideDialog(guide["title"], guide["text"], self.font_family, self)
            dialog.exec()

    def _show_akira_capabilities(self):
        title = "КОМАНДЫ И ВОЗМОЖНОСТИ АКИРЫ"
        text = (
            "Руководство по управлению системой Акира:\n\n"
            "1. СИСТЕМНЫЙ КОНТРОЛЬ:\n"
            "— Блокировка экрана, сон, выключение и перезагрузка ПК.\n"
            "— Запуск любого установленного приложения или игры.\n"
            "— Профили 'Работа' и 'Отдых' с запуском выбранных веб-ресурсов и софта.\n\n"
            "2. МЕДИА И РАЗВЛЕЧЕНИЯ:\n"
            "— Запуск треков и Моей волны в Яндекс Музыке и Spotify.\n"
            "— Управление громкостью, паузой, переключением треков, отметки лайков.\n"
            "— Автономная сводка погоды по всему миру без сторонних API-ключей.\n"
            "— Поиск видеороликов на YouTube с авторазворачиванием на весь экран.\n"
            "— Поиск фильмов и сериалов на HDRezka с автоматической ротацией зеркал.\n\n"
            "3. СЕТЬ И УМНЫЙ ДОМ:\n"
            "— Управление освещением, розетками и сценариями Дома с Алисой.\n"
            "— Голосовой контроль VPN-соединений и обхода zapret.\n\n"
            "4. НЕЙРОСЕТЕВОЙ МОДУЛЬ VISION:\n"
            "— Автоматическая биометрическая идентификация владельца по лицу.\n"
            "— Управление жестами рук через камеру и трекинг усталости глаз.\n\n"
            "5. ДИАЛОГОВЙ ИНТЕЛЛЕКТ:\n"
            "— Распознавание тонких эмоций собеседника (сарказм, радость, усталость).\n"
            "— Локальная долговременная память ключевых фактов о пользователе.\n"
            "— Распознавание шёпота и верификация владельца по голосу (Voice ID).\n"
            "— Встроенные интеллектуальные игры (Города, Верю-не-верю, Данетки).\n\n"
            "6. TELEGRAM REMOTE:\n"
            "— Дистанционный мониторинг и управление системой через бота."
        )
        dialog = ApiGuideDialog(title, text, self.font_family, self, width=520, height=430)
        dialog.exec()

    def _open_telegram_pairing(self):
        try:
            from gui.dialogs.telegram_pair_dialog import TelegramPairDialog
            dialog = TelegramPairDialog(self.font_family, self)
            screen = QGuiApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - dialog.width()) // 2
            y = screen.y() + (screen.height() - dialog.height()) // 2
            dialog.move(x, y)
            if dialog.exec():
                self.load_settings()
        except Exception as e:
            print(f"[Telegram Pair Error]: {e}")

    def _get_status_colors(self):
        if self.current_theme == "light":
            return "#111318", "#555e6d"
        return "#ded7c4", "rgba(255, 253, 231, 0.45)"

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(6)

        title = QLabel("ПАРАМЕТРЫ СИСТЕМЫ")
        title.setObjectName("SettingsMainTitle")
        title.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        header_layout.addWidget(title)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        header_layout.addWidget(self.status_label)

        header_layout.addStretch()

        author_label = QLabel("Created by Svetozar")
        author_label.setObjectName("AuthorLabel")
        author_label.setFont(QFont(self.font_family, 8))
        header_layout.addWidget(author_label, 0, Qt.AlignmentFlag.AlignVCenter)
        main_layout.addLayout(header_layout)

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setObjectName("SettingsScroll")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(8)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_capabilities = QPushButton("СПРАВОЧНИК И ВОЗМОЖНОСТИ АКИРЫ")
        self.btn_capabilities.setObjectName("GuideCloseBtn")
        self.btn_capabilities.setFixedHeight(28)
        self.btn_capabilities.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        self.btn_capabilities.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_capabilities.clicked.connect(self._show_akira_capabilities)
        scroll_layout.addWidget(self.btn_capabilities)

        self.card_user = BentoCard("ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ", self.font_family, self, expanded=True)

        row_user_top = QHBoxLayout()
        row_user_top.setSpacing(8)

        cell_name = QFrame(self.card_user.content_widget)
        cell_name.setObjectName("BentoCell")
        cell_name_l = QHBoxLayout(cell_name)
        cell_name_l.setContentsMargins(8, 6, 8, 6)
        lbl_name = QLabel("Имя")
        lbl_name.setObjectName("ToggleLabel")
        lbl_name.setFont(QFont(self.font_family, 10))
        cell_name_l.addWidget(lbl_name)
        cell_name_l.addStretch()
        self.name_input = QLineEdit(cell_name)
        self.name_input.setObjectName("SettingInput")
        self.name_input.setFont(QFont(self.font_family, 10))
        self.name_input.setPlaceholderText("Имя...")
        self.name_input.setFixedWidth(84)
        cell_name_l.addWidget(self.name_input)
        row_user_top.addWidget(cell_name, 1)

        cell_gender = QFrame(self.card_user.content_widget)
        cell_gender.setObjectName("BentoCell")
        cell_gender_l = QHBoxLayout(cell_gender)
        cell_gender_l.setContentsMargins(8, 6, 8, 6)
        lbl_gender = QLabel("Пол")
        lbl_gender.setObjectName("ToggleLabel")
        lbl_gender.setFont(QFont(self.font_family, 10))
        cell_gender_l.addWidget(lbl_gender)
        cell_gender_l.addStretch()
        cell_gender_l.addWidget(self._create_hint_button("user_gender"))
        self.gender_combo = NoScrollComboBox(cell_gender)
        self.gender_combo.setObjectName("SettingCombo")
        self.gender_combo.setFont(QFont(self.font_family, 9))
        self.gender_combo.setFixedWidth(80)
        self.gender_combo.addItem("Муж.", "male")
        self.gender_combo.addItem("Жен.", "female")
        cell_gender_l.addWidget(self.gender_combo)
        row_user_top.addWidget(cell_gender, 1)

        self.card_user.add_layout(row_user_top)

        scroll_layout.addWidget(self.card_user)

        self.card_sys = BentoCard("СИСТЕМНОЕ ЯДРО", self.font_family, self, expanded=False)

        row_sys_top = QHBoxLayout()
        row_sys_top.setSpacing(8)

        cell_auto = QFrame(self.card_sys.content_widget)
        cell_auto.setObjectName("BentoCell")
        cell_auto_l = QHBoxLayout(cell_auto)
        cell_auto_l.setContentsMargins(8, 6, 8, 6)
        lbl_auto = QLabel("Автостарт")
        lbl_auto.setObjectName("ToggleLabel")
        lbl_auto.setFont(QFont(self.font_family, 10))
        cell_auto_l.addWidget(lbl_auto)
        cell_auto_l.addStretch()
        cell_auto_l.addWidget(self._create_hint_button("autostart"))
        self.autostart_toggle = ModernToggle(parent=cell_auto)
        cell_auto_l.addWidget(self.autostart_toggle)
        row_sys_top.addWidget(cell_auto, 1)

        cell_theme = QFrame(self.card_sys.content_widget)
        cell_theme.setObjectName("BentoCell")
        cell_theme_l = QHBoxLayout(cell_theme)
        cell_theme_l.setContentsMargins(8, 6, 8, 6)
        lbl_theme = QLabel("Тема")
        lbl_theme.setObjectName("ToggleLabel")
        lbl_theme.setFont(QFont(self.font_family, 10))
        cell_theme_l.addWidget(lbl_theme)
        cell_theme_l.addStretch()
        cell_theme_l.addWidget(self._create_hint_button("theme"))
        self.theme_combo = NoScrollComboBox(cell_theme)
        self.theme_combo.setObjectName("SettingCombo")
        self.theme_combo.setFont(QFont(self.font_family, 9))
        self.theme_combo.setFixedWidth(84)
        self.theme_combo.addItem("Тёмная", "dark")
        self.theme_combo.addItem("Светлая", "light")
        cell_theme_l.addWidget(self.theme_combo)
        row_sys_top.addWidget(cell_theme, 1)

        self.card_sys.add_layout(row_sys_top)

        row_sys_second = QHBoxLayout()
        row_sys_second.setSpacing(8)

        cell_fps = QFrame(self.card_sys.content_widget)
        cell_fps.setObjectName("BentoCell")
        cell_fps_l = QHBoxLayout(cell_fps)
        cell_fps_l.setContentsMargins(8, 6, 8, 6)
        lbl_fps = QLabel("FPS")
        lbl_fps.setObjectName("ToggleLabel")
        lbl_fps.setFont(QFont(self.font_family, 10))
        cell_fps_l.addWidget(lbl_fps)
        cell_fps_l.addStretch()
        self.fps_combo = NoScrollComboBox(cell_fps)
        self.fps_combo.setObjectName("SettingCombo")
        self.fps_combo.setFont(QFont(self.font_family, 9))
        self.fps_combo.setFixedWidth(82)
        self.fps_combo.addItem("60", 60)
        self.fps_combo.addItem("120", 120)
        cell_fps_l.addWidget(self.fps_combo)
        row_sys_second.addWidget(cell_fps, 1)

        cell_vpn = QFrame(self.card_sys.content_widget)
        cell_vpn.setObjectName("BentoCell")
        cell_vpn_l = QHBoxLayout(cell_vpn)
        cell_vpn_l.setContentsMargins(8, 6, 8, 6)
        lbl_v = QLabel("VPN")
        lbl_v.setObjectName("ToggleLabel")
        lbl_v.setFont(QFont(self.font_family, 10))
        cell_vpn_l.addWidget(lbl_v)
        cell_vpn_l.addStretch()
        self.vpn_combo = NoScrollComboBox(cell_vpn)
        self.vpn_combo.setObjectName("SettingCombo")
        self.vpn_combo.setFont(QFont(self.font_family, 9))
        self.vpn_combo.setFixedWidth(82)
        for name, key in [("Нет", "none"), ("Sota", "sota"), ("Happ", "happ"), ("V2Ray", "v2ray"), ("WG", "wireguard")]:
            self.vpn_combo.addItem(name, key)
        cell_vpn_l.addWidget(self.vpn_combo)
        row_sys_second.addWidget(cell_vpn, 1)

        self.card_sys.add_layout(row_sys_second)

        row_vol = QFrame(self.card_sys.content_widget)
        row_vol.setObjectName("BentoCell")
        row_vol_l = QHBoxLayout(row_vol)
        row_vol_l.setContentsMargins(8, 6, 8, 6)
        self.lbl_vol_title = QLabel("Голос: 100%")
        self.lbl_vol_title.setObjectName("ToggleLabel")
        self.lbl_vol_title.setFont(QFont(self.font_family, 10))
        row_vol_l.addWidget(self.lbl_vol_title)
        row_vol_l.addStretch()
        self.voice_slider = QSlider(Qt.Orientation.Horizontal, row_vol)
        self.voice_slider.setObjectName("VoiceSlider")
        self.voice_slider.setRange(0, 100)
        self.voice_slider.setValue(100)
        self.voice_slider.setFixedWidth(130)
        self.voice_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_slider.valueChanged.connect(self._on_volume_slider_changed)
        row_vol_l.addWidget(self.voice_slider)
        self.card_sys.add_widget(row_vol)

        row_alarm = QFrame(self.card_sys.content_widget)
        row_alarm.setObjectName("BentoCell")
        row_alarm_l = QHBoxLayout(row_alarm)
        row_alarm_l.setContentsMargins(8, 6, 8, 6)
        lbl_al = QLabel("Будильник")
        lbl_al.setObjectName("ToggleLabel")
        lbl_al.setFont(QFont(self.font_family, 10))
        row_alarm_l.addWidget(lbl_al)
        row_alarm_l.addStretch()

        self.btn_preview_alarm = QPushButton("ТЕСТ", row_alarm)
        self.btn_preview_alarm.setObjectName("BentoSecondaryBtn")
        self.btn_preview_alarm.setFixedSize(46, 22)
        self.btn_preview_alarm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_preview_alarm.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.btn_preview_alarm.clicked.connect(self._toggle_preview_alarm)
        row_alarm_l.addWidget(self.btn_preview_alarm)

        self.btn_choose_custom_alarm = QPushButton("ОБЗОР", row_alarm)
        self.btn_choose_custom_alarm.setObjectName("BentoSecondaryBtn")
        self.btn_choose_custom_alarm.setFixedSize(48, 22)
        self.btn_choose_custom_alarm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_choose_custom_alarm.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.btn_choose_custom_alarm.clicked.connect(self._choose_custom_alarm_file)
        self.btn_choose_custom_alarm.hide()
        row_alarm_l.addWidget(self.btn_choose_custom_alarm)

        self.lbl_alarm_status = QLabel("", row_alarm)
        self.lbl_alarm_status.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.lbl_alarm_status.setFixedWidth(96)
        self.lbl_alarm_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_alarm_status.hide()
        row_alarm_l.addWidget(self.lbl_alarm_status)

        self.alarm_sound_combo = NoScrollComboBox(row_alarm)
        self.alarm_sound_combo.setObjectName("SettingCombo")
        self.alarm_sound_combo.setFont(QFont(self.font_family, 9))
        self.alarm_sound_combo.setFixedWidth(105)
        for name, key in [("Сигнал 1", "alarm_1"), ("Сигнал 2", "alarm_2"), ("Сигнал 3", "alarm_3"), ("Свой трек", "custom")]:
            self.alarm_sound_combo.addItem(name, key)
        self.alarm_sound_combo.currentIndexChanged.connect(self._on_alarm_combo_changed)
        row_alarm_l.addWidget(self.alarm_sound_combo)
        self.card_sys.add_widget(row_alarm)

        row_tg = QFrame(self.card_sys.content_widget)
        row_tg.setObjectName("BentoCell")
        row_tg_l = QHBoxLayout(row_tg)
        row_tg_l.setContentsMargins(8, 6, 8, 6)
        lbl_t = QLabel("Telegram")
        lbl_t.setObjectName("ToggleLabel")
        lbl_t.setFont(QFont(self.font_family, 10))
        row_tg_l.addWidget(lbl_t)
        row_tg_l.addStretch()
        row_tg_l.addWidget(self._create_guide_button("telegram_pair"))
        self.pair_btn = QPushButton("QR", row_tg)
        self.pair_btn.setObjectName("BentoActionBtn")
        self.pair_btn.setFixedSize(34, 22)
        self.pair_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pair_btn.clicked.connect(self._open_telegram_pairing)
        row_tg_l.addWidget(self.pair_btn)
        self.card_sys.add_widget(row_tg)

        scroll_layout.addWidget(self.card_sys)

        self.card_modes = BentoCard("ПРОФИЛИ ДЕЙСТВИЙ", self.font_family, self, expanded=False)
        grid_modes = QHBoxLayout()
        grid_modes.setSpacing(8)

        cell_work = QFrame(self.card_modes.content_widget)
        cell_work.setObjectName("BentoCell")
        cell_work_l = QVBoxLayout(cell_work)
        cell_work_l.setContentsMargins(8, 8, 8, 8)
        cell_work_l.setSpacing(4)
        t_work = QLabel("РАБОТА")
        t_work.setObjectName("BentoCellTitle")
        t_work.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        cell_work_l.addWidget(t_work)
        self.lbl_work_status = QLabel("не настроен")
        self.lbl_work_status.setObjectName("BentoStatusIdle")
        cell_work_l.addWidget(self.lbl_work_status)
        btn_w = QPushButton("НАСТРОИТЬ", cell_work)
        btn_w.setObjectName("BentoActionBtn")
        btn_w.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_w.clicked.connect(self._open_work_mode_setup)
        cell_work_l.addWidget(btn_w)
        grid_modes.addWidget(cell_work, 1)

        cell_rest = QFrame(self.card_modes.content_widget)
        cell_rest.setObjectName("BentoCell")
        cell_rest_l = QVBoxLayout(cell_rest)
        cell_rest_l.setContentsMargins(8, 8, 8, 8)
        cell_rest_l.setSpacing(4)
        t_rest = QLabel("ОТДЫХ")
        t_rest.setObjectName("BentoCellTitle")
        t_rest.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        cell_rest_l.addWidget(t_rest)
        self.lbl_rest_status = QLabel("не настроен")
        self.lbl_rest_status.setObjectName("BentoStatusIdle")
        cell_rest_l.addWidget(self.lbl_rest_status)
        btn_r = QPushButton("НАСТРОИТЬ", cell_rest)
        btn_r.setObjectName("BentoActionBtn")
        btn_r.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_r.clicked.connect(self._open_rest_mode_setup)
        cell_rest_l.addWidget(btn_r)
        grid_modes.addWidget(cell_rest, 1)

        self.card_modes.add_layout(grid_modes)
        scroll_layout.addWidget(self.card_modes)

        self.card_bio = BentoCard("БИОМЕТРИЯ И НЕЙРО-СЕНСОРЫ", self.font_family, self, expanded=False)

        cell_voice = QFrame(self.card_bio.content_widget)
        cell_voice.setObjectName("BentoCell")
        cell_voice_l = QVBoxLayout(cell_voice)
        cell_voice_l.setContentsMargins(8, 8, 8, 8)
        cell_voice_l.setSpacing(6)

        row_v_head = QHBoxLayout()
        lbl_v_id = QLabel("VOICE ID")
        lbl_v_id.setObjectName("BentoCellTitle")
        lbl_v_id.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        row_v_head.addWidget(lbl_v_id)
        row_v_head.addStretch()
        row_v_head.addWidget(self._create_hint_button("voice_id"))
        cell_voice_l.addLayout(row_v_head)

        self.lbl_vp_status = QLabel("Слепок: не записан")
        self.lbl_vp_status.setObjectName("BentoStatusIdle")
        self.lbl_vp_status.setWordWrap(True)
        cell_voice_l.addWidget(self.lbl_vp_status)

        row_v_btns = QHBoxLayout()
        row_v_btns.setSpacing(6)
        self.btn_enroll_owner = QPushButton("ЗАПИСАТЬ", cell_voice)
        self.btn_enroll_owner.setObjectName("BentoActionBtn")
        self.btn_enroll_owner.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enroll_owner.clicked.connect(self._open_enroll_owner)
        row_v_btns.addWidget(self.btn_enroll_owner, 1)

        self.btn_add_friend = QPushButton("+ ДОСТУП", cell_voice)
        self.btn_add_friend.setObjectName("BentoSecondaryBtn")
        self.btn_add_friend.setFixedHeight(22)
        self.btn_add_friend.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_friend.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.btn_add_friend.clicked.connect(self._open_enroll_friend)
        row_v_btns.addWidget(self.btn_add_friend, 1)
        cell_voice_l.addLayout(row_v_btns)

        self.card_bio.add_widget(cell_voice)

        cell_vis = QFrame(self.card_bio.content_widget)
        cell_vis.setObjectName("BentoCell")
        cell_vis_l = QVBoxLayout(cell_vis)
        cell_vis_l.setContentsMargins(8, 8, 8, 8)
        cell_vis_l.setSpacing(6)

        row_face = QHBoxLayout()
        lbl_face = QLabel("Face ID (Камера)")
        lbl_face.setObjectName("ToggleLabel")
        lbl_face.setFont(QFont(self.font_family, 10))
        row_face.addWidget(lbl_face)
        row_face.addStretch()
        row_face.addWidget(self._create_hint_button("face_recognition"))
        self.face_rec_toggle = ModernToggle(parent=cell_vis)
        row_face.addWidget(self.face_rec_toggle)
        cell_vis_l.addLayout(row_face)

        row_face_btns = QHBoxLayout()
        row_face_btns.setSpacing(6)

        self.btn_manage_faces = QPushButton("ФОТО ЛИЦА (0)", cell_vis)
        self.btn_manage_faces.setObjectName("BentoActionBtn")
        self.btn_manage_faces.setFixedHeight(22)
        self.btn_manage_faces.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.btn_manage_faces.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_manage_faces.clicked.connect(self._open_face_manager)
        row_face_btns.addWidget(self.btn_manage_faces, 1)

        self.btn_add_face = QPushButton("+ СНИМОК", cell_vis)
        self.btn_add_face.setObjectName("BentoSecondaryBtn")
        self.btn_add_face.setFixedHeight(22)
        self.btn_add_face.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.btn_add_face.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_face.clicked.connect(self._add_owner_face)
        row_face_btns.addWidget(self.btn_add_face, 1)

        cell_vis_l.addLayout(row_face_btns)

        row_sens = QHBoxLayout()
        row_sens.setSpacing(6)

        lbl_eye = QLabel("Усталость глаз")
        lbl_eye.setObjectName("ToggleLabel")
        lbl_eye.setFont(QFont(self.font_family, 9))
        row_sens.addWidget(lbl_eye)
        self.eye_tracking_toggle = ModernToggle(parent=cell_vis)
        row_sens.addWidget(self.eye_tracking_toggle)

        row_sens.addSpacing(10)

        lbl_g = QLabel("Жесты")
        lbl_g.setObjectName("ToggleLabel")
        lbl_g.setFont(QFont(self.font_family, 9))
        row_sens.addWidget(lbl_g)
        self.gestures_toggle = ModernToggle(parent=cell_vis)
        row_sens.addWidget(self.gestures_toggle)

        cell_vis_l.addLayout(row_sens)
        self.card_bio.add_widget(cell_vis)
        scroll_layout.addWidget(self.card_bio)

        self.card_cloud = BentoCard("ИНТЕГРАЦИИ И СЕРВИСЫ", self.font_family, self, expanded=False)

        def _make_service_cell(title, guide_key, hint_key, status_lbl, btn):
            cell = QFrame(self.card_cloud.content_widget)
            cell.setObjectName("BentoCell")
            l = QHBoxLayout(cell)
            l.setContentsMargins(8, 6, 8, 6)
            l.setSpacing(6)

            info_col = QVBoxLayout()
            info_col.setSpacing(2)
            t = QLabel(title)
            t.setObjectName("BentoCellTitle")
            t.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
            info_col.addWidget(t)
            info_col.addWidget(status_lbl)
            l.addLayout(info_col, 1)

            l.addWidget(self._create_guide_button(guide_key))
            l.addWidget(self._create_hint_button(hint_key))
            btn.setParent(cell)
            l.addWidget(btn)
            return cell

        self.lbl_gigachat_status = QLabel("НЕ ПРИВЯЗАН")
        self.lbl_gigachat_status.setObjectName("BentoStatusIdle")
        self.btn_gigachat_auth = QPushButton("НАСТРОИТЬ")
        self.btn_gigachat_auth.setObjectName("BentoActionBtn")
        self.btn_gigachat_auth.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_gigachat_auth.clicked.connect(self._open_gigachat_auth)
        self.card_cloud.add_widget(_make_service_cell("GIGACHAT AI", "gigachat", "gigachat", self.lbl_gigachat_status, self.btn_gigachat_auth))

        self.lbl_ya_status = QLabel("НЕ ПРИВЯЗАН")
        self.lbl_ya_status.setObjectName("BentoStatusIdle")
        self.btn_ya_auth = QPushButton("ВОЙТИ")
        self.btn_ya_auth.setObjectName("BentoActionBtn")
        self.btn_ya_auth.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ya_auth.clicked.connect(self._open_yandex_auth)
        self.card_cloud.add_widget(_make_service_cell("ЯНДЕКС МУЗЫКА", "yandex", "yandex", self.lbl_ya_status, self.btn_ya_auth))

        self.lbl_ya_iot_status = QLabel("НЕ ПРИВЯЗАН")
        self.lbl_ya_iot_status.setObjectName("BentoStatusIdle")
        self.btn_ya_iot_auth = QPushButton("ВОЙТИ")
        self.btn_ya_iot_auth.setObjectName("BentoActionBtn")
        self.btn_ya_iot_auth.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ya_iot_auth.clicked.connect(self._open_yandex_iot_auth)
        self.card_cloud.add_widget(_make_service_cell("ДОМ С АЛИСОЙ", "yandex_iot", "yandex_iot", self.lbl_ya_iot_status, self.btn_ya_iot_auth))

        self.lbl_spotify_status = QLabel("НЕ ПРИВЯЗАН")
        self.lbl_spotify_status.setObjectName("BentoStatusIdle")
        self.btn_spotify_auth = QPushButton("ВОЙТИ")
        self.btn_spotify_auth.setObjectName("BentoActionBtn")
        self.btn_spotify_auth.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_spotify_auth.clicked.connect(self._open_spotify_auth)
        self.card_cloud.add_widget(_make_service_cell("SPOTIFY", "spotify", "spotify", self.lbl_spotify_status, self.btn_spotify_auth))

        cell_sp_toggle = QFrame(self.card_cloud.content_widget)
        cell_sp_toggle.setObjectName("BentoCell")
        cell_sp_l = QHBoxLayout(cell_sp_toggle)
        cell_sp_l.setContentsMargins(8, 6, 8, 6)
        lbl_sp_tog = QLabel("Приоритет Spotify (вместо Яндекс)")
        lbl_sp_tog.setObjectName("ToggleLabel")
        lbl_sp_tog.setFont(QFont(self.font_family, 9))
        cell_sp_l.addWidget(lbl_sp_tog)
        cell_sp_l.addStretch()
        cell_sp_l.addWidget(self._create_hint_button("music_service"))
        self.spotify_toggle = ModernToggle(parent=cell_sp_toggle)
        cell_sp_l.addWidget(self.spotify_toggle)
        self.card_cloud.add_widget(cell_sp_toggle)

        scroll_layout.addWidget(self.card_cloud)

        self.card_upd = BentoCard("СИСТЕМНОЕ ОБНОВЛЕНИЕ", self.font_family, self, expanded=False)
        row_upd = QHBoxLayout()
        self.lbl_current_ver = QLabel(f"v{CURRENT_VERSION}")
        self.lbl_current_ver.setObjectName("BentoStatusActive")
        row_upd.addWidget(self.lbl_current_ver)

        self.lbl_update_status = QLabel("Версия актуальна")
        self.lbl_update_status.setObjectName("BentoStatusIdle")
        row_upd.addWidget(self.lbl_update_status, 1)

        self.btn_update = QPushButton("ОБНОВИТЬ", self.card_upd.content_widget)
        self.btn_update.setObjectName("UpdateButton")
        self.btn_update.setFixedHeight(22)
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.btn_update.clicked.connect(self._start_download_update)
        self.btn_update.hide()
        row_upd.addWidget(self.btn_update)
        self.card_upd.add_layout(row_upd)

        self.update_progress = QProgressBar(self.card_upd.content_widget)
        self.update_progress.setObjectName("UpdateProgressBar")
        self.update_progress.setFixedHeight(16)
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(0)
        self.update_progress.hide()
        self.card_upd.add_widget(self.update_progress)

        scroll_layout.addWidget(self.card_upd)
        scroll_layout.addStretch()

        self.cards = [self.card_user, self.card_sys, self.card_modes, self.card_bio, self.card_cloud, self.card_upd]

        self.scroll.setWidget(scroll_content)
        main_layout.addWidget(self.scroll, 1)

    def _connect_auto_save(self):
        self.name_input.editingFinished.connect(self.auto_save)
        self.gender_combo.currentIndexChanged.connect(self.auto_save)
        self.autostart_toggle.toggled.connect(self.auto_save)
        self.theme_combo.currentIndexChanged.connect(self.auto_save)
        self.fps_combo.currentIndexChanged.connect(self.auto_save)
        self.voice_slider.sliderReleased.connect(self.auto_save)
        self.alarm_sound_combo.currentIndexChanged.connect(self.auto_save)
        self.vpn_combo.currentIndexChanged.connect(self.auto_save)
        self.spotify_toggle.toggled.connect(self.auto_save)
        self.face_rec_toggle.toggled.connect(self.auto_save)
        self.eye_tracking_toggle.toggled.connect(self.auto_save)
        self.gestures_toggle.toggled.connect(self.auto_save)

    def auto_save(self):
        if getattr(self, "_is_loading", False):
            return
        self.save_settings()

    def scroll_to_bottom(self):
        def _do_scroll():
            v_bar = self.scroll.verticalScrollBar()
            v_bar.setValue(v_bar.maximum())
            self.scroll._target_pos = None

        QTimer.singleShot(250, _do_scroll)
        QTimer.singleShot(650, _do_scroll)

    def set_update_available(self, new_ver: str, changelog: str, download_url: str):
        active_col, _ = self._get_status_colors()
        self.update_download_url = download_url
        self.card_upd.set_expanded(True)
        self.lbl_update_status.setText(f"Доступно обновление: v{new_ver}")
        self.lbl_update_status.setStyleSheet(f"color: {active_col}; font-weight: bold;")
        self.btn_update.setText(f"ОБНОВИТЬ v{new_ver}")
        self.btn_update.show()

    def _start_download_update(self):
        if not self.update_download_url:
            return

        self.btn_update.setEnabled(False)
        self.btn_update.setText("ЗАГРУЗКА...")
        self.update_progress.setValue(0)
        self.update_progress.show()
        self.lbl_update_status.setText("Загрузка обновления...")

        self.downloader_thread = DownloaderThread(self.update_download_url)
        self.downloader_thread.progress_changed.connect(self._on_download_progress)
        self.downloader_thread.download_finished.connect(self._on_download_finished)
        self.downloader_thread.error_occurred.connect(self._on_download_error)
        self.downloader_thread.start()

    def _on_download_progress(self, percent: int):
        self.update_progress.setValue(percent)

    def _on_download_finished(self, installer_path: str):
        self.lbl_update_status.setText("Запуск пакета...")
        QTimer.singleShot(1000, lambda: apply_update_and_restart(installer_path))

    def _on_download_error(self, err: str):
        self.update_progress.hide()
        self.btn_update.setEnabled(True)
        self.btn_update.setText("ПОВТОРИТЬ")
        self.lbl_update_status.setText("Ошибка загрузки")
        self.lbl_update_status.setStyleSheet("color: #ff5252;")

    def _on_volume_slider_changed(self, value):
        self.lbl_vol_title.setText(f"Голос: {value}%")

    def _update_face_count_ui(self):
        face_dir = os.path.normpath(get_user_data_path("owner_face"))
        count = 0
        if os.path.exists(face_dir):
            valid_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
            count = len([f for f in os.listdir(face_dir) if f.lower().endswith(valid_exts)])
        self.btn_manage_faces.setText(f"ФОТО ЛИЦА ({count})")

    def _open_face_manager(self):
        dialog = FaceManagerDialog(font_family=self.font_family, parent=self.window())
        dialog.photos_changed.connect(self._update_face_count_ui)
        dialog.exec()
        self._update_face_count_ui()
        if self.window():
            self.window().activateWindow()
            self.window().raise_()
            self.window().setFocus()

    def _add_owner_face(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Выбор фотографий владельца", "", "Images (*.png *.jpg *.jpeg)")
        if files:
            face_dir = os.path.normpath(get_user_data_path("owner_face"))
            os.makedirs(face_dir, exist_ok=True)
            count = 0
            for f in files:
                try:
                    shutil.copy(f, os.path.join(face_dir, os.path.basename(f)))
                    count += 1
                except Exception:
                    pass
            active_col, _ = self._get_status_colors()
            self.status_label.setText(f"✓ ФОТО: +{count}")
            self.status_label.setStyleSheet(f"color: {active_col}; font-size: 8px; font-weight: bold;")
            self._update_face_count_ui()
            self.auto_save()
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))

    def _apply_windows_autostart(self, enabled: bool):
        app_name = "AkiraAssistant"
        if getattr(sys, "frozen", False):
            exec_cmd = f'"{sys.executable}"'
        else:
            script_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
            exec_cmd = f'"{pythonw}" "{script_path}"' if os.path.exists(pythonw) else f'"{python_exe}" "{script_path}"'

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exec_cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Autostart Reg Error]: {e}")

    def _on_preview_playing_changed(self):
        if self.preview_sound.isPlaying():
            self.btn_preview_alarm.setText("СТОП")
        else:
            self.btn_preview_alarm.setText("ТЕСТ")

    def _on_alarm_combo_changed(self, index):
        mode = self.alarm_sound_combo.currentData()
        if mode == "custom":
            self.btn_choose_custom_alarm.show()
        else:
            self.btn_choose_custom_alarm.hide()

        if self.preview_sound.isPlaying():
            self.preview_sound.stop()

    def _choose_custom_alarm_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбор звукового файла",
            "",
            "Аудио файлы (*.wav *.mp3 *.ogg *.flac *.m4a);;WAV (*.wav);;MP3 (*.mp3);;Все файлы (*.*)"
        )
        if file_path:
            self.btn_preview_alarm.hide()
            self.btn_choose_custom_alarm.hide()
            active_col, _ = self._get_status_colors()
            self.lbl_alarm_status.setText("ПРОВЕРКА...")
            self.lbl_alarm_status.setStyleSheet(f"color: {active_col}; letter-spacing: 0.5px;")
            self.lbl_alarm_status.show()
            QGuiApplication.processEvents()

            target_wav = get_user_data_path("custom_alarm.wav")
            ok = convert_audio_to_wav(file_path, target_wav)

            if ok and os.path.exists(target_wav) and is_valid_wav(target_wav):
                self.custom_alarm_path = target_wav
                idx_custom = self.alarm_sound_combo.findData("custom")
                if idx_custom != -1:
                    self.alarm_sound_combo.blockSignals(True)
                    self.alarm_sound_combo.setCurrentIndex(idx_custom)
                    self.alarm_sound_combo.blockSignals(False)
                self.lbl_alarm_status.setText("✓ ЗВУК ЗАДАН")
                self.lbl_alarm_status.setStyleSheet(f"color: {active_col};")
                self.auto_save()
            else:
                self.lbl_alarm_status.setText("✕ ОШИБКА")
                self.lbl_alarm_status.setStyleSheet("color: #ff5252;")

            def _restore_alarm_btns():
                self.lbl_alarm_status.hide()
                self.btn_preview_alarm.show()
                if self.alarm_sound_combo.currentData() == "custom":
                    self.btn_choose_custom_alarm.show()

            QTimer.singleShot(2200, _restore_alarm_btns)

    def _toggle_preview_alarm(self):
        if self.preview_sound.isPlaying():
            self.preview_sound.stop()
            return

        mode = self.alarm_sound_combo.currentData()
        path = None

        if mode == "custom":
            if self.custom_alarm_path and os.path.exists(self.custom_alarm_path):
                path = self.custom_alarm_path
        else:
            path = get_resource_path("assets", "sounds", f"{mode}.wav")

        if path and os.path.exists(path) and is_valid_wav(path):
            self.preview_sound.stop()
            self.preview_sound.setSource(QUrl.fromLocalFile(path))
            self.preview_sound.setLoopCount(1)
            vol = self.voice_slider.value() / 100.0
            self.preview_sound.setVolume(max(0.1, vol))
            self.preview_sound.play()
        else:
            self.status_label.setText("✕ НЕТ ЗВУКА")
            self.status_label.setStyleSheet("color: #ff5252; font-size: 8px; font-weight: bold;")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))

    def _format_items_count(self, items: list) -> str:
        n = len(items)
        if n == 0:
            return "не настроен"
        if n % 10 == 1 and n % 100 != 11:
            return f"{n} элемент"
        elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
            return f"{n} элемента"
        else:
            return f"{n} элементов"

    def _update_modes_status_ui(self):
        active_col, idle_col = self._get_status_colors()
        self.lbl_work_status.setText(self._format_items_count(self.work_apps))
        self.lbl_work_status.setStyleSheet(f"color: {active_col if self.work_apps else idle_col}; font-weight: bold;")

        self.lbl_rest_status.setText(self._format_items_count(self.rest_apps))
        self.lbl_rest_status.setStyleSheet(f"color: {active_col if self.rest_apps else idle_col}; font-weight: bold;")

    def _open_work_mode_setup(self):
        dialog = ModeConfigDialog(
            mode_title="Профиль «Работа»",
            items=self.work_apps,
            font_family=self.font_family,
            parent=self.window()
        )
        dialog.items_saved.connect(self._on_work_items_saved)
        dialog.exec()
        if self.window():
            self.window().activateWindow()
            self.window().raise_()
            self.window().setFocus()

    def _on_work_items_saved(self, items: list):
        self.work_apps = items
        self._update_modes_status_ui()
        self.auto_save()

    def _open_rest_mode_setup(self):
        dialog = ModeConfigDialog(
            mode_title="Профиль «Отдых»",
            items=self.rest_apps,
            font_family=self.font_family,
            parent=self.window()
        )
        dialog.items_saved.connect(self._on_rest_items_saved)
        dialog.exec()
        if self.window():
            self.window().activateWindow()
            self.window().raise_()
            self.window().setFocus()

    def _on_rest_items_saved(self, items: list):
        self.rest_apps = items
        self._update_modes_status_ui()
        self.auto_save()

    def _open_gigachat_auth(self):
        dialog = GigaChatAuthDialog(font_family=self.font_family, parent=self.window())
        dialog.key_saved.connect(self._on_gigachat_key_saved)
        dialog.exec()
        if self.window():
            self.window().activateWindow()
            self.window().raise_()
            self.window().setFocus()

    def _on_gigachat_key_saved(self, key):
        self.gigachat_key = key
        self._update_gigachat_status_ui()
        self.auto_save()

    def _update_gigachat_status_ui(self):
        active_col, idle_col = self._get_status_colors()
        if self.gigachat_key:
            self.lbl_gigachat_status.setText("АКТИВЕН ✓")
            self.lbl_gigachat_status.setStyleSheet(f"color: {active_col}; font-weight: bold;")
            self.btn_gigachat_auth.setText("ИЗМЕНИТЬ")
        else:
            self.lbl_gigachat_status.setText("НЕ ПРИВЯЗАН")
            self.lbl_gigachat_status.setStyleSheet(f"color: {idle_col};")
            self.btn_gigachat_auth.setText("НАСТРОИТЬ")

    def _open_yandex_auth(self):
        dialog = YandexAuthDialog(font_family=self.font_family, parent=self.window())
        dialog.token_obtained.connect(self._on_yandex_token_received)
        dialog.exec()
        if self.window():
            self.window().activateWindow()
            self.window().raise_()
            self.window().setFocus()

    def _on_yandex_token_received(self, token):
        self.yandex_music_token = token
        self._update_yandex_status_ui()
        self.auto_save()

    def _update_yandex_status_ui(self):
        active_col, idle_col = self._get_status_colors()
        if self.yandex_music_token:
            self.lbl_ya_status.setText("ПРИВЯЗАНА ✓")
            self.lbl_ya_status.setStyleSheet(f"color: {active_col}; font-weight: bold;")
            self.btn_ya_auth.setText("ИЗМЕНИТЬ")
        else:
            self.lbl_ya_status.setText("НЕ ПРИВЯЗАНА")
            self.lbl_ya_status.setStyleSheet(f"color: {idle_col};")
            self.btn_ya_auth.setText("ВОЙТИ")

    def _open_yandex_iot_auth(self):
        dialog = YandexIotAuthDialog(font_family=self.font_family, parent=self.window())
        dialog.token_obtained.connect(self._on_yandex_iot_token_received)
        dialog.exec()
        if self.window():
            self.window().activateWindow()
            self.window().raise_()
            self.window().setFocus()

    def _on_yandex_iot_token_received(self, token):
        self.yandex_iot_token = token
        self._update_yandex_iot_status_ui()
        self.auto_save()

    def _update_yandex_iot_status_ui(self):
        active_col, idle_col = self._get_status_colors()
        if self.yandex_iot_token:
            self.lbl_ya_iot_status.setText("ПРИВЯЗАН ✓")
            self.lbl_ya_iot_status.setStyleSheet(f"color: {active_col}; font-weight: bold;")
            self.btn_ya_iot_auth.setText("ИЗМЕНИТЬ")
        else:
            self.lbl_ya_iot_status.setText("НЕ ПРИВЯЗАН")
            self.lbl_ya_iot_status.setStyleSheet(f"color: {idle_col};")
            self.btn_ya_iot_auth.setText("ВОЙТИ")

    def _open_spotify_auth(self):
        dialog = SpotifyAuthDialog(font_family=self.font_family, parent=self.window())
        dialog.auth_completed.connect(self._on_spotify_auth_completed)
        dialog.exec()
        if self.window():
            self.window().activateWindow()
            self.window().raise_()
            self.window().setFocus()

    def _on_spotify_auth_completed(self):
        self._update_spotify_status_ui()
        self.auto_save()

    def _update_spotify_status_ui(self):
        active_col, idle_col = self._get_status_colors()
        if self.spotify_manager.is_authenticated():
            self.lbl_spotify_status.setText("ПРИВЯЗАН ✓")
            self.lbl_spotify_status.setStyleSheet(f"color: {active_col}; font-weight: bold;")
            self.btn_spotify_auth.setText("ИЗМЕНИТЬ")
        else:
            self.lbl_spotify_status.setText("НЕ ПРИВЯЗАН")
            self.lbl_spotify_status.setStyleSheet(f"color: {idle_col};")
            self.btn_spotify_auth.setText("ВОЙТИ")

    def _update_update_status_ui(self):
        active_col, idle_col = self._get_status_colors()
        if not self.update_download_url:
            self.lbl_update_status.setText("Версия актуальна")
            self.lbl_update_status.setStyleSheet(f"color: {idle_col};")
        else:
            self.lbl_update_status.setStyleSheet(f"color: {active_col}; font-weight: bold;")

    def _update_all_statuses_ui(self):
        self._update_modes_status_ui()
        self._update_gigachat_status_ui()
        self._update_yandex_status_ui()
        self._update_yandex_iot_status_ui()
        self._update_spotify_status_ui()
        self._refresh_voiceprint_ui()
        self._update_update_status_ui()

    def _apply_button_styles(self):
        if self.current_theme == "light":
            action_css = """
                QPushButton#BentoActionBtn {
                    background-color: #111318;
                    color: #ffffff;
                    font-weight: bold;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 9px;
                    letter-spacing: 0.5px;
                }
                QPushButton#BentoActionBtn:hover {
                    background-color: #2b313d;
                    color: #ffffff;
                }
            """
            secondary_css = """
                QPushButton#BentoSecondaryBtn {
                    background-color: #ffffff;
                    color: #111318;
                    font-weight: bold;
                    border: 1.5px solid #111318;
                    border-radius: 6px;
                    padding: 2px 4px;
                    font-size: 8px;
                    letter-spacing: 0.5px;
                }
                QPushButton#BentoSecondaryBtn:hover {
                    background-color: #111318;
                    color: #ffffff;
                    border: 1.5px solid #111318;
                }
            """
            action_buttons = [
                self.btn_enroll_owner, self.btn_manage_faces, self.pair_btn,
                self.btn_gigachat_auth, self.btn_ya_auth, self.btn_ya_iot_auth, self.btn_spotify_auth
            ]
            for btn in action_buttons:
                btn.setStyleSheet(action_css)

            secondary_buttons = [
                self.btn_add_friend, self.btn_add_face, self.btn_preview_alarm, self.btn_choose_custom_alarm
            ]
            for btn in secondary_buttons:
                btn.setStyleSheet(secondary_css)

            if hasattr(self, 'card_modes') and hasattr(self.card_modes, 'content_widget'):
                for b in self.card_modes.content_widget.findChildren(QPushButton, "BentoActionBtn"):
                    b.setStyleSheet(action_css)
        else:
            action_css = """
                QPushButton#BentoActionBtn {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
                    color: #121008;
                    font-weight: bold;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 9px;
                    letter-spacing: 0.5px;
                }
                QPushButton#BentoActionBtn:hover {
                    background: #ffffff;
                    color: #121008;
                }
            """
            secondary_css = """
                QPushButton#BentoSecondaryBtn {
                    background-color: #070705;
                    color: #ded7c4;
                    font-weight: bold;
                    border: 1px solid #78735f;
                    border-radius: 6px;
                    padding: 2px 4px;
                    font-size: 8px;
                    letter-spacing: 0.5px;
                }
                QPushButton#BentoSecondaryBtn:hover {
                    background-color: #1e1b14;
                    color: #ffffff;
                    border: 1px solid #9e9780;
                }
            """
            action_buttons = [
                self.btn_enroll_owner, self.btn_manage_faces, self.pair_btn,
                self.btn_gigachat_auth, self.btn_ya_auth, self.btn_ya_iot_auth, self.btn_spotify_auth
            ]
            for btn in action_buttons:
                btn.setStyleSheet(action_css)

            secondary_buttons = [
                self.btn_add_friend, self.btn_add_face, self.btn_preview_alarm, self.btn_choose_custom_alarm
            ]
            for btn in secondary_buttons:
                btn.setStyleSheet(secondary_css)

            if hasattr(self, 'card_modes') and hasattr(self.card_modes, 'content_widget'):
                for b in self.card_modes.content_widget.findChildren(QPushButton, "BentoActionBtn"):
                    b.setStyleSheet(action_css)

    def _update_theme_ui(self):
        for tog in (self.autostart_toggle, self.spotify_toggle, self.face_rec_toggle, self.eye_tracking_toggle, self.gestures_toggle):
            tog.set_theme(self.current_theme)
        for combo in (self.theme_combo, self.fps_combo, self.vpn_combo, self.alarm_sound_combo, self.gender_combo):
            combo.set_theme(self.current_theme)
        if hasattr(self, 'cards'):
            for card in self.cards:
                card.set_theme(self.current_theme)
        self._apply_button_styles()
        self._update_all_statuses_ui()
        self.update()

    def set_theme(self, theme: str):
        self.current_theme = theme
        idx = self.theme_combo.findData(theme)
        if idx != -1 and self.theme_combo.currentIndex() != idx:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(idx)
            self.theme_combo.blockSignals(False)
        self._update_theme_ui()

    def load_settings(self):
        cfg = load_config()
        api_keys = cfg.get("api_keys", {})
        modules = cfg.get("modules", {})

        self.autostart_toggle.setChecked(cfg.get("autostart", False))
        self._refresh_voiceprint_ui()

        theme_val = cfg.get("theme", "dark").lower()
        idx_th = self.theme_combo.findData(theme_val)
        if idx_th != -1:
            self.theme_combo.setCurrentIndex(idx_th)
        self.current_theme = theme_val

        self.name_input.setText(cfg.get("user_name", "друг"))

        vol_val = int(cfg.get("voice_volume", 100))
        self.voice_slider.setValue(vol_val)
        self.lbl_vol_title.setText(f"Голос: {vol_val}%")

        alarm_sound_val = cfg.get("alarm_sound", "alarm_1")
        idx_alarm = self.alarm_sound_combo.findData(alarm_sound_val)
        if idx_alarm != -1:
            self.alarm_sound_combo.setCurrentIndex(idx_alarm)
        self.custom_alarm_path = cfg.get("custom_alarm_path", "")
        self.btn_choose_custom_alarm.setVisible(alarm_sound_val == "custom")

        fps_val = int(cfg.get("target_fps", 60))
        idx_fps = self.fps_combo.findData(fps_val)
        if idx_fps != -1:
            self.fps_combo.setCurrentIndex(idx_fps)

        gender_val = cfg.get("user_gender", "male").lower()
        idx_g = self.gender_combo.findData(gender_val)
        if idx_g != -1:
            self.gender_combo.setCurrentIndex(idx_g)

        vpn_val = cfg.get("vpn_service", "none").lower()
        idx = self.vpn_combo.findData(vpn_val)
        if idx != -1:
            self.vpn_combo.setCurrentIndex(idx)

        use_sp = cfg.get("music_service", "yandex") == "spotify" or cfg.get("use_spotify", False)
        self.spotify_toggle.setChecked(use_sp)

        w_apps = cfg.get("work_apps", [])
        self.work_apps = [x.strip() for x in w_apps.split(",") if x.strip()] if isinstance(w_apps, str) else list(w_apps)

        r_apps = cfg.get("rest_apps", [])
        self.rest_apps = [x.strip() for x in r_apps.split(",") if x.strip()] if isinstance(r_apps, str) else list(r_apps)

        self._update_modes_status_ui()

        self.gigachat_key = api_keys.get("gigachat", "")
        self._update_gigachat_status_ui()

        self.yandex_music_token = api_keys.get("yandex_music_token", "")
        self._update_yandex_status_ui()

        self.yandex_iot_token = api_keys.get("yandex_iot_token", "")
        self._update_yandex_iot_status_ui()

        self._update_spotify_status_ui()

        vision_legacy = modules.get("vision", False)
        face_on = modules.get("face_recognition", vision_legacy)
        eye_on = modules.get("eye_tracking", vision_legacy)
        gest_on = modules.get("gestures", False)

        self.saved_vision_state = face_on or eye_on or gest_on

        self.face_rec_toggle.blockSignals(True)
        self.eye_tracking_toggle.blockSignals(True)
        self.gestures_toggle.blockSignals(True)

        self.face_rec_toggle.setChecked(face_on)
        self.eye_tracking_toggle.setChecked(eye_on)
        self.gestures_toggle.setChecked(gest_on)

        self.face_rec_toggle.blockSignals(False)
        self.eye_tracking_toggle.blockSignals(False)
        self.gestures_toggle.blockSignals(False)

        self._update_face_count_ui()
        self._update_theme_ui()

    def save_settings(self):
        config_data = load_config()

        if "api_keys" not in config_data or not isinstance(config_data["api_keys"], dict):
            config_data["api_keys"] = {}
        if "modules" not in config_data or not isinstance(config_data["modules"], dict):
            config_data["modules"] = {}

        name_val = self.name_input.text().strip()
        config_data["user_name"] = name_val if name_val else "друг"

        config_data["user_gender"] = self.gender_combo.currentData()

        autostart_val = self.autostart_toggle.isChecked()
        config_data["autostart"] = autostart_val
        self._apply_windows_autostart(autostart_val)

        theme_val = self.theme_combo.currentData()
        config_data["theme"] = theme_val
        if theme_val != self.current_theme:
            self.current_theme = theme_val
            self.theme_changed.emit(theme_val)
            self.update()

        fps_val = self.fps_combo.currentData()
        config_data["target_fps"] = fps_val

        self.fps_changed.emit(fps_val)

        config_data["voice_volume"] = self.voice_slider.value()
        config_data["alarm_sound"] = self.alarm_sound_combo.currentData()
        config_data["custom_alarm_path"] = self.custom_alarm_path
        config_data["vpn_service"] = self.vpn_combo.currentData()

        use_spotify_val = self.spotify_toggle.isChecked()
        config_data["music_service"] = "spotify" if use_spotify_val else "yandex"
        config_data["use_spotify"] = use_spotify_val

        config_data["work_apps"] = self.work_apps
        config_data["rest_apps"] = self.rest_apps

        config_data["api_keys"]["gigachat"] = self.gigachat_key
        config_data["api_keys"]["yandex_music_token"] = self.yandex_music_token
        config_data["api_keys"]["yandex_iot_token"] = self.yandex_iot_token

        config_data["modules"]["gigachat"] = bool(self.gigachat_key)
        config_data["modules"]["telegram"] = bool(config_data["api_keys"].get("telegram_admin_id", 0))

        face_on = self.face_rec_toggle.isChecked()
        eye_on = self.eye_tracking_toggle.isChecked()
        gest_on = self.gestures_toggle.isChecked()

        config_data["modules"]["face_recognition"] = face_on
        config_data["modules"]["eye_tracking"] = eye_on
        config_data["modules"]["gestures"] = gest_on

        any_vision_on = face_on or eye_on or gest_on
        config_data["modules"]["vision"] = any_vision_on

        try:
            save_config(config_data)

            if any_vision_on and not self.saved_vision_state:
                self.speak_requested.emit("Подожди чуточку!")
            elif not any_vision_on and self.saved_vision_state:
                self.speak_requested.emit("Закрываю глазки!")

            if any_vision_on != self.saved_vision_state:
                self.saved_vision_state = any_vision_on
                self.vision_state_changed.emit(any_vision_on)

        except Exception as e:
            self.status_label.setText("✕ ОШИБКА")
            self.status_label.setStyleSheet("color: #ff5252; font-size: 8px; font-weight: bold;")
            print(f"[Settings Save Error]: {e}")

    def _on_border_anim_step(self, val):
        self.border_opacity = float(val)
        self.update()

    def fade_in_border(self, duration=350):
        self.border_anim.stop()
        self.border_anim.setDuration(duration)
        self.border_anim.setStartValue(self.border_opacity)
        self.border_anim.setEndValue(1.0)
        self.border_anim.start()

    def fade_out_border(self, duration=150):
        self.border_anim.stop()
        self.border_anim.setDuration(duration)
        self.border_anim.setStartValue(self.border_opacity)
        self.border_anim.setEndValue(0.0)
        self.border_anim.start()

    def reset_border(self):
        self.border_anim.stop()
        self.border_opacity = 0.0
        self.update()

    def animate_border(self):
        if self.border_opacity > 0.001:
            self.border_phase += 0.010
            self.update()

    def _refresh_voiceprint_ui(self):
        active_col, idle_col = self._get_status_colors()
        if self.speaker_verifier.is_enrolled():
            owner_name = self.speaker_verifier.get_owner_name()
            users = self.speaker_verifier.get_users_list()
            friends = [u["name"] for u in users if not u["is_owner"]]
            friends_str = f" | Доверенные: {', '.join(friends)}" if friends else ""
            self.lbl_vp_status.setText(f"Владелец: {owner_name}{friends_str}")
            self.lbl_vp_status.setStyleSheet(f"color: {active_col};")
            self.btn_enroll_owner.setText("ПЕРЕЗАПИСАТЬ")
            self.btn_add_friend.setEnabled(True)
        else:
            self.lbl_vp_status.setText("Слепок: не записан")
            self.lbl_vp_status.setStyleSheet(f"color: {idle_col};")
            self.btn_enroll_owner.setText("ЗАПИСАТЬ")
            self.btn_add_friend.setEnabled(False)

    def _open_enroll_owner(self):
        dialog = VoiceEnrollmentDialog(self.speaker_verifier, is_owner=True, font_family=self.font_family, parent=self.window())
        dialog.enrollment_completed.connect(self._refresh_voiceprint_ui)
        dialog.exec()
        if self.window():
            self.window().activateWindow()

    def _open_enroll_friend(self):
        dialog = VoiceEnrollmentDialog(self.speaker_verifier, is_owner=False, font_family=self.font_family, parent=self.window())
        dialog.enrollment_completed.connect(self._refresh_voiceprint_ui)
        dialog.exec()
        if self.window():
            self.window().activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        if w < 15 or h < 15:
            return

        rect = QRectF(0.75, 0.75, w - 1.5, h - 1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        bg_col = QColor(234, 238, 246, 252) if self.current_theme == "light" else QColor(8, 8, 5, 240)
        painter.fillPath(path, bg_col)

        if self.border_opacity > 0.001:
            cx, cy = w / 2, h / 2
            dx = math.cos(self.border_phase) * w
            dy = math.sin(self.border_phase) * h

            border_width = 2.5 if self.current_theme == "light" else 1.5
            border_grad = QLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
            if self.current_theme == "light":
                border_grad.setColorAt(0.0, QColor(17, 19, 24, 75))
                border_grad.setColorAt(0.35, QColor(17, 19, 24, 185))
                border_grad.setColorAt(0.5, QColor(17, 19, 24, 255))
                border_grad.setColorAt(0.65, QColor(17, 19, 24, 185))
                border_grad.setColorAt(1.0, QColor(17, 19, 24, 75))
            else:
                border_grad.setColorAt(0.0, QColor("#141310"))
                border_grad.setColorAt(0.35, QColor("#38352b"))
                border_grad.setColorAt(0.5, QColor("#78735f"))
                border_grad.setColorAt(0.65, QColor("#38352b"))
                border_grad.setColorAt(1.0, QColor("#141310"))

            painter.setOpacity(self.border_opacity)
            pen_border = QPen(QBrush(border_grad), border_width)
            painter.setPen(pen_border)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)