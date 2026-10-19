from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRectF, QTimer, QThread
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QGuiApplication
from spotipy.oauth2 import SpotifyPKCE
from core.utils.config import load_config, save_config, get_user_data_path
from gui.styles import get_main_style


class SpotifyAuthWorker(QThread):
    auth_success = pyqtSignal()
    auth_error = pyqtSignal(str)

    def __init__(self, client_id, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.is_running = True

    def run(self):
        try:
            cache_path = get_user_data_path(".spotify_cache")
            scope = (
                "user-read-playback-state "
                "user-modify-playback-state "
                "user-read-currently-playing "
                "user-library-read "
                "user-library-modify "
                "playlist-read-private"
            )
            auth_manager = SpotifyPKCE(
                client_id=self.client_id,
                redirect_uri="http://127.0.0.1:8888/callback",
                scope=scope,
                cache_path=cache_path,
                open_browser=True
            )
            token_info = auth_manager.get_access_token(check_cache=False)
            if token_info and self.is_running:
                self.auth_success.emit()
            elif self.is_running:
                self.auth_error.emit("Не удалось получить токен авторизации.")
        except Exception as e:
            if self.is_running:
                self.auth_error.emit(str(e))

    def stop(self):
        self.is_running = False


class SpotifyAuthDialog(QDialog):
    auth_completed = pyqtSignal()

    def __init__(self, font_family="Arial", parent=None, theme: str = None):
        super().__init__(parent)
        self.font_family = font_family
        self.drag_position = QPoint()
        self.worker = None

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
        self.client_id = cfg.get("api_keys", {}).get("spotify_client_id", "").strip()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(410, 310)
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
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_lbl = QLabel("Вход в Spotify (PKCE)")
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

        self.desc_lbl = QLabel("Для подключения укажи Client ID приложения.")
        self.desc_lbl.setFont(QFont(self.font_family, 10))
        desc_color = "rgba(17, 19, 24, 0.70)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.65)"
        self.desc_lbl.setStyleSheet(f"color: {desc_color};")
        self.desc_lbl.setWordWrap(True)
        layout.addWidget(self.desc_lbl)

        self.card = QFrame()
        self.card.setObjectName("BentoCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        lbl_cid = QLabel("SPOTIFY CLIENT ID:")
        lbl_cid.setObjectName("BentoSectionTitle")
        lbl_cid.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        card_layout.addWidget(lbl_cid)

        self.client_id_input = QLineEdit()
        self.client_id_input.setObjectName("SettingInput")
        self.client_id_input.setFont(QFont("Consolas", 10))
        self.client_id_input.setPlaceholderText("Вставь Client ID из developer.spotify.com...")
        self.client_id_input.setText(self.client_id)
        card_layout.addWidget(self.client_id_input)

        layout.addWidget(self.card)

        self.status_lbl = QLabel("Нажми «Войти через браузер» для авторизации")
        self.status_lbl.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        status_color = "rgba(17, 19, 24, 0.65)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.6)"
        self.status_lbl.setStyleSheet(f"color: {status_color};")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
            self.status_lbl.setText("✕ Введи Spotify Client ID")
            err_col = "#e53935" if self.current_theme == "light" else "#ff5252"
            self.status_lbl.setStyleSheet(f"color: {err_col};")
            return

        self.client_id = cid
        cfg = load_config()
        if "api_keys" not in cfg:
            cfg["api_keys"] = {}
        cfg["api_keys"]["spotify_client_id"] = cid
        save_config(cfg)

        self.status_lbl.setText("Ожидаю подтверждения в браузере...")
        col = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.status_lbl.setStyleSheet(f"color: {col};")
        self.auth_btn.setEnabled(False)

        self.worker = SpotifyAuthWorker(self.client_id, self)
        self.worker.auth_success.connect(self._on_auth_success)
        self.worker.auth_error.connect(self._on_auth_error)
        self.worker.start()

    def _on_auth_success(self):
        self.status_lbl.setText("✓ Spotify успешно подключен! Закрываю...")
        succ_col = "#00c853" if self.current_theme == "light" else "#00e676"
        self.status_lbl.setStyleSheet(f"color: {succ_col};")
        self.auth_completed.emit()
        QTimer.singleShot(1400, self.accept)

    def _on_auth_error(self, err):
        self.status_lbl.setText("✕ Ошибка авторизации")
        err_col = "#e53935" if self.current_theme == "light" else "#ff5252"
        self.status_lbl.setStyleSheet(f"color: {err_col};")
        self.auth_btn.setEnabled(True)

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            self.worker.wait(300)
        self._restore_parent_focus()
        super().reject()

    def accept(self):
        if self.worker and self.worker.isRunning():
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