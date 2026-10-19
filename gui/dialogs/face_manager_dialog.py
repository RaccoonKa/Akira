import os
import shutil
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QFileDialog, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QFont, QPainterPath, QGuiApplication,
    QPixmap
)
from core.utils.config import get_user_data_path, load_config
from gui.styles import get_main_style


class FaceManagerDialog(QDialog):
    photos_changed = pyqtSignal()

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

        self.face_dir = os.path.normpath(get_user_data_path("owner_face"))
        os.makedirs(self.face_dir, exist_ok=True)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(460, 480)
        self.setStyleSheet(get_main_style(self.current_theme))

        self._center_on_screen(parent)
        self.init_ui()
        self._refresh_gallery()

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

        title_lbl = QLabel("БИОМЕТРИЯ // БАЗА ФОТО ЛИЦА")
        title_lbl.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        title_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        title_lbl.setStyleSheet(f"color: {title_color}; letter-spacing: 1px;")
        title_col.addWidget(title_lbl)

        sub_title = QLabel("ЭТАЛОННЫЕ СНИМКИ ДЛЯ СИСТЕМЫ FACE ID")
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
        close_btn.clicked.connect(self.accept)
        header.addWidget(close_btn)
        layout.addLayout(header)

        top_actions = QHBoxLayout()
        top_actions.setContentsMargins(0, 2, 0, 2)

        self.lbl_count = QLabel("ВСЕГО СНИМКОВ: 0")
        self.lbl_count.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        count_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.lbl_count.setStyleSheet(f"color: {count_color}; letter-spacing: 0.5px;")
        top_actions.addWidget(self.lbl_count)
        top_actions.addStretch()

        btn_add = QPushButton("+ ДОБАВИТЬ СНИМКИ")
        btn_add.setObjectName("BentoActionBtn")
        btn_add.setFixedHeight(24)
        btn_add.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._add_photos)
        top_actions.addWidget(btn_add)
        layout.addLayout(top_actions)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setContentsMargins(0, 4, 4, 4)
        self.grid_layout.setSpacing(8)

        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        ok_btn = QPushButton("ЗАКРЫТЬ")
        ok_btn.setObjectName("BentoActionBtn")
        ok_btn.setFixedHeight(26)
        ok_btn.setFixedWidth(100)
        ok_btn.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        bottom_row.addWidget(ok_btn)

        layout.addLayout(bottom_row)

    def _get_rounded_thumbnail(self, img_path: str, w: int, h: int, radius: int = 6) -> QPixmap:
        src = QPixmap(img_path)
        if src.isNull():
            dest = QPixmap(w, h)
            fallback_col = QColor(220, 226, 235) if self.current_theme == "light" else QColor(15, 12, 7)
            dest.fill(fallback_col)
            return dest

        scaled = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x_off = max(0, (scaled.width() - w) // 2)
        y_off = max(0, (scaled.height() - h) // 2)
        cropped = scaled.copy(x_off, y_off, w, h)

        dest = QPixmap(w, h)
        dest.fill(Qt.GlobalColor.transparent)

        painter = QPainter(dest)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()

        return dest

    def _refresh_gallery(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
        files = []
        if os.path.exists(self.face_dir):
            files = [f for f in sorted(os.listdir(self.face_dir)) if f.lower().endswith(valid_exts)]

        self.lbl_count.setText(f"ВСЕГО СНИМКОВ: {len(files)}")

        if not files:
            empty_frame = QFrame()
            if self.current_theme == "light":
                empty_frame.setStyleSheet("""
                    QFrame {
                        background-color: rgba(255, 255, 255, 0.7);
                        border: 1.5px dashed rgba(17, 19, 24, 0.35);
                        border-radius: 8px;
                        padding: 24px;
                    }
                """)
            else:
                empty_frame.setStyleSheet("""
                    QFrame {
                        background-color: rgba(14, 12, 7, 0.4);
                        border: 1px dashed #78735f;
                        border-radius: 8px;
                        padding: 24px;
                    }
                """)
            empty_l = QVBoxLayout(empty_frame)
            empty_l.setSpacing(4)

            lbl1 = QLabel("НЕТ СОХРАНЁННЫХ СНИМКОВ")
            lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c1 = "rgba(17, 19, 24, 0.8)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.6)"
            lbl1.setStyleSheet(f"color: {c1}; font-size: 10px; font-weight: bold; letter-spacing: 0.8px;")
            empty_l.addWidget(lbl1)

            lbl2 = QLabel("Добавь 3–5 фото лица с разным освещением и ракурсами для точной работы Face ID")
            lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl2.setWordWrap(True)
            c2 = "rgba(17, 19, 24, 0.5)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.35)"
            lbl2.setStyleSheet(f"color: {c2}; font-size: 8px;")
            empty_l.addWidget(lbl2)

            self.grid_layout.addWidget(empty_frame, 0, 0, 1, 3)
            return

        columns = 3
        for idx, filename in enumerate(files):
            full_path = os.path.join(self.face_dir, filename)

            card = QFrame()
            card.setObjectName("BentoCell")
            card.setFixedSize(130, 142)

            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(6, 6, 6, 6)
            c_layout.setSpacing(4)

            img_lbl = QLabel()
            img_lbl.setFixedSize(118, 98)
            img_lbl.setPixmap(self._get_rounded_thumbnail(full_path, 118, 98, radius=5))
            c_layout.addWidget(img_lbl)

            bottom_bar = QHBoxLayout()
            bottom_bar.setContentsMargins(2, 0, 2, 0)
            bottom_bar.setSpacing(4)

            name_lbl = QLabel(filename)
            name_lbl.setFont(QFont(self.font_family, 7))
            name_color = "rgba(17, 19, 24, 0.75)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.65)"
            name_lbl.setStyleSheet(f"color: {name_color}; font-family: 'Consolas', monospace;")
            bottom_bar.addWidget(name_lbl, 1)

            del_btn = QPushButton("✕")
            del_btn.setObjectName("RemoveFileBtn")
            del_btn.setFixedSize(18, 18)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda _, p=full_path: self._delete_photo(p))
            bottom_bar.addWidget(del_btn)

            c_layout.addLayout(bottom_bar)

            row = idx // columns
            col = idx % columns
            self.grid_layout.addWidget(card, row, col)

    def _add_photos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выбор фотографий владельца",
            "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)"
        )
        if files:
            count = 0
            for f in files:
                try:
                    dst = os.path.join(self.face_dir, os.path.basename(f))
                    shutil.copy(f, dst)
                    count += 1
                except Exception:
                    pass

            if count > 0:
                self._refresh_gallery()
                self.photos_changed.emit()

    def _delete_photo(self, path: str):
        try:
            if os.path.exists(path):
                os.remove(path)
                self._refresh_gallery()
                self.photos_changed.emit()
        except Exception as e:
            print(f"[Face Delete Error]: {e}")

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