import os
import sys
import ctypes
import time
import re
import subprocess
import webbrowser
import psutil
import pyautogui

VLC_DOWNLOAD_URL = "https://www.videolan.org/vlc/"


class VLCPlayer:
    def __init__(self):
        self.vlc_path = self._find_vlc()
        self.process = None

    def _find_vlc(self) -> str | None:
        candidates = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(os.environ.get("LocalAppData", ""), "Programs", "VideoLAN", "VLC", "vlc.exe")
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def is_available(self) -> bool:
        if not self.vlc_path or not os.path.exists(self.vlc_path):
            self.vlc_path = self._find_vlc()
        return self.vlc_path is not None

    def _get_installer_path(self) -> str:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, "assets", "installers", "vlc_installer.exe")

    def install_silent(self) -> bool:
        installer = self._get_installer_path()
        if not os.path.exists(installer):
            return False
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                installer,
                "/S /L=1049",
                None,
                1
            )
            if ret > 32:
                for _ in range(60):
                    time.sleep(1)
                    if self.is_available():
                        return True
            return False
        except Exception:
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