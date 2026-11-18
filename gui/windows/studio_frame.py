import os
import re
import math
import random
from datetime import datetime
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFileDialog, QSizePolicy,
    QTextEdit, QLineEdit, QGraphicsOpacityEffect, QLayout
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QRect, QRectF, QPoint, QPointF, pyqtSignal, QThread,
    QVariantAnimation, QEasingCurve, QByteArray, QEvent, QUrl
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QRadialGradient, QGradient,
    QBrush, QPainterPath, QFont, QFontMetrics, QFontDatabase, QIcon, QPixmap,
    QTextCursor, QGuiApplication, QImage
)
from PyQt6.QtSvg import QSvgRenderer
from core.utils.config import get_resource_path, load_config
from gui.styles import get_main_style
from core.database.chat_db import studio_db
from core.nlp.generative.media_provider import media_provider
from gui.widgets.code_formatter import (
    CodeBlockWidget,
    parse_message_blocks,
    markdown_to_rich_html,
    print_markdown_console,
)

from core.utils.text_cleaner import clean_chat_display_text, clean_voice_text, CHAT_ACTION_TAG_REGEX as ACTION_TAG_REGEX

SVG_SIDEBAR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/>
</svg>"""

SVG_PAPERCLIP = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
</svg>"""

SVG_SEND = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
</svg>"""

SVG_EDIT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
</svg>"""

SVG_MEDIA_IMAGE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
<circle cx="8.5" cy="8.5" r="1.5"/>
<polyline points="21 15 16 10 5 21"/>
</svg>"""

SVG_MEDIA_MUSIC = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M9 18V5l12-2v13"/>
<circle cx="6" cy="18" r="3"/>
<circle cx="18" cy="16" r="3"/>
</svg>"""

SVG_SPARKLES = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M12 3v3m0 12v3M3 12h3m12 0h3M6.34 6.34l2.12 2.12m7.08 7.08l2.12 2.12M6.34 17.66l2.12-2.12m7.08-7.08l2.12-2.12"/>
</svg>"""

SVG_PLAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
<polygon points="6 4 20 12 6 20 6 4"/>
</svg>"""

SVG_PAUSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
<rect x="6" y="4" width="4" height="16" rx="1"/>
<rect x="14" y="4" width="4" height="16" rx="1"/>
</svg>"""

SVG_DOWNLOAD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
<polyline points="7 10 12 15 17 10"/>
<line x1="12" y1="15" x2="12" y2="3"/>
</svg>"""

SVG_COPY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
</svg>"""

SVG_CHECK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<polyline points="20 6 9 17 4 12"/>
</svg>"""


def resolve_media_path(path_str: str) -> str:
    """Универсальное разрешение пути к медиафайлу (относительный или абсолютный)."""
    if not path_str:
        return ""
    clean = path_str.strip().replace('\\', '/')
    if os.path.isabs(clean) and os.path.exists(clean):
        return os.path.normpath(clean)
    cwd_path = os.path.normpath(os.path.join(os.getcwd(), clean))
    if os.path.exists(cwd_path):
        return cwd_path
    app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root_path = os.path.normpath(os.path.join(app_root, clean))
    if os.path.exists(root_path):
        return root_path
    p_data = os.path.normpath(os.path.join(app_root, "personal_data", clean))
    if os.path.exists(p_data):
        return p_data
    return clean

ALL_STUDIO_MODELS = [
    ("Hikari", "hikari"),
    ("Kasumi", "kasumi"),
    ("Ginga", "ginga"),
    ("Uchū", "uchuu"),
]

