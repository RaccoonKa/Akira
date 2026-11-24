"""
Кроссплатформенные базовые утилиты для Windows и Linux (Linux Mint Cinnamon).
Минимальный набор без тяжёлых зависимостей для предотвращения циклических импортов.
"""

import os
import sys
import shutil
import subprocess
import webbrowser

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

_PYAUTOGUI_UNSET = object()
_pyautogui_cache = _PYAUTOGUI_UNSET


def is_wayland() -> bool:
    """Возвращает True, если текущая сессия Linux работает под Wayland."""
    if not IS_LINUX:
        return False
    session_type = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
    if session_type == "wayland":
        return True
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    return False


def get_default_user_data_dir(*subpaths: str) -> str:
    """
    Возвращает стандартный системный каталог пользовательских данных приложения:
    - Windows: %APPDATA%\\Akira (без изменений относительно исторического поведения)
    - Linux: $XDG_DATA_HOME/Akira (по умолчанию ~/.local/share/Akira)
    """
    if IS_WINDOWS:
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base_dir = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base_dir, "Akira", *subpaths) if subpaths else os.path.join(base_dir, "Akira")


def subprocess_no_window_kwargs() -> dict:
    """Возвращает платформенные аргументы для скрытого запуска фонового процесса без окна консоли."""
    if IS_WINDOWS:
        kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
        return kwargs
    return {}


def get_pyautogui():
    """
    Безопасный ленивый импорт pyautogui.
    На Linux при отсутствии X11 DISPLAY (или под чистым Wayland/headless) импорт pyautogui
    выбрасывает KeyError('DISPLAY') — перехватываем это и возвращаем None вместо падения модуля.
    """
    global _pyautogui_cache
    if _pyautogui_cache is not _PYAUTOGUI_UNSET:
        return _pyautogui_cache

    if IS_LINUX and not os.environ.get("DISPLAY"):
        _pyautogui_cache = None
        return None

    try:
        import pyautogui as _pag
        _pag.FAILSAFE = False
        _pyautogui_cache = _pag
    except Exception:
        _pyautogui_cache = None
    return _pyautogui_cache


def open_path(target: str) -> bool:
    """Кроссплатформенное открытие файла, директории, ярлыка или URI в приложении по умолчанию."""
    if not target:
        return False

    if IS_WINDOWS:
        try:
            os.startfile(target)
            return True
        except Exception:
            pass
        if target.startswith(("http://", "https://")):
            return webbrowser.open(target)
        return False

    # Linux: xdg-open / gio open
    for launcher in ("xdg-open", "gio"):
        exe = shutil.which(launcher)
        if not exe:
            continue
        cmd = [exe, "open", target] if launcher == "gio" else [exe, target]
        try:
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            continue

    if target.startswith(("http://", "https://")):
        try:
            return webbrowser.open(target)
        except Exception:
            pass
    return False


