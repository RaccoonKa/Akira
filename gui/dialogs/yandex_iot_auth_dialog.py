import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRectF, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QGuiApplication
from core.utils.config import load_config, save_config
from gui.styles import get_main_style


AUTH_SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Акира: Умный Дом</title>
    <style>
        body {
            background-color: #080805;
            color: #ffd700;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }
        .card {
            background: rgba(18, 16, 10, 0.85);
            border: 1px solid rgba(196, 160, 40, 0.4);
            border-radius: 12px;
            padding: 30px 40px;
            text-align: center;
            max-width: 420px;
        }
        h2 { margin-top: 0; color: #ffd700; }
        p { color: #fffde7; font-size: 14px; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Дом с Алисой подключен!</h2>
        <p>Акира успешно получила доступ к устройствам.<br>Можете закрыть эту вкладку и вернуться в приложение.</p>
    </div>
    <script>
        const hash = window.location.hash.substring(1);
        if (hash) {
            fetch('/token?' + hash);
        }
    </script>
</body>
</html>
"""


class LocalAuthServer:
    def __init__(self, port=8585, on_token_received=None):
        self.port = port
        self.on_token_received = on_token_received
        self.httpd = None
        self.thread = None

    def start(self):
        handler_cls = self._make_handler()
        self.httpd = HTTPServer(('127.0.0.1', self.port), handler_cls)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None

    def _make_handler(self):
        server_self = self

        class AuthCallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                if self.path.startswith('/callback'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(AUTH_SUCCESS_HTML.encode('utf-8'))

                elif self.path.startswith('/token'):
                    query_str = self.path.split('?', 1)[-1] if '?' in self.path else ''
                    params = urllib.parse.parse_qs(query_str)
                    token = params.get('access_token', [''])[0]

                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b"OK")

                    if token and server_self.on_token_received:
                        server_self.on_token_received(token)
                else:
                    self.send_response(404)
                    self.end_headers()

        return AuthCallbackHandler


class YandexIotAuthDialog(QDialog):
    token_obtained = pyqtSignal(str)

    def __init__(self, font_family="Arial", parent=None, theme: str = None):
        super().__init__(parent)
        self.font_family = font_family
        self.drag_position = QPoint()
        self.server = None

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
        self.client_id = cfg.get("api_keys", {}).get("yandex_iot_client_id", "").strip()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(410, 320)
        self.setStyleSheet(get_main_style(self.current_theme))

        self._center_on_screen(parent)
        self.init_ui()

        if self.client_id:
            self._start_browser_auth()

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
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_lbl = QLabel("Дом с Алисой (IoT)")
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

        self.desc_lbl = QLabel(
            "Для подключения достаточно нажать кнопку — откроется страница Яндекса, где нужно подтвердить доступ."
        )
        self.desc_lbl.setFont(QFont(self.font_family, 10))
        self.desc_lbl.setWordWrap(True)
        desc_color = "rgba(17, 19, 24, 0.70)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.65)"
        self.desc_lbl.setStyleSheet(f"color: {desc_color};")
        layout.addWidget(self.desc_lbl)

        self.card = QFrame()
        self.card.setObjectName("BentoCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        lbl_cid = QLabel("CLIENT ID ПРИЛОЖЕНИЯ:")
        lbl_cid.setObjectName("BentoSectionTitle")
        lbl_cid.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        card_layout.addWidget(lbl_cid)

        self.client_id_input = QLineEdit()
        self.client_id_input.setObjectName("SettingInput")
        self.client_id_input.setFont(QFont("Consolas", 10))
        self.client_id_input.setPlaceholderText("Вставь Client ID из oauth.yandex.ru...")
        self.client_id_input.setText(self.client_id)
        card_layout.addWidget(self.client_id_input)

        layout.addWidget(self.card)

        self.status_lbl = QLabel("Нажми «Войти через браузер» для авторизации")
        self.status_lbl.setFont(QFont(self.font_family, 10))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_color = "rgba(17, 19, 24, 0.65)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.6)"
        self.status_lbl.setStyleSheet(f"color: {status_color};")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.auth_btn = QPushButton("ВОЙТИ ЧЕРЕЗ БРАУЗЕР")
        self.auth_btn.setObjectName("BentoActionBtn")
        self.auth_btn.setFixedHeight(34)
        self.auth_btn.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        self.auth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auth_btn.clicked.connect(self._on_auth_clicked)
        btn_row.addWidget(self.auth_btn)

        layout.addLayout(btn_row)

    def _on_auth_clicked(self):
        cid = self.client_id_input.text().strip()
        if not cid:
            self.status_lbl.setText("✕ Введи Client ID приложения Яндекса")
            err_col = "#e53935" if self.current_theme == "light" else "#ff5252"
            self.status_lbl.setStyleSheet(f"color: {err_col};")
            return

        self.client_id = cid
        cfg = load_config()
        if "api_keys" not in cfg:
            cfg["api_keys"] = {}
        cfg["api_keys"]["yandex_iot_client_id"] = cid
        save_config(cfg)

        self._start_browser_auth()

    def _start_browser_auth(self):
        if self.server:
            self.server.stop()

        self.status_lbl.setText("Ожидаю подтверждения в браузере...")
        col = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.status_lbl.setStyleSheet(f"color: {col};")

        self.server = LocalAuthServer(port=8585, on_token_received=self._on_token_received)
        self.server.start()

        auth_url = (
            f"https://oauth.yandex.ru/authorize?response_type=token"
            f"&client_id={self.client_id}"
            f"&redirect_uri=http://localhost:8585/callback"
        )
        webbrowser.open(auth_url)

    def _on_token_received(self, token):
        cfg = load_config()
        if "api_keys" not in cfg:
            cfg["api_keys"] = {}
        cfg["api_keys"]["yandex_iot_token"] = token
        save_config(cfg)

        QTimer.singleShot(0, lambda: self._show_success(token))

    def _show_success(self, token):
        succ_col = "#2e7d32" if self.current_theme == "light" else "#00e676"
        self.status_lbl.setText("✓ Умный дом привязан! Закрываю...")
        self.status_lbl.setStyleSheet(f"color: {succ_col}; font-weight: bold;")
        self.token_obtained.emit(token)
        self.auth_btn.setEnabled(False)
        QTimer.singleShot(1400, self.accept)

    def reject(self):
        if self.server:
            self.server.stop()
            self.server = None
        self._restore_parent_focus()
        super().reject()

    def accept(self):
        if self.server:
            self.server.stop()
            self.server = None
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