import os
import sys
import ctypes
import time
import re
import subprocess
import webbrowser
import psutil
import pyautogui
from core.utils.config import get_resource_path

VLC_DOWNLOAD_URL = "https://www.videolan.org/vlc/"


class VLCPlayer:
    def __init__(self):
        self.vlc_path = self._find_vlc()
        self.process = None

    def _find_vlc(self) -> str | None:
        # 1. Проверяем реестр Windows
        if sys.platform == "win32":
            try:
                import winreg
                reg_paths = [
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\vlc.exe"),
                    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\vlc.exe"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VideoLAN\VLC"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\VideoLAN\VLC"),
                    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\VideoLAN\VLC"),
                ]
                for root_key, subkey in reg_paths:
                    try:
                        with winreg.OpenKey(root_key, subkey) as k:
                            try:
                                val, _ = winreg.QueryValueEx(k, "")
                                if val and os.path.exists(val):
                                    return val
                            except Exception:
                                pass
                            try:
                                val, _ = winreg.QueryValueEx(k, "InstallDir")
                                if val:
                                    cand = os.path.join(val, "vlc.exe")
                                    if os.path.exists(cand):
                                        return cand
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

        # 2. Проверяем стандартные каталоги установки
        candidates = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(os.environ.get("ProgramW6432", "C:\\Program Files"), "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(os.environ.get("LocalAppData", ""), "Programs", "VideoLAN", "VLC", "vlc.exe")
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def is_available(self) -> bool:
        if not self.vlc_path or not os.path.exists(self.vlc_path):
            self.vlc_path = self._find_vlc()
        return self.vlc_path is not None

    def _get_installer_path(self) -> str:
        candidates = [
            get_resource_path("assets", "installers", "vlc_installer.exe"),
            get_resource_path("installers", "vlc_installer.exe"),
            get_resource_path("assets", "vlc_installer.exe")
        ]
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            candidates.extend([
                os.path.join(exe_dir, "_internal", "assets", "installers", "vlc_installer.exe"),
                os.path.join(exe_dir, "assets", "installers", "vlc_installer.exe"),
                os.path.join(exe_dir, "_internal", "vlc_installer.exe"),
                os.path.join(exe_dir, "vlc_installer.exe")
            ])
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return candidates[0]

    def install_silent(self) -> bool:
        installer = self._get_installer_path()
        if not os.path.exists(installer):
            print(f"[VLC Installer Warning]: Установщик не найден по пути: {installer}")
            return False
        try:
            print(f"[VLC Installer]: Запуск тихого установщика из {installer}...")
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                installer,
                "/S /L=1049",
                None,
                1
            )
            if ret > 32:
                for i in range(60):
                    time.sleep(1)
                    if self.is_available():
                        print(f"[VLC Installer]: VLC успешно установлен и готов к работе ({i + 1} сек.)")
                        return True
            else:
                print(f"[VLC Installer Error]: ShellExecute вернул код {ret}")
            return False
        except Exception as e:
            print(f"[VLC Installer Exception]: {e}")
            return False

    def open_download_page(self):
        webbrowser.open(VLC_DOWNLOAD_URL)

    def is_playing(self) -> bool:
        if self.process and self.process.poll() is None:
            return True
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == "vlc.exe":
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _focus_vlc(self):
        try:
            def enum_cb(hwnd, lparam):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    if "VLC" in buff.value:
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                        return False
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            time.sleep(0.04)
        except Exception:
            pass

    def play(self, stream_url: str, title: str = "") -> bool:
        if not self.is_available():
            return False
        try:
            cmd = [
                self.vlc_path,
                stream_url,
                "--fullscreen",
                "--network-caching=3000"
            ]
            if title and not stream_url.lower().endswith(".m3u"):
                clean_title = re.sub(r'[\/\\"]', ' ', title).strip()
                if clean_title:
                    cmd.append(f"--meta-title={clean_title}")

            self.process = subprocess.Popen(cmd)
            return True
        except Exception:
            return False

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == "vlc.exe":
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def toggle_pause(self):
        self._focus_vlc()
        pyautogui.press('space')

    def toggle_fullscreen(self):
        self._focus_vlc()
        pyautogui.press('f')

    def seek(self, direction: str = "forward", seconds: int = 10):
        self._focus_vlc()
        presses = max(1, round(seconds / 10))
        key = "right" if direction == "forward" else "left"
        for _ in range(presses):
            pyautogui.press(key)
            time.sleep(0.04)

    def next_episode(self):
        self._focus_vlc()
        pyautogui.press('n')

    def prev_episode(self):
        self._focus_vlc()
        pyautogui.press('p')

    def next_audio_track(self):
        self._focus_vlc()
        pyautogui.press('b')

    def toggle_subtitles(self):
        self._focus_vlc()
        pyautogui.press('v')

    def speed_up(self):
        self._focus_vlc()
        pyautogui.press(']')

    def speed_down(self):
        self._focus_vlc()
        pyautogui.press('[')

    def speed_normal(self):
        self._focus_vlc()
        pyautogui.press('=')


vlc_player = VLCPlayer()