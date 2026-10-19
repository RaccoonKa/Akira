import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QScrollArea, QWidget, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QGuiApplication
from core.utils.config import load_config
from gui.styles import get_main_style


class ModeConfigDialog(QDialog):
    items_saved = pyqtSignal(list)

    def __init__(self, mode_title: str, items: list, font_family="Arial", parent=None, theme: str = None):
        super().__init__(parent)
        self.mode_title = mode_title
        self.items = list(items)
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

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(430, 440)
        self.setStyleSheet(get_main_style(self.current_theme))

        self._center_on_screen(parent)
        self.init_ui()
        self._refresh_items_list()

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

        clean_title = self.mode_title.replace("Профиль «", "").replace("Режим «", "").replace("»", "").upper()
        title_lbl = QLabel(f"ПРОФИЛЬ // {clean_title}")
        title_lbl.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        title_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        title_lbl.setStyleSheet(f"color: {title_color}; letter-spacing: 1px;")
        title_col.addWidget(title_lbl)

        sub_title = QLabel("АВТОЗАПУСК ПРИЛОЖЕНИЙ И ССЫЛОК")
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

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.items_layout = QVBoxLayout(self.scroll_content)
        self.items_layout.setContentsMargins(0, 4, 4, 4)
        self.items_layout.setSpacing(5)

        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, 1)

        input_box = QFrame()
        input_box.setObjectName("BentoCard")
        box_layout = QVBoxLayout(input_box)
        box_layout.setContentsMargins(10, 8, 10, 8)
        box_layout.setSpacing(6)

        site_row = QHBoxLayout()
        site_row.setSpacing(6)

        self.site_input = QLineEdit()
        self.site_input.setObjectName("SettingInput")
        self.site_input.setFont(QFont(self.font_family, 9))
        self.site_input.setPlaceholderText("Адрес сайта (например, github.com)...")
        self.site_input.setFixedHeight(28)
        self.site_input.returnPressed.connect(self._add_site)
        site_row.addWidget(self.site_input, 1)

        btn_add_site = QPushButton("+ URL")
        btn_add_site.setObjectName("BentoActionBtn")
        btn_add_site.setFixedHeight(28)
        btn_add_site.setFixedWidth(68)
        btn_add_site.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        btn_add_site.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_site.clicked.connect(self._add_site)
        site_row.addWidget(btn_add_site)
        box_layout.addLayout(site_row)

        btn_choose_exe = QPushButton("ОБЗОР ПРОГРАММЫ (.EXE / .LNK)")
        btn_choose_exe.setObjectName("AttachBtn")
        btn_choose_exe.setFixedHeight(26)
        btn_choose_exe.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        btn_choose_exe.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_choose_exe.clicked.connect(self._choose_app_file)
        box_layout.addWidget(btn_choose_exe)

        layout.addWidget(input_box)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        save_btn = QPushButton("ГОТОВО")
        save_btn.setObjectName("BentoActionBtn")
        save_btn.setFixedHeight(26)
        save_btn.setFixedWidth(100)
        save_btn.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_and_close)
        bottom_row.addWidget(save_btn)

        layout.addLayout(bottom_row)

    def _refresh_items_list(self):
        while self.items_layout.count():
            child = self.items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.items:
            empty_frame = QFrame()
            if self.current_theme == "light":
                empty_frame.setStyleSheet("""
                    QFrame {
                        background-color: rgba(255, 255, 255, 0.7);
                        border: 1.5px dashed rgba(17, 19, 24, 0.35);
                        border-radius: 8px;
                        padding: 16px;
                    }
                """)
            else:
                empty_frame.setStyleSheet("""
                    QFrame {
                        background-color: rgba(14, 12, 7, 0.4);
                        border: 1px dashed #78735f;
                        border-radius: 8px;
                        padding: 16px;
                    }
                """)
            empty_l = QVBoxLayout(empty_frame)
            empty_l.setSpacing(3)

            lbl1 = QLabel("НЕТ ПРИВЯЗАННЫХ РЕСУРСОВ")
            lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c1 = "rgba(17, 19, 24, 0.8)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.6)"
            lbl1.setStyleSheet(f"color: {c1}; font-size: 9px; font-weight: bold; letter-spacing: 0.8px;")
            empty_l.addWidget(lbl1)

            lbl2 = QLabel("Добавь веб-адрес или исполняемый файл ниже")
            lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c2 = "rgba(17, 19, 24, 0.5)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.35)"
            lbl2.setStyleSheet(f"color: {c2}; font-size: 8px;")
            empty_l.addWidget(lbl2)

            self.items_layout.addWidget(empty_frame)
            return

        for idx, item in enumerate(self.items):
            card = QFrame()
            card.setObjectName("BentoCell")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(8, 5, 8, 5)
            card_layout.setSpacing(8)

            is_url = item.startswith("http://") or item.startswith("https://")

            tag_lbl = QLabel("WEB" if is_url else "APP")
            tag_lbl.setFont(QFont(self.font_family, 7, QFont.Weight.Bold))
            if is_url:
                if self.current_theme == "light":
                    tag_lbl.setStyleSheet("""
                        background: rgba(17, 19, 24, 0.08);
                        color: #111318;
                        border: 1.2px solid #111318;
                        border-radius: 4px;
                        padding: 2px 4px;
                    """)
                else:
                    tag_lbl.setStyleSheet("""
                        background: rgba(120, 115, 95, 0.2);
                        color: #ded7c4;
                        border: 1px solid #78735f;
                        border-radius: 4px;
                        padding: 2px 4px;
                    """)
            else:
                if self.current_theme == "light":
                    tag_lbl.setStyleSheet("""
                        background: rgba(2, 119, 189, 0.12);
                        color: #0277bd;
                        border: 1.2px solid rgba(2, 119, 189, 0.4);
                        border-radius: 4px;
                        padding: 2px 4px;
                    """)
                else:
                    tag_lbl.setStyleSheet("""
                        background: rgba(100, 180, 255, 0.15);
                        color: #80d8ff;
                        border: 1px solid rgba(100, 180, 255, 0.35);
                        border-radius: 4px;
                        padding: 2px 4px;
                    """)
            card_layout.addWidget(tag_lbl)

            text_container = QVBoxLayout()
            text_container.setSpacing(1)

            if is_url:
                title = item.replace("https://", "").replace("http://", "").split("/")[0]
                subtitle = item
            else:
                title = os.path.basename(item)
                subtitle = item

            t_lbl = QLabel(title)
            t_lbl.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
            t_color = "#111318" if self.current_theme == "light" else "#fffde7"
            t_lbl.setStyleSheet(f"color: {t_color};")
            text_container.addWidget(t_lbl)

            sub_lbl = QLabel(subtitle)
            sub_lbl.setFont(QFont("Consolas", 8))
            sub_color = "rgba(17, 19, 24, 0.55)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.4)"
            sub_lbl.setStyleSheet(f"color: {sub_color};")
            text_container.addWidget(sub_lbl)

            card_layout.addLayout(text_container, 1)

            del_btn = QPushButton("✕")
            del_btn.setObjectName("RemoveFileBtn")
            del_btn.setFixedSize(18, 18)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda _, i=idx: self._remove_item(i))
            card_layout.addWidget(del_btn)

            self.items_layout.addWidget(card)

    def _add_site(self):
        raw_url = self.site_input.text().strip()
        if not raw_url:
            return

        if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            raw_url = "https://" + raw_url

        if raw_url not in self.items:
            self.items.append(raw_url)
            self._refresh_items_list()

        self.site_input.clear()

    def _choose_app_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбор программы",
            "",
            "Исполняемые файлы (*.exe *.lnk *.bat *.cmd);;Все файлы (*.*)"
        )
        if file_path and file_path not in self.items:
            self.items.append(file_path)
            self._refresh_items_list()

    def _remove_item(self, index: int):
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self._refresh_items_list()

    def _save_and_close(self):
        self.items_saved.emit(self.items)
        self.accept()

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