def get_system_timezone_name() -> str | None:
    """
    Возвращает имя системной таймзоны:
    - Windows: TimeZoneKeyName из реестра.
    - Linux: IANA-идентификатор вида Europe/Moscow (/etc/localtime, /etc/timezone, timedatectl).
    """
    if IS_WINDOWS:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation")
            tz_name, _ = winreg.QueryValueEx(key, "TimeZoneKeyName")
            winreg.CloseKey(key)
            return str(tz_name).strip() if tz_name else None
        except Exception:
            return None

    # Linux: 1) /etc/localtime -> .../zoneinfo/<Area/City>
    try:
        if os.path.exists("/etc/localtime"):
            resolved = os.path.realpath("/etc/localtime")
            marker = "/zoneinfo/"
            if marker in resolved:
                tz = resolved.split(marker, 1)[1].strip()
                if tz:
                    return tz
    except Exception:
        pass

    # Linux: 2) /etc/timezone (используется в Debian / Ubuntu / Linux Mint)
    try:
        if os.path.isfile("/etc/timezone"):
            with open("/etc/timezone", "r", encoding="utf-8") as f:
                tz = f.read().strip()
            if tz:
                return tz
    except Exception:
        pass

    # Linux: 3) timedatectl show
    timedatectl = shutil.which("timedatectl")
    if timedatectl:
        try:
            res = subprocess.run(
                [timedatectl, "show", "--property=Timezone", "--value"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    return None


def _pil_from_qpixmap(pixmap):
    """Конвертирует QPixmap в PIL.Image.Image без сохранения промежуточного файла на диск."""
    from io import BytesIO
    from PIL import Image
    from PyQt6.QtCore import QBuffer, QIODevice

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.ReadWrite)
    pixmap.save(buf, "PNG")
    raw = bytes(buf.data())
    buf.close()
    return Image.open(BytesIO(raw)).convert("RGB")


def take_screenshot_pil(bbox: tuple[int, int, int, int] | None = None):
    """
    Кроссплатформенный захват экрана (или области bbox=(left, top, right, bottom)) в PIL.Image.Image.
    - Windows: PIL.ImageGrab.grab
    - Linux: mss (X11) -> ImageGrab (X11) -> Qt6 QScreen.grabWindow -> CLI (scrot / gnome-screenshot / grim)
    """
    from PIL import Image, ImageGrab

    if IS_WINDOWS:
        return ImageGrab.grab(bbox=bbox)

    # Linux 1: mss (быстрый захват X11 без subprocess)
    if not is_wayland() and os.environ.get("DISPLAY"):
        try:
            import mss
            with mss.mss() as sct:
                if bbox is not None:
                    left, top, right, bottom = [int(v) for v in bbox]
                    region = {
                        "left": left,
                        "top": top,
                        "width": max(1, right - left),
                        "height": max(1, bottom - top),
                    }
                else:
                    region = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                shot = sct.grab(region)
                return Image.frombytes("RGB", shot.size, shot.rgb)
        except Exception:
            pass

    # Linux 2: Pillow ImageGrab (Xlib backend)
    if os.environ.get("DISPLAY"):
        try:
            return ImageGrab.grab(bbox=bbox)
        except Exception:
            pass

    # Linux 3: Qt6 QScreen.grabWindow (если QGuiApplication уже запущен)
    try:
        from PyQt6.QtGui import QGuiApplication
        if QGuiApplication.instance() is not None:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                pixmap = screen.grabWindow(0)
                if not pixmap.isNull():
                    img = _pil_from_qpixmap(pixmap)
                    return img.crop(bbox) if bbox is not None else img
    except Exception:
        pass

    # Linux 4: внешние утилиты (scrot / gnome-screenshot / grim)
    import tempfile
    cli_candidates = (
        [("grim", lambda p: ["grim", p])]
        if is_wayland()
        else [
            ("scrot", lambda p: ["scrot", "-z", p]),
            ("gnome-screenshot", lambda p: ["gnome-screenshot", "-f", p]),
            ("import", lambda p: ["import", "-window", "root", p]),
        ]
    )
    for tool_name, cmd_builder in cli_candidates:
        exe = shutil.which(tool_name)
        if not exe:
            continue
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(prefix="akira_shot_", suffix=".png")
            os.close(fd)
            cmd = cmd_builder(tmp_path)
            cmd[0] = exe
            res = subprocess.run(cmd, capture_output=True, timeout=5.0)
            if res.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                with Image.open(tmp_path) as im:
                    img = im.convert("RGB")
                return img.crop(bbox) if bbox is not None else img
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    raise RuntimeError("Не удалось сделать снимок экрана на текущей графической сессии Linux")


def open_video_capture(camera_index: int = 0):
    """
    Кроссплатформенно открывает камеру OpenCV:
    - Windows: DirectShow (cv2.CAP_DSHOW)
    - Linux: Video4Linux2 (cv2.CAP_V4L2) с откатом на cv2.CAP_ANY
    """
    import cv2

    if IS_WINDOWS:
        return cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

    cap = cv2.VideoCapture(camera_index, getattr(cv2, "CAP_V4L2", cv2.CAP_ANY))
    if cap is not None and cap.isOpened():
        return cap
    try:
        if cap is not None:
            cap.release()
    except Exception:
        pass
    return cv2.VideoCapture(camera_index, cv2.CAP_ANY)


def ensure_pkg_resources_shim():
    """
    Обеспечивает наличие `pkg_resources.resource_filename` в Python 3.12+ / Nuitka
    для старых пакетов вроде face_recognition_models, если setuptools не установлен.
    """
    if "pkg_resources" in sys.modules:
        return
    try:
        import pkg_resources  # noqa: F401
        return
    except ImportError:
        pass

    import importlib.util
    import types

    shim = types.ModuleType("pkg_resources")

    def _resource_filename(package_or_requirement: str, resource_name: str) -> str:
        pkg_name = str(package_or_requirement).split(";")[0].split(">")[0].split("<")[0].split("=")[0].strip()
        spec = importlib.util.find_spec(pkg_name)
        base_dir = ""
        if spec is not None:
            if spec.origin:
                base_dir = os.path.dirname(spec.origin)
            elif spec.submodule_search_locations:
                base_dir = list(spec.submodule_search_locations)[0]
        return os.path.join(base_dir, resource_name) if base_dir else resource_name

    shim.resource_filename = _resource_filename
    sys.modules["pkg_resources"] = shim
