from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QSize

class StudioFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StudioFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_theme = "dark"
        
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.placeholder_label = QLabel(
            "Студия\n\n"
            "Здесь будет просторный терминал с кодом,\n"
            "прикрепление файлов и селектор мощных моделей."
        )
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setWordWrap(True)
        self.placeholder_label.setMinimumWidth(0)
        self.placeholder_label.setStyleSheet(
            "color: #888; font-size: 15px; border: 2px dashed #555; border-radius: 12px; padding: 20px;"
        )
        layout.addWidget(self.placeholder_label)
        
    def set_theme(self, theme: str):
        self.current_theme = theme
        if theme == "light":
            self.placeholder_label.setStyleSheet(
                "color: #666; font-size: 15px; border: 2px dashed #bbb; border-radius: 12px; padding: 20px;"
            )
        else:
            self.placeholder_label.setStyleSheet(
                "color: #888; font-size: 15px; border: 2px dashed #555; border-radius: 12px; padding: 20px;"
            )
        self.update()

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def sizeHint(self) -> QSize:
        return QSize(0, 0)