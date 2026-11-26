import os
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction, QIcon, QPixmap
from core.utils.config import get_resource_path


class SystemTray(QSystemTrayIcon):
    def __init__(self, window, app):
        ico_path = get_resource_path("assets", "icon", "ico", "akira_icon.ico")
        png_path = get_resource_path("assets", "icon", "png", "akira_icon.png")

        tray_icon = QIcon()
        if sys.platform == "win32":
            if os.path.exists(ico_path):
                tray_icon.addFile(ico_path)
            elif os.path.exists(png_path):
                tray_icon.addPixmap(QPixmap(png_path))
            else:
                tray_icon = app.windowIcon()
        else:
            if os.path.exists(png_path):
                tray_icon.addFile(png_path)
                tray_icon.addPixmap(QPixmap(png_path))
            elif os.path.exists(ico_path):
                tray_icon.addFile(ico_path)
            else:
                tray_icon = app.windowIcon()

            if tray_icon.isNull():
                tray_icon = app.windowIcon()

        super().__init__(tray_icon, parent=window)
        self.window = window
        self.app = app
        self.setToolTip("Акира")
        self.init_menu()

    def init_menu(self):
        menu = QMenu()

        show_action = QAction("Открыть окно", self)
        show_action.triggered.connect(self.show_window)
        menu.addAction(show_action)

        hide_action = QAction("Свернуть", self)
        hide_action.triggered.connect(self.hide_window)
        menu.addAction(hide_action)

        menu.addSeparator()

        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.window.exit_app)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self.on_tray_activated)

    def show_window(self):
        if hasattr(self.window, "setWindowOpacity") and not hasattr(self.window, "show_animated"):
            self.window.setWindowOpacity(1.0)
        self.window.setWindowState((self.window.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        if hasattr(self.window, "bring_to_front"):
            self.window.showNormal()
            self.window.bring_to_front()
        else:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()

    def hide_window(self):
        if hasattr(self.window, "close_animated"):
            self.window.close_animated()
        else:
            self.window.hide()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.window.isVisible() and not self.window.isMinimized() and (sys.platform != "win32" or self.window.isActiveWindow()):
                self.hide_window()
            else:
                self.show_window()
