import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal, QThread
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QPainterPath, QFont, QGuiApplication
)
from core.utils.config import load_config


class RouterAiOAuthWorker(QThread):
    """Фоновый поток OAuth PKCE: открывает браузер, ловит редирект и забирает API-ключ."""
    auth_success = pyqtSignal(str)
    auth_error = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    AUTH_URL = "https://routerai.ru/auth"
    KEYS_EXCHANGE_URL = "https://routerai.ru/api/v1/auth/keys"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._server = None

    def stop_listening(self):
        self._running = False

    def run(self):
        try:
            # 1. Генерируем PKCE code_verifier и SHA-256 code_challenge
            verifier_bytes = secrets.token_bytes(32)
            code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode("ascii")
            digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
            code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

            auth_code_holder = {"code": None}

            class CallbackHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed = urllib.parse.urlparse(self.path)
                    if parsed.path != "/callback":
                        self.send_response(404)
                        self.end_headers()
                        return

                    params = urllib.parse.parse_qs(parsed.query)
                    auth_code_holder["code"] = params.get("code", [None])[0]

                    html_page = (
                        "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
                        "<title>Akira × RouterAI</title>"
                        "<style>"
                        "body{background:#0b0c10;color:#ded7c4;font-family:Segoe UI,Arial,sans-serif;"
                        "display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}"
                        ".card{background:#13151c;border:1px solid #78735f;border-radius:14px;"
                        "padding:28px 36px;text-align:center;max-width:420px;}"
                        "h2{margin:0 0 10px;color:#ffffff;font-size:20px;}"
                        "p{margin:0;color:#a69f8d;font-size:14px;line-height:1.5;}"
                        "</style></head><body><div class='card'>"
                        "<h2>Готово! Ключ передан в Акиру ✨</h2>"
                        "<p>Авторизация прошла успешно. Эту вкладку браузера можно закрыть.</p>"
                        "</div></body></html>"
                    )
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html_page.encode("utf-8"))

                def log_message(self, format, *args):
                    pass

            # 2. Поднимаем локальный сервер на свободном порту ОС
            self._server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
            self._server.timeout = 0.5
            port = self._server.server_address[1]
            callback_url = f"http://127.0.0.1:{port}/callback"

            # 3. Открываем страницу входа RouterAI (с выбором Яндекс / VK / почты)
            query = urllib.parse.urlencode({
                "callback_url": callback_url,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            })
            webbrowser.open(f"{self.AUTH_URL}?{query}")
            self.status_changed.emit("Браузер открыт! Войди через Яндекс / VK и нажми «Разрешить»...")

            # 4. Ожидаем редирект до 3 минут с возможностью мгновенной отмены
            ticks = 0
            max_ticks = 360  # 360 * 0.5 сек = 180 сек
            while self._running and auth_code_holder["code"] is None and ticks < max_ticks:
                self._server.handle_request()
                ticks += 1

            self._server.server_close()
            self._server = None

            if not self._running:
                return

            code = auth_code_holder["code"]
            if not code:
                self.auth_error.emit("Время ожидания истекло. Попробуй ещё раз.")
                return

            # 5. Обмениваем одноразовый code на постоянный API-ключ
            self.status_changed.emit("Получаю API-ключ от RouterAI...")
            payload = json.dumps({
                "code": code,
                "code_verifier": code_verifier,
                "code_challenge_method": "S256",
                "callback_url": callback_url,
            }).encode("utf-8")

            req = urllib.request.Request(
                self.KEYS_EXCHANGE_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                api_key = str(data.get("key", "")).strip()

            if not api_key:
                self.auth_error.emit("RouterAI не вернул ключ. Попробуй создать его вручную на сайте.")
                return

            self.auth_success.emit(api_key)

        except Exception as e:
            if self._server:
                try:
                    self._server.server_close()
                except Exception:
                    pass
            if self._running:
                self.auth_error.emit(f"Ошибка подключения: {e}")


class RouterAiAuthDialog(QDialog):
    """Окно подключения RouterAI в 1 клик (Яндекс / VK) или по готовому ключу."""
    key_saved = pyqtSignal(str)

    def __init__(self, font_family: str = "Arial", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(460, 405)
        self.font_family = font_family
        self.drag_position = QPoint()
        self.oauth_worker = None

        if parent and hasattr(parent, "current_theme"):
            self.current_theme = parent.current_theme
        else:
            self.current_theme = load_config().get("theme", "dark")

        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.x() + (screen.width() - self.width()) // 2,
            screen.y() + (screen.height() - self.height()) // 2
        )

        self._init_ui()

    def _init_ui(self):
        is_light = (self.current_theme == "light")
        title_col = "#111318" if is_light else "#ded7c4"
        text_col = "#1f2328" if is_light else "#fffde7"
        sub_col = "#555e6d" if is_light else "rgba(255, 253, 231, 0.65)"
        card_bg = "rgba(255, 255, 255, 0.88)" if is_light else "rgba(14, 12, 7, 0.78)"
        border_col = "rgba(17, 19, 24, 0.22)" if is_light else "#78735f"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Заголовок
        header_row = QHBoxLayout()
        title_lbl = QLabel("ПОДКЛЮЧЕНИЕ ROUTERAI")
        title_lbl.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {title_col}; letter-spacing: 1px;")
        header_row.addWidget(title_lbl)
        header_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Карточка 1: Быстрый вход через браузер (Яндекс / VK)
        oauth_card = QFrame()
        oauth_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1.2px solid {border_col};
                border-radius: 10px;
            }}
        """)
        oauth_l = QVBoxLayout(oauth_card)
        oauth_l.setContentsMargins(12, 10, 12, 10)
        oauth_l.setSpacing(8)

        desc_lbl = QLabel(
            "Авторизуйся в один клик через <b>Яндекс ID</b>, <b>VK ID</b> или почту — "
            "Акира сама получит API-ключ и разблокирует в Студии модели "
            "<b>DeepSeek</b>, <b>Claude Opus</b> и <b>Gemini Carbon</b>."
        )
        desc_lbl.setFont(QFont(self.font_family, 10))
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {text_col}; border: none; background: transparent;")
        oauth_l.addWidget(desc_lbl)

        self.btn_oauth = QPushButton("ВОЙТИ ЧЕРЕЗ ЯНДЕКС / VK (В 1 КЛИК)")
        self.btn_oauth.setFixedHeight(34)
        self.btn_oauth.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        self.btn_oauth.setCursor(Qt.CursorShape.PointingHandCursor)
        if is_light:
            self.btn_oauth.setStyleSheet("""
                QPushButton {
                    background-color: #111318;
                    color: #ffffff;
                    border: none;
                    border-radius: 7px;
                    letter-spacing: 0.6px;
                }
                QPushButton:hover { background-color: #2b313d; }
                QPushButton:disabled { background-color: #94a3b8; color: #f8fafc; }
            """)
        else:
            self.btn_oauth.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
                    color: #0d0a05;
                    border: none;
                    border-radius: 7px;
                    letter-spacing: 0.6px;
                }
                QPushButton:hover { background: #ffffff; }
                QPushButton:disabled { background: #3b382e; color: #8c8572; }
            """)
        self.btn_oauth.clicked.connect(self._start_oauth)
        oauth_l.addWidget(self.btn_oauth)

        self.status_lbl = QLabel("Пополнение баланса на сайте от 100 ₽ через СБП или карту РФ")
        self.status_lbl.setFont(QFont(self.font_family, 9))
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color: {sub_col}; border: none; background: transparent;")
        oauth_l.addWidget(self.status_lbl)

        layout.addWidget(oauth_card)

        # Карточка 2: Ручной ввод ключа и пополнение
        manual_card = QFrame()
        manual_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1.2px solid {border_col};
                border-radius: 10px;
            }}
        """)
        manual_l = QVBoxLayout(manual_card)
        manual_l.setContentsMargins(12, 10, 12, 10)
        manual_l.setSpacing(7)

        manual_title = QLabel("ИЛИ ВСТАВЬ API-КЛЮЧ ВРУЧНУЮ")
        manual_title.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        manual_title.setStyleSheet(f"color: {sub_col}; letter-spacing: 0.8px; border: none; background: transparent;")
        manual_l.addWidget(manual_title)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.key_input.setPlaceholderText("sk-...")
        self.key_input.setFixedHeight(30)
        self.key_input.setFont(QFont("Consolas", 10))

        cfg = load_config()
        api_keys = cfg.get("api_keys", {})
        existing_key = (
            api_keys.get("routerai", "").strip()
            or api_keys.get("openrouter", "").strip()
        )
        if existing_key:
            self.key_input.setText(existing_key)

        if is_light:
            self.key_input.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    color: #111318;
                    border: 1.5px solid #111318;
                    border-radius: 6px;
                    padding: 0px 8px;
                }
            """)
        else:
            self.key_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(7, 7, 5, 0.92);
                    color: #ded7c4;
                    border: 1px solid #78735f;
                    border-radius: 6px;
                    padding: 0px 8px;
                }
            """)
        input_row.addWidget(self.key_input, 1)

        btn_paste = QPushButton("ВСТАВИТЬ")
        btn_paste.setFixedSize(72, 30)
        btn_paste.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_paste.clicked.connect(self._paste_from_clipboard)
        input_row.addWidget(btn_paste)

        btn_save = QPushButton("СОХРАНИТЬ")
        btn_save.setFixedSize(82, 30)
        btn_save.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._save_manual_key)
        input_row.addWidget(btn_save)

        sec_btn_css = (
            "QPushButton { background-color: #ffffff; color: #111318; border: 1.5px solid #111318; border-radius: 6px; }"
            "QPushButton:hover { background-color: #111318; color: #ffffff; }"
            if is_light else
            "QPushButton { background-color: rgba(120, 115, 95, 0.22); color: #ded7c4; border: 1px solid #78735f; border-radius: 6px; }"
            "QPushButton:hover { background-color: rgba(222, 215, 196, 0.25); color: #ffffff; }"
        )
        btn_paste.setStyleSheet(sec_btn_css)
        btn_save.setStyleSheet(sec_btn_css)

        manual_l.addLayout(input_row)
        layout.addWidget(manual_card)

        # Нижняя панель: ссылка на пополнение и кнопка отключения
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        btn_topup = QPushButton("ПОПОЛНИТЬ БАЛАНС (СБП / КАРТА)")
        btn_topup.setFixedHeight(28)
        btn_topup.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        btn_topup.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_topup.setStyleSheet(sec_btn_css)
        btn_topup.clicked.connect(lambda: webbrowser.open("https://routerai.ru/credits"))
        bottom_row.addWidget(btn_topup, 1)

        if existing_key:
            btn_disconnect = QPushButton("ОТКЛЮЧИТЬ")
            btn_disconnect.setFixedHeight(28)
            btn_disconnect.setFixedWidth(96)
            btn_disconnect.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
            btn_disconnect.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_disconnect.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 82, 82, 0.14);
                    color: #ff5252;
                    border: 1px solid rgba(255, 82, 82, 0.45);
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #ff5252;
                    color: #ffffff;
                }
            """)
            btn_disconnect.clicked.connect(self._disconnect_key)
            bottom_row.addWidget(btn_disconnect)

        layout.addLayout(bottom_row)

    def _start_oauth(self):
        if self.oauth_worker and self.oauth_worker.isRunning():
            return

        self.btn_oauth.setEnabled(False)
        self.btn_oauth.setText("ОЖИДАЮ ВХОД В БРАУЗЕРЕ...")

        self.oauth_worker = RouterAiOAuthWorker(self)
        self.oauth_worker.status_changed.connect(self._on_oauth_status)
        self.oauth_worker.auth_success.connect(self._on_oauth_success)
        self.oauth_worker.auth_error.connect(self._on_oauth_error)
        self.oauth_worker.start()

    def _on_oauth_status(self, text: str):
        self.status_lbl.setText(text)

    def _on_oauth_success(self, api_key: str):
        self.key_input.setText(api_key)
        self.status_lbl.setText("✓ Ключ успешно получен и сохранён!")
        self.status_lbl.setStyleSheet("color: #22c55e; font-weight: bold; border: none; background: transparent;")
        self.key_saved.emit(api_key)
        self.accept()

    def _on_oauth_error(self, err: str):
        self.btn_oauth.setEnabled(True)
        self.btn_oauth.setText("ВОЙТИ ЧЕРЕЗ ЯНДЕКС / VK (В 1 КЛИК)")
        self.status_lbl.setText(err)
        self.status_lbl.setStyleSheet("color: #ff5252; border: none; background: transparent;")

    def _paste_from_clipboard(self):
        text = QGuiApplication.clipboard().text().strip()
        if text:
            self.key_input.setText(text)

    def _save_manual_key(self):
        key = self.key_input.text().strip()
        if not key:
            self.status_lbl.setText("Сначала вставь ключ или нажми «Войти через Яндекс / VK».")
            self.status_lbl.setStyleSheet("color: #ff5252; border: none; background: transparent;")
            return
        self.key_saved.emit(key)
        self.accept()

    def _disconnect_key(self):
        self.key_saved.emit("")
        self.accept()

    def closeEvent(self, event):
        if self.oauth_worker and self.oauth_worker.isRunning():
            self.oauth_worker.stop_listening()
            self.oauth_worker.wait(800)
        super().closeEvent(event)

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

        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
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