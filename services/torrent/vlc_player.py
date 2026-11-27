import os
import sys
import time
import re
import shutil
import subprocess
import webbrowser
import psutil
from core.utils.config import get_resource_path, load_config, save_config
from core.utils.platform_utils import get_pyautogui, is_wayland, open_path

if sys.platform == "win32":
    import ctypes

VLC_DOWNLOAD_URL = "https://www.videolan.org/vlc/"
_MPRIS_VLC_SERVICE = "org.mpris.MediaPlayer2.vlc"
_MPRIS_OBJ_PATH = "/org/mpris/MediaPlayer2"


class VLCPlayer:
    def __init__(self):
        self.vlc_path = self._find_vlc()
        self.process = None

    def _get_vlc_config_dirs(self) -> list[str]:
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            return [os.path.join(appdata, "vlc")] if appdata else []
        xdg_cfg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        dirs = [os.path.join(xdg_cfg, "vlc")]
        if self.vlc_path == "flatpak:org.videolan.VLC":
            dirs.insert(0, os.path.expanduser("~/.var/app/org.videolan.VLC/config/vlc"))
        return dirs

    def setup_vlc_privacy_config(self):
        """Создает/обновляет конфигурацию vlcrc, отключая блокирующий диалог первого запуска."""
        try:
            cfg_dirs = self._get_vlc_config_dirs()
            if not cfg_dirs:
                return
            vlc_config_dir = cfg_dirs[0]
            os.makedirs(vlc_config_dir, exist_ok=True)
            vlcrc_path = os.path.join(vlc_config_dir, "vlcrc")
            if not os.path.exists(vlcrc_path):
                with open(vlcrc_path, "w", encoding="utf-8") as f:
                    f.write("[qt]\nqt-privacy-ask=0\nqt-updates-notif=0\n")
            else:
                with open(vlcrc_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if "qt-privacy-ask=0" not in content:
                    content = re.sub(r'#?\s*qt-privacy-ask=\d+', 'qt-privacy-ask=0', content)
                    if "qt-privacy-ask=0" not in content:
                        content += "\n[qt]\nqt-privacy-ask=0\n"
                    with open(vlcrc_path, "w", encoding="utf-8") as f:
                        f.write(content)
        except Exception:
            pass

    def mark_setup_done(self):
        """Фиксирует завершение первичной настройки в конфигурации."""
        try:
            cfg = load_config()
            cfg["vlc_setup_completed"] = True
            save_config(cfg)
        except Exception:
            pass

    def needs_initial_setup(self) -> bool:
        """Проверяет, требуется ли первичная настройка VLC пользователем (галочки политики сети)."""
        if sys.platform != "win32":
            self.setup_vlc_privacy_config()
            self.mark_setup_done()
            return False
        try:
            cfg = load_config()
            if cfg.get("vlc_setup_completed", False):
                return False

            for cfg_dir in self._get_vlc_config_dirs():
                vlcrc = os.path.join(cfg_dir, "vlcrc")
                # Если vlcrc уже существует и создан самим VLC (>500 байт), настройка уже была
                if os.path.exists(vlcrc) and os.path.getsize(vlcrc) > 500:
                    self.mark_setup_done()
                    return False
        except Exception:
            pass
        return True

    def _build_vlc_cmd(self, extra_args: list[str]) -> list[str]:
        if self.vlc_path == "flatpak:org.videolan.VLC":
            flatpak = shutil.which("flatpak") or "flatpak"
            return [flatpak, "run", "org.videolan.VLC", *extra_args]
        return [self.vlc_path, *extra_args]

    def open_for_setup(self) -> bool:
        """Открывает VLC Player для ручной первичной настройки пользователем (галочки сети/обновлений)."""
        if not self.is_available():
            return False
        try:
            self.mark_setup_done()
            kwargs = {"start_new_session": True} if sys.platform != "win32" else {}
            subprocess.Popen(self._build_vlc_cmd([]), **kwargs)
            return True
        except Exception:
            return False

    def _find_vlc(self) -> str | None:
        if sys.platform == "win32":
            # 1. Проверяем реестр Windows
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

            # 2. Проверяем стандартные каталоги установки Windows
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

        # Linux: PATH -> стандартные пути -> Snap -> Flatpak
        which_vlc = shutil.which("vlc")
        if which_vlc:
            return which_vlc

        for cand in ("/usr/bin/vlc", "/usr/local/bin/vlc", "/snap/bin/vlc"):
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand

        flatpak = shutil.which("flatpak")
        if flatpak:
            try:
                res = subprocess.run([flatpak, "info", "org.videolan.VLC"], capture_output=True, timeout=2.5)
                if res.returncode == 0:
                    return "flatpak:org.videolan.VLC"
            except Exception:
                pass
        return None

    def is_available(self) -> bool:
        if not self.vlc_path or (self.vlc_path != "flatpak:org.videolan.VLC" and not os.path.exists(self.vlc_path)):
            self.vlc_path = self._find_vlc()
        return self.vlc_path is not None

    def _get_installer_path(self) -> str:
        candidates = [
            get_resource_path("assets", "installers", "vlc_installer.exe"),
            get_resource_path("installers", "vlc_installer.exe"),
            get_resource_path("assets", "vlc_installer.exe")
        ]
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(os.path.realpath(sys.executable))
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

    def _install_linux(self) -> bool:
        pkexec = shutil.which("pkexec")
        apt_get = shutil.which("apt-get")
        if pkexec and apt_get:
            try:
                print("[VLC Installer]: Автоматическая установка VLC (vlc + libvlc5) через apt-get...")
                apt_script = (
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y vlc libvlc5 "
                    "|| (apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y vlc libvlc5)"
                )
                res = subprocess.run(
                    [pkexec, "sh", "-c", apt_script],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                self.vlc_path = self._find_vlc()
                if res.returncode == 0 and self.vlc_path:
                    self.setup_vlc_privacy_config()
                    self.mark_setup_done()
                    print("[VLC Installer]: VLC успешно установлен через APT!")
                    return True
            except Exception as e:
                print(f"[VLC Installer APT Warning]: {e}")

        flatpak = shutil.which("flatpak")
        if flatpak:
            for extra in (["--user"], []):
                try:
                    print("[VLC Installer]: Пробуем установку VLC через Flatpak...")
                    res = subprocess.run(
                        [flatpak, "install", "-y", "--noninteractive", *extra, "flathub", "org.videolan.VLC"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    self.vlc_path = self._find_vlc()
                    if res.returncode == 0 and self.vlc_path:
                        self.setup_vlc_privacy_config()
                        self.mark_setup_done()
                        print("[VLC Installer]: VLC успешно установлен через Flatpak!")
                        return True
                except Exception as e:
                    print(f"[VLC Installer Flatpak Warning]: {e}")

        snap = shutil.which("snap")
        if pkexec and snap:
            try:
                print("[VLC Installer]: Пробуем установку VLC через Snap...")
                res = subprocess.run([pkexec, snap, "install", "vlc"], capture_output=True, text=True, timeout=300)
                self.vlc_path = self._find_vlc()
                if res.returncode == 0 and self.vlc_path:
                    self.setup_vlc_privacy_config()
                    self.mark_setup_done()
                    return True
            except Exception as e:
                print(f"[VLC Installer Snap Warning]: {e}")

        return False

    def install_silent(self) -> bool:
        if sys.platform != "win32":
            return self._install_linux()

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
        if sys.platform == "win32":
            webbrowser.open(VLC_DOWNLOAD_URL)
        else:
            open_path(VLC_DOWNLOAD_URL)

    @staticmethod
    def _is_vlc_proc_name(name: str | None) -> bool:
        if not name:
            return False
        low = name.lower()
        if sys.platform == "win32":
            return low == "vlc.exe"
        return low in ("vlc", "vlc.bin")

    def is_playing(self) -> bool:
        if self.process and self.process.poll() is None:
            return True
        for proc in psutil.process_iter(['name']):
            try:
                if self._is_vlc_proc_name(proc.info['name']):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _mpris_call(self, member: str, *typed_args: str, iface: str = "org.mpris.MediaPlayer2.Player") -> bool:
        if sys.platform == "win32":
            return False
        dbus_send = shutil.which("dbus-send")
        if dbus_send:
            try:
                res = subprocess.run(
                    [
                        dbus_send,
                        "--session",
                        "--print-reply",
                        f"--dest={_MPRIS_VLC_SERVICE}",
                        _MPRIS_OBJ_PATH,
                        f"{iface}.{member}",
                        *typed_args,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                )
                if res.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    def _mpris_toggle_fullscreen(self) -> bool:
        if sys.platform == "win32":
            return False
        gdbus = shutil.which("gdbus")
        if not gdbus:
            return False
        try:
            res = subprocess.run(
                [
                    gdbus, "call", "--session",
                    "--dest", _MPRIS_VLC_SERVICE,
                    "--object-path", _MPRIS_OBJ_PATH,
                    "--method", "org.freedesktop.DBus.Properties.Get",
                    "org.mpris.MediaPlayer2", "Fullscreen",
                ],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res.returncode != 0:
                return False
            is_fs = "true" in res.stdout.lower()
            new_val = "false" if is_fs else "true"
            set_res = subprocess.run(
                [
                    gdbus, "call", "--session",
                    "--dest", _MPRIS_VLC_SERVICE,
                    "--object-path", _MPRIS_OBJ_PATH,
                    "--method", "org.freedesktop.DBus.Properties.Set",
                    "org.mpris.MediaPlayer2", "Fullscreen", f"<boolean {new_val}>",
                ],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            return set_res.returncode == 0
        except Exception:
            return False

    def _focus_vlc(self):
        if sys.platform == "win32":
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
            return

        if is_wayland() or not os.environ.get("DISPLAY"):
            return

        wmctrl = shutil.which("wmctrl")
        if wmctrl:
            try:
                if subprocess.run([wmctrl, "-a", "VLC"], capture_output=True, timeout=1.5).returncode == 0:
                    time.sleep(0.05)
                    return
            except Exception:
                pass

        xdotool = shutil.which("xdotool")
        if xdotool:
            try:
                res = subprocess.run(
                    [xdotool, "search", "--name", "VLC", "windowactivate"],
                    capture_output=True,
                    timeout=1.5,
                )
                if res.returncode == 0:
                    time.sleep(0.05)
                    return
            except Exception:
                pass

        try:
            from Xlib import X
            from Xlib.display import Display
            disp = Display()
            root = disp.screen().root
            atom_clients = disp.intern_atom("_NET_CLIENT_LIST")
            atom_active = disp.intern_atom("_NET_ACTIVE_WINDOW")
            prop = root.get_full_property(atom_clients, X.AnyPropertyType)
            if prop and prop.value:
                for wid in prop.value:
                    w = disp.create_resource_object("window", int(wid))
                    w_name = w.get_wm_name() or ""
                    if isinstance(w_name, bytes):
                        w_name = w_name.decode("utf-8", errors="ignore")
                    if "vlc" in w_name.lower():
                        w.set_input_focus(X.RevertToParent, X.CurrentTime)
                        disp.sync()
                        time.sleep(0.05)
                        break
            disp.close()
        except Exception:
            pass

    def play(self, stream_url: str, title: str = "") -> bool:
        if not self.is_available():
            return False
        try:
            self.setup_vlc_privacy_config()
            args = [
                stream_url,
                "--fullscreen",
                "--network-caching=2000",
                "--no-qt-privacy-ask",
                "--no-qt-error-dialogs",
            ]
            if sys.platform == "win32":
                args.append("--no-qt-updates-notif")
            if title and not stream_url.lower().endswith(".m3u"):
                clean_title = re.sub(r'[\/\\"]', ' ', title).strip()
                if clean_title:
                    args.append(f"--meta-title={clean_title}")

            cmd = self._build_vlc_cmd(args)
            kwargs = {"start_new_session": True} if sys.platform != "win32" else {}
            self.process = subprocess.Popen(cmd, **kwargs)
            return True
        except Exception:
            return False

    def stop(self):
        if sys.platform != "win32":
            self._mpris_call("Quit", iface="org.mpris.MediaPlayer2")

        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        for proc in psutil.process_iter(['name']):
            try:
                if self._is_vlc_proc_name(proc.info['name']):
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def toggle_pause(self):
        if sys.platform != "win32" and self._mpris_call("PlayPause"):
            return
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press('space')

    def toggle_fullscreen(self):
        if sys.platform != "win32" and self._mpris_toggle_fullscreen():
            return
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press('f')

    def seek(self, direction: str = "forward", seconds: int = 10):
        if sys.platform != "win32":
            offset_us = int(seconds) * 1_000_000 * (-1 if direction == "backward" else 1)
            if self._mpris_call("Seek", f"int64:{offset_us}"):
                return
        self._focus_vlc()
        pag = get_pyautogui()
        if not pag:
            return
        presses = max(1, round(seconds / 10))
        key = "right" if direction == "forward" else "left"
        for _ in range(presses):
            pag.press(key)
            time.sleep(0.04)

    def next_episode(self):
        if sys.platform != "win32" and self._mpris_call("Next"):
            return
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press('n')

    def prev_episode(self):
        if sys.platform != "win32" and self._mpris_call("Previous"):
            return
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press('p')

    def next_audio_track(self):
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press('b')

    def toggle_subtitles(self):
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press('v')

    def speed_up(self):
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press(']')

    def speed_down(self):
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press('[')

    def speed_normal(self):
        self._focus_vlc()
        pag = get_pyautogui()
        if pag:
            pag.press('=')


vlc_player = VLCPlayer()