STUDIO_PLACEHOLDERS = [
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

STUDIO_NEW_CHAT_PHRASES = [
    "+ Хадзиме!",
    "+ Новая история...",
    "+ К звёздам...",
    "+ Поехали!",
    "+ Расскажи, я тут!",
    "+ Чмок!",
    "+ Пойдём болтать!",
    "+ Всегда рядом!"
]


def _has_routerai_key() -> bool:
    """Проверяет наличие активного ключа RouterAI или OpenRouter в config.json."""
    try:
        cfg = load_config()
        api_keys = cfg.get("api_keys", {})
        return bool(
            api_keys.get("routerai", "").strip()
            or api_keys.get("openrouter", "").strip()
        )
    except Exception:
        return False


def _get_available_studio_models() -> list[tuple[str, str]]:
    """Возвращает доступные слоты моделей в зависимости от настроенных ключей."""
    try:
        cfg = load_config()
        api_keys = cfg.get("api_keys", {})
        has_giga = bool(api_keys.get("gigachat", "").strip())
        has_routerai = _has_routerai_key()
    except Exception:
        has_giga, has_routerai = True, False

    if has_giga and has_routerai:
        return list(ALL_STUDIO_MODELS)
    if has_routerai and not has_giga:
        return [m for m in ALL_STUDIO_MODELS if m[1] != "hikari"]
    return [("Hikari", "hikari")]


def _render_svg(svg_xml: str, color: str, size: int = 14) -> QIcon:
    xml = svg_xml.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(xml.encode("utf-8")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)

class SmoothScrollArea(QScrollArea):
    """Плавный инерционный скролл колёсиком мыши и мягкая автопрокрутка вниз."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._current_pos = 0.0
        self._velocity = 0.0
        self._friction = 0.935
        self._auto_target = None

        self._timer = QTimer(self)
        self._timer.setInterval(12)
        self._timer.timeout.connect(self._on_smooth_step)

        v_bar = self.verticalScrollBar()
        v_bar.sliderPressed.connect(self._on_slider_pressed)

    def _on_slider_pressed(self):
        self._timer.stop()
        self._velocity = 0.0
        self._auto_target = None
        self._current_pos = float(self.verticalScrollBar().value())

    def smooth_scroll_to_bottom(self):
        v_bar = self.verticalScrollBar()
        max_val = float(v_bar.maximum())
        if max_val <= 0:
            return
        self._current_pos = float(v_bar.value())
        self._velocity = 0.0
        self._auto_target = max_val
        if not self._timer.isActive():
            self._timer.start()

    def wheelEvent(self, event):
        v_bar = self.verticalScrollBar()
        min_val = float(v_bar.minimum())
        max_val = float(v_bar.maximum())

        if min_val >= max_val:
            super().wheelEvent(event)
            return

        self._auto_target = None
        if not self._timer.isActive():
            self._current_pos = float(v_bar.value())
            self._velocity = 0.0

        p_delta = event.pixelDelta().y()
        a_delta = event.angleDelta().y()

        if p_delta != 0:
            impulse = -p_delta * 0.45
        elif a_delta != 0:
            impulse = -(a_delta / 120.0) * 8.5
        else:
            super().wheelEvent(event)
            return

        self._velocity += impulse
        self._velocity = max(-40.0, min(40.0, self._velocity))

        if not self._timer.isActive():
            self._timer.start()

        event.accept()

    def _on_smooth_step(self):
        v_bar = self.verticalScrollBar()
        min_val = float(v_bar.minimum())
        max_val = float(v_bar.maximum())

        if self._auto_target is not None:
            target = float(v_bar.maximum())
            diff = target - self._current_pos
            if abs(diff) < 1.0:
                self._current_pos = target
                v_bar.setValue(int(round(target)))
                self._auto_target = None
                self._timer.stop()
                return
            self._current_pos += diff * 0.18
            v_bar.setValue(int(round(self._current_pos)))
            return

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


class MessageRail(QWidget):
    """Сглаженная вертикальная полоска-индикатор со скруглёнными краями."""
    def __init__(self, color: QColor, width: int = 4, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedWidth(width)
        self.setMinimumHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_color(self, color: QColor):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())
        if w <= 0 or h <= 0:
            return
        radius = w / 2.0
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.0, 0.0, w, h), radius, radius)
        painter.fillPath(path, self._color)
        painter.end()

class StudioWorker(QThread):
    result_ready = pyqtSignal(object)

    def __init__(self, parser, text, attached_file=None, model="hikari", parent=None):
        super().__init__(parent)
        self.parser = parser
        self.text = text
        self.attached_file = attached_file
        self.model = model

    def run(self):
        if hasattr(self.parser, 'llm') and hasattr(self.parser.llm, 'set_model'):
            try:
                self.parser.llm.set_model(self.model)
            except Exception:
                pass

        response = self.parser.process_command(
            self.text,
            is_voice=False,
            attached_file=self.attached_file
        )
        self.result_ready.emit(response)


class StudioTitleWorker(QThread):
    """Фоновый генератор краткого заголовка темы диалога с помощью нейросети."""
    title_ready = pyqtSignal(int, str)

    def __init__(self, parser, session_id: int, user_text: str, akira_text: str, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.session_id = session_id
        self.user_text = user_text
        self.akira_text = akira_text

    def run(self):
        prompt = (
            "Сформулируй краткую суть темы диалога на русском языке для заголовка вкладки.\n"
            "ТРЕБОВАНИЯ:\n"
            "1. Длина строго от 2 до 4 слов.\n"
            "2. Первая буква заглавная, без точки в конце, без кавычек и вводных слов.\n"
            f"Вопрос пользователя: {self.user_text[:200]}\n"
            f"Ответ: {self.akira_text[:200]}\n"
            "Заголовок:"
        )

        title = ""
        try:
            llm = getattr(self.parser, 'llm', None)
            if llm:
                # 1. Приоритет — быстрые не-reasoning модели RouterAI (deepseek-chat, gpt-4o-mini, gemini-2.5-flash-lite)
                if hasattr(llm, "_init_routerai") and llm._init_routerai()[0]:
                    candidate_models = [
                        "deepseek/deepseek-chat",
                        "openai/gpt-4o-mini",
                        "google/gemini-2.5-flash-lite"
                    ]
                    for cand in candidate_models:
                        try:
                            response = llm.routerai_client.chat.completions.create(
                                model=cand,
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.3,
                                max_tokens=30
                            )
                            if response and getattr(response, "choices", None):
                                txt = getattr(response.choices[0].message, "content", "") or ""
                                if txt.strip():
                                    title = txt.strip()
                                    break
                        except Exception:
                            continue

                # 2. Если RouterAI недоступен или не вернул ответ, используем GigaChat
                if not title and hasattr(llm, "_init_gigachat") and llm._init_gigachat()[0]:
                    try:
                        ans = llm._ask_gigachat([{"role": "user", "content": prompt}])
                        if ans and isinstance(ans, str) and not ans.startswith("Ай, споткнулась"):
                            title = ans.strip()
                    except Exception:
                        pass
        except Exception:
            pass

        clean_title = title.replace('"', '').replace("'", '').replace("«", '').replace("»", '').replace("“", '').replace("”", '').strip()
        clean_title = re.sub(r'^(?:заголовок|тема)\s*[:—\-]\s*', '', clean_title, flags=re.IGNORECASE).strip()
        clean_title = clean_title.rstrip('.!? ')

        if not clean_title or len(clean_title) < 3:
            words = [w for w in self.user_text.strip().split() if len(w) > 1][:4]
            clean_title = " ".join(words).capitalize() if words else "Диалог"
        else:
            clean_title = clean_title[0].upper() + clean_title[1:]

        if len(clean_title) > 34:
            clean_title = clean_title[:31] + "..."

        self.title_ready.emit(self.session_id, clean_title)


class StudioMediaWorker(QThread):
    """Фоновый поток генерации медиаконтента (изображения или музыки) через RouterAI."""
    media_ready = pyqtSignal(str, str, str)  # media_type, file_path, prompt
    media_failed = pyqtSignal(str, str)      # media_type, error_str

    def __init__(self, media_type: str, prompt: str, attached_file: str = None, parent=None):
        super().__init__(parent)
        self.media_type = media_type
        self.prompt = prompt
        self.attached_file = attached_file

    def run(self):
        try:
            if self.media_type == "image":
                path = media_provider.generate_image(self.prompt, ref_image_path=self.attached_file)
                self.media_ready.emit("image", path, self.prompt)
            elif self.media_type == "music":
                path = media_provider.generate_music(self.prompt, ref_image_path=self.attached_file)
                self.media_ready.emit("music", path, self.prompt)
            else:
                self.media_failed.emit(self.media_type, f"Неизвестный тип медиа: {self.media_type}")
        except Exception as e:
            self.media_failed.emit(self.media_type, str(e))


class AudioTrackBar(QWidget):
    """Интерактивный индикатор воспроизведения аудио с волнообразной фактурой."""
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self.current_theme = "dark"
        self.emotion_color = QColor("#38bdf8")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._is_dragging = False

    def set_progress(self, pos_ms: int, dur_ms: int):
        if dur_ms > 0:
            self._progress = max(0.0, min(1.0, float(pos_ms) / float(dur_ms)))
            self.update()

    def set_theme(self, theme: str, emo_col: QColor):
        self.current_theme = theme
        self.emotion_color = QColor(emo_col)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._emit_seek(event.pos().x())

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self._emit_seek(event.pos().x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False

    def _emit_seek(self, x: int):
        ratio = max(0.0, min(1.0, float(x) / max(1.0, float(self.width()))))
        self._progress = ratio
        self.update()
        self.seek_requested.emit(ratio)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        is_light = (self.current_theme == "light")

        num_bars = 28
        spacing = 2.0
        total_bar_w = max(1.5, (w - (num_bars - 1) * spacing) / num_bars)
        mid_y = h / 2.0
        active_x = w * self._progress

        for i in range(num_bars):
            bx = i * (total_bar_w + spacing)
            seed = (math.sin(i * 0.75) * 0.4 + math.cos(i * 1.3) * 0.3 + 0.7)
            bar_h = max(4.0, min(h - 2.0, seed * (h - 4.0)))
            by = mid_y - bar_h / 2.0

            is_active = (bx + total_bar_w <= active_x)
            if is_active:
                col = self.emotion_color
            else:
                col = QColor(15, 23, 42, 45) if is_light else QColor(255, 255, 255, 45)

            bar_rect = QRectF(bx, by, total_bar_w, bar_h)
            path = QPainterPath()
            path.addRoundedRect(bar_rect, 1.5, 1.5)
            painter.fillPath(path, col)

        painter.end()


class ImageMediaCard(QFrame):
    """Карточка сгенерированного изображения:
    - loading: "Цифровой эфир" 60 FPS с дрейфующим градиентом эмоции, 12-18 частицами и шиммером
    - revealing: 450ms OutCubic сканирующая полоса с открытием кадра (scale 1.03 -> 1.0)
    - ready: просмотр изображения со скруглёнными краями и оверлей-кнопками (Копировать, Скачать)
    """
    def __init__(
        self,
        image_path: str = "",
        emotion_color: QColor = None,
        font_family: str = "Segoe UI",
        theme: str = "dark",
        state: str = "ready",
        parent=None
    ):
        super().__init__(parent)
        self.raw_image_path = image_path
        self.image_path = resolve_media_path(image_path)
        self.emotion_color = QColor(emotion_color) if emotion_color else QColor("#38bdf8")
        self.font_family = font_family
        self.current_theme = theme
        self.state = state  # "loading", "revealing", "ready", "failed"
        self.error_text = ""
        self._pixmap = None
        self._hovered = False

        self._anim_timer = None
        self._particles = []
        self._shimmer_phase = 0.0
        self._scan_progress = 0.0

        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self.overlay_widget = QWidget(self)
        self.overlay_layout = QHBoxLayout(self.overlay_widget)
        self.overlay_layout.setContentsMargins(6, 6, 6, 6)
        self.overlay_layout.setSpacing(6)
        self.overlay_layout.addStretch()

        self.copy_btn = QPushButton(self.overlay_widget)
        self.copy_btn.setFixedSize(26, 26)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setToolTip("Скопировать изображение")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        self.overlay_layout.addWidget(self.copy_btn)

        self.save_btn = QPushButton(self.overlay_widget)
        self.save_btn.setFixedSize(26, 26)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setToolTip("Сохранить PNG")
        self.save_btn.clicked.connect(self._save_image)
        self.overlay_layout.addWidget(self.save_btn)

        self._update_overlay_style()
        self.overlay_widget.hide()

        if self.state == "loading":
            self._init_loading()
        else:
            self._load_pixmap()

    def _init_loading(self):
        self.state = "loading"
        self.setFixedSize(380, 260)
        self.overlay_widget.hide()

        self._particles = []
        for _ in range(16):
            self._particles.append({
                "x": random.uniform(0.05, 0.95),
                "y": random.uniform(0.05, 0.95),
                "vx": random.uniform(-0.002, 0.002),
                "vy": random.uniform(-0.003, 0.003),
                "r": random.uniform(1.8, 3.8),
                "alpha": random.uniform(0.25, 0.75)
            })

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_loading_tick)
        self._anim_timer.start()

    def _on_loading_tick(self):
        for p in self._particles:
            p["x"] = (p["x"] + p["vx"]) % 1.0
            p["y"] = (p["y"] + p["vy"]) % 1.0
        self._shimmer_phase = (self._shimmer_phase + 0.016) % 2.5
        self.update()

    def reveal_image(self, file_path: str):
        if self._anim_timer and self._anim_timer.isActive():
            self._anim_timer.stop()
        self.raw_image_path = file_path
        self.image_path = resolve_media_path(file_path)
        self._load_pixmap()

        self.state = "revealing"
        self._reveal_anim = QVariantAnimation(self)
        self._reveal_anim.setDuration(450)
        self._reveal_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._reveal_anim.setStartValue(0.0)
        self._reveal_anim.setEndValue(1.0)
        self._reveal_anim.valueChanged.connect(self._on_reveal_step)
        self._reveal_anim.finished.connect(self._on_reveal_finished)
        self._reveal_anim.start()

    def _on_reveal_step(self, val):
        self._scan_progress = float(val)
        self.update()

    def _on_reveal_finished(self):
        self.state = "ready"
        self.update()

    def set_failed(self, error_msg: str):
        if self._anim_timer and self._anim_timer.isActive():
            self._anim_timer.stop()
        self.state = "failed"
        self.error_text = error_msg
        self.setFixedSize(380, 110)
        self.overlay_widget.hide()
        self.update()

    def _load_pixmap(self):
        if self.image_path and os.path.exists(self.image_path):
            self._pixmap = QPixmap(self.image_path)
            if not self._pixmap.isNull():
                orig_size = self._pixmap.size()
                max_w, max_h = 440, 360
                scaled = orig_size.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio)
                card_w = max(280, scaled.width())
                card_h = max(180, scaled.height())
                self.setFixedSize(card_w, card_h)
                self.overlay_widget.setGeometry(0, 0, card_w, 40)
                self.state = "ready"
                return
        self.setFixedSize(380, 200)

    def _copy_to_clipboard(self):
        if self._pixmap and not self._pixmap.isNull():
            QGuiApplication.clipboard().setPixmap(self._pixmap)
            QGuiApplication.clipboard().setImage(self._pixmap.toImage())
            self.copy_btn.setIcon(_render_svg(SVG_CHECK, "#4ade80", 14))
            icon_col = "#1e293b" if self.current_theme == "light" else "#ded7c4"
            QTimer.singleShot(1800, lambda: self.copy_btn.setIcon(_render_svg(SVG_COPY, icon_col, 14)))

    def _save_image(self):
        if not self._pixmap or self._pixmap.isNull():
            return
        default_name = os.path.basename(self.image_path) if self.image_path else "akira_art.png"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить изображение",
            default_name,
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;All Files (*.*)"
        )
        if save_path:
            self._pixmap.save(save_path)

    def mouseDoubleClickEvent(self, event):
        if self.state == "ready" and self.image_path and os.path.exists(self.image_path):
            try:
                os.startfile(self.image_path)
            except Exception:
                pass
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        if self.state == "ready":
            self.overlay_widget.show()
            self.overlay_widget.raise_()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.overlay_widget.hide()
        self.update()
        super().leaveEvent(event)

    def set_theme(self, theme: str, emotion_color: QColor = None):
        self.current_theme = theme
        if emotion_color is not None:
            self.emotion_color = QColor(emotion_color)
        self._update_overlay_style()
        self.update()

    def _update_overlay_style(self):
        is_light = (self.current_theme == "light")
        icon_col = "#1e293b" if is_light else "#ded7c4"
        btn_bg = "rgba(255, 255, 255, 0.85)" if is_light else "rgba(15, 17, 23, 0.78)"
        btn_border = "rgba(0, 0, 0, 0.15)" if is_light else "rgba(255, 255, 255, 0.18)"
        btn_hover = "rgba(255, 255, 255, 0.98)" if is_light else "rgba(30, 34, 45, 0.9)"

        btn_qss = f"""
            QPushButton {{
                background-color: {btn_bg};
                border: 1px solid {btn_border};
                border-radius: 6px;
                padding: 3px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
                border: 1px solid {self.emotion_color.name()};
            }}
        """
        self.copy_btn.setStyleSheet(btn_qss)
        self.save_btn.setStyleSheet(btn_qss)
        self.copy_btn.setIcon(_render_svg(SVG_COPY, icon_col, 14))
        self.save_btn.setIcon(_render_svg(SVG_DOWNLOAD, icon_col, 14))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        is_light = (self.current_theme == "light")
        emo = self.emotion_color

        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, 14.0, 14.0)
        painter.save()
        painter.setClipPath(clip_path)

        if self.state == "loading":
            bg_col = QColor(241, 245, 249) if is_light else QColor(13, 15, 18)
            painter.fillRect(self.rect(), bg_col)

            aura = QRadialGradient(w * 0.5, h * 0.5, max(w, h) * 0.7)
            aura.setColorAt(0.0, QColor(emo.red(), emo.green(), emo.blue(), 55 if is_light else 42))
            aura.setColorAt(0.65, QColor(emo.red(), emo.green(), emo.blue(), 18 if is_light else 12))
            aura.setColorAt(1.0, QColor(emo.red(), emo.green(), emo.blue(), 0))
            painter.fillRect(self.rect(), aura)

            for p in self._particles:
                px = p["x"] * w
                py = p["y"] * h
                pr = p["r"]
                p_alpha = int(p["alpha"] * 255)
                p_col = QColor(emo.red(), emo.green(), emo.blue(), min(255, p_alpha))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(p_col))
                painter.drawEllipse(QPointF(px, py), pr, pr)

            shim_w = w * 0.5
            shim_x = -shim_w + self._shimmer_phase * (w + shim_w) / 2.0
            shimmer = QLinearGradient(shim_x, 0, shim_x + shim_w, h)
            shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
            shimmer.setColorAt(0.5, QColor(255, 255, 255, 38 if is_light else 22))
            shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.fillRect(self.rect(), shimmer)

            icon_size = 32
            icon_col = emo.name()
            icon_pix = _render_svg(SVG_MEDIA_IMAGE, icon_col, icon_size).pixmap(icon_size, icon_size)
            painter.drawPixmap(int((w - icon_size) / 2), int(h * 0.35 - icon_size / 2), icon_pix)

            painter.setPen(QColor("#1e293b" if is_light else "#ded7c4"))
            painter.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
            painter.drawText(QRectF(0, h * 0.48, w, 22), Qt.AlignmentFlag.AlignCenter, "Синтезирую кадр...")

            painter.setPen(QColor("#64748b" if is_light else "#888270"))
            painter.setFont(QFont(self.font_family, 9))
            painter.drawText(QRectF(0, h * 0.58, w, 18), Qt.AlignmentFlag.AlignCenter, "Iro")

        elif self.state == "revealing":
            scale = 1.03 - 0.03 * self._scan_progress
            scan_y = h * self._scan_progress

            bg_col = QColor(241, 245, 249) if is_light else QColor(13, 15, 18)
            painter.fillRect(self.rect(), bg_col)

            if self._pixmap and not self._pixmap.isNull():
                painter.save()
                painter.translate(w / 2.0, h / 2.0)
                painter.scale(scale, scale)
                painter.translate(-w / 2.0, -h / 2.0)
                painter.setClipRect(QRectF(0, 0, w, scan_y), Qt.ClipOperation.IntersectClip)
                painter.drawPixmap(self.rect(), self._pixmap)
                painter.restore()

            scan_grad = QLinearGradient(0, scan_y, w, scan_y)
            scan_grad.setColorAt(0.0, QColor(emo.red(), emo.green(), emo.blue(), 0))
            scan_grad.setColorAt(0.5, QColor(255, 255, 255, 230))
            scan_grad.setColorAt(1.0, QColor(emo.red(), emo.green(), emo.blue(), 0))
            painter.setPen(QPen(QBrush(scan_grad), 2.5))
            painter.drawLine(QPointF(0, scan_y), QPointF(w, scan_y))

        elif self.state == "ready":
            if self._pixmap and not self._pixmap.isNull():
                painter.drawPixmap(self.rect(), self._pixmap)
            else:
                painter.fillRect(self.rect(), QColor(20, 22, 28))
                painter.setPen(QColor("#ded7c4"))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Изображение недоступно")

            badge_w, badge_h = 148, 20
            badge_x, badge_y = 10, h - badge_h - 10
            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
            badge_path = QPainterPath()
            badge_path.addRoundedRect(badge_rect, 6.0, 6.0)
            painter.fillPath(badge_path, QColor(12, 14, 18, 180))
            painter.setPen(QColor(222, 215, 196, 210))
            painter.setFont(QFont(self.font_family, 8))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "Iro")

        elif self.state == "failed":
            bg_col = QColor(254, 242, 242) if is_light else QColor(24, 14, 16)
            painter.fillRect(self.rect(), bg_col)
            painter.setPen(QColor("#ef4444"))
            painter.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
            painter.drawText(QRectF(14, 14, w - 28, 22), Qt.AlignmentFlag.AlignLeft, "⚠️ Ошибка синтеза изображения")
            painter.setPen(QColor("#7f1d1d" if is_light else "#fca5a5"))
            painter.setFont(QFont(self.font_family, 9))
            painter.drawText(QRectF(14, 38, w - 28, h - 46), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self.error_text or "Не удалось получить изображение от модели.")

        painter.restore()

        border_col = QColor(15, 23, 42, 35) if is_light else QColor(120, 115, 95, 75)
        if self._hovered and self.state == "ready":
            border_col = QColor(emo.red(), emo.green(), emo.blue(), 160)
        painter.setPen(QPen(border_col, 1.2))
        painter.drawPath(clip_path)
        painter.end()


class AudioMediaCard(QFrame):
    """Карточка сгенерированной музыки:
    - loading: компактный бар (64px) с живым эквалайзером (18 столбиков) и анимацией генерации
    - ready: мини-плеер (72px) с кнопкой Play/Pause, интерактивным прогресс-баром/волной в цвет эмоции,
      таймером 00:00 / 00:30 и кнопкой сохранения MP3 через PyQt6.QtMultimedia
    """
    def __init__(
        self,
        audio_path: str = "",
        emotion_color: QColor = None,
        font_family: str = "Segoe UI",
        theme: str = "dark",
        state: str = "ready",
        parent=None
    ):
        super().__init__(parent)
        self.raw_audio_path = audio_path
        self.audio_path = resolve_media_path(audio_path)
        self.emotion_color = QColor(emotion_color) if emotion_color else QColor("#38bdf8")
        self.font_family = font_family
        self.current_theme = theme
        self.state = state  # "loading", "ready", "failed"
        self.error_text = ""
        self._hovered = False
        self._is_playing = False
        self._duration = 30000
        self._position = 0
        self._eq_phase = 0.0

        self._player = None
        self._audio_out = None

        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._setup_ui()

        if self.state == "loading":
            self._init_loading()
        else:
            self._init_ready()

    def _setup_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(12, 8, 12, 8)
        self.main_layout.setSpacing(12)

        self.play_btn = QPushButton(self)
        self.play_btn.setFixedSize(34, 34)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self._toggle_playback)
        self.main_layout.addWidget(self.play_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.center_col = QVBoxLayout()
        self.center_col.setContentsMargins(0, 0, 0, 0)
        self.center_col.setSpacing(3)

        self.info_row = QHBoxLayout()
        self.info_row.setContentsMargins(0, 0, 0, 0)
        self.title_lbl = QLabel("Hibiki", self)
        self.title_lbl.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        self.info_row.addWidget(self.title_lbl)

        self.info_row.addStretch()

        self.time_lbl = QLabel("00:00 / 00:30", self)
        self.time_lbl.setFont(QFont(self.font_family, 8))
        self.info_row.addWidget(self.time_lbl)
        self.center_col.addLayout(self.info_row)

        self.track_widget = AudioTrackBar(self)
        self.track_widget.setFixedHeight(18)
        self.track_widget.seek_requested.connect(self._seek_to)
        self.center_col.addWidget(self.track_widget)

        self.main_layout.addLayout(self.center_col, 1)

        self.download_btn = QPushButton(self)
        self.download_btn.setFixedSize(28, 28)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setToolTip("Сохранить MP3")
        self.download_btn.clicked.connect(self._save_audio)
        self.main_layout.addWidget(self.download_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._update_styles()

    def _init_loading(self):
        self.state = "loading"
        self.setFixedSize(390, 58)
        self.play_btn.hide()
        self.download_btn.hide()
        self.track_widget.hide()
        self.title_lbl.hide()
        self.time_lbl.hide()

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_eq_tick)
        self._anim_timer.start()

    def _on_eq_tick(self):
        self._eq_phase += 0.09
        self.update()

    def _init_ready(self):
        if hasattr(self, "_anim_timer") and self._anim_timer and self._anim_timer.isActive():
            self._anim_timer.stop()
        self.state = "ready"
        self.setFixedSize(410, 72)
        self.play_btn.show()
        self.download_btn.show()
        self.track_widget.show()
        self.title_lbl.show()
        self.time_lbl.show()
        self.title_lbl.setText("Hibiki")

        self._setup_player()
        self._update_styles()
        self.update()

    def set_ready(self, file_path: str):
        self.raw_audio_path = file_path
        self.audio_path = resolve_media_path(file_path)
        self._init_ready()

    def set_failed(self, error_msg: str):
        if hasattr(self, "_anim_timer") and self._anim_timer and self._anim_timer.isActive():
            self._anim_timer.stop()
        self.state = "failed"
        self.error_text = error_msg
        self.setFixedSize(390, 64)
        self.play_btn.hide()
        self.download_btn.hide()
        self.track_widget.hide()
        self.title_lbl.setText("⚠️ Ошибка синтеза музыки")
        self.time_lbl.setText("")
        self.update()

    def _setup_player(self):
        if not self._player:
            self._player = QMediaPlayer(self)
            self._audio_out = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_out)
            self._audio_out.setVolume(1.0)
            self._player.positionChanged.connect(self._on_position_changed)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.playbackStateChanged.connect(self._on_playback_state_changed)
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)

        if self.audio_path and os.path.exists(self.audio_path):
            self._player.setSource(QUrl.fromLocalFile(self.audio_path))

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._position = 0
            self.track_widget.set_progress(0, self._duration)
            self._update_time_label()

    def _toggle_playback(self):
        if not self._player:
            self._setup_player()
        if not self._player:
            return

        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                if self.audio_path and os.path.exists(self.audio_path):
                    self._player.setSource(QUrl.fromLocalFile(self.audio_path))
            self._player.play()

    def _on_playback_state_changed(self, state):
        self._is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
        self._update_play_icon()

    def _on_position_changed(self, pos_ms: int):
        self._position = pos_ms
        self.track_widget.set_progress(self._position, self._duration)
        self._update_time_label()

    def _on_duration_changed(self, dur_ms: int):
        if dur_ms > 0:
            self._duration = dur_ms
            self.track_widget.set_progress(self._position, self._duration)
            self._update_time_label()

    def _seek_to(self, ratio: float):
        if self._player and self._duration > 0:
            new_pos = int(ratio * self._duration)
            self._player.setPosition(new_pos)

    def _update_time_label(self):
        cur_s = int(self._position / 1000)
        tot_s = int(self._duration / 1000)
        cur_str = f"{cur_s // 60:02d}:{cur_s % 60:02d}"
        tot_str = f"{tot_s // 60:02d}:{tot_s % 60:02d}"
        self.time_lbl.setText(f"{cur_str} / {tot_str}")

    def _save_audio(self):
        if not self.audio_path or not os.path.exists(self.audio_path):
            return
        default_name = os.path.basename(self.audio_path) if self.audio_path else "akira_melody.mp3"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить аудиозапись",
            default_name,
            "MP3 Audio (*.mp3);;All Files (*.*)"
        )
        if save_path:
            import shutil
            shutil.copy2(self.audio_path, save_path)

    def _update_play_icon(self):
        icon_col = "#ffffff" if self.current_theme == "dark" else "#111318"
        svg = SVG_PAUSE if self._is_playing else SVG_PLAY
        self.play_btn.setIcon(_render_svg(svg, icon_col, 16))

    def _update_styles(self):
        is_light = (self.current_theme == "light")
        icon_col = "#1e293b" if is_light else "#ded7c4"
        text_col = "#1e293b" if is_light else "#ded7c4"
        sub_col = "#64748b" if is_light else "#888270"

        self.title_lbl.setStyleSheet(f"color: {text_col};")
        self.time_lbl.setStyleSheet(f"color: {sub_col};")

        btn_bg = self.emotion_color.name()
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_bg};
                border: none;
                border-radius: 17px;
            }}
            QPushButton:hover {{
                background-color: {self.emotion_color.lighter(115).name()};
            }}
        """)
        self._update_play_icon()

        d_bg = "rgba(0, 0, 0, 0.06)" if is_light else "rgba(255, 255, 255, 0.08)"
        d_hover = "rgba(0, 0, 0, 0.12)" if is_light else "rgba(255, 255, 255, 0.16)"
        self.download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {d_bg};
                border: 1px solid rgba(120, 115, 95, 0.25);
                border-radius: 6px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {d_hover};
                border: 1px solid {self.emotion_color.name()};
            }}
        """)
        self.download_btn.setIcon(_render_svg(SVG_DOWNLOAD, icon_col, 14))

        self.track_widget.set_theme(self.current_theme, self.emotion_color)

    def set_theme(self, theme: str, emotion_color: QColor = None):
        self.current_theme = theme
        if emotion_color is not None:
            self.emotion_color = QColor(emotion_color)
        self._update_styles()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        is_light = (self.current_theme == "light")
        emo = self.emotion_color

        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, 12.0, 12.0)
        painter.save()
        painter.setClipPath(clip_path)

        bg_col = QColor(245, 248, 252) if is_light else QColor(14, 16, 20)
        painter.fillRect(self.rect(), bg_col)

        if self.state == "loading":
            num_bars = 32
            bar_w = 4.0
            bar_spacing = 4.0
            total_bars_w = num_bars * bar_w + (num_bars - 1) * bar_spacing
            start_x = (w - total_bars_w) / 2.0
            mid_y = h / 2.0
            max_h = max(10.0, h - 18.0)

            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(num_bars):
                phase = self._eq_phase + i * 0.35
                sine_val = (math.sin(phase) + 1.0) * 0.5
                sine_val2 = (math.cos(phase * 1.5) + 1.0) * 0.3
                bar_h = max(5.0, (sine_val * 0.7 + sine_val2 * 0.3) * max_h)
                bx = start_x + i * (bar_w + bar_spacing)
                by = mid_y - bar_h / 2.0

                bar_rect = QRectF(bx, by, bar_w, bar_h)
                bar_path = QPainterPath()
                bar_path.addRoundedRect(bar_rect, 2.0, 2.0)
                b_grad = QLinearGradient(bx, by, bx, by + bar_h)
                b_grad.setColorAt(0.0, emo.lighter(130))
                b_grad.setColorAt(1.0, emo)
                painter.fillPath(bar_path, b_grad)

        painter.restore()

        border_col = QColor(15, 23, 42, 28) if is_light else QColor(120, 115, 95, 75)
        if self._hovered and self.state == "ready":
            border_col = QColor(emo.red(), emo.green(), emo.blue(), 150)
        painter.setPen(QPen(border_col, 1.2))
        painter.drawPath(clip_path)
        painter.end()

    def closeEvent(self, event):
        if self._player:
            self._player.stop()
        super().closeEvent(event)

    def deleteLater(self):
        if self._player:
            self._player.stop()
        super().deleteLater()


class ShadowLabel(QLabel):
    """QLabel с нативным субпиксельным сглаживанием шрифта."""
    def __init__(self, text: str = "", theme: str = "dark", parent=None):
        super().__init__(text, parent)
        self.current_theme = theme

    def set_theme(self, theme: str):
        if self.current_theme != theme:
            self.current_theme = theme
            self.update()

class StudioUserMessage(QWidget):
    """Воздушное сообщение пользователя с неоновым рельсом справа."""
    def __init__(
        self,
        text: str,
        user_name: str,
        font_family: str,
        chat_font_family: str = None,
        theme: str = "dark",
        attached_file: str = None,
        parent=None
    ):
        super().__init__(parent)
        self.font_family = font_family
        self.chat_font_family = chat_font_family or font_family
        self.current_theme = theme

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(10)

        content_col = QVBoxLayout()
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(4)

        display_name = user_name.strip() if user_name else "друг"
        self.header = ShadowLabel(display_name, theme=self.current_theme)
        self.header.setObjectName("StudioUserHeader")
        self.header.setFont(QFont(self.font_family, 8))
        self.header.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_col.addWidget(self.header)

        self.body = ShadowLabel(text, theme=self.current_theme)
        self.body.setObjectName("StudioUserBody")
        self.body.setWordWrap(True)
        self.body.setFont(QFont(self.chat_font_family, 11))
        self.body.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_col.addWidget(self.body)

        if attached_file:
            fname = os.path.basename(attached_file)
            self.file_pill = QLabel(f"📎 {fname}")
            self.file_pill.setObjectName("StudioFilePill")
            self.file_pill.setFont(QFont(self.font_family, 9))
            self.file_pill.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.file_pill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            content_col.addWidget(self.file_pill)

        main_layout.addLayout(content_col, 1)

        rail_col = QColor("#ffffff" if theme == "dark" else "#111318")
        self.rail = MessageRail(rail_col, width=4, parent=self)
        main_layout.addWidget(self.rail)

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.header.set_theme(theme)
        self.body.set_theme(theme)
        rail_col = QColor("#ffffff" if theme == "dark" else "#111318")
        self.rail.set_color(rail_col)


class StudioAkiraStream(QWidget):
    """Поток мыслей Акиры с поддержкой живой печати в реальном времени."""
    def __init__(
        self,
        text: str,
        emotion_color: QColor,
        font_family: str,
        chat_font_family: str = None,
        theme: str = "dark",
        emotion: str = "neutral",
        animate: bool = False,
        on_stream_tick=None,
        parent=None
    ):
        super().__init__(parent)
        self.emotion_color = emotion_color
        self.emotion = emotion
        self.font_family = font_family
        self.chat_font_family = chat_font_family or font_family
        self.current_theme = theme
        self.code_blocks = []
        self.text_labels = []
        self.media_cards = []
        self._rendered_widgets = []
        self._on_stream_tick = on_stream_tick

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(10)

        self.rail = MessageRail(emotion_color, width=4, parent=self)
        main_layout.addWidget(self.rail)

        self.content_col = QVBoxLayout()
        self.content_col.setContentsMargins(0, 0, 0, 0)
        self.content_col.setSpacing(4)

        self.header_lbl = ShadowLabel("Аки", theme=self.current_theme)
        self.header_lbl.setFont(QFont(self.font_family, 8))
        self.header_lbl.setStyleSheet(f"color: {emotion_color.name()}; letter-spacing: 1.2px;")
        self.content_col.addWidget(self.header_lbl)

        main_layout.addLayout(self.content_col, 1)

        if animate and text:
            self._start_typewriter(text)
        else:
            self._render_blocks(parse_message_blocks(text))

    def _create_block_widget(self, b_type: str, b_val):
        if b_type == "code":
            lang, code_body = b_val
            return CodeBlockWidget(
                lang,
                code_body,
                font_family=self.font_family,
                theme=self.current_theme,
                parent=self
            )
        elif b_type == "image":
            card = ImageMediaCard(
                image_path=b_val,
                emotion_color=self.emotion_color,
                font_family=self.font_family,
                theme=self.current_theme,
                state="ready",
                parent=self
            )
            self.media_cards.append(card)
            return card
        elif b_type == "audio":
            card = AudioMediaCard(
                audio_path=b_val,
                emotion_color=self.emotion_color,
                font_family=self.font_family,
                theme=self.current_theme,
                state="ready",
                parent=self
            )
            self.media_cards.append(card)
            return card
        lbl = ShadowLabel(theme=self.current_theme)
        lbl.setObjectName("StudioAkiraBody")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setOpenExternalLinks(True)
        lbl.setText(markdown_to_rich_html(b_val, theme=self.current_theme))
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl.setFont(QFont(self.chat_font_family, 11))
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return lbl

    def add_loading_media_card(self, media_type: str):
        """Создает и добавляет карточку генерации медиа в состоянии loading."""
        if media_type == "image":
            card = ImageMediaCard(
                image_path="",
                emotion_color=self.emotion_color,
                font_family=self.font_family,
                theme=self.current_theme,
                state="loading",
                parent=self
            )
        else:
            card = AudioMediaCard(
                audio_path="",
                emotion_color=self.emotion_color,
                font_family=self.font_family,
                theme=self.current_theme,
                state="loading",
                parent=self
            )
        self.content_col.addWidget(card)
        self._rendered_widgets.append((media_type, card))
        self.media_cards.append(card)
        return card

    def _render_blocks(self, blocks):
        for b_type, b_val in blocks:
            w = self._create_block_widget(b_type, b_val)
            self.content_col.addWidget(w)
            self._rendered_widgets.append((b_type, w))
            if b_type == "code":
                self.code_blocks.append(w)
            elif b_type in ("image", "audio"):
                if w not in self.media_cards:
                    self.media_cards.append(w)
            else:
                self.text_labels.append((w, b_val))

    def _start_typewriter(self, full_text: str):
        self._tokens = re.findall(r'\S+|\s+', full_text)
        self._streamed_text = ""

        total = len(self._tokens)
        if total > 180:
            interval, self._chunk_size = 12, 3
        elif total > 70:
            interval, self._chunk_size = 15, 2
        else:
            interval, self._chunk_size = 22, 1

        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(interval)
        self._stream_timer.timeout.connect(self._on_stream_step)
        self._stream_timer.start()
        self._on_stream_step()

    def _on_stream_step(self):
        if not getattr(self, "_tokens", None):
            if hasattr(self, "_stream_timer"):
                self._stream_timer.stop()
            final_blocks = parse_message_blocks(self._streamed_text)
            self._apply_blocks_to_widgets(final_blocks)
            self._sync_theme_refs(final_blocks)
            return

        for _ in range(self._chunk_size):
            if self._tokens:
                self._streamed_text += self._tokens.pop(0)

        blocks = parse_message_blocks(self._streamed_text)
        self._apply_blocks_to_widgets(blocks)

        if callable(self._on_stream_tick):
            self._on_stream_tick()

        if not self._tokens:
            if hasattr(self, "_stream_timer"):
                self._stream_timer.stop()
            self._sync_theme_refs(blocks)

    def _apply_blocks_to_widgets(self, blocks):
        for idx, (b_type, b_val) in enumerate(blocks):
            if idx < len(self._rendered_widgets):
                old_type, widget = self._rendered_widgets[idx]
                if old_type != b_type:
                    self.content_col.removeWidget(widget)
                    widget.deleteLater()
                    new_w = self._create_block_widget(b_type, b_val)
                    self.content_col.insertWidget(idx + 1, new_w)
                    self._rendered_widgets[idx] = (b_type, new_w)
                else:
                    if b_type == "text":
                        new_html = markdown_to_rich_html(b_val, theme=self.current_theme)
                        if widget.text() != new_html:
                            widget.setText(new_html)
                    elif b_type == "code":
                        _, code_body = b_val
                        clean_code = code_body.strip("\n")
                        if widget.code != clean_code:
                            widget.code = clean_code
                            widget.code_edit.setPlainText(clean_code)
                            lines_count = max(2, min(26, len(clean_code.splitlines())))
                            widget.code_edit.setFixedHeight(lines_count * 18 + 16)
            else:
                new_w = self._create_block_widget(b_type, b_val)
                self.content_col.addWidget(new_w)
                self._rendered_widgets.append((b_type, new_w))

        # Если количество блоков уменьшилось, удаляем лишние виджеты с конца
        while len(self._rendered_widgets) > len(blocks):
            _, extra_w = self._rendered_widgets.pop()
            self.content_col.removeWidget(extra_w)
            extra_w.deleteLater()

    def _sync_theme_refs(self, blocks):
        self.code_blocks.clear()
        self.text_labels.clear()
        self.media_cards.clear()
        for (b_type, widget), (_, b_val) in zip(self._rendered_widgets, blocks):
            if b_type == "code":
                self.code_blocks.append(widget)
            elif b_type in ("image", "audio"):
                self.media_cards.append(widget)
            elif b_type == "text":
                self.text_labels.append((widget, b_val))
            else:
                if hasattr(widget, "setText"):
                    self.text_labels.append((widget, b_val))

    def set_theme(self, theme: str, emotion_color: QColor = None):
        self.current_theme = theme
        if emotion_color is not None:
            self.emotion_color = emotion_color
            self.rail.set_color(emotion_color)
            if hasattr(self, "header_lbl"):
                self.header_lbl.setStyleSheet(f"color: {emotion_color.name()}; letter-spacing: 1.2px;")
        if hasattr(self, "header_lbl"):
            self.header_lbl.set_theme(theme)
        for cb in self.code_blocks:
            cb.set_theme(theme)
        for mc in getattr(self, "media_cards", []):
            if hasattr(mc, "set_theme"):
                mc.set_theme(theme, emotion_color or self.emotion_color)
        for lbl, raw_md in self.text_labels:
            if hasattr(lbl, "set_theme"):
                lbl.set_theme(theme)
            if hasattr(lbl, "setText"):
                lbl.setText(markdown_to_rich_html(raw_md, theme=theme))


class StudioThinkingLabel(QWidget):
    """Парящий статус размышлений Акиры с бегущим градиентом в цвет её текущей эмоции."""
    def __init__(self, font_family: str, theme: str = "dark", parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFont(QFont(font_family, 9))

        self.current_theme = theme
        self._old_text = ""
        self._new_text = ""
        self._progress = 1.0
        self._accent_color = QColor("#ded7c4")

        # Анимация плавной смены фраз (OutCubic)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_step)
        self._anim.finished.connect(self._on_anim_finished)

        # Непрерывный переливающийся бегающий шиммер букв
        self._shimmer_phase = 0.0
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(24)
        self._shimmer_timer.timeout.connect(self._on_shimmer_tick)
        self.hide()

    def _on_shimmer_tick(self):
        self._shimmer_phase = (self._shimmer_phase + 0.013) % 1.0
        if self.isVisible():
            self.update()

    def set_theme(self, theme: str):
        self.current_theme = theme
        if self.isVisible():
            self.update()

    def set_accent_color(self, color: QColor):
        self._accent_color = QColor(color)
        if self.isVisible():
            self.update()

    def show_phrase(self, text: str, color: QColor):
        self._anim.stop()
        self._old_text = ""
        self._new_text = text
        self._accent_color = QColor(color)
        self._progress = 0.0
        self._shimmer_phase = 0.0
        self.show()
        if not self._shimmer_timer.isActive():
            self._shimmer_timer.start()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def transition_to(self, text: str, color: QColor):
        if not self.isVisible():
            self.show_phrase(text, color)
            return
        self._anim.stop()
        self._old_text = self._new_text
        self._new_text = text
        self._accent_color = QColor(color)
        self._progress = 0.0
        if not self._shimmer_timer.isActive():
            self._shimmer_timer.start()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def stop_and_hide(self):
        self._anim.stop()
        self._shimmer_timer.stop()
        self._old_text = ""
        self._new_text = ""
        self.hide()

    def _on_anim_step(self, val):
        self._progress = float(val)
        self.update()

    def _on_anim_finished(self):
        self._old_text = ""
        self._progress = 1.0
        self.update()

    def _build_shimmer_pen(self, text: str, opacity: float = 1.0) -> QPen:
        fm = self.fontMetrics()
        text_w = max(40.0, float(fm.horizontalAdvance(text)))

        is_light = (self.current_theme == "light")
        # Базовый цвет букв парящий: в темной теме под цвет рамочки chat_window (#ded7c4), в светлой (#111318)
        if is_light:
            base_col = QColor(17, 19, 24, int(155 * opacity))
        else:
            base_col = QColor(222, 215, 196, int(150 * opacity))

        wave_w = max(90.0, text_w * 0.40)
        cx = -wave_w + self._shimmer_phase * (text_w + 2.0 * wave_w)
        sx = cx - wave_w / 2.0
        ex = cx + wave_w / 2.0

        grad = QLinearGradient(sx, 0, ex, 0)
        grad.setSpread(QGradient.Spread.PadSpread)

        # Переливающийся блик строго в цвет текущей эмоции Акиры
        accent = QColor(self._accent_color)
        h = accent.hue()
        s = accent.saturation()
        v = accent.value()
        if is_light:
            if h < 0:
                h = 35
            accent_peak = QColor.fromHsv(h, min(255, s + 35), max(40, int(v * 0.78)), int(255 * opacity))
        else:
            if h < 0:
                h = 42
            accent_peak = QColor.fromHsv(h, min(255, int(s * 1.15)), 255, int(255 * opacity))

        mid_col = QColor(
            int(base_col.red() * 0.35 + accent_peak.red() * 0.65),
            int(base_col.green() * 0.35 + accent_peak.green() * 0.65),
            int(base_col.blue() * 0.35 + accent_peak.blue() * 0.65),
            int(min(255, (base_col.alpha() + accent_peak.alpha()) * 0.6))
        )

        grad.setColorAt(0.0, base_col)
        grad.setColorAt(0.32, mid_col)
        grad.setColorAt(0.50, accent_peak)
        grad.setColorAt(0.68, mid_col)
        grad.setColorAt(1.0, base_col)

        return QPen(QBrush(grad), 1.0)

    def paintEvent(self, event):
        if not self._new_text and not self._old_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())

        p = self._progress
        pad_x = 4.0
        rect = QRectF(pad_x, 0.0, max(10.0, float(self.width()) - pad_x * 2), float(self.height()))

        # Предыдущая фраза плавно уплывает вверх и растворяется
        if self._old_text and p < 1.0:
            old_opacity = max(0.0, 1.0 - p * 1.25)
            if old_opacity > 0.01:
                painter.save()
                painter.translate(0, -p * 6.0)
                painter.setPen(self._build_shimmer_pen(self._old_text, old_opacity))
                painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._old_text)
                painter.restore()

        # Новая фраза мягко выплывает снизу с бегающим градиентом эмоции
        if self._new_text:
            new_opacity = min(1.0, p * 1.25)
            if new_opacity > 0.01:
                painter.save()
                if p < 1.0:
                    painter.translate(0, (1.0 - p) * 6.0)
                painter.setPen(self._build_shimmer_pen(self._new_text, new_opacity))
                painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._new_text)
                painter.restore()

        painter.end()


class StudioTextEdit(QTextEdit):
    send_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StudioInputEdit")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.viewport().setAutoFillBackground(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(0)
        self.textChanged.connect(self.adjust_height)
        self.setFixedHeight(30)
        QTimer.singleShot(0, self.adjust_height)

    def setFont(self, font: QFont):
        super().setFont(font)
        self.adjust_height()

    def showEvent(self, event):
        super().showEvent(event)
        self.adjust_height()

    def adjust_height(self):
        fm = self.fontMetrics()
        line_h = fm.height()
        ascent = fm.ascent()
        doc_h = self.document().size().height()
        is_multiline = doc_h > (line_h + 6)

        if is_multiline:
            target_h = 54
            policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded
            self.setViewportMargins(4, 6, 4, 4)
        else:
            target_h = 30
            policy = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            top_pad = max(4, int(round((target_h - ascent) / 2.0)))
            self.setViewportMargins(4, top_pad, 4, 0)

        self.setVerticalScrollBarPolicy(policy)
        if self.height() != target_h:
            self.setFixedHeight(target_h)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
                event.accept()
                return
        else:
            super().keyPressEvent(event)


class ModelItemRow(QFrame):
    """Строка отдельной модели с динамической подсветкой эмоциями и пальцем-курсором."""
    clicked = pyqtSignal(int)
    hovered = pyqtSignal(str)

    def __init__(self, index: int, name: str, code: str, font_family: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.name = name
        self.code = code
        self.font_family = font_family
        self.is_selected = False
        self.current_theme = "dark"
        self.hover_color = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self.rail = QFrame()
        self.rail.setFixedWidth(2)
        self.rail.setFixedHeight(14)
        self.rail.setStyleSheet("background: transparent; border-radius: 1px;")
        layout.addWidget(self.rail)

        self.label = QLabel(self.name)
        self.label.setFont(QFont(self.font_family, 10))
        layout.addWidget(self.label)
        layout.addStretch()

        self.check_label = QLabel("")
        self.check_label.setFont(QFont(self.font_family, 9))
        layout.addWidget(self.check_label)

        self.update_style()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.check_label.setText("✓" if selected else "")
        self.update_style()

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update_style()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hovered.emit(self.code)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_color = None
        self.update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_hover_color(self, color: QColor):
        self.hover_color = color
        self.update_style()

    def update_style(self):
        is_light = (self.current_theme == "light")
        if self.hover_color:
            bg_col = QColor(self.hover_color)
            bg_col.setAlpha(35 if is_light else 50)
            border_col = QColor(self.hover_color)
            border_col.setAlpha(170 if is_light else 215)
            text_col = "#000000" if is_light else "#ffffff"
            rail_col = self.hover_color.name()

            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_col.name(QColor.NameFormat.HexArgb)};
                    border: 1px solid {border_col.name(QColor.NameFormat.HexArgb)};
                    border-radius: 6px;
                }}
            """)
            self.rail.setStyleSheet(f"background-color: {rail_col}; border-radius: 1px; border: none;")
            self.label.setStyleSheet(f"color: {text_col}; border: none; background: transparent;")
            self.check_label.setStyleSheet(f"color: {text_col}; border: none; background: transparent;")
        elif self.is_selected:
            bg_col = "rgba(0, 0, 0, 0.06)" if is_light else "rgba(255, 255, 255, 0.08)"
            border_col = "rgba(0, 0, 0, 0.16)" if is_light else "rgba(222, 215, 196, 0.35)"
            text_col = "#111318" if is_light else "#ded7c4"
            rail_col = "#111318" if is_light else "#ded7c4"

            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_col};
                    border: 1px solid {border_col};
                    border-radius: 6px;
                }}
            """)
            self.rail.setStyleSheet(f"background-color: {rail_col}; border-radius: 1px; border: none;")
            self.label.setStyleSheet(f"color: {text_col}; border: none; background: transparent;")
            self.check_label.setStyleSheet(f"color: {text_col}; border: none; background: transparent;")
        else:
            text_col = "#444950" if is_light else "#a69f8d"
            self.setStyleSheet("""
                QFrame {
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                }
            """)
            self.rail.setStyleSheet("background: transparent; border: none;")
            self.label.setStyleSheet(f"color: {text_col}; border: none; background: transparent;")
            self.check_label.setStyleSheet("color: transparent; border: none; background: transparent;")


class ModelSelectorPopup(QFrame):
    """Анимированное всплывающее окно выбора моделей, подстраивающее высоту под число слотов."""
    closed = pyqtSignal()
    model_selected = pyqtSignal(int)
    emotion_triggered = pyqtSignal(str)

    EMOTIONS = [
        "happy", "surprise", "weather_hot", "weather_rain",
        "weather_thunder", "sad", "weather_snow", "angry"
    ]

    DARK_EMO_COLORS = {
        "happy": QColor("#facc15"),
        "surprise": QColor("#c084fc"),
        "weather_hot": QColor("#fb923c"),
        "weather_rain": QColor("#38bdf8"),
        "weather_thunder": QColor("#f472b6"),
        "sad": QColor("#67e8f9"),
        "weather_snow": QColor("#4ade80"),
        "angry": QColor("#f43f5e")
    }

    LIGHT_EMO_COLORS = {
        "happy": QColor("#915805"),
        "surprise": QColor("#5b21b6"),
        "weather_hot": QColor("#9a3412"),
        "weather_rain": QColor("#075985"),
        "weather_thunder": QColor("#6b21a8"),
        "sad": QColor("#155e75"),
        "weather_snow": QColor("#065f46"),
        "angry": QColor("#9f1239")
    }

    def __init__(self, font_family: str, parent=None, models: list[tuple[str, str]] = None):
        super().__init__(parent)
        self.font_family = font_family
        self.setObjectName("ModelSelectorPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(0, 0)
        self.hide()

        self.current_theme = "dark"
        self.last_emotion = None
        self.is_open = False
        self.target_geom = QRect()
        self.start_y = 0
        self._anim_progress = 0.0
        self._selected_index = 0

        self.rows_layout = QVBoxLayout(self)
        self.rows_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.rows_layout.setContentsMargins(6, 6, 6, 6)
        self.rows_layout.setSpacing(3)

        self.rows = []
        self.set_models(models if models is not None else _get_available_studio_models())

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(240)
        self.anim.valueChanged.connect(self._on_anim_step)
        self.anim.finished.connect(self._on_anim_finished)

    def set_models(self, models: list[tuple[str, str]]):
        for r in self.rows:
            self.rows_layout.removeWidget(r)
            r.deleteLater()
        self.rows.clear()

        for i, (name, code) in enumerate(models):
            row = ModelItemRow(i, name, code, self.font_family, self)
            row.set_theme(self.current_theme)
            row.set_selected(i == self._selected_index)
            row.clicked.connect(self._on_row_clicked)
            row.hovered.connect(self._on_row_hovered)
            self.rows_layout.addWidget(row)
            self.rows.append(row)

    def set_theme(self, theme: str):
        self.current_theme = theme
        for r in self.rows:
            r.set_theme(theme)
        self.update()

    def set_selected_index(self, index: int):
        self._selected_index = index
        for r in self.rows:
            r.set_selected(r.index == index)

    def _on_row_clicked(self, index: int):
        self.model_selected.emit(index)
        self.close_animated()

    def _on_row_hovered(self, code: str):
        available = [e for e in self.EMOTIONS if e != self.last_emotion]
        emo = random.choice(available) if available else self.EMOTIONS[0]
        self.last_emotion = emo

        palette = self.LIGHT_EMO_COLORS if self.current_theme == "light" else self.DARK_EMO_COLORS
        color = palette.get(emo, QColor("#facc15"))

        for row in self.rows:
            if row.code == code:
                row.set_hover_color(color)
            else:
                row.hover_color = None
                row.update_style()

        self.emotion_triggered.emit(emo)

    def open_animated(self, target_x: int, btn_y: int):
        self.is_open = True
        self.last_emotion = None
        self.show()
        self.raise_()

        count = max(1, len(self.rows))
        target_w = 122
        target_h = 13 + count * 30 + (count - 1) * 3
        gap = 12
        final_y = btn_y - target_h - gap

        self.target_geom = QRect(target_x, final_y, target_w, target_h)
        self.start_y = btn_y - gap

        self.anim.stop()
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(self._anim_progress)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def close_animated(self):
        if not self.is_open:
            return
        self.is_open = False
        self.anim.stop()
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.setStartValue(self._anim_progress)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def _on_anim_step(self, val):
        self._anim_progress = float(val)
        cur_h = max(2, int(self.target_geom.height() * self._anim_progress))
        cur_y = int(self.start_y - cur_h)
        self.setGeometry(self.target_geom.x(), cur_y, self.target_geom.width(), cur_h)

    def _on_anim_finished(self):
        if not self.is_open:
            self.hide()
            self.closed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_light = (self.current_theme == "light")

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        r = min(10.0, max(1.0, self.height() / 2.0))
        path = QPainterPath()
        path.addRoundedRect(rect, r, r)

        bg_col = QColor(245, 248, 252, 248) if is_light else QColor(14, 15, 18, 248)
        border_col = QColor(17, 19, 24, 55) if is_light else QColor(120, 115, 95, 85)

        painter.fillPath(path, bg_col)
        painter.setPen(QPen(border_col, 1.2))
        painter.drawPath(path)
        painter.end()


class StudioModelSelector(QPushButton):
    """Кастомный селектор модели с динамическим фильтром по активным ключам."""
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, font_family: str, studio_frame, parent=None):
        super().__init__(parent)
        self.font_family = font_family
        self.studio_frame = studio_frame
        self.setObjectName("StudioModelSelectorBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.setFixedWidth(104)

        self.models = _get_available_studio_models()
        self._current_index = 0
        self.current_theme = "dark"

        self.popup = ModelSelectorPopup(self.font_family, self.studio_frame, models=self.models)
        self.popup.model_selected.connect(self.setCurrentIndex)
        if self.studio_frame and hasattr(self.studio_frame, "set_emotion"):
            self.popup.emotion_triggered.connect(self.studio_frame.set_emotion)
        self.popup.closed.connect(self.update)
        self.popup.set_selected_index(0)

        self.clicked.connect(self._toggle_popup)
        self._update_button_text()
        self.update_style()

        if self.studio_frame:
            self.studio_frame.installEventFilter(self)

    def refresh_models(self):
        """Синхронизирует список доступных слотов с актуальными ключами в config.json."""
        if hasattr(self.parent(), "refresh_media_capability"):
            self.parent().refresh_media_capability()

        new_models = _get_available_studio_models()
        if new_models == self.models:
            return

        prev_code = self.currentData()
        self.models = new_models
        self.popup.set_models(self.models)

        new_idx = self.findData(prev_code)
        if new_idx == -1:
            new_idx = 0

        self._current_index = new_idx
        self._update_button_text()
        self.popup.set_selected_index(new_idx)

    def _toggle_popup(self):
        self.refresh_models()
        if self.popup.is_open:
            self.popup.close_animated()
        else:
            pos = self.mapTo(self.studio_frame, QPoint(0, 0))
            popup_x = max(6, pos.x() - 9)
            self.popup.open_animated(popup_x, pos.y())

    def eventFilter(self, obj, event):
        if obj == self.studio_frame:
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
                if self.popup.isVisible() and self.popup.is_open:
                    pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    if not self.popup.geometry().contains(pos):
                        btn_pos = self.mapTo(self.studio_frame, QPoint(0, 0))
                        btn_rect = QRect(btn_pos, self.size())
                        if not btn_rect.contains(pos):
                            self.popup.close_animated()
        return super().eventFilter(obj, event)

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def mouseMoveEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().mouseMoveEvent(event)

    def currentData(self) -> str:
        if 0 <= self._current_index < len(self.models):
            return self.models[self._current_index][1]
        return self.models[0][1]

    def currentText(self) -> str:
        if 0 <= self._current_index < len(self.models):
            return self.models[self._current_index][0]
        return self.models[0][0]

    def currentIndex(self) -> int:
        return self._current_index

    def findData(self, data: str) -> int:
        for i, (name, code) in enumerate(self.models):
            if code == data:
                return i
        return -1

    def setCurrentIndex(self, idx: int):
        if 0 <= idx < len(self.models):
            self._current_index = idx
            self._update_button_text()
            self.popup.set_selected_index(idx)
            self.currentIndexChanged.emit(idx)

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.refresh_models()
        self.popup.set_theme(theme)
        self.update_style()

    def _update_button_text(self):
        name = self.currentText()
        self.setText(f"{name}  ▾")

    def update_style(self):
        is_light = (self.current_theme == "light")
        if is_light:
            bg_col = "rgba(15, 23, 42, 0.05)"
            bg_hover = "rgba(15, 23, 42, 0.09)"
            border_col = "rgba(15, 23, 42, 0.10)"
            border_hover = "rgba(15, 23, 42, 0.22)"
            text_col = "#111318"
        else:
            bg_col = "rgba(255, 255, 255, 0.05)"
            bg_hover = "rgba(255, 255, 255, 0.10)"
            border_col = "rgba(120, 115, 95, 0.35)"
            border_hover = "rgba(222, 215, 196, 0.55)"
            text_col = "#ded7c4"

        self.setStyleSheet(f"""
            QPushButton#StudioModelSelectorBtn {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 7px;
                color: {text_col};
                font-family: '{self.font_family}';
                font-size: 11px;
                padding: 0px 8px;
            }}
            QPushButton#StudioModelSelectorBtn:hover {{
                background-color: {bg_hover};
                border: 1px solid {border_hover};
                color: {'#000000' if is_light else '#ffffff'};
            }}
        """)


class MediaModeRow(QFrame):
    """Строка выбора режима в MediaModePopup."""
    clicked = pyqtSignal(str)

    def __init__(self, mode: str, title: str, subtitle: str, svg_xml: str, font_family: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.title = title
        self.subtitle = subtitle
        self.svg_xml = svg_xml
        self.font_family = font_family
        self.current_theme = "dark"
        self.is_active = False
        self.is_hovered = False
        self.hover_color = None

        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        l = QHBoxLayout(self)
        l.setContentsMargins(8, 2, 8, 2)
        l.setSpacing(8)

        self.icon_lbl = QLabel(self)
        self.icon_lbl.setFixedSize(16, 16)
        l.addWidget(self.icon_lbl)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)

        self.title_lbl = QLabel(title, self)
        self.title_lbl.setFont(QFont(font_family, 9, QFont.Weight.Bold))
        text_col.addWidget(self.title_lbl)

        self.sub_lbl = QLabel(subtitle, self)
        self.sub_lbl.setFont(QFont(font_family, 7))
        text_col.addWidget(self.sub_lbl)

        l.addLayout(text_col, 1)

        self.check_lbl = QLabel("✓", self)
        self.check_lbl.setFont(QFont(font_family, 10, QFont.Weight.Bold))
        self.check_lbl.setFixedWidth(14)
        l.addWidget(self.check_lbl)

        self.update_style()

    def set_active(self, active: bool):
        self.is_active = active
        self.update_style()

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update_style()

    def set_hover_color(self, color: QColor):
        self.hover_color = color
        self.update_style()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.hover_color = None
        self.update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mode)
        super().mousePressEvent(event)

    def update_style(self):
        is_light = (self.current_theme == "light")
        icon_col = "#1e293b" if is_light else "#ded7c4"
        text_col = "#111318" if is_light else "#ded7c4"
        sub_col = "#64748b" if is_light else "#888270"

        if self.is_hovered:
            accent = self.hover_color.name() if self.hover_color else ("#0284c7" if is_light else "#38bdf8")
            bg_col = f"rgba({QColor(accent).red()}, {QColor(accent).green()}, {QColor(accent).blue()}, 0.16)"
            border_col = f"rgba({QColor(accent).red()}, {QColor(accent).green()}, {QColor(accent).blue()}, 0.35)"
            icon_col = accent
        elif self.is_active:
            bg_col = "rgba(15, 23, 42, 0.08)" if is_light else "rgba(255, 255, 255, 0.10)"
            border_col = "rgba(15, 23, 42, 0.14)" if is_light else "rgba(255, 255, 255, 0.18)"
        else:
            bg_col = "transparent"
            border_col = "transparent"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 6px;
            }}
        """)
        self.icon_lbl.setPixmap(_render_svg(self.svg_xml, icon_col, 16).pixmap(16, 16))
        self.title_lbl.setStyleSheet(f"color: {text_col}; border: none; background: transparent;")
        self.sub_lbl.setStyleSheet(f"color: {sub_col}; border: none; background: transparent;")

        if self.is_active:
            check_col = self.hover_color.name() if self.hover_color else ("#0284c7" if is_light else "#38bdf8")
            self.check_lbl.setStyleSheet(f"color: {check_col}; border: none; background: transparent;")
        else:
            self.check_lbl.setStyleSheet("color: transparent; border: none; background: transparent;")


