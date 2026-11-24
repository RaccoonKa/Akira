import inspect

if not getattr(inspect.findsource, "_is_safe", False):
    _orig_findsource = inspect.findsource
    def _safe_findsource(obj):
        try:
            return _orig_findsource(obj)
        except Exception:
            return (["def stub():\n", "    pass\n"], 0)
    _safe_findsource._is_safe = True
    inspect.findsource = _safe_findsource

if not getattr(inspect.getsource, "_is_safe", False):
    _orig_getsource = inspect.getsource
    def _safe_getsource(obj):
        try:
            return _orig_getsource(obj)
        except Exception:
            return "def stub():\n    pass\n"
    _safe_getsource._is_safe = True
    inspect.getsource = _safe_getsource

import os
import sys

# Гарантируем корректное определение автономного / скомпилированного режима (Nuitka, PyInstaller и др.)
if getattr(sys, "frozen", False) or "__compiled__" in globals() or (
    sys.executable and not os.path.basename(sys.executable).lower().startswith("python")
):
    sys.frozen = True

# Автоматический запуск через .venv проекта, если скрипт запущен через глобальный Python в IDE
if not getattr(sys, "frozen", False) and "__compiled__" not in globals():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(base_dir, ".venv")
    venv_python = (
        os.path.join(venv_dir, "Scripts", "python.exe")
        if sys.platform == "win32"
        else os.path.join(venv_dir, "bin", "python")
    )
    in_project_venv = os.path.normcase(os.path.abspath(sys.prefix)) == os.path.normcase(os.path.abspath(venv_dir))
    if (
        os.path.isfile(venv_python)
        and not in_project_venv
        and os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(os.path.abspath(venv_python))
    ):
        import subprocess
        sys.exit(subprocess.call([venv_python] + sys.argv))

# Настройка переменных окружения до импорта тяжелых ML-библиотек
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

