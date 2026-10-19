import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QLineEdit, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRectF, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QGuiApplication
from core.utils.config import load_config, save_config
from gui.styles import get_main_style


class GigaChatAuthDialog(QDialog):
    key_saved = pyqtSignal(str)

    def __init__(self, font_family="Arial", parent=None, theme: str = None):
        super().__init__(parent)
        self.font_family = font_family
        self.drag_position = QPoint()

        if theme:
            self.current_theme = theme
        elif parent and hasattr(parent, 'current_theme'):
            self.current_theme = parent.current_theme
        elif parent and hasattr(parent, 'window') and hasattr(parent.window(), 'current_theme'):
            self.current_theme = parent.window().current_theme
        else:
            cfg = load_config()
            self.current_theme = cfg.get("theme", "dark")

        cfg = load_config()
        self.current_key = cfg.get("api_keys", {}).get("gigachat", "").strip()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 280)
        self.setStyleSheet(get_main_style(self.current_theme))

        self._center_on_screen(parent)
        self.init_ui()

    def _center_on_screen(self, parent=None):
        if parent and hasattr(parent, 'window') and parent.window() and parent.window().screen():
            screen = parent.window().screen().availableGeometry()
        else:
            screen = QGuiApplication.primaryScreen().availableGeometry()

        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def _restore_parent_focus(self):
        if self.parent():
            top = self.parent().window()
            if top:
                top.activateWindow()
                top.raise_()
                top.setFocus()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)

        title_lbl = QLabel("СЕРВИС // GIGACHAT AI")
        title_lbl.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        title_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        title_lbl.setStyleSheet(f"color: {title_color}; letter-spacing: 1px;")
        title_col.addWidget(title_lbl)

        sub_title = QLabel("АВТОРИЗАЦИОННЫЙ ТОКЕН SBER API")
        sub_title.setFont(QFont(self.font_family, 8))
        sub_color = "rgba(17, 19, 24, 0.55)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.45)"
        sub_title.setStyleSheet(f"color: {sub_color}; letter-spacing: 0.8px;")
        title_col.addWidget(sub_title)

        header.addLayout(title_col)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        desc_lbl = QLabel(
            "Введи Client Secret (Base64) из личного кабинета developers.sber.ru для доступа к нейросетевому диалогу."
        )
        desc_lbl.setFont(QFont(self.font_family, 9))
        desc_color = "rgba(17, 19, 24, 0.70)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.65)"
        desc_lbl.setStyleSheet(f"color: {desc_color}; line-height: 1.4;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        self.card = QFrame()
        self.card.setObjectName("BentoCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(10, 8, 10, 10)
        card_layout.setSpacing(6)

        field_header = QHBoxLayout()
        lbl_key = QLabel("CLIENT SECRET (BASE64):")
        lbl_key.setObjectName("BentoSectionTitle")
        lbl_key.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        field_header.addWidget(lbl_key)
        field_header.addStretch()

        self.btn_paste = QPushButton("ВСТАВИТЬ")
        self.btn_paste.setObjectName("AttachBtn")
        self.btn_paste.setFixedSize(70, 22)
        self.btn_paste.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_paste.clicked.connect(self._paste_from_clipboard)
        field_header.addWidget(self.btn_paste)
        card_layout.addLayout(field_header)

        self.key_input = QLineEdit()
        self.key_input.setObjectName("SettingInput")
        self.key_input.setFont(QFont("Consolas", 9))
        self.key_input.setPlaceholderText("Вставь строку токена Base64...")
        self.key_input.setText(self.current_key)
        self.key_input.setFixedHeight(30)
        card_layout.addWidget(self.key_input)

        layout.addWidget(self.card)

        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setFixedHeight(14)
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.open_portal_btn = QPushButton("ПОРТАЛ SBER")
        self.open_portal_btn.setObjectName("AttachBtn")
        self.open_portal_btn.setFixedHeight(28)
        self.open_portal_btn.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.open_portal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_portal_btn.clicked.connect(self._open_sber_portal)
        btn_row.addWidget(self.open_portal_btn, 1)

        self.save_btn = QPushButton("ПОДКЛЮЧИТЬ")
        self.save_btn.setObjectName("BentoActionBtn")
        self.save_btn.setFixedHeight(28)
        self.save_btn.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(self.save_btn, 1)

        layout.addLayout(btn_row)

    def _paste_from_clipboard(self):
        clip = QApplication.clipboard().text().strip()
        if clip:
            self.key_input.setText(clip)
            self.status_lbl.setText("✓ ТОКЕН ВСТАВЛЕН ИЗ БУФЕРА")
            col = "#111318" if self.current_theme == "light" else "#ded7c4"
            self.status_lbl.setStyleSheet(f"color: {col};")
            QTimer.singleShot(1500, lambda: self.status_lbl.setText(""))

    def _open_sber_portal(self):
        webbrowser.open("https://developers.sber.ru/studio/workspaces")

    def _save_and_close(self):
        key = self.key_input.text().strip()
        if not key:
            self.status_lbl.setText("✕ ПОЛЕ ТОКЕНА НЕ МОЖЕТ БЫТЬ ПУСТЫМ")
            err_col = "#e53935" if self.current_theme == "light" else "#ff5252"
            self.status_lbl.setStyleSheet(f"color: {err_col};")
            return

        cfg = load_config()
        if "api_keys" not in cfg:
            cfg["api_keys"] = {}
        if "modules" not in cfg:
            cfg["modules"] = {}

        cfg["api_keys"]["gigachat"] = key
        cfg["modules"]["gigachat"] = True
        save_config(cfg)

        self.status_lbl.setText("✓ ТОКЕН АКТИВИРОВАН")
        col = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.status_lbl.setStyleSheet(f"color: {col};")
        self.key_saved.emit(key)
        self.save_btn.setEnabled(False)
        QTimer.singleShot(900, self.accept)

    def reject(self):
        self._restore_parent_focus()
        super().reject()

    def accept(self):
        self._restore_parent_focus()
        super().accept()

    def closeEvent(self, event):
        self.reject()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
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
            pen = QPen(QColor("#111318"), 1.5)
        else:
            painter.fillPath(path, QColor(8, 8, 5, 248))
            pen = QPen(QColor("#78735f"), 1.2)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)