class MediaModePopup(QFrame):
    """Анимированное всплывающее меню переключения режимов генерации (Изображение / Музыка / Текст)."""
    closed = pyqtSignal()
    mode_selected = pyqtSignal(str)

    def __init__(self, font_family: str, studio_frame, parent=None):
        super().__init__(parent)
        self.font_family = font_family
        self.studio_frame = studio_frame
        self.setObjectName("MediaModePopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide()

        self.current_theme = "dark"
        self.active_mode = "text"
        self.is_open = False
        self.target_geom = QRect()
        self.start_y = 0
        self._anim_progress = 0.0

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.row_image = MediaModeRow(
            "image",
            "Изображение",
            "Iro",
            SVG_MEDIA_IMAGE,
            self.font_family,
            self
        )
        self.row_image.clicked.connect(self._on_row_clicked)
        layout.addWidget(self.row_image)

        self.row_music = MediaModeRow(
            "music",
            "Музыка",
            "Hibiki",
            SVG_MEDIA_MUSIC,
            self.font_family,
            self
        )
        self.row_music.clicked.connect(self._on_row_clicked)
        layout.addWidget(self.row_music)

        self.rows = [self.row_image, self.row_music]

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(200)
        self.anim.valueChanged.connect(self._on_anim_step)
        self.anim.finished.connect(self._on_anim_finished)

    def set_active_mode(self, mode: str):
        self.active_mode = mode
        self.row_image.set_active(mode == "image")
        self.row_music.set_active(mode == "music")

    def set_theme(self, theme: str):
        self.current_theme = theme
        for r in self.rows:
            r.set_theme(theme)
        self.update()

    def _on_row_clicked(self, clicked_mode: str):
        if self.active_mode == clicked_mode:
            self.mode_selected.emit("text")
        else:
            self.mode_selected.emit(clicked_mode)
        self.close_animated()

    def open_animated(self, target_x: int, btn_y: int):
        self.is_open = True
        self.show()
        self.raise_()

        if self.studio_frame:
            cur_h = getattr(self.studio_frame, "cur_h", 200.0)
            cur_s = getattr(self.studio_frame, "cur_s", 180.0)
            cur_v = getattr(self.studio_frame, "cur_v", 240.0)
            emo_col = QColor.fromHsv(int(cur_h), int(cur_s), int(cur_v))
            for r in self.rows:
                r.set_hover_color(emo_col)

        target_w = 168
        target_h = 84
        gap = 12
        final_y = btn_y - target_h - gap

        self.target_geom = QRect(target_x, final_y, target_w, target_h)
        self.start_y = btn_y - gap

        self.anim.stop()
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(self._anim_progress)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def close_animated(self):
        if not self.is_open:
            return
        self.is_open = False
        self.anim.stop()
        self.anim.setDuration(160)
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.setStartValue(self._anim_progress)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def _on_anim_step(self, val):
        self._anim_progress = float(val)
        cur_h = max(2, int(self.target_geom.height() * self._anim_progress))
        cur_y = int(self.start_y - cur_h)
        self.setGeometry(self.target_geom.x(), cur_y, self.target_geom.width(), cur_h)

    def _on_anim_finished(self):
        if not self.is_open:
            self.hide()
            self.closed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_light = (self.current_theme == "light")

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        r = min(10.0, max(1.0, self.height() / 2.0))
        path = QPainterPath()
        path.addRoundedRect(rect, r, r)

        bg_col = QColor(245, 248, 252, 248) if is_light else QColor(14, 15, 18, 248)
        border_col = QColor(17, 19, 24, 55) if is_light else QColor(120, 115, 95, 85)

        painter.fillPath(path, bg_col)
        painter.setPen(QPen(border_col, 1.2))
        painter.drawPath(path)
        painter.end()


class StudioMediaModeBtn(QPushButton):
    """Кнопка переключателя режимов генерации (Текст / Изображения / Музыка)."""
    def __init__(self, studio_frame, parent=None):
        super().__init__(parent)
        self.studio_frame = studio_frame
        self.setObjectName("StudioMediaModeBtn")
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.media_mode = "text"
        self.current_theme = "dark"
        self.update_style()

    def set_mode(self, mode: str):
        self.media_mode = mode
        self.update_style()

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update_style()

    def _get_emotion_color(self) -> QColor:
        if self.studio_frame:
            cur_h = getattr(self.studio_frame, "cur_h", 200.0)
            cur_s = getattr(self.studio_frame, "cur_s", 180.0)
            cur_v = getattr(self.studio_frame, "cur_v", 240.0)
            return QColor.fromHsv(int(cur_h), int(cur_s), int(cur_v))
        return QColor("#38bdf8")

    def update_style(self):
        is_light = (self.current_theme == "light")
        icon_col = "#1e293b" if is_light else "#ded7c4"

        if self.media_mode == "image":
            emo_col = self._get_emotion_color()
            border_col = emo_col.name()
            bg_col = f"rgba({emo_col.red()}, {emo_col.green()}, {emo_col.blue()}, 0.22)"
            self.setIcon(_render_svg(SVG_MEDIA_IMAGE, border_col, 16))
            self.setToolTip("Режим: Изображение (Iro)\nКликните для выбора другого режима")
        elif self.media_mode == "music":
            emo_col = self._get_emotion_color()
            border_col = emo_col.name()
            bg_col = f"rgba({emo_col.red()}, {emo_col.green()}, {emo_col.blue()}, 0.22)"
            self.setIcon(_render_svg(SVG_MEDIA_MUSIC, border_col, 16))
            self.setToolTip("Режим: Музыка (Hibiki)\nКликните для выбора другого режима")
        else:
            border_col = "rgba(15, 23, 42, 0.12)" if is_light else "rgba(120, 115, 95, 0.35)"
            bg_col = "rgba(15, 23, 42, 0.05)" if is_light else "rgba(255, 255, 255, 0.05)"
            self.setIcon(_render_svg(SVG_SPARKLES, icon_col, 15))
            self.setToolTip("Режим: Текст\nКликните для выбора Изображения или Музыки")

        bg_hover = "rgba(15, 23, 42, 0.10)" if is_light else "rgba(255, 255, 255, 0.12)"
        self.setStyleSheet(f"""
            QPushButton#StudioMediaModeBtn {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 7px;
            }}
            QPushButton#StudioMediaModeBtn:hover {{
                background-color: {bg_hover};
                border: 1px solid {border_col};
            }}
        """)


class StudioFloatingDock(QFrame):
    """Парящий остров ввода внизу студии."""
    submit_requested = pyqtSignal(str, str, str)

    def __init__(self, font_family: str, chat_font_family: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("StudioFloatingDock")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.font_family = font_family
        self.chat_font_family = chat_font_family or font_family
        self.studio_frame = parent
        self.attached_file = None
        self.current_theme = "dark"
        self.media_mode = "text"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        self.file_chip = QWidget()
        file_l = QHBoxLayout(self.file_chip)
        file_l.setContentsMargins(0, 0, 0, 0)
        file_l.setSpacing(6)

        self.file_name_lbl = QLabel("")
        self.file_name_lbl.setObjectName("StudioFileNameLabel")
        self.file_name_lbl.setFont(QFont(self.font_family, 9))
        file_l.addWidget(self.file_name_lbl)

        self.file_remove_btn = QPushButton("✕")
        self.file_remove_btn.setObjectName("StudioFileRemoveBtn")
        self.file_remove_btn.setFixedSize(16, 16)
        self.file_remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_remove_btn.clicked.connect(self.clear_attachment)
        file_l.addWidget(self.file_remove_btn)
        file_l.addStretch()

        self.file_chip.hide()
        layout.addWidget(self.file_chip)

        self.media_popup = MediaModePopup(font_family=self.font_family, studio_frame=parent, parent=parent or self)
        self.media_popup.mode_selected.connect(self.set_media_mode)
        self.media_popup.closed.connect(self._on_media_popup_closed)

        dock_row = QHBoxLayout()
        dock_row.setContentsMargins(0, 0, 0, 0)
        dock_row.setSpacing(6)

        self.model_combo = StudioModelSelector(font_family=self.font_family, studio_frame=parent, parent=self)
        dock_row.addWidget(self.model_combo, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.media_mode_btn = StudioMediaModeBtn(studio_frame=parent, parent=self)
        self.media_mode_btn.clicked.connect(self._toggle_media_popup)
        dock_row.addWidget(self.media_mode_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.attach_btn = QPushButton()
        self.attach_btn.setObjectName("StudioDockBtn")
        self.attach_btn.setFixedSize(28, 28)
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.clicked.connect(self._select_file)
        dock_row.addWidget(self.attach_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.input_edit = StudioTextEdit()
        self.input_edit.setFont(QFont(self.chat_font_family, 11))
        self.randomize_placeholder()
        self.input_edit.send_requested.connect(self._submit)
        dock_row.addWidget(self.input_edit, 1, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.send_btn = QPushButton()
        self.send_btn.setObjectName("StudioDockBtn")
        self.send_btn.setFixedSize(28, 28)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._submit)
        dock_row.addWidget(self.send_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(dock_row)

        if self.studio_frame and hasattr(self.studio_frame, "installEventFilter"):
            self.studio_frame.installEventFilter(self)

        self.refresh_media_capability()

    def refresh_media_capability(self):
        """Проверяет подключение ключа RouterAI и показывает/скрывает кнопку и возможность работы с медиа."""
        has_routerai = _has_routerai_key()
        self.media_mode_btn.setVisible(has_routerai)
        if not has_routerai:
            if self.media_mode != "text":
                self.set_media_mode("text")
            if hasattr(self, "media_popup") and self.media_popup.is_open:
                self.media_popup.close_animated()

    def _toggle_media_popup(self):
        if not _has_routerai_key():
            self.refresh_media_capability()
            return
        if self.media_popup.is_open:
            self.media_popup.close_animated()
        else:
            ref_w = self.studio_frame or self
            pos = self.media_mode_btn.mapTo(ref_w, QPoint(0, 0))
            popup_x = max(6, pos.x() - 40)
            self.media_popup.open_animated(popup_x, pos.y())

    def _on_media_popup_closed(self):
        self.media_mode_btn.update_style()

    def set_media_mode(self, mode: str):
        self.media_mode = mode
        self.media_popup.set_active_mode(mode)
        self.media_mode_btn.set_mode(mode)

        if mode == "image":
            self.model_combo.setEnabled(False)
            opacity = QGraphicsOpacityEffect(self.model_combo)
            opacity.setOpacity(0.45)
            self.model_combo.setGraphicsEffect(opacity)
            self.input_edit.setPlaceholderText("Опиши желаемое изображение (стиль, детали, композицию)... 🥰🖼️")
        elif mode == "music":
            self.model_combo.setEnabled(False)
            opacity = QGraphicsOpacityEffect(self.model_combo)
            opacity.setOpacity(0.45)
            self.model_combo.setGraphicsEffect(opacity)
            self.input_edit.setPlaceholderText("Опиши стиль или тему трека (жанр, инструменты, настроение)... 🥰🎵")
        else:
            self.model_combo.setEnabled(True)
            self.model_combo.setGraphicsEffect(None)
            self.randomize_placeholder()

    def eventFilter(self, obj, event):
        if obj == self.studio_frame:
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
                if self.media_popup.isVisible() and self.media_popup.is_open:
                    pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    if not self.media_popup.geometry().contains(pos):
                        btn_pos = self.media_mode_btn.mapTo(self.studio_frame, QPoint(0, 0))
                        btn_rect = QRect(btn_pos, self.media_mode_btn.size())
                        if not btn_rect.contains(pos):
                            self.media_popup.close_animated()
        return super().eventFilter(obj, event)

    def randomize_placeholder(self):
        self.input_edit.setPlaceholderText(random.choice(STUDIO_PLACEHOLDERS))

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл для Студии",
            "",
            "Все поддерживаемые (*.py *.cs *.txt *.md *.json *.log *.pdf *.docx *.png *.jpg);;Все файлы (*.*)"
        )
        if path:
            self.attached_file = path
            self.file_name_lbl.setText(f"📎 {os.path.basename(path)}")
            self.file_chip.show()

    def clear_attachment(self):
        self.attached_file = None
        self.file_name_lbl.setText("")
        self.file_chip.hide()

    def _submit(self):
        text = self.input_edit.toPlainText().strip()
        if not text and not self.attached_file:
            return
        self.model_combo.refresh_models()
        model = self.model_combo.currentData()
        f_path = self.attached_file
        self.input_edit.clear()
        self.input_edit.adjust_height()
        self.clear_attachment()
        if self.media_mode == "text":
            self.randomize_placeholder()
        self.submit_requested.emit(text, f_path, model)

    def set_active(self, enabled: bool):
        self.input_edit.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        self.attach_btn.setEnabled(enabled)
        if self.media_mode == "text":
            self.model_combo.setEnabled(enabled)
        self.media_mode_btn.setEnabled(enabled)
        if enabled:
            self.input_edit.setFocus()

    def update_icons(self, theme: str):
        self.current_theme = theme
        icon_col = "#1e293b" if theme == "light" else "#ded7c4"
        self.attach_btn.setIcon(_render_svg(SVG_PAPERCLIP, icon_col, 15))
        self.send_btn.setIcon(_render_svg(SVG_SEND, icon_col, 15))
        self.model_combo.set_theme(theme)
        self.media_mode_btn.set_theme(theme)
        self.media_popup.set_theme(theme)
        self.refresh_media_capability()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_light = (self.current_theme == "light")

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 14.0, 14.0)

        if is_light:
            bg_col = QColor(255, 255, 255, 245)
            border_col = QColor(15, 23, 42, 28)
        else:
            bg_col = QColor(12, 13, 16, 226)
            border_col = QColor(120, 115, 95, 82)

        painter.fillPath(path, bg_col)
        painter.setPen(QPen(border_col, 1.0))
        painter.drawPath(path)
        painter.end()


class ElidedLabel(QLabel):
    """QLabel с плавной обрезкой многоточием (...) и тултипом без выталкивания соседних кнопок."""
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self._text_color = None
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setToolTip(text)

    def setText(self, text: str):
        self._full_text = text
        self.setToolTip(text)
        self.update()

    def text(self) -> str:
        return self._full_text

    def set_color(self, color_str: str):
        self._text_color = QColor(color_str)
        self.update()

    def sizeHint(self) -> QSize:
        m = QFontMetrics(self.font())
        return QSize(m.horizontalAdvance(self._full_text), m.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(20, QFontMetrics(self.font()).height())

    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, max(0, self.width()))
        if self._text_color:
            painter.setPen(self._text_color)
        else:
            painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)
        painter.end()


class HistorySessionCard(QFrame):
    """Карточка отдельного чата с инлайн-переименованием без рамки."""
    clicked = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    rename_requested = pyqtSignal(int, str)

    MODEL_DISPLAY_NAMES = {
        "hikari": "Hikari",
        "kasumi": "Kasumi",
        "ginga": "Ginga",
        "uchuu": "Uchū",
    }

    def __init__(self, session_data: dict, font_family: str, is_active: bool = False, theme: str = "dark", parent=None):
        super().__init__(parent)
        self.session_id = session_data["id"]
        self.font_family = font_family
        self.is_active = is_active
        self.current_theme = theme
        self._is_editing = False
        self._raw_title = session_data.get("title", "Новый диалог")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(8)

        self.indicator = QFrame()
        self.indicator.setFixedWidth(3)
        self.indicator.setFixedHeight(34)
        layout.addWidget(self.indicator)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.title_row = QHBoxLayout()
        self.title_row.setContentsMargins(0, 0, 0, 0)
        self.title_row.setSpacing(4)

        self.title_lbl = ElidedLabel(self._raw_title)
        self.title_lbl.setFont(QFont(self.font_family, 11))
        self.title_row.addWidget(self.title_lbl)

        self.edit_btn = QPushButton()
        self.edit_btn.setFixedSize(20, 20)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self._start_editing)
        self.title_row.addWidget(self.edit_btn)

        self.title_edit = QLineEdit(self._raw_title)
        self.title_edit.setFont(QFont(self.font_family, 11))
        self.title_edit.setFrame(False)
        self.title_edit.setMaxLength(60)
        self.title_edit.hide()
        self.title_edit.returnPressed.connect(self._commit_editing)
        self.title_edit.installEventFilter(self)
        self.title_row.addWidget(self.title_edit, 1)

        self.title_row.addStretch(1)

        text_col.addLayout(self.title_row)

        raw_time = session_data.get("updated_at", "")
        time_display = self._format_time(raw_time)
        raw_model = str(session_data.get("model", "hikari")).lower()
        model_name = self.MODEL_DISPLAY_NAMES.get(raw_model, raw_model.capitalize())

        self.sub_lbl = QLabel(f"{time_display} • {model_name}")
        self.sub_lbl.setFont(QFont(self.font_family, 9))
        text_col.addWidget(self.sub_lbl)

        layout.addLayout(text_col, 1)

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(26, 26)
        self.del_btn.setToolTip("Удалить диалог")
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.del_btn)

        self.update_style()

    def _start_editing(self):
        if self._is_editing:
            return
        self._is_editing = True
        self.title_lbl.hide()
        self.edit_btn.hide()
        self.title_row.setStretch(3, 0)

        self.title_edit.setText(self._raw_title)
        self.title_edit.show()
        self.title_edit.setFocus()
        self.title_edit.setCursorPosition(len(self._raw_title))

        app = QGuiApplication.instance()
        if app:
            app.installEventFilter(self)

    def _finish_editing_ui(self):
        self._is_editing = False
        app = QGuiApplication.instance()
        if app:
            app.removeEventFilter(self)

        self.title_edit.hide()
        self.title_row.setStretch(3, 1)
        self.title_lbl.show()
        self.edit_btn.show()

    def _cancel_editing(self):
        if not self._is_editing:
            return
        self._finish_editing_ui()

    def _commit_editing(self):
        if not self._is_editing:
            return
        new_title = self.title_edit.text().strip()
        self._finish_editing_ui()

        if new_title and new_title != self._raw_title:
            self._raw_title = new_title
            self.title_lbl.setText(new_title)
            self.rename_requested.emit(self.session_id, new_title)

    def hideEvent(self, event):
        if self._is_editing:
            self._commit_editing()
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        if not self._is_editing:
            return super().eventFilter(obj, event)

        if obj is self.title_edit:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self._cancel_editing()
                return True
            if event.type() == QEvent.Type.FocusOut:
                self._commit_editing()
                return False

        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            local_pos = self.title_edit.mapFromGlobal(global_pos)
            if not self.title_edit.rect().contains(local_pos):
                self._commit_editing()

        return super().eventFilter(obj, event)

    def _format_time(self, raw_str: str) -> str:
        try:
            dt = datetime.strptime(raw_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if dt.date() == now.date():
                return f"Сегодня, {dt.strftime('%H:%M')}"
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return "Недавно"

    def _on_delete(self, *args):
        self.delete_requested.emit(self.session_id)

    def mousePressEvent(self, event):
        if self._is_editing:
            event.accept()
            return
        child = self.childAt(event.pos())
        if child in (self.del_btn, self.edit_btn, self.title_edit):
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.session_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        self.is_active = active
        self.update_style()

    def update_style(self):
        is_light = (self.current_theme == "light")
        if self.is_active:
            bg_col = "rgba(40, 160, 255, 0.16)" if is_light else "rgba(222, 215, 196, 0.14)"
            border_col = "rgba(40, 120, 240, 0.55)" if is_light else "rgba(222, 215, 196, 0.45)"
            ind_col = "#2a75d3" if is_light else "#ded7c4"
            title_col = "#0d1117" if is_light else "#ffffff"
        else:
            bg_col = "rgba(255, 255, 255, 0.65)" if is_light else "rgba(255, 255, 255, 0.03)"
            border_col = "rgba(0, 0, 0, 0.08)" if is_light else "rgba(255, 255, 255, 0.07)"
            ind_col = "transparent"
            title_col = "#1f2328" if is_light else "#ded7c4"

        sub_col = "#656d76" if is_light else "#9e9780"
        del_col = "#8c959f" if is_light else "#78735f"
        edit_col = "#656d76" if is_light else "#9e9780"
        sel_bg = "rgba(42, 117, 211, 0.25)" if is_light else "rgba(222, 215, 196, 0.25)"

        self.setStyleSheet(f"""
            HistorySessionCard {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 9px;
            }}
            HistorySessionCard:hover {{
                background-color: {'rgba(0, 0, 0, 0.06)' if is_light else 'rgba(255, 255, 255, 0.07)'};
                border: 1px solid {'rgba(0, 0, 0, 0.18)' if is_light else 'rgba(222, 215, 196, 0.25)'};
            }}
        """)
        self.indicator.setStyleSheet(f"background-color: {ind_col}; border-radius: 1.5px; border: none;")
        self.title_lbl.setStyleSheet(f"color: {title_col}; border: none; background: transparent;")
        if hasattr(self.title_lbl, 'set_color'):
            self.title_lbl.set_color(title_col)
        self.sub_lbl.setStyleSheet(f"color: {sub_col}; border: none; background: transparent;")

        self.edit_btn.setIcon(_render_svg(SVG_EDIT, edit_col, 12))
        self.edit_btn.setIconSize(QSize(12, 12))
        self.edit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {'rgba(0, 0, 0, 0.08)' if is_light else 'rgba(222, 215, 196, 0.14)'};
            }}
        """)

        self.title_edit.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {title_col};
                border: none;
                padding: 0px;
                margin: 0px;
                selection-background-color: {sel_bg};
                selection-color: {title_col};
            }}
        """)

        self.del_btn.setStyleSheet(f"""
            QPushButton {{
                color: {del_col};
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                color: #ff4d4f;
                background-color: rgba(255, 77, 79, 0.18);
            }}
        """)


