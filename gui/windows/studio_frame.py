import os
import re
import math
import random
from datetime import datetime
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFileDialog, QSizePolicy,
    QTextEdit, QGraphicsOpacityEffect, QLayout
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QRect, QRectF, QPoint, QPointF, pyqtSignal, QThread,
    QVariantAnimation, QEasingCurve, QByteArray, QEvent
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QRadialGradient,
    QBrush, QPainterPath, QFont, QFontDatabase, QIcon, QPixmap,
    QTextCursor, QGuiApplication
)
from PyQt6.QtSvg import QSvgRenderer
from core.utils.config import get_resource_path, load_config
from gui.styles import get_main_style
from core.database.chat_db import studio_db
from gui.widgets.code_formatter import (
    CodeBlockWidget,
    parse_message_blocks,
    markdown_to_rich_html,
    print_markdown_console,
)

SVG_SIDEBAR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/>
</svg>"""

SVG_PAPERCLIP = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
</svg>"""

SVG_SEND = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
</svg>"""

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


def _get_available_studio_models() -> list[tuple[str, str]]:
    """Возвращает доступные слоты моделей в зависимости от настроенных ключей."""
    try:
        cfg = load_config()
        api_keys = cfg.get("api_keys", {})
        has_giga = bool(api_keys.get("gigachat", "").strip())
        has_routerai = bool(
            api_keys.get("routerai", "").strip()
            or api_keys.get("openrouter", "").strip()
        )
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
    """Фоновый генератор краткого заголовка темы диалога."""
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
            "1. Длина строго от 2 до 5 слов.\n"
            "2. Первая буква заглавная, без точки, без кавычек и вводных слов.\n"
            f"Вопрос пользователя: {self.user_text[:200]}\n"
            f"Ответ: {self.akira_text[:200]}\n"
            "Заголовок:"
        )

        title = ""
        try:
            llm = getattr(self.parser, 'llm', None)
            if llm:
                # Приоритет — быстрый и дешёвый DeepSeek V4.1 Flash через RouterAI
                if hasattr(llm, "_init_routerai") and llm._init_routerai()[0]:
                    slug = llm.ROUTERAI_MODELS.get("kasumi", "deepseek/deepseek-v4.1-flash")
                    response = llm.routerai_client.chat.completions.create(
                        model=slug,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=30
                    )
                    if response and getattr(response, "choices", None):
                        title = getattr(response.choices[0].message, "content", "") or ""
                elif hasattr(llm, "_init_gigachat") and llm._init_gigachat()[0]:
                    res = llm.giga_client.chat({
                        "model": llm.giga_model_name,
                        "messages": [{"role": "user", "content": prompt}]
                    })
                    if res and getattr(res, "choices", None):
                        title = getattr(res.choices[0].message, "content", "") or ""
        except Exception:
            pass

        clean_title = title.replace('"', '').replace("'", '').replace("«", '').replace("»", '').strip()
        if not clean_title or len(clean_title) < 3 or clean_title.lower().startswith("заголовок"):
            words = [w for w in self.user_text.strip().split() if len(w) > 1][:4]
            clean_title = " ".join(words).capitalize() if words else "Диалог"

        if len(clean_title) > 34:
            clean_title = clean_title[:31] + "..."

        self.title_ready.emit(self.session_id, clean_title)


class StudioUserMessage(QWidget):
    """Воздушное сообщение пользователя с неоновым рельсом справа."""
    def __init__(self, text: str, user_name: str, font_family: str, theme: str = "dark", attached_file: str = None, parent=None):
        super().__init__(parent)
        self.font_family = font_family
        self.current_theme = theme

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(10)
        main_layout.addStretch(1)

        content_col = QVBoxLayout()
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(4)
        content_col.setAlignment(Qt.AlignmentFlag.AlignRight)

        display_name = user_name.strip() if user_name else "СВЯТ"
        self.header = QLabel(display_name)
        self.header.setObjectName("StudioUserHeader")
        self.header.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.header.setAlignment(Qt.AlignmentFlag.AlignRight)
        content_col.addWidget(self.header)

        self.body = QLabel(text)
        self.body.setObjectName("StudioUserBody")
        self.body.setWordWrap(True)
        self.body.setFont(QFont(self.font_family, 11))
        self.body.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.setMaximumWidth(400)
        content_col.addWidget(self.body)

        if attached_file:
            fname = os.path.basename(attached_file)
            self.file_pill = QLabel(f"📎 {fname}")
            self.file_pill.setObjectName("StudioFilePill")
            self.file_pill.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
            self.file_pill.setAlignment(Qt.AlignmentFlag.AlignRight)
            content_col.addWidget(self.file_pill)

        main_layout.addLayout(content_col)

        self.rail = QFrame()
        self.rail.setObjectName("StudioUserRail")
        self.rail.setFixedWidth(2)
        self.rail.setMinimumHeight(24)
        rail_col = "#ffffff" if theme == "dark" else "#111318"
        self.rail.setStyleSheet(f"background-color: {rail_col}; border-radius: 1px;")
        main_layout.addWidget(self.rail)


class StudioAkiraStream(QWidget):
    """Поток мыслей Акиры: слева со светящимся неоновым рельсом цвета эмоции."""
    def __init__(self, text: str, emotion_color: QColor, font_family: str, theme: str = "dark", parent=None):
        super().__init__(parent)
        self.emotion_color = emotion_color
        self.font_family = font_family
        self.current_theme = theme
        self.code_blocks = []
        self.text_labels = []

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(10)

        self.rail = QFrame()
        self.rail.setFixedWidth(2)
        self.rail.setStyleSheet(f"background-color: {emotion_color.name()}; border-radius: 1px;")
        main_layout.addWidget(self.rail)

        content_col = QVBoxLayout()
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(6)

        header = QLabel("Аки")
        header.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {emotion_color.name()}; letter-spacing: 1.2px;")
        content_col.addWidget(header)

        blocks = parse_message_blocks(text)
        for b_type, b_val in blocks:
            if b_type == "code":
                lang, code_body = b_val
                cb = CodeBlockWidget(
                    lang,
                    code_body,
                    font_family=self.font_family,
                    theme=self.current_theme,
                    parent=self
                )
                content_col.addWidget(cb)
                self.code_blocks.append(cb)
            else:
                lbl = QLabel()
                lbl.setObjectName("StudioAkiraBody")
                lbl.setTextFormat(Qt.TextFormat.RichText)
                lbl.setOpenExternalLinks(True)
                lbl.setText(markdown_to_rich_html(b_val, theme=self.current_theme))
                lbl.setWordWrap(True)
                lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                lbl.setFont(QFont(self.font_family, 11))
                lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                content_col.addWidget(lbl)
                self.text_labels.append((lbl, b_val))

        main_layout.addLayout(content_col, 1)

    def set_theme(self, theme: str):
        self.current_theme = theme
        for cb in self.code_blocks:
            cb.set_theme(theme)
        for lbl, raw_md in self.text_labels:
            lbl.setText(markdown_to_rich_html(raw_md, theme=theme))


class StudioTextEdit(QTextEdit):
    send_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StudioInputEdit")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(0)
        self.textChanged.connect(self.adjust_height)
        self.setFixedHeight(32)

    def adjust_height(self):
        doc_h = self.document().size().height()
        target_h = 50 if doc_h > 20 else 32
        policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if doc_h > 20 else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
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
        self.label.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        layout.addWidget(self.label)
        layout.addStretch()

        self.check_label = QLabel("")
        self.check_label.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
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
        "happy": QColor("#d97706"),
        "surprise": QColor("#7c3aed"),
        "weather_hot": QColor("#ea580c"),
        "weather_rain": QColor("#0284c7"),
        "weather_thunder": QColor("#9333ea"),
        "sad": QColor("#0891b2"),
        "weather_snow": QColor("#059669"),
        "angry": QColor("#e11d48")
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
            bg_col = "rgba(17, 19, 24, 0.05)"
            bg_hover = "rgba(17, 19, 24, 0.10)"
            border_col = "rgba(17, 19, 24, 0.22)"
            border_hover = "#111318"
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
                font-weight: bold;
                padding: 0px 8px;
            }}
            QPushButton#StudioModelSelectorBtn:hover {{
                background-color: {bg_hover};
                border: 1px solid {border_hover};
                color: {'#000000' if is_light else '#ffffff'};
            }}
        """)


