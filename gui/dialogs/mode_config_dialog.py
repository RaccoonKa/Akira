import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QGuiApplication
from core.utils.config import load_config
from gui.styles import get_main_style
from gui.ui_helpers import open_file_dialog


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
        self.setFixedSize(480, 470)
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

    def _format_count_badge(self, count: int) -> str:
        if count == 0:
            return "ПУСТО"
        if count % 10 == 1 and count % 100 != 11:
            return f"{count} РЕСУРС"
        if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            return f"{count} РЕСУРСА"
        return f"{count} РЕСУРСОВ"

    def init_ui(self):
        is_light = self.current_theme == "light"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # --- Шапка окна ---
        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 0, 0)
        header.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)

        title_top_row = QHBoxLayout()
        title_top_row.setSpacing(8)

        clean_title = self.mode_title.replace("Профиль «", "").replace("Режим «", "").replace("»", "").upper()
        title_lbl = QLabel(f"ПРОФИЛЬ // {clean_title}")
        title_lbl.setFont(QFont(self.font_family, 11))
        title_color = "#111318" if is_light else "#ded7c4"
        title_lbl.setStyleSheet(f"color: {title_color}; letter-spacing: 0.9px; background: transparent;")
        title_top_row.addWidget(title_lbl)

        self.count_badge = QLabel("ПУСТО")
        self.count_badge.setFont(QFont(self.font_family, 8))
        if is_light:
            self.count_badge.setStyleSheet("""
                background-color: rgba(17, 19, 24, 0.08);
                color: #111318;
                border: 1px solid rgba(17, 19, 24, 0.22);
                border-radius: 6px;
                padding: 2px 7px;
                letter-spacing: 0.6px;
            """)
        else:
            self.count_badge.setStyleSheet("""
                background-color: rgba(222, 215, 196, 0.12);
                color: #ded7c4;
                border: 1px solid rgba(120, 115, 95, 0.45);
                border-radius: 6px;
                padding: 2px 7px;
                letter-spacing: 0.6px;
            """)
        title_top_row.addWidget(self.count_badge)
        title_top_row.addStretch()
        title_col.addLayout(title_top_row)

        sub_title = QLabel("Автозапуск приложений и веб-страниц по голосовой команде")
        sub_title.setFont(QFont(self.font_family, 8))
        sub_color = "rgba(17, 19, 24, 0.58)" if is_light else "rgba(255, 253, 231, 0.50)"
        sub_title.setStyleSheet(f"color: {sub_color}; background: transparent;")
        title_col.addWidget(sub_title)

        header.addLayout(title_col, 1)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if is_light:
            close_btn.setStyleSheet("""
                QPushButton#CloseBtn {
                    background-color: transparent;
                    color: #111318;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                }
                QPushButton#CloseBtn:hover {
                    background-color: #e53935;
                    color: #ffffff;
                }
            """)
        else:
            close_btn.setStyleSheet("""
                QPushButton#CloseBtn {
                    background-color: transparent;
                    color: #ded7c4;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                }
                QPushButton#CloseBtn:hover {
                    background-color: #ff5252;
                    color: #ffffff;
                }
            """)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        # --- Разделитель под заголовком ---
        divider = QFrame()
        divider.setFixedHeight(1)
        div_col = "rgba(17, 19, 24, 0.14)" if is_light else "rgba(120, 115, 95, 0.35)"
        divider.setStyleSheet(f"background-color: {div_col}; border: none;")
        layout.addWidget(divider)

        # --- Список привязанных ресурсов ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.items_layout = QVBoxLayout(self.scroll_content)
        self.items_layout.setContentsMargins(0, 2, 4, 2)
        self.items_layout.setSpacing(7)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, 1)

        # --- Нижняя Bento-карточка добавления ---
        input_box = QFrame()
        if is_light:
            input_box.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 255, 255, 0.90);
                    border: 1.5px solid rgba(17, 19, 24, 0.20);
                    border-radius: 11px;
                }
            """)
        else:
            input_box.setStyleSheet("""
                QFrame {
                    background-color: rgba(14, 13, 9, 0.86);
                    border: 1px solid rgba(120, 115, 95, 0.35);
                    border-radius: 11px;
                }
            """)

        box_layout = QVBoxLayout(input_box)
        box_layout.setContentsMargins(12, 10, 12, 10)
        box_layout.setSpacing(8)

        add_lbl = QLabel("ДОБАВИТЬ РЕСУРС")
        add_lbl.setFont(QFont(self.font_family, 8))
        add_lbl_col = "#111318" if is_light else "#ded7c4"
        add_lbl.setStyleSheet(f"color: {add_lbl_col}; letter-spacing: 1px; background: transparent; border: none;")
        box_layout.addWidget(add_lbl)

        site_row = QHBoxLayout()
        site_row.setSpacing(8)

        self.site_input = QLineEdit()
        self.site_input.setFont(QFont(self.font_family, 9))
        self.site_input.setPlaceholderText("Адрес сайта (например, github.com)...")
        self.site_input.setFixedHeight(32)
        if is_light:
            self.site_input.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    color: #111318;
                    border: 1.5px solid #111318;
                    border-radius: 7px;
                    padding: 4px 12px;
                }
                QLineEdit:focus {
                    border: 2px solid #000000;
                }
            """)
        else:
            self.site_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(7, 7, 5, 0.92);
                    color: #fffde7;
                    border: 1px solid #78735f;
                    border-radius: 7px;
                    padding: 4px 12px;
                }
                QLineEdit:hover {
                    border: 1px solid #9e9780;
                    background-color: #12110d;
                }
                QLineEdit:focus {
                    border: 1px solid #ded7c4;
                    background-color: #15130f;
                }
            """)
        self.site_input.returnPressed.connect(self._add_site)
        site_row.addWidget(self.site_input, 1)

        btn_add_site = QPushButton("+ САЙТ")
        btn_add_site.setFixedSize(76, 32)
        btn_add_site.setFont(QFont(self.font_family, 9))
        btn_add_site.setCursor(Qt.CursorShape.PointingHandCursor)
        if is_light:
            btn_add_site.setStyleSheet("""
                QPushButton {
                    background-color: #111318;
                    color: #ffffff;
                    border: none;
                    border-radius: 7px;
                    letter-spacing: 0.6px;
                }
                QPushButton:hover {
                    background-color: #2b313d;
                }
            """)
        else:
            btn_add_site.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
                    color: #121008;
                    border: none;
                    border-radius: 7px;
                    letter-spacing: 0.6px;
                }
                QPushButton:hover {
                    background: #ffffff;
                }
            """)
        btn_add_site.clicked.connect(self._add_site)
        site_row.addWidget(btn_add_site)
        box_layout.addLayout(site_row)

        btn_choose_exe = QPushButton("+ ВЫБРАТЬ ПРОГРАММУ (.EXE / .LNK)")
        btn_choose_exe.setFixedHeight(30)
        btn_choose_exe.setFont(QFont(self.font_family, 8))
        btn_choose_exe.setCursor(Qt.CursorShape.PointingHandCursor)
        if is_light:
            btn_choose_exe.setStyleSheet("""
                QPushButton {
                    background-color: rgba(238, 242, 248, 0.95);
                    color: #111318;
                    border: 1.5px solid #111318;
                    border-radius: 7px;
                    letter-spacing: 0.6px;
                }
                QPushButton:hover {
                    background-color: #111318;
                    color: #ffffff;
                }
            """)
        else:
            btn_choose_exe.setStyleSheet("""
                QPushButton {
                    background-color: rgba(8, 8, 6, 0.85);
                    color: #ded7c4;
                    border: 1px solid #78735f;
                    border-radius: 7px;
                    letter-spacing: 0.6px;
                }
                QPushButton:hover {
                    background-color: #1e1b14;
                    border-color: #9e9780;
                    color: #ffffff;
                }
            """)
        btn_choose_exe.clicked.connect(self._choose_app_file)
        box_layout.addWidget(btn_choose_exe)

        layout.addWidget(input_box)

        # --- Нижняя панель кнопок ---
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(2, 2, 0, 0)
        bottom_row.setSpacing(8)

        cancel_btn = QPushButton("ОТМЕНА")
        cancel_btn.setFixedSize(96, 32)
        cancel_btn.setFont(QFont(self.font_family, 9))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if is_light:
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #555e6d;
                    border: 1px solid rgba(17, 19, 24, 0.25);
                    border-radius: 7px;
                    letter-spacing: 0.6px;
                }
                QPushButton:hover {
                    background-color: rgba(17, 19, 24, 0.06);
                    color: #111318;
                }
            """)
        else:
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: rgba(222, 215, 196, 0.65);
                    border: 1px solid rgba(120, 115, 95, 0.40);
                    border-radius: 7px;
                    letter-spacing: 0.6px;
                }
                QPushButton:hover {
                    background-color: rgba(222, 215, 196, 0.08);
                    color: #ffffff;
                }
            """)
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        bottom_row.addStretch()

        save_btn = QPushButton("ГОТОВО ✓")
        save_btn.setFixedSize(116, 32)
        save_btn.setFont(QFont(self.font_family, 9))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if is_light:
            save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #111318;
                    color: #ffffff;
                    border: none;
                    border-radius: 7px;
                    letter-spacing: 0.8px;
                }
                QPushButton:hover {
                    background-color: #2b313d;
                }
            """)
        else:
            save_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
                    color: #121008;
                    border: none;
                    border-radius: 7px;
                    letter-spacing: 0.8px;
                }
                QPushButton:hover {
                    background: #ffffff;
                }
            """)
        save_btn.clicked.connect(self._save_and_close)
        bottom_row.addWidget(save_btn)

        layout.addLayout(bottom_row)

    def _refresh_items_list(self):
        is_light = self.current_theme == "light"
        self.count_badge.setText(self._format_count_badge(len(self.items)))

        while self.items_layout.count():
            child = self.items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.items:
            empty_frame = QFrame()
            empty_frame.setMinimumHeight(145)
            if is_light:
                empty_frame.setStyleSheet("""
                    QFrame {
                        background-color: rgba(255, 255, 255, 0.72);
                        border: 1.5px dashed rgba(17, 19, 24, 0.28);
                        border-radius: 10px;
                    }
                """)
            else:
                empty_frame.setStyleSheet("""
                    QFrame {
                        background-color: rgba(16, 14, 9, 0.55);
                        border: 1px dashed rgba(120, 115, 95, 0.45);
                        border-radius: 10px;
                    }
                """)
            empty_l = QVBoxLayout(empty_frame)
            empty_l.setContentsMargins(16, 20, 16, 20)
            empty_l.setSpacing(6)
            empty_l.setAlignment(Qt.AlignmentFlag.AlignCenter)

            badge_empty = QLabel("00")
            badge_empty.setFont(QFont(self.font_family, 9))
            badge_empty.setFixedSize(28, 22)
            badge_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_light:
                badge_empty.setStyleSheet("background-color: #111318; color: #ffffff; border: none; border-radius: 6px;")
            else:
                badge_empty.setStyleSheet(
                    "background-color: rgba(222, 215, 196, 0.14); color: #ded7c4; "
                    "border: 1px solid rgba(120, 115, 95, 0.50); border-radius: 6px;"
                )
            empty_l.addWidget(badge_empty, 0, Qt.AlignmentFlag.AlignCenter)

            lbl1 = QLabel("СПИСОК АВТОЗАПУСКА ПУСТ")
            lbl1.setFont(QFont(self.font_family, 9))
            lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c1 = "#111318" if is_light else "#ded7c4"
            lbl1.setStyleSheet(f"color: {c1}; letter-spacing: 0.8px; background: transparent; border: none;")
            empty_l.addWidget(lbl1)

            lbl2 = QLabel("Добавьте адрес сайта или выберите программу ниже")
            lbl2.setFont(QFont(self.font_family, 8))
            lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c2 = "#555e6d" if is_light else "rgba(255, 253, 231, 0.45)"
            lbl2.setStyleSheet(f"color: {c2}; background: transparent; border: none;")
            empty_l.addWidget(lbl2)

            self.items_layout.addWidget(empty_frame)
            return

        for idx, item in enumerate(self.items):
            card = QFrame()
            card.setFixedHeight(50)
            card.setToolTip(item)
            if is_light:
                card.setStyleSheet("""
                    QFrame {
                        background-color: rgba(255, 255, 255, 0.92);
                        border: 1.2px solid rgba(17, 19, 24, 0.18);
                        border-radius: 9px;
                    }
                    QFrame:hover {
                        background-color: #ffffff;
                        border: 1.2px solid #111318;
                    }
                """)
            else:
                card.setStyleSheet("""
                    QFrame {
                        background-color: rgba(16, 14, 9, 0.84);
                        border: 1px solid rgba(120, 115, 95, 0.35);
                        border-radius: 9px;
                    }
                    QFrame:hover {
                        background-color: rgba(24, 21, 15, 0.94);
                        border: 1px solid rgba(158, 151, 128, 0.55);
                    }
                """)

            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(11, 6, 10, 6)
            card_layout.setSpacing(10)

            is_url = item.startswith("http://") or item.startswith("https://")

            tag_lbl = QLabel("WEB" if is_url else "APP")
            tag_lbl.setFont(QFont(self.font_family, 8))
            tag_lbl.setFixedSize(38, 22)
            tag_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_url:
                if is_light:
                    tag_lbl.setStyleSheet("""
                        background-color: #111318;
                        color: #ffffff;
                        border: none;
                        border-radius: 6px;
                    """)
                else:
                    tag_lbl.setStyleSheet("""
                        background-color: rgba(222, 215, 196, 0.14);
                        color: #ded7c4;
                        border: 1px solid rgba(120, 115, 95, 0.55);
                        border-radius: 6px;
                    """)
            else:
                if is_light:
                    tag_lbl.setStyleSheet("""
                        background-color: rgba(2, 119, 189, 0.12);
                        color: #0277bd;
                        border: 1px solid rgba(2, 119, 189, 0.45);
                        border-radius: 6px;
                    """)
                else:
                    tag_lbl.setStyleSheet("""
                        background-color: rgba(56, 189, 248, 0.14);
                        color: #7dd3fc;
                        border: 1px solid rgba(56, 189, 248, 0.40);
                        border-radius: 6px;
                    """)
            card_layout.addWidget(tag_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

            text_container = QVBoxLayout()
            text_container.setContentsMargins(0, 0, 0, 0)
            text_container.setSpacing(2)

            if is_url:
                title = item.replace("https://", "").replace("http://", "").split("/")[0]
                subtitle = item
            else:
                title = os.path.basename(item)
                subtitle = item

            if len(subtitle) > 48:
                subtitle = subtitle[:22] + "..." + subtitle[-23:]

            t_lbl = QLabel(title)
            t_lbl.setFont(QFont(self.font_family, 10))
            t_color = "#111318" if is_light else "#fffde7"
            t_lbl.setStyleSheet(f"color: {t_color}; background: transparent; border: none;")
            text_container.addWidget(t_lbl)

            from gui.ui_helpers import get_monospace_font
            sub_lbl = QLabel(subtitle)
            sub_lbl.setFont(get_monospace_font(8))
            sub_color = "#555e6d" if is_light else "rgba(255, 253, 231, 0.48)"
            sub_lbl.setStyleSheet(f"color: {sub_color}; background: transparent; border: none;")
            text_container.addWidget(sub_lbl)

            card_layout.addLayout(text_container, 1)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip("Удалить из профиля")
            if is_light:
                del_btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #7a8494;
                        border: none;
                        border-radius: 6px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: rgba(229, 57, 53, 0.14);
                        color: #e53935;
                    }
                """)
            else:
                del_btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #78735f;
                        border: none;
                        border-radius: 6px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 82, 82, 0.18);
                        color: #ff5252;
                    }
                """)
            del_btn.clicked.connect(lambda _, i=idx: self._remove_item(i))
            card_layout.addWidget(del_btn, 0, Qt.AlignmentFlag.AlignVCenter)

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
        import sys
        if sys.platform == "win32":
            file_filter = "Исполняемые файлы (*.exe *.lnk *.bat *.cmd);;Все файлы (*.*)"
        else:
            file_filter = "Программы и ярлыки (*.desktop *.sh *.AppImage);;Все файлы (*)"
        file_path = open_file_dialog(
            self,
            "Выбор программы",
            "",
            file_filter
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
        from gui.ui_helpers import handle_drag_press
        handle_drag_press(self, event)

    def mouseMoveEvent(self, event):
        from gui.ui_helpers import handle_drag_move
        handle_drag_move(self, event)

    def mouseReleaseEvent(self, event):
        from gui.ui_helpers import handle_drag_release
        handle_drag_release(self, event)

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
            pen = QPen(QColor("#78735f"), 1.4)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)