class StudioHistoryDrawer(QFrame):
    """Парящая стеклянная панель истории, не вылезающая за пределы окна."""
    close_requested = pyqtSignal()
    new_chat_requested = pyqtSignal()
    session_selected = pyqtSignal(int)
    session_deleted = pyqtSignal(int)
    session_renamed = pyqtSignal(int, str)

    def __init__(self, font_family: str, parent=None):
        super().__init__(parent)
        self.font_family = font_family
        self.setObjectName("StudioHistoryDrawer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.current_theme = "dark"
        self.card_widgets = {}
        self.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)

        title = QLabel("ИСТОРИЯ ДИАЛОГОВ")
        title.setObjectName("StudioDrawerTitle")
        title.setFont(QFont(self.font_family, 10))
        header_row.addWidget(title)
        header_row.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("StudioDrawerCloseBtn")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_requested.emit)
        header_row.addWidget(self.close_btn)

        layout.addLayout(header_row)

        self.btn_new_chat = QPushButton()
        self.btn_new_chat.setObjectName("StudioNewChatBtn")
        self.btn_new_chat.setFixedHeight(34)
        self.btn_new_chat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_chat.setFont(QFont(self.font_family, 10))
        self.btn_new_chat.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self.btn_new_chat)
        self.randomize_new_chat_text()

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 4, 4, 4)
        self.list_layout.setSpacing(8)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.empty_label = QLabel("Нет сохранённых диалогов\nНачните общение в Студии")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setFont(QFont(self.font_family, 9))
        self.empty_label.setStyleSheet("color: rgba(222, 215, 196, 0.45); padding-top: 30px;")
        self.list_layout.addWidget(self.empty_label)

        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll, 1)

        self.update_drawer_style()

    def randomize_new_chat_text(self):
        cur = self.btn_new_chat.text()
        candidates = [p for p in STUDIO_NEW_CHAT_PHRASES if p != cur]
        phrase = random.choice(candidates) if candidates else STUDIO_NEW_CHAT_PHRASES[0]
        self.btn_new_chat.setText(phrase)

    def update_drawer_style(self):
        is_light = (self.current_theme == "light")
        bg_col = "rgba(240, 244, 250, 0.96)" if is_light else "rgba(10, 10, 8, 0.94)"
        border_col = "rgba(0, 0, 0, 0.12)" if is_light else "rgba(222, 215, 196, 0.18)"
        title_col = "#111318" if is_light else "#ded7c4"
        close_col = "#656d76" if is_light else "#888373"

        btn_bg = "rgba(17, 19, 24, 0.05)" if is_light else "rgba(222, 215, 196, 0.08)"
        btn_border = "rgba(17, 19, 24, 0.18)" if is_light else "rgba(222, 215, 196, 0.22)"
        btn_hover = "rgba(17, 19, 24, 0.10)" if is_light else "rgba(222, 215, 196, 0.16)"

        self.setStyleSheet(f"""
            QFrame#StudioHistoryDrawer {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 14px;
            }}
            QLabel#StudioDrawerTitle {{
                color: {title_col};
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }}
            QPushButton#StudioDrawerCloseBtn {{
                color: {close_col};
                background: transparent;
                border: none;
                font-size: 13px;
                border-radius: 6px;
            }}
            QPushButton#StudioDrawerCloseBtn:hover {{
                color: {'#111318' if is_light else '#ffffff'};
                background-color: {'rgba(0, 0, 0, 0.08)' if is_light else 'rgba(255, 255, 255, 0.12)'};
            }}
            QPushButton#StudioNewChatBtn {{
                background-color: {btn_bg};
                border: 1px solid {btn_border};
                border-radius: 8px;
                color: {title_col};
                letter-spacing: 0.8px;
            }}
            QPushButton#StudioNewChatBtn:hover {{
                background-color: {btn_hover};
                border: 1px solid {'rgba(17, 19, 24, 0.35)' if is_light else 'rgba(222, 215, 196, 0.45)'};
            }}
        """)

        if getattr(self, "empty_label", None) is not None:
            try:
                empty_col = "rgba(17, 19, 24, 0.45)" if is_light else "rgba(222, 215, 196, 0.45)"
                self.empty_label.setStyleSheet(f"color: {empty_col}; padding-top: 30px; background: transparent; border: none;")
            except RuntimeError:
                self.empty_label = None

        for card in self.card_widgets.values():
            card.current_theme = self.current_theme
            card.update_style()

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update_drawer_style()

    def refresh_sessions(self, sessions: list, active_id: int):
        self.randomize_new_chat_text()
        self.card_widgets.clear()
        self.empty_label = None

        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        if not sessions:
            self.empty_label = QLabel("Нет сохранённых диалогов\nНачните общение в Студии")
            self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty_label.setFont(QFont(self.font_family, 9))
            empty_col = "rgba(17, 19, 24, 0.45)" if self.current_theme == "light" else "rgba(222, 215, 196, 0.45)"
            self.empty_label.setStyleSheet(f"color: {empty_col}; padding-top: 30px; background: transparent; border: none;")
            self.list_layout.addWidget(self.empty_label)
            return

        for s in sessions:
            s_id = s["id"]
            is_active = (s_id == active_id)
            card = HistorySessionCard(
                s,
                font_family=self.font_family,
                is_active=is_active,
                theme=self.current_theme,
                parent=self.list_container
            )
            card.clicked.connect(self.session_selected.emit)
            card.delete_requested.connect(self.session_deleted.emit)
            card.rename_requested.connect(self.session_renamed.emit)
            self.list_layout.addWidget(card)
            card.show()
            self.card_widgets[s_id] = card

    def update_active_highlight(self, active_id: int):
        for s_id, card in self.card_widgets.items():
            card.set_active(s_id == active_id)


