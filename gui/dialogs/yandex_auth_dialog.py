import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QRectF, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QGuiApplication
from yandex_music import Client
from core.utils.config import load_config, save_config
from gui.styles import get_main_style


class YandexAuthWorker(QThread):
    code_received = pyqtSignal(str, str)
    auth_success = pyqtSignal(str)
    auth_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True

    def run(self):
        try:
            client = Client()

            def on_code_callback(code):
                if not self.is_running:
                    return
                user_code = getattr(code, 'user_code', '')
                verify_url = getattr(code, 'verification_url', 'https://ya.ru/device')
                self.code_received.emit(user_code, verify_url)

            token_data = client.device_auth(on_code=on_code_callback)

            if token_data and hasattr(token_data, 'access_token') and self.is_running:
                pure_token = token_data.access_token

                cfg = load_config()
                if "api_keys" not in cfg:
                    cfg["api_keys"] = {}
                cfg["api_keys"]["yandex_music_token"] = pure_token
                save_config(cfg)

                self.auth_success.emit(pure_token)
            elif self.is_running:
                self.auth_error.emit("Не удалось получить токен.")
        except Exception as e:
            if self.is_running:
                self.auth_error.emit(str(e))

    def stop(self):
        self.is_running = False


class YandexAuthDialog(QDialog):
    token_obtained = pyqtSignal(str)

    def __init__(self, font_family="Arial", parent=None, theme: str = None):
        super().__init__(parent)
        self.font_family = font_family
        self.verify_url = "https://ya.ru/device"
        self.current_code = ""
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

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 310)
        self.setStyleSheet(get_main_style(self.current_theme))

        self._center_on_screen(parent)
        self.init_ui()

        self.worker = YandexAuthWorker(None)
        self.worker.code_received.connect(self._on_code_received)
        self.worker.auth_success.connect(self._on_auth_success)
        self.worker.auth_error.connect(self._on_auth_error)
        self.worker.start()

    def _center_on_screen(self, parent=None):
        screen = None
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
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_lbl = QLabel("Вход в Яндекс Музыку")
        title_lbl.setFont(QFont(self.font_family, 13, QFont.Weight.Bold))
        title_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        title_lbl.setStyleSheet(f"color: {title_color}; letter-spacing: 0.5px;")
        header.addWidget(title_lbl)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.desc_lbl = QLabel("Генерирую код для входа...")
        self.desc_lbl.setFont(QFont(self.font_family, 10))
        self.desc_lbl.setWordWrap(True)
        desc_color = "rgba(17, 19, 24, 0.70)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.65)"
        self.desc_lbl.setStyleSheet(f"color: {desc_color};")
        layout.addWidget(self.desc_lbl)

        self.code_card = QFrame()
        self.code_card.setObjectName("BentoCard")
        card_layout = QVBoxLayout(self.code_card)
        card_layout.setContentsMargins(12, 10, 12, 10)

        self.code_label = QLabel("•••• ••••")
        self.code_label.setFont(QFont(self.font_family, 22, QFont.Weight.Bold))
        self.code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        code_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.code_label.setStyleSheet(f"color: {code_color}; letter-spacing: 3px;")
        card_layout.addWidget(self.code_label)

        layout.addWidget(self.code_card)

        self.status_lbl = QLabel("Ожидаю подключение к сети...")
        self.status_lbl.setFont(QFont(self.font_family, 10))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_color = "rgba(17, 19, 24, 0.65)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.6)"
        self.status_lbl.setStyleSheet(f"color: {status_color};")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.copy_btn = QPushButton("СКОПИРОВАТЬ")
        self.copy_btn.setObjectName("AttachBtn")
        self.copy_btn.setFixedHeight(34)
        self.copy_btn.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self._copy_code)
        self.copy_btn.setEnabled(False)
        btn_row.addWidget(self.copy_btn)

        self.open_btn = QPushButton("ОТКРЫТЬ САЙТ")
        self.open_btn.setObjectName("BentoActionBtn")
        self.open_btn.setFixedHeight(34)
        self.open_btn.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(self._open_browser)
        self.open_btn.setEnabled(False)
        btn_row.addWidget(self.open_btn)

        layout.addLayout(btn_row)

    def _on_code_received(self, code, url):
        self.current_code = code
        self.verify_url = url
        self.code_label.setText(code)
        self.desc_lbl.setText("Перейди по ссылке, введи этот код и нажми «Разрешить»:")
        self.status_lbl.setText("Ожидаю подтверждения в браузере...")
        col = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.status_lbl.setStyleSheet(f"color: {col};")
        self.copy_btn.setEnabled(True)
        self.open_btn.setEnabled(True)
        webbrowser.open(self.verify_url)

    def _copy_code(self):
        if self.current_code:
            QApplication.clipboard().setText(self.current_code)
            self.status_lbl.setText("✓ Код скопирован в буфер!")
            col = "#111318" if self.current_theme == "light" else "#ded7c4"
            self.status_lbl.setStyleSheet(f"color: {col};")

    def _open_browser(self):
        webbrowser.open(self.verify_url)

    def _on_auth_success(self, token):
        succ_col = "#2e7d32" if self.current_theme == "light" else "#00e676"
        self.code_label.setText("УСПЕШНО")
        self.code_label.setStyleSheet(f"color: {succ_col}; font-size: 18px;")
        self.status_lbl.setText("✓ Аккаунт привязан! Закрываю...")
        self.status_lbl.setStyleSheet(f"color: {succ_col}; font-weight: bold;")
        self.token_obtained.emit(token)
        self.copy_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        QTimer.singleShot(1400, self.accept)

    def _on_auth_error(self, err_msg):
        err_col = "#e53935" if self.current_theme == "light" else "#ff5252"
        self.code_label.setText("ОШИБКА")
        self.code_label.setStyleSheet(f"color: {err_col}; font-size: 18px;")
        self.status_lbl.setText("✕ Проверь подключение к интернету")
        self.status_lbl.setStyleSheet(f"color: {err_col};")

    def reject(self):
        if hasattr(self, 'worker'):
            self.worker.stop()
            try:
                self.worker.code_received.disconnect()
                self.worker.auth_success.disconnect()
                self.worker.auth_error.disconnect()
            except Exception:
                pass
        self._restore_parent_focus()
        super().reject()

    def accept(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            self.worker.wait(300)
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