class StudioFloatingDock(QFrame):
    """Парящий остров ввода внизу студии."""
    submit_requested = pyqtSignal(str, str, str)

    def __init__(self, font_family: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StudioFloatingDock")
        self.font_family = font_family
        self.attached_file = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        self.file_chip = QWidget()
        file_l = QHBoxLayout(self.file_chip)
        file_l.setContentsMargins(0, 0, 0, 0)
        file_l.setSpacing(6)

        self.file_name_lbl = QLabel("")
        self.file_name_lbl.setObjectName("StudioFileNameLabel")
        self.file_name_lbl.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
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

        dock_row = QHBoxLayout()
        dock_row.setContentsMargins(0, 0, 0, 0)
        dock_row.setSpacing(6)

        self.model_combo = StudioModelSelector(font_family=self.font_family, studio_frame=parent, parent=self)
        self.model_combo.setToolTip("Выбор нейросетевого ядра")
        dock_row.addWidget(self.model_combo, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.attach_btn = QPushButton()
        self.attach_btn.setObjectName("StudioDockBtn")
        self.attach_btn.setFixedSize(28, 28)
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setToolTip("Прикрепить файл")
        self.attach_btn.clicked.connect(self._select_file)
        dock_row.addWidget(self.attach_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.input_edit = StudioTextEdit()
        self.input_edit.setFont(QFont(self.font_family, 11))
        self.randomize_placeholder()
        self.input_edit.send_requested.connect(self._submit)
        dock_row.addWidget(self.input_edit, 1, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.send_btn = QPushButton()
        self.send_btn.setObjectName("StudioDockBtn")
        self.send_btn.setFixedSize(28, 28)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setToolTip("Отправить (Enter)")
        self.send_btn.clicked.connect(self._submit)
        dock_row.addWidget(self.send_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(dock_row)

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
        self.randomize_placeholder()
        self.submit_requested.emit(text, f_path, model)

    def set_active(self, enabled: bool):
        self.input_edit.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        self.attach_btn.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        if enabled:
            self.input_edit.setFocus()

    def update_icons(self, theme: str):
        icon_col = "#111318" if theme == "light" else "#ded7c4"
        self.attach_btn.setIcon(_render_svg(SVG_PAPERCLIP, icon_col, 15))
        self.send_btn.setIcon(_render_svg(SVG_SEND, icon_col, 15))
        self.model_combo.set_theme(theme)


class HistorySessionCard(QFrame):
    """Карточка отдельного чата с крупным шрифтом, временем и кнопкой удаления."""
    clicked = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

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

        self.title_lbl = QLabel(session_data.get("title", "Новый диалог"))
        self.title_lbl.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        text_col.addWidget(self.title_lbl)

        raw_time = session_data.get("updated_at", "")
        time_display = self._format_time(raw_time)
        raw_model = str(session_data.get("model", "hikari")).lower()
        model_name = self.MODEL_DISPLAY_NAMES.get(raw_model, raw_model.capitalize())

        self.sub_lbl = QLabel(f"{time_display} • {model_name}")
        self.sub_lbl.setFont(QFont(self.font_family, 9))
        text_col.addWidget(self.sub_lbl)

        layout.addLayout(text_col, 1)

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(22, 22)
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setToolTip("Удалить диалог")
        self.del_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.del_btn)

        self.update_style()

    def _format_time(self, raw_str: str) -> str:
        try:
            dt = datetime.strptime(raw_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if dt.date() == now.date():
                return f"Сегодня, {dt.strftime('%H:%M')}"
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return "Недавно"

    def _on_delete(self):
        self.delete_requested.emit(self.session_id)

    def mousePressEvent(self, event):
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
        self.sub_lbl.setStyleSheet(f"color: {sub_col}; border: none; background: transparent;")
        self.del_btn.setStyleSheet(f"""
            QPushButton {{
                color: {del_col};
                background: transparent;
                border: none;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                color: #ff4d4f;
                background-color: rgba(255, 77, 79, 0.16);
            }}
        """)


class StudioHistoryDrawer(QFrame):
    """Парящая стеклянная панель истории, не вылезающая за пределы окна."""
    close_requested = pyqtSignal()
    new_chat_requested = pyqtSignal()
    session_selected = pyqtSignal(int)
    session_deleted = pyqtSignal(int)

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
        title.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
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
        self.btn_new_chat.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
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
                font-weight: bold;
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

        empty_col = "rgba(17, 19, 24, 0.45)" if is_light else "rgba(222, 215, 196, 0.45)"
        self.empty_label.setStyleSheet(f"color: {empty_col}; padding-top: 30px; background: transparent; border: none;")

        for card in self.card_widgets.values():
            card.current_theme = self.current_theme
            card.update_style()

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.update_drawer_style()

    def refresh_sessions(self, sessions: list, active_id: int):
        self.randomize_new_chat_text()
        self.card_widgets.clear()

        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
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
            self.list_layout.addWidget(card)
            card.show()
            self.card_widgets[s_id] = card

    def update_active_highlight(self, active_id: int):
        for s_id, card in self.card_widgets.items():
            card.set_active(s_id == active_id)


class StudioFrame(QFrame):
    """Студия Акиры с историей диалогов, парящим меню и динамическим селектором моделей."""
    DRAWER_TARGET_WIDTH = 275

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StudioFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_theme = "dark"
        self.main_window = parent
        self.current_session_id = None

        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        font_path = get_resource_path("assets", "fonts", "SSFBreakthrough-Regular.ttf")
        if not os.path.exists(font_path):
            font_path = get_resource_path("assets", "fonts", "SSFBreakthrough-Regular.otf")

        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            self.font_family = families[0] if families else "Arial"
        else:
            self.font_family = "Arial"

        self.setFont(QFont(self.font_family, 11))

        self.dark_palette = {
            "happy": (45.0, 230.0, 255.0),
            "sad": (198.0, 220.0, 255.0),
            "angry": (352.0, 235.0, 255.0),
            "surprise": (280.0, 220.0, 255.0),
            "neutral": (42.0, 50.0, 220.0),
        }
        self.light_palette = {
            "happy": (35.0, 235.0, 115.0),
            "sad": (218.0, 220.0, 110.0),
            "angry": (352.0, 230.0, 110.0),
            "surprise": (282.0, 215.0, 100.0),
            "neutral": (215.0, 60.0, 60.0),
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
        self.btn_history.setToolTip("История диалогов")
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

        self.thinking_status = QLabel("")
        self.thinking_status.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        self.thinking_status.hide()
        layout.addWidget(self.thinking_status)

        self.thinking_cycle_timer = QTimer(self)
        self.thinking_cycle_timer.setInterval(2600)
        self.thinking_cycle_timer.timeout.connect(self._cycle_thinking_phrase)
        self._current_thinking_pool = THINKING_PHRASES
        self._last_phrase = ""

        # Док ввода (селектор моделей привязан к StudioFrame)
        self.dock = StudioFloatingDock(font_family=self.font_family, parent=self)
        self.dock.submit_requested.connect(self._on_user_submit)
        layout.addWidget(self.dock)

        # Выдвижное меню истории
        self.drawer = StudioHistoryDrawer(font_family=self.font_family, parent=self)
        self.drawer.close_requested.connect(self.close_drawer)
        self.drawer.new_chat_requested.connect(self.create_new_dialog)
        self.drawer.session_selected.connect(self.load_session)
        self.drawer.session_deleted.connect(self.delete_session)

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
                    theme=self.current_theme,
                    attached_file=attached,
                    parent=self.feed_widget
                )
                self.feed_layout.addWidget(u_msg)
            else:
                self.set_emotion(emotion)
                emo_col = QColor.fromHsv(int(self.target_h), int(self.target_s), int(self.target_v))
                akira_stream = StudioAkiraStream(
                    content,
                    emo_col,
                    font_family=self.font_family,
                    theme=self.current_theme,
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
        if self.current_session_id == session_id:
            if sessions:
                self.load_session(sessions[0]["id"])
            else:
                self.create_new_dialog()
        self.drawer.refresh_sessions(sessions, self.current_session_id)

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
        if hasattr(self, 'drawer'):
            self.drawer.set_theme(theme)

        if hasattr(self, 'feed_layout'):
            for i in range(self.feed_layout.count()):
                w = self.feed_layout.itemAt(i).widget()
                if w and hasattr(w, 'set_theme'):
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
        self.thinking_status.setText(f"⚡ {new_phrase}")
        accent = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v)).name()
        self.thinking_status.setStyleSheet(f"color: {accent}; letter-spacing: 0.8px;")

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
            theme=self.current_theme,
            attached_file=attached_file,
            parent=self.feed_widget
        )
        self.feed_layout.addWidget(u_msg)

        self._current_thinking_pool = THINKING_FILE_PHRASES if attached_file else THINKING_PHRASES
        self._last_phrase = random.choice(self._current_thinking_pool)
        self.thinking_status.setText(f"⚡ {self._last_phrase}")
        accent = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v)).name()
        self.thinking_status.setStyleSheet(f"color: {accent}; letter-spacing: 0.8px;")
        self.thinking_status.show()
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
            self.thinking_status.hide()
            self.dock.set_active(True)

    def _on_worker_finished(self, response, user_prompt: str):
        self.thinking_cycle_timer.stop()
        self.thinking_status.hide()
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

            studio_db.add_message(
                self.current_session_id,
                role="akira",
                content=chat_text,
                emotion=emotion
            )

            self.set_emotion(emotion)
            emo_col = QColor.fromHsv(int(self.target_h), int(self.target_s), int(self.target_v))
            akira_stream = StudioAkiraStream(
                chat_text,
                emo_col,
                font_family=self.font_family,
                theme=self.current_theme,
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
                self.main_window.speak_reply(voice_text, is_whisper=False)

    def _on_title_generated(self, session_id: int, title: str):
        studio_db.update_session_title(session_id, title)
        if self._is_drawer_open:
            sessions = studio_db.get_sessions()
            self.drawer.refresh_sessions(sessions, self.current_session_id)

    def _scroll_bottom(self):
        QTimer.singleShot(40, self.scroll.smooth_scroll_to_bottom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        aura = QRadialGradient(w * 0.5, 0, w * 0.75)
        aura_alpha = 18 if self.current_theme == "light" else 28
        c_glow = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v), aura_alpha)
        c_fade = QColor.fromHsv(int(self.cur_h), int(self.cur_s), int(self.cur_v), 0)
        aura.setColorAt(0.0, c_glow)
        aura.setColorAt(0.7, c_fade)
        aura.setColorAt(1.0, c_fade)
        painter.fillRect(self.rect(), aura)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def sizeHint(self) -> QSize:
        return QSize(0, 0)