class StudioFrame(QFrame):
    """Студия Акиры с историей диалогов, парящим меню и динамическим селектором моделей."""
    DRAWER_TARGET_WIDTH = 295

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StudioFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_theme = "dark"
        self.main_window = parent
        self.current_session_id = None

        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        ui_font_path = get_resource_path("assets", "fonts", "Arian_normal.otf")
        ui_font_id = QFontDatabase.addApplicationFont(ui_font_path)
        if ui_font_id != -1:
            families = QFontDatabase.applicationFontFamilies(ui_font_id)
            self.font_family = families[0] if families else "Arial"
        else:
            self.font_family = "Arial"

        chat_font_path = get_resource_path("assets", "fonts", "J Audio Cassette.otf")
        chat_font_id = QFontDatabase.addApplicationFont(chat_font_path)
        if chat_font_id != -1:
            chat_families = QFontDatabase.applicationFontFamilies(chat_font_id)
            self.chat_font_family = chat_families[0] if chat_families else self.font_family
        else:
            self.chat_font_family = self.font_family

        self.setFont(QFont(self.font_family, 11))

        self.dark_palette = {
            "happy": (45.0, 230.0, 255.0),
            "sad": (198.0, 220.0, 255.0),
            "angry": (352.0, 235.0, 255.0),
            "surprise": (280.0, 220.0, 255.0),
            "neutral": (42.0, 50.0, 220.0),
            "other": (280.0, 220.0, 255.0),
            "weather_rain": (212.0, 235.0, 255.0),
            "weather_hot": (45.0, 245.0, 255.0),
            "weather_snow": (185.0, 160.0, 255.0),
            "weather_thunder": (280.0, 235.0, 255.0),
            "weather_cloudy": (215.0, 60.0, 240.0),
        }
        self.light_palette = {
            "happy": (34.0, 245.0, 145.0),          # глубокий янтарно-медовый
            "sad": (212.0, 235.0, 140.0),           # насыщенный сапфирово-лазурный
            "angry": (350.0, 240.0, 145.0),         # глубокий рубиновый
            "surprise": (276.0, 230.0, 140.0),      # насыщенный аметистовый
            "neutral": (216.0, 225.0, 135.0),       # глубокий кобальтово-синий
            "other": (276.0, 230.0, 140.0),
            "weather_rain": (214.0, 245.0, 140.0),
            "weather_hot": (26.0, 255.0, 150.0),
            "weather_snow": (190.0, 225.0, 130.0),
            "weather_thunder": (282.0, 235.0, 140.0),
            "weather_cloudy": (215.0, 130.0, 125.0),
        }
        self.palette = self.dark_palette
        self.cur_h, self.cur_s, self.cur_v = self.palette["neutral"]
        self.target_h, self.target_s, self.target_v = self.palette["neutral"]

        self.aura_speed_mult = 1.0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_aura)
        self.anim_timer.start(16)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 10)
        layout.setSpacing(6)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 2)

        self.btn_history = QPushButton()
        self.btn_history.setObjectName("StudioHistoryBtn")
        self.btn_history.setFixedSize(26, 26)
        self.btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_history.clicked.connect(self.toggle_drawer)
        top_bar.addWidget(self.btn_history, alignment=Qt.AlignmentFlag.AlignLeft)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.feed_widget = QWidget()
        self.feed_widget.setStyleSheet("background: transparent;")
        self.feed_layout = QVBoxLayout(self.feed_widget)
        self.feed_layout.setContentsMargins(0, 4, 4, 8)
        self.feed_layout.setSpacing(12)
        self.feed_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.feed_widget)
        layout.addWidget(self.scroll, 1)

        self.thinking_status = StudioThinkingLabel(font_family=self.font_family, parent=self)
        layout.addWidget(self.thinking_status)

        self.thinking_cycle_timer = QTimer(self)
        self.thinking_cycle_timer.setInterval(4400)
        self.thinking_cycle_timer.timeout.connect(self._cycle_thinking_phrase)
        self._current_thinking_pool = THINKING_PHRASES
        self._last_phrase = ""

        # Док ввода (селектор моделей привязан к StudioFrame)
        self.dock = StudioFloatingDock(
            font_family=self.font_family,
            chat_font_family=self.chat_font_family,
            parent=self
        )
        self.dock.submit_requested.connect(self._on_user_submit)
        layout.addWidget(self.dock)

        # Выдвижное меню истории
        self.drawer = StudioHistoryDrawer(font_family=self.font_family, parent=self)
        self.drawer.close_requested.connect(self.close_drawer)
        self.drawer.new_chat_requested.connect(self.create_new_dialog)
        self.drawer.session_selected.connect(self.load_session)
        self.drawer.session_deleted.connect(self.delete_session)
        self.drawer.session_renamed.connect(self._on_session_renamed)

        self.drawer_anim = QVariantAnimation(self)
        self.drawer_anim.setDuration(260)
        self.drawer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.drawer_anim.valueChanged.connect(self._on_drawer_step)
        self.drawer_anim.finished.connect(self._on_drawer_finished)
        self._is_drawer_open = False

        self.set_theme(self.current_theme)
        self._init_session_from_db()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'dock') and hasattr(self.dock, 'model_combo'):
            self.dock.model_combo.refresh_models()
        if hasattr(self, 'dock') and hasattr(self.dock, 'refresh_media_capability'):
            self.dock.refresh_media_capability()

    def _init_session_from_db(self):
        sessions = studio_db.get_sessions()
        if sessions:
            self.load_session(sessions[0]["id"])
        else:
            self.create_new_dialog()

    def create_new_dialog(self):
        self.dock.model_combo.refresh_models()
        model = self.dock.model_combo.currentData()
        new_id = studio_db.create_session(title="Новый диалог", model=model)
        self.load_session(new_id)
        if self._is_drawer_open:
            self.close_drawer()

    def load_session(self, session_id: int):
        self.current_session_id = session_id
        self._clear_feed()
        self.dock.model_combo.refresh_models()

        msgs = studio_db.get_messages(session_id)
        current_name = self._get_user_name()

        for m in msgs:
            role = m["role"]
            content = m["content"]
            attached = m.get("attached_file")
            emotion = m.get("emotion", "neutral")

            if role == "user":
                u_msg = StudioUserMessage(
                    content,
                    user_name=current_name,
                    font_family=self.font_family,
                    chat_font_family=self.chat_font_family,
                    theme=self.current_theme,
                    attached_file=attached,
                    parent=self.feed_widget
                )
                self.feed_layout.addWidget(u_msg)
            else:
                self.set_emotion(emotion)
                emo_col = QColor.fromHsv(int(self.target_h), int(self.target_s), int(self.target_v))
                disp_content = clean_chat_display_text(content) or content
                akira_stream = StudioAkiraStream(
                    disp_content,
                    emo_col,
                    font_family=self.font_family,
                    chat_font_family=self.chat_font_family,
                    theme=self.current_theme,
                    emotion=emotion,
                    animate=False,
                    parent=self.feed_widget
                )
                self.feed_layout.addWidget(akira_stream)

        session_data = studio_db.get_session(session_id)
        if session_data:
            s_model = session_data.get("model", "hikari")
            idx = self.dock.model_combo.findData(s_model)
            self.dock.model_combo.setCurrentIndex(idx if idx != -1 else 0)

        self._scroll_bottom()
        self.drawer.update_active_highlight(session_id)

    def delete_session(self, session_id: int):
        studio_db.delete_session(session_id)
        sessions = studio_db.get_sessions()
        existing_ids = [s["id"] for s in sessions]

        if self.current_session_id == session_id or self.current_session_id not in existing_ids:
            if sessions:
                self.load_session(sessions[0]["id"])
            else:
                self._clear_feed()
                self.dock.model_combo.refresh_models()
                model = self.dock.model_combo.currentData()
                new_id = studio_db.create_session(title="Новый диалог", model=model)
                self.load_session(new_id)
                sessions = studio_db.get_sessions()

        self.drawer.refresh_sessions(sessions, self.current_session_id)

    def _on_session_renamed(self, session_id: int, new_title: str):
        studio_db.update_session_title(session_id, new_title)

    def _get_user_name(self) -> str:
        try:
            cfg = load_config()
            return cfg.get("user_name", "СВЯТ")
        except Exception:
            return "СВЯТ"

    def set_framerate(self, fps: int):
     self.aura_speed_mult = 60.0 / max(1, fps)
     self.anim_timer.setInterval(max(1, int(1000 / fps)))

    def _animate_aura(self):
        rate = min(1.0, 0.045 * self.aura_speed_mult)
        h_diff = (self.target_h - self.cur_h + 180.0) % 360.0 - 180.0
        self.cur_h = (self.cur_h + h_diff * rate) % 360.0
        self.cur_s += (self.target_s - self.cur_s) * rate
        self.cur_v += (self.target_v - self.cur_v) * rate
        if hasattr(self, "thinking_status") and self.thinking_status.isVisible():
            self.thinking_status.set_accent_color(
                QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v))
            )
        if hasattr(self, "dock") and hasattr(self.dock, "media_mode_btn"):
            if getattr(self.dock, "media_mode", "text") in ("image", "music"):
                self.dock.media_mode_btn.update_style()
        self.update()

    def set_emotion(self, emotion: str):
        emo = emotion if emotion in self.palette else "neutral"
        self.target_h, self.target_s, self.target_v = self.palette[emo]

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.palette = self.light_palette if theme == "light" else self.dark_palette
        self.target_h, self.target_s, self.target_v = self.palette["neutral"]

        icon_col = "#111318" if theme == "light" else "#ded7c4"
        self.btn_history.setIcon(_render_svg(SVG_SIDEBAR, icon_col, 15))
        self.dock.update_icons(theme)
        if hasattr(self, 'thinking_status'):
            self.thinking_status.set_theme(theme)

        if hasattr(self, 'drawer'):
            self.drawer.set_theme(theme)

        if hasattr(self, 'feed_layout'):
            for i in range(self.feed_layout.count()):
                w = self.feed_layout.itemAt(i).widget()
                if w and hasattr(w, 'set_theme'):
                    if isinstance(w, StudioAkiraStream):
                        emo_key = w.emotion if w.emotion in self.palette else "neutral"
                        eh, es, ev = self.palette[emo_key]
                        w.set_theme(theme, QColor.fromHsv(int(eh), int(es), int(ev)))
                    else:
                        w.set_theme(theme)

        self.setStyleSheet(get_main_style(theme))
        self.update()

    def toggle_drawer(self):
        if self._is_drawer_open:
            self.close_drawer()
        else:
            self.open_drawer()

    def open_drawer(self):
        sessions = studio_db.get_sessions()
        self.drawer.refresh_sessions(sessions, self.current_session_id)
        self._is_drawer_open = True
        self.drawer.setMaximumWidth(self.DRAWER_TARGET_WIDTH)
        self.drawer.show()
        self.drawer.raise_()
        self.drawer_anim.stop()
        self.drawer_anim.setStartValue(self.drawer.width())
        self.drawer_anim.setEndValue(self.DRAWER_TARGET_WIDTH)
        self.drawer_anim.start()

    def close_drawer(self):
        self._is_drawer_open = False
        self.drawer_anim.stop()
        self.drawer_anim.setStartValue(self.drawer.width())
        self.drawer_anim.setEndValue(0)
        self.drawer_anim.start()

    def _on_drawer_step(self, val):
        w = int(val)
        self.drawer.setMaximumWidth(w)
        self.drawer.setFixedWidth(w)
        self.drawer.setGeometry(8, 8, w, max(0, self.height() - 16))

    def _on_drawer_finished(self):
        if not self._is_drawer_open:
            self.drawer.hide()
            self.drawer.setMaximumWidth(0)
        else:
            self.drawer.setGeometry(8, 8, self.DRAWER_TARGET_WIDTH, max(0, self.height() - 16))
            self.drawer.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'drawer'):
            w = self.DRAWER_TARGET_WIDTH if self._is_drawer_open else 0
            self.drawer.setGeometry(8, 8, w, max(0, self.height() - 16))
        if hasattr(self, 'dock') and hasattr(self.dock, 'model_combo'):
            if self.dock.model_combo.popup.is_open:
                self.dock.model_combo.popup.close_animated()
        if hasattr(self, 'dock') and hasattr(self.dock, 'media_popup'):
            if self.dock.media_popup.is_open:
                self.dock.media_popup.close_animated()

    def _clear_feed(self):
        while self.feed_layout.count():
            item = self.feed_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _cycle_thinking_phrase(self):
        candidates = [p for p in self._current_thinking_pool if p != self._last_phrase]
        new_phrase = random.choice(candidates) if candidates else self._current_thinking_pool[0]
        self._last_phrase = new_phrase
        accent = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v))
        self.thinking_status.transition_to(f"{new_phrase}", accent)

    def _on_user_submit(self, text: str, attached_file: str, model: str):
        if not self.current_session_id:
            self.current_session_id = studio_db.create_session(title="Новый диалог", model=model)

        studio_db.add_message(
            self.current_session_id,
            role="user",
            content=text,
            attached_file=attached_file
        )

        current_name = self._get_user_name()
        u_msg = StudioUserMessage(
            text,
            user_name=current_name,
            font_family=self.font_family,
            chat_font_family=self.chat_font_family,
            theme=self.current_theme,
            attached_file=attached_file,
            parent=self.feed_widget
        )
        self.feed_layout.addWidget(u_msg)

        media_mode = getattr(self.dock, "media_mode", "text")
        if media_mode in ("image", "music"):
            phrase = "Синтезирую кадр..." if media_mode == "image" else "Сочиняю мелодию..."
            accent = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v))
            self.thinking_status.show_phrase(phrase, accent)

            akira_stream = StudioAkiraStream(
                "",
                accent,
                font_family=self.font_family,
                chat_font_family=self.chat_font_family,
                theme=self.current_theme,
                emotion="happy",
                animate=False,
                parent=self.feed_widget
            )
            loading_card = akira_stream.add_loading_media_card(media_mode)
            self.feed_layout.addWidget(akira_stream)

            self.dock.set_active(False)
            self._scroll_bottom()

            self.media_worker = StudioMediaWorker(
                media_type=media_mode,
                prompt=text,
                attached_file=attached_file,
                parent=self
            )
            self.media_worker.media_ready.connect(
                lambda m_type, path, prompt, card=loading_card, stream=akira_stream:
                    self._on_media_worker_ready(m_type, path, prompt, card, stream)
            )
            self.media_worker.media_failed.connect(
                lambda m_type, err, card=loading_card, stream=akira_stream:
                    self._on_media_worker_failed(m_type, err, card, stream)
            )
            self.media_worker.start()
            return

        self._current_thinking_pool = THINKING_FILE_PHRASES if attached_file else THINKING_PHRASES
        self._last_phrase = random.choice(self._current_thinking_pool)
        accent = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v))
        self.thinking_status.show_phrase(f"{self._last_phrase}", accent)
        self.thinking_cycle_timer.start()

        self.dock.set_active(False)
        self._scroll_bottom()

        parser = getattr(self.main_window, 'command_parser', None)
        if parser:
            self.worker = StudioWorker(parser, text, attached_file=attached_file, model=model, parent=self)
            self.worker.result_ready.connect(lambda resp, u_text=text: self._on_worker_finished(resp, u_text))
            self.worker.start()
        else:
            self.thinking_cycle_timer.stop()
            self.thinking_status.stop_and_hide()
            self.dock.set_active(True)

    def _on_media_worker_ready(self, media_type: str, file_path: str, prompt: str, card, stream):
        self.thinking_cycle_timer.stop()
        self.thinking_status.stop_and_hide()
        self.dock.set_active(True)

        rel_path = os.path.relpath(file_path, os.getcwd()).replace('\\', '/')
        tag = f"[AKIRA_IMAGE:{rel_path}]" if media_type == "image" else f"[AKIRA_AUDIO:{rel_path}]"

        studio_db.add_message(
            self.current_session_id,
            role="akira",
            content=tag,
            emotion="happy"
        )

        self.set_emotion("happy")
        emo_col = QColor.fromHsv(int(self.target_h), int(self.target_s), int(self.target_v))
        stream.rail.set_color(emo_col)

        if media_type in ("image", "photo") and hasattr(card, "reveal_image"):
            card.reveal_image(file_path)
        elif media_type in ("audio", "music") and hasattr(card, "set_ready"):
            card.set_ready(file_path)
        elif hasattr(card, "set_ready"):
            card.set_ready(file_path)
        elif hasattr(card, "reveal_image"):
            card.reveal_image(file_path)

        self._scroll_bottom()

        session_meta = studio_db.get_session(self.current_session_id)
        if session_meta and session_meta.get("title") == "Новый диалог":
            if studio_db.get_message_count(self.current_session_id) <= 2:
                prefix = "Арт:" if media_type == "image" else "Трек:"
                clean_p = (prompt or "").strip().splitlines()[0][:26]
                media_title = f"{prefix} {clean_p}..." if clean_p else ("Генерация арта" if media_type == "image" else "Музыкальный трек")
                self._on_title_generated(self.current_session_id, media_title)

        voice_msg = "Готово! Сгенерировала изображение." if media_type == "image" else "Готово! Композиция создана."
        if hasattr(self.main_window, 'speak_reply'):
            self.main_window.speak_reply(voice_msg, is_whisper=False)

    def _on_media_worker_failed(self, media_type: str, err_msg: str, card, stream):
        self.thinking_cycle_timer.stop()
        self.thinking_status.stop_and_hide()
        self.dock.set_active(True)
        self.set_emotion("sad")

        if hasattr(card, "set_failed"):
            card.set_failed(err_msg)

        studio_db.add_message(
            self.current_session_id,
            role="akira",
            content=f"⚠️ Ошибка генерации ({media_type}): {err_msg}",
            emotion="sad"
        )
        self._scroll_bottom()

        if hasattr(self.main_window, 'speak_reply'):
            self.main_window.speak_reply("Не получилось создать медиа, проверь настройки ключа.", is_whisper=False)

    def _on_worker_finished(self, response, user_prompt: str):
        self.thinking_cycle_timer.stop()
        self.thinking_status.stop_and_hide()
        self.dock.set_active(True)

        if response:
            if isinstance(response, dict):
                chat_text = response.get("chat", "") or response.get("voice", "")
                voice_text = response.get("voice", "")
                emotion = response.get("emotion", "neutral")
            else:
                chat_text = str(response)
                voice_text = chat_text
                emotion = "neutral"

            display_text = clean_chat_display_text(chat_text) or chat_text

            studio_db.add_message(
                self.current_session_id,
                role="akira",
                content=display_text,
                emotion=emotion
            )

            print_markdown_console(display_text, speaker="Акира")
            self.set_emotion(emotion)
            emo_col = QColor.fromHsv(int(self.target_h), int(self.target_s), int(self.target_v))
            akira_stream = StudioAkiraStream(
                display_text,
                emo_col,
                font_family=self.font_family,
                chat_font_family=self.chat_font_family,
                theme=self.current_theme,
                emotion=emotion,
                animate=True,
                on_stream_tick=self.scroll.smooth_scroll_to_bottom,
                parent=self.feed_widget
            )
            self.feed_layout.addWidget(akira_stream)
            self._scroll_bottom()

            session_meta = studio_db.get_session(self.current_session_id)
            if session_meta and session_meta.get("title") == "Новый диалог":
                if studio_db.get_message_count(self.current_session_id) <= 2:
                    parser = getattr(self.main_window, 'command_parser', None)
                    if parser:
                        self.title_worker = StudioTitleWorker(
                            parser,
                            self.current_session_id,
                            user_prompt,
                            chat_text,
                            parent=self
                        )
                        self.title_worker.title_ready.connect(self._on_title_generated)
                        self.title_worker.start()

            if voice_text and hasattr(self.main_window, 'speak_reply'):
                clean_v = clean_voice_text(voice_text)
                if clean_v:
                    self.main_window.speak_reply(clean_v, is_whisper=False)

    def _on_title_generated(self, session_id: int, title: str):
        studio_db.update_session_title(session_id, title)
        if hasattr(self, 'drawer'):
            if session_id in self.drawer.card_widgets:
                card = self.drawer.card_widgets[session_id]
                card._raw_title = title
                card.title_lbl.setText(title)
                card.title_edit.setText(title)
            if self._is_drawer_open:
                sessions = studio_db.get_sessions()
                self.drawer.refresh_sessions(sessions, self.current_session_id)

    def _scroll_bottom(self):
        QTimer.singleShot(40, self.scroll.smooth_scroll_to_bottom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()

        aura = QRadialGradient(w * 0.5, 0, w * 0.72)
        is_light = (self.current_theme == "light")
        c_glow = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v), 85 if is_light else 36)
        c_mid = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v), 34 if is_light else 14)
        c_fade = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v), 0)
        aura.setColorAt(0.0, c_glow)
        aura.setColorAt(0.4, c_mid)
        aura.setColorAt(0.85, c_fade)
        aura.setColorAt(1.0, c_fade)
        painter.fillRect(self.rect(), aura)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def sizeHint(self) -> QSize:
        return QSize(0, 0)