# Гарантируем, что папка приложения и _internal находятся в sys.path
app_dir = os.path.dirname(
    os.path.realpath(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
)
for p in (app_dir, os.path.join(app_dir, "_internal")):
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

# Приоритет стандартного файлового загрузчика (FileFinder) перед хуками Nuitka
# Это необходимо для правильной загрузки распакованных подмодулей внешних библиотек (websockets, torch и др.)
try:
    for _i, _h in enumerate(sys.path_hooks):
        if "FileFinder" in str(_h):
            sys.path_hooks.insert(0, sys.path_hooks.pop(_i))
            break
    sys.path_importer_cache.clear()
except Exception:
    pass

# Подключение библиотек PyTorch в standalone-режиме
torch_lib = os.path.join(app_dir, "torch", "lib")
if os.path.isdir(torch_lib):
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(torch_lib)
        except Exception:
            pass
        os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
    elif sys.platform != "win32":
        ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        if torch_lib not in ld_path.split(os.pathsep):
            os.environ["LD_LIBRARY_PATH"] = torch_lib + (os.pathsep + ld_path if ld_path else "")

# Безопасный fallback для проверки версий зависимостей (transformers dependency_versions_check)
try:
    import importlib.metadata
    if not getattr(importlib.metadata.version, "_is_safe", False):
        _orig_metadata_version = importlib.metadata.version
        def _safe_metadata_version(pkg_name: str) -> str:
            try:
                return _orig_metadata_version(pkg_name)
            except Exception:
                return "999.999.999"
        _safe_metadata_version._is_safe = True
        importlib.metadata.version = _safe_metadata_version
except Exception:
    pass

# Защита unittest и unittest.mock в standalone-сборках (требуется для PyTorch)
try:
    import unittest
    u_dir = os.path.join(app_dir, "unittest")
    if os.path.isdir(u_dir):
        if not hasattr(unittest, "__path__"):
            unittest.__path__ = [u_dir]
        elif u_dir not in unittest.__path__:
            unittest.__path__.append(u_dir)
    import unittest.mock
except Exception:
    pass

import types as _types_mod
if "unittest" not in sys.modules:
    sys.modules["unittest"] = _types_mod.ModuleType("unittest")
if not hasattr(sys.modules["unittest"], "TestCase"):
    sys.modules["unittest"].TestCase = type("TestCase", (), {})

if "unittest.mock" not in sys.modules:
    _mock_loaded = False
    _mock_file = os.path.join(app_dir, "unittest", "mock.py")
    if os.path.isfile(_mock_file):
        try:
            import importlib.util
            _spec = importlib.util.spec_from_file_location("unittest.mock", _mock_file)
            if _spec and _spec.loader:
                _mock_mod = importlib.util.module_from_spec(_spec)
                sys.modules["unittest.mock"] = _mock_mod
                sys.modules["unittest"].mock = _mock_mod
                _spec.loader.exec_module(_mock_mod)
                _mock_loaded = True
        except Exception:
            _mock_loaded = False
    if not _mock_loaded:
        _dummy_mock = _types_mod.ModuleType("unittest.mock")
        _dummy_mock.patch = lambda *args, **kwargs: (lambda f: f)
        class _DummyMockObj:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def __getattr__(self, name): return self
        _dummy_mock.patch.object = lambda *args, **kwargs: _DummyMockObj()
        _dummy_mock.Mock = _DummyMockObj
        _dummy_mock.MagicMock = _DummyMockObj
        _dummy_mock.AsyncMock = _DummyMockObj
        _dummy_mock.NonCallableMock = _DummyMockObj
        sys.modules["unittest.mock"] = _dummy_mock
        sys.modules["unittest"].mock = _dummy_mock
else:
    if not hasattr(sys.modules["unittest"], "mock"):
        sys.modules["unittest"].mock = sys.modules["unittest.mock"]

# Предварительная инициализация PyTorch для исключения циклических импортов в подмодулях
try:
    import torch
except Exception:
    pass

# Мост для устаревших путей импорта модулей (core.nlp.asr_corrector)
if "core.nlp.asr_corrector" not in sys.modules:
    class _LazyASRCorrector:
        def __init__(self, *args, **kwargs):
            self._inst = None
        def __getattr__(self, name):
            if self._inst is None:
                from core.nlp.speech.asr_corrector import ASRCorrector
                self._inst = ASRCorrector()
            return getattr(self._inst, name)
        def correct(self, text):
            try:
                from core.nlp.speech.asr_corrector import ASRCorrector
                if self._inst is None:
                    self._inst = ASRCorrector()
                return self._inst.correct(text)
            except Exception:
                return text

    _dummy_asr_mod = _types_mod.ModuleType("core.nlp.asr_corrector")
    _dummy_asr_mod.ASRCorrector = _LazyASRCorrector
    sys.modules['core.nlp.asr_corrector'] = _dummy_asr_mod

# Логирование критических ошибок запуска в crash.log и нативное диалоговое окно ошибки
def _global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    import traceback
    err_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        from datetime import datetime
        from core.utils.platform_utils import get_default_user_data_dir
        crash_log_path = os.path.join(get_default_user_data_dir(), "crash.log")
        os.makedirs(os.path.dirname(crash_log_path), exist_ok=True)
        with open(crash_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now()}] CRITICAL STARTUP ERROR:\n{err_text}\n")
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Ошибка запуска Akira:\n\n{err_text[:1200]}", "Akira Error", 0x10)
        except Exception:
            pass
    else:
        shown = False
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                QMessageBox.critical(None, "Akira Error", f"Ошибка запуска Akira:\n\n{err_text[:1200]}")
                shown = True
        except Exception:
            pass
        if not shown:
            try:
                import shutil
                import subprocess
                zenity_exe = shutil.which("zenity")
                kdialog_exe = shutil.which("kdialog")
                if zenity_exe:
                    subprocess.Popen(
                        [zenity_exe, "--error", "--title=Akira Error", f"--text=Ошибка запуска Akira:\n\n{err_text[:800]}"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif kdialog_exe:
                    subprocess.Popen(
                        [kdialog_exe, "--error", f"Ошибка запуска Akira:\n\n{err_text[:800]}", "--title", "Akira Error"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
            except Exception:
                pass
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = _global_exception_handler

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import ctypes
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

def _qt_message_handler(msg_type, context, message):
    # Подавляем диагностические сообщения завершения QThreadStorage
    if "QThreadStorage" in message:
        return
    if "qt.qpa" in getattr(context, "category", ""):
        return
    if msg_type == QtMsgType.QtFatalMsg:
        print(f"[Qt Fatal]: {message}", file=sys.stderr)
    elif msg_type == QtMsgType.QtCriticalMsg:
        print(f"[Qt Critical]: {message}", file=sys.stderr)

qInstallMessageHandler(_qt_message_handler)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from core.utils.config import load_config, get_resource_path
from gui.windows.chat_window import MainWindow
from gui.components.tray import SystemTray
from gui.dialogs.onboarding_wizard import OnboardingWizard

def get_app_icon_path():
    if sys.platform == "win32":
        candidates = [
            get_resource_path("assets", "icon", "ico", "akira_icon.ico"),
            get_resource_path("assets", "icon", "icon.ico"),
            get_resource_path("assets", "icon", "png", "akira_icon.png"),
        ]
    else:
        candidates = [
            get_resource_path("assets", "icon", "png", "akira_icon.png"),
            get_resource_path("assets", "icon", "ico", "akira_icon.ico"),
        ]
    for cand in candidates:
        if cand and os.path.exists(cand):
            return os.path.abspath(cand)
    return ""

def get_ico_path():
    return get_app_icon_path()

def apply_native_windows_icon(hwnd, icon_path):
    if sys.platform != "win32" or not icon_path or not os.path.exists(icon_path):
        return

    wm_seticon = 0x0080
    icon_small = 0
    icon_big = 1
    image_icon = 1
    lr_loadfromfile = 0x00000010
    gclp_hicon = -14
    gclp_hiconsm = -34

    h_icon_big = ctypes.windll.user32.LoadImageW(
        None, icon_path, image_icon, 48, 48, lr_loadfromfile
    )
    h_icon_small = ctypes.windll.user32.LoadImageW(
        None, icon_path, image_icon, 32, 32, lr_loadfromfile
    )

    if h_icon_big:
        ctypes.windll.user32.SendMessageW(hwnd, wm_seticon, icon_big, h_icon_big)
        try:
            ctypes.windll.user32.SetClassLongPtrW(hwnd, gclp_hicon, h_icon_big)
        except AttributeError:
            ctypes.windll.user32.SetClassLongW(hwnd, gclp_hicon, h_icon_big)

    if h_icon_small:
        ctypes.windll.user32.SendMessageW(hwnd, wm_seticon, icon_small, h_icon_small)
        try:
            ctypes.windll.user32.SetClassLongPtrW(hwnd, gclp_hiconsm, h_icon_small)
        except AttributeError:
            ctypes.windll.user32.SetClassLongW(hwnd, gclp_hiconsm, h_icon_small)

def _sanitize_linux_qt_env():
    """Убирает переопределения Qt5-путей от OpenCV (cv2/qt), мешающие PyQt6."""
    if sys.platform == "win32":
        return
    for var in ("QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_FONTDIR", "QT_PLUGIN_PATH"):
        val = os.environ.get(var, "")
        if "cv2" in val.replace("\\", "/").split("/") or "cv2/qt" in val.replace("\\", "/"):
            os.environ.pop(var, None)


def _check_linux_qt_x11_prereqs():
    """Проверяет наличие системной libxcb-cursor.so.0 до вызова QApplication на X11."""
    if not sys.platform.startswith("linux"):
        return
    qpa = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
    if qpa in ("offscreen", "minimal", "wayland", "wayland-egl", "linuxfb", "eglfs", "vnc"):
        return
    try:
        from core.utils.platform_utils import is_wayland
        if is_wayland():
            return
    except Exception:
        pass

    try:
        ctypes.CDLL("libxcb-cursor.so.0")
    except OSError:
        msg = (
            "Не найдена системная библиотека libxcb-cursor.so.0 (требуется для PyQt6 6.5+ на X11).\n\n"
            "Установите её в терминале Linux Mint / Ubuntu командой:\n"
            "sudo apt update && sudo apt install -y libxcb-cursor0 vlc libvlc5 xdotool scrot"
        )
        print(f"[Startup Error]: {msg}", file=sys.stderr, flush=True)
        try:
            import shutil
            import subprocess
            zenity_exe = shutil.which("zenity")
            kdialog_exe = shutil.which("kdialog")
            if zenity_exe:
                subprocess.Popen([zenity_exe, "--error", "--title=Akira — не хватает пакетов", f"--text={msg}"])
            elif kdialog_exe:
                subprocess.Popen([kdialog_exe, "--error", msg, "--title", "Akira — не хватает пакетов"])
        except Exception:
            pass
        sys.exit(1)


def main():
    if sys.platform == "win32":
        myappid = 'svetozar.akira.voiceassistant.5.0.0'
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
    else:
        _sanitize_linux_qt_env()
        _check_linux_qt_x11_prereqs()

    app = QApplication(sys.argv)
    app.setApplicationName("Akira")
    app.setApplicationDisplayName("Akira")
    if sys.platform != "win32" and hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName("akira")
    app.setQuitOnLastWindowClosed(False)

    server_name = "AkiraVoiceAssistant_SingleInstance_IPC"
    client_socket = QLocalSocket()
    client_socket.connectToServer(server_name)

    if client_socket.waitForConnected(400):
        client_socket.write(b"RESTORE")
        client_socket.waitForBytesWritten(400)
        client_socket.disconnectFromServer()
        sys.exit(0)

    server = QLocalServer()
    server.removeServer(server_name)
    server.listen(server_name)

    ico_path = get_app_icon_path()
    app_icon = QIcon(ico_path) if ico_path else QIcon()
    app.setWindowIcon(app_icon)

    config = load_config()

    is_first_run = config.get("first_run", True) and not config.get("is_configured", False)
    if is_first_run:
        wizard = OnboardingWizard(config)
        wizard.setWindowTitle("Akira")
        wizard.setWindowIcon(app_icon)

        if sys.platform == "win32":
            wizard_hwnd = int(wizard.winId())
            apply_native_windows_icon(wizard_hwnd, ico_path)

        wizard.exec()
        config = load_config()

    window = MainWindow(config)
    window.setWindowTitle("Akira")
    window.setWindowIcon(app_icon)

    def handle_second_instance():
        conn = server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(lambda: conn.readAll())
            window.bring_to_front()
    server.newConnection.connect(handle_second_instance)

    if sys.platform == "win32":
        hwnd = int(window.winId())
        apply_native_windows_icon(hwnd, ico_path)

    window.show()
    window.bring_to_front()
    if sys.platform == "win32":
        hwnd = int(window.winId())
        apply_native_windows_icon(hwnd, ico_path)

    tray = SystemTray(window, app)
    tray.show()

    app.aboutToQuit.connect(window.shutdown)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()