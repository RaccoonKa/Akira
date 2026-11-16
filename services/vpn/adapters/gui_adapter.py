import os
import sys
import time
import subprocess
import ctypes
from ctypes import wintypes
import psutil
import cv2
import numpy as np
from PIL import ImageGrab
import pyautogui
import winreg
import shutil

from core.utils.config import get_resource_path

pyautogui.FAILSAFE = False


class GuiAdapter:
    def __init__(self):
        cand_list = [
            get_resource_path("services", "vpn", "templates"),
            get_resource_path("templates")
        ]
        if getattr(sys, 'frozen', False):
            base_app = os.path.dirname(sys.executable)
            cand_list.extend([
                os.path.join(base_app, "_internal", "services", "vpn", "templates"),
                os.path.join(base_app, "services", "vpn", "templates"),
                os.path.join(base_app, "_internal", "templates"),
                os.path.join(base_app, "templates"),
            ])
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cand_list.append(os.path.join(self.base_dir, "templates"))

        self.templates_dir = cand_list[0]
        for c in cand_list:
            if c and os.path.exists(c):
                self.templates_dir = c
                break

        self._cached_sota_target = None
        self._cached_happ_target = None
        self._cached_browsec_target = None

    def _get_system_scale(self) -> int:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            return int(round(dpi / 96.0 * 100))
        except Exception:
            return 100

    def _get_closest_scale_folder(self) -> str:
        if not os.path.exists(self.templates_dir):
            return "100"

        available_scales = []
        for entry in os.listdir(self.templates_dir):
            full_path = os.path.join(self.templates_dir, entry)
            if os.path.isdir(full_path) and entry.isdigit():
                available_scales.append(int(entry))

        if not available_scales:
            return "100"

        current_scale = self._get_system_scale()
        closest = min(available_scales, key=lambda s: abs(s - current_scale))
        return str(closest)

    def _collect_template_paths(self, app_name: str, subfolder: str = "") -> list:
        scale_folder = self._get_closest_scale_folder()
        candidates = []

        # 1. Поиск по системному масштабу (100, 125...)
        d1 = os.path.join(self.templates_dir, scale_folder, app_name)
        if subfolder:
            d1 = os.path.join(d1, subfolder)
        candidates.append(d1)

        # 2. Прямой поиск в templates/<app_name>/...
        d2 = os.path.join(self.templates_dir, app_name)
        if subfolder:
            d2 = os.path.join(d2, subfolder)
        candidates.append(d2)

        template_paths = []
        for c_dir in candidates:
            if os.path.exists(c_dir):
                for root, _, files in os.walk(c_dir):
                    for file in files:
                        if file.lower().endswith(".png"):
                            template_paths.append(os.path.join(root, file))
            if template_paths:
                break

        return template_paths

    def _find_best_match(self, template_paths: list, hwnd: int = 0, threshold: float = 0.78, bottom_only: bool = False):
        if not template_paths:
            return None

        offset_x, offset_y = 0, 0
        grab_success = False
        screen = None

        if hwnd and ctypes.windll.user32.IsWindow(hwnd):
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 100 and h > 100 and rect.left > -10000:
                try:
                    if bottom_only:
                        top_bound = rect.bottom - int(h * 0.28)
                        bbox = (rect.left, top_bound, rect.right, rect.bottom)
                        offset_x, offset_y = rect.left, top_bound
                    else:
                        bbox = (rect.left, rect.top, rect.right, rect.bottom)
                        offset_x, offset_y = rect.left, rect.top

                    screen = np.array(ImageGrab.grab(bbox=bbox))
                    grab_success = True
                except Exception:
                    grab_success = False

        if not grab_success or screen is None:
            screen = np.array(ImageGrab.grab())
            offset_x, offset_y = 0, 0

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)

        best_score = -1.0
        best_coords = None

        for tpl_path in template_paths:
            template = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue

            th, tw = template.shape[:2]
            if screen_gray.shape[0] < th or screen_gray.shape[1] < tw:
                continue

            res = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_score:
                best_score = max_val
                best_coords = (offset_x + max_loc[0] + tw // 2, offset_y + max_loc[1] + th // 2)

        if best_score >= threshold and best_coords is not None:
            return best_coords

        return None

    def _safe_click(self, x, y):
        """Безопасный клик с задержкой, чтобы избежать ложных двойных кликов во Flutter"""
        pyautogui.mouseDown(x, y)
        time.sleep(0.08)
        pyautogui.mouseUp(x, y)

    def click_app_toggle(self, app_name: str, hwnd: int = 0, retries: int = 8, delay: float = 0.15,
                         threshold: float = 0.78, bottom_only: bool = False) -> bool:
        template_paths = self._collect_template_paths(app_name)
        if not template_paths:
            return False

        for _ in range(retries):
            coords = self._find_best_match(template_paths, hwnd=hwnd, threshold=threshold, bottom_only=bottom_only)
            if coords:
                self._safe_click(coords[0], coords[1])
                time.sleep(0.2)
                return True
            time.sleep(delay)

        return False

    def _get_window_hwnd(self, title_keywords: list, process_names: list = None) -> int:
        candidates = []

        def enum_windows_proc(hwnd, extra):
            if not ctypes.windll.user32.IsWindow(hwnd):
                return True

            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            window_title = buff.value.strip().lower()

            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            class_buff = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, class_buff, 256)
            class_name = class_buff.value.strip()

            is_visible = bool(ctypes.windll.user32.IsWindowVisible(hwnd))
            is_iconic = bool(ctypes.windll.user32.IsIconic(hwnd))

            title_matched = any(kw.lower() in window_title for kw in title_keywords) if title_keywords else False
            proc_matched = False
            if process_names:
                lpdw_pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
                try:
                    p = psutil.Process(lpdw_pid.value)
                    p_name = (p.name() or "").lower()
                    if any(pn.lower() in p_name for pn in process_names):
                        proc_matched = True
                except Exception:
                    pass

            if title_matched or proc_matched:
                score = 0
                if title_matched:
                    score += 50
                if class_name == "Chrome_WidgetWin_1":
                    score += 40
                elif "Chrome_WidgetWin" in class_name:
                    score += 20
                if is_visible:
                    score += 20
                if is_iconic:
                    score += 15
                if w > 150 and h > 150 and rect.left > -10000:
                    score += 30
                if length > 0:
                    score += 20
                candidates.append((score, hwnd))

            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return 0

    def _show_and_focus(self, hwnd: int):
        if not hwnd or not ctypes.windll.user32.IsWindow(hwnd):
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 1. Если окно свернуто, восстанавливаем
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            user32.ShowWindow(hwnd, 5)  # SW_SHOW
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE

        # 2. Обход Windows Foreground Lock через виртуальный Alt и AttachThreadInput
        # Сначала гарантируем отпускание клавиши Alt на случай залипания
        user32.keybd_event(0x12, 0, 2, 0)  # KEYEVENTF_KEYUP
        time.sleep(0.02)
        user32.keybd_event(0x12, 0, 0, 0)  # KEYEVENTF_KEYDOWN
        time.sleep(0.02)
        user32.keybd_event(0x12, 0, 2, 0)  # KEYEVENTF_KEYUP
        time.sleep(0.02)

        fore_hwnd = user32.GetForegroundWindow()
        cur_thread = kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None) if fore_hwnd else 0

        attached_fore = False
        attached_target = False

        if fore_thread and fore_thread != cur_thread:
            attached_fore = bool(user32.AttachThreadInput(cur_thread, fore_thread, True))
        if target_thread and target_thread != cur_thread:
            attached_target = bool(user32.AttachThreadInput(cur_thread, target_thread, True))

        user32.BringWindowToTop(hwnd)
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.ShowWindowAsync(hwnd, 9)

        if attached_target:
            user32.AttachThreadInput(cur_thread, target_thread, False)
        if attached_fore:
            user32.AttachThreadInput(cur_thread, fore_thread, False)

        # Всегда гарантированно отпускаем Alt
        user32.keybd_event(0x12, 0, 2, 0)
        time.sleep(0.1)

    def _minimize(self, hwnd: int):
        if hwnd and ctypes.windll.user32.IsWindow(hwnd):
            time.sleep(0.2)
            ctypes.windll.user32.ShowWindow(hwnd, 6)

    def _get_path_from_uninstall_registry(self, target_name: str) -> str:
        paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        ]
        for hkey, path in paths:
            try:
                with winreg.OpenKey(hkey, path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if target_name.lower() in display_name.lower():
                                    try:
                                        install_loc, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                        if install_loc:
                                            exe_path = os.path.join(install_loc, f"{target_name}.exe")
                                            if os.path.exists(exe_path):
                                                return exe_path
                                    except OSError:
                                        pass
                                    try:
                                        display_icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                        if display_icon:
                                            clean_path = display_icon.strip('"').split(',')[0]
                                            if clean_path.lower().endswith(".exe") and os.path.exists(clean_path):
                                                return clean_path
                                    except OSError:
                                        pass
                        except OSError:
                            continue
            except OSError:
                continue
        return ""

    def _get_path_from_protocol_registry(self, protocol_name: str) -> str:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{protocol_name}\shell\open\command") as key:
                cmd, _ = winreg.QueryValueEx(key, "")
                import re
                match = re.search(r'"([^"]+\.exe)"', cmd, re.IGNORECASE)
                if match and os.path.exists(match.group(1)):
                    return match.group(1)
        except Exception:
            pass
        return ""

    def _find_target_executable(self, exact_name: str, name_keywords: list) -> str:
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                p_name = (proc.info.get('name') or '').lower()
                if p_name == exact_name.lower():
                    exe_path = proc.info.get('exe')
                    if exe_path and os.path.exists(exe_path):
                        return exe_path
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("PROGRAMFILES", "")
        prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")
        user_profile = os.environ.get("USERPROFILE", "")
        public_profile = os.environ.get("PUBLIC", r"C:\Users\Public")

        shortcut_dirs = [
            os.path.join(user_profile, "Desktop"),
            os.path.join(public_profile, "Desktop")
        ]

        for s_dir in shortcut_dirs:
            if os.path.exists(s_dir):
                for root, _, files in os.walk(s_dir):
                    for f in files:
                        f_low = f.lower()
                        if any(kw in f_low for kw in name_keywords) and f_low.endswith(".lnk"):
                            return os.path.join(root, f)

        search_roots = [
            os.path.join(localappdata, "Programs"),
            localappdata,
            appdata,
            prog_files,
            prog_files_x86
        ]

        for s_root in search_roots:
            if not s_root or not os.path.exists(s_root):
                continue
            try:
                entries = os.listdir(s_root)
            except Exception:
                continue

            for entry in entries:
                entry_low = entry.lower()
                if any(kw in entry_low for kw in name_keywords):
                    full_entry_dir = os.path.join(s_root, entry)
                    if os.path.isdir(full_entry_dir):
                        try:
                            for root, _, files in os.walk(full_entry_dir):
                                for f in files:
                                    if f.lower() == exact_name.lower():
                                        return os.path.join(root, f)
                        except Exception:
                            pass

        return ""

    def _find_sota_target(self) -> str:
        if self._cached_sota_target and os.path.exists(self._cached_sota_target):
            return self._cached_sota_target

        reg_path = self._get_path_from_uninstall_registry("Sota") or self._get_path_from_protocol_registry("sota")
        if reg_path:
            self._cached_sota_target = reg_path
            return reg_path

        target = self._find_target_executable("sota connect.exe", ["sota", "interhive"])
        if not target:
            target = self._find_target_executable("sota.exe", ["sota", "interhive"])

        if not target:
            target = shutil.which("sota connect.exe") or shutil.which("sota.exe")

        if target:
            self._cached_sota_target = target
        return target or ""

    def _find_happ_target(self) -> str:
        if self._cached_happ_target and os.path.exists(self._cached_happ_target):
            return self._cached_happ_target

        reg_path = self._get_path_from_uninstall_registry("Happ") or self._get_path_from_protocol_registry("happ")
        if reg_path:
            self._cached_happ_target = reg_path
            return reg_path

        target = self._find_target_executable("happ.exe", ["happ", "хапп"])

        if not target:
            target = shutil.which("happ.exe")

        if target:
            self._cached_happ_target = target
        return target or ""

    def _find_browsec_target(self) -> str:
        if self._cached_browsec_target and os.path.exists(self._cached_browsec_target):
            return self._cached_browsec_target

        reg_path = self._get_path_from_uninstall_registry("Browsec") or self._get_path_from_protocol_registry("browsec")
        if reg_path:
            self._cached_browsec_target = reg_path
            return reg_path

        # 1. Проверяем стандартную папку установки Electron
        localappdata = os.environ.get("LOCALAPPDATA", "")
        std_electron_path = os.path.join(localappdata, "Programs", "browsec-desktop", "Browsec.exe")
        if os.path.exists(std_electron_path):
            self._cached_browsec_target = std_electron_path
            return std_electron_path

        # 2. Ищем по процессам и стандартным каталогам
        target = self._find_target_executable("Browsec.exe", ["browsec", "browsec-desktop"])
        if not target:
            target = self._find_target_executable("browsec.exe", ["browsec", "browsec-desktop"])

        # 3. Проверяем ярлык в меню Пуск
        if not target:
            appdata = os.environ.get("APPDATA", "")
            lnk_path = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Browsec.lnk")
            if os.path.exists(lnk_path):
                target = lnk_path

        if not target:
            target = shutil.which("Browsec.exe") or shutil.which("browsec.exe")

        if target:
            self._cached_browsec_target = target
        return target or ""

    def _launch_target(self, target_path: str):
        try:
            os.startfile(target_path)
        except Exception:
            work_dir = os.path.dirname(target_path)
            subprocess.Popen(f'"{target_path}"', cwd=work_dir, shell=True)

    def connect_sota(self):
        return self.toggle_sota()

    def disconnect_sota(self):
        return self.toggle_sota()

    def toggle_sota(self):
        try:
            hwnd = self._get_window_hwnd(["Sota Connect", "Sota"],
                                         ["sota connect.exe", "sotaconnect.exe", "sota.exe", "sotaconnectclient.exe"])

            if not hwnd:
                target_path = self._find_sota_target()
                if target_path:
                    self._launch_target(target_path)
                    for _ in range(15):
                        time.sleep(0.25)
                        hwnd = self._get_window_hwnd(["Sota Connect", "Sota"],
                                                     ["sota connect.exe", "sotaconnect.exe", "sota.exe",
                                                      "sotaconnectclient.exe"])
                        if hwnd:
                            break
                else:
                    return "Не удалось найти путь к приложению Сота"

            self._show_and_focus(hwnd)

            if self.click_app_toggle("sota_connect", hwnd=hwnd, threshold=0.72):
                self._minimize(hwnd)
                return "Сделала!"

            return "Открыла Соту"
        except Exception as e:
            return f"Не удалось запустить Соту: {e}"

    def connect_happ(self):
        return self._set_happ_state(target_state=True)

    def disconnect_happ(self):
        return self._set_happ_state(target_state=False)

    def _set_happ_state(self, target_state: bool):
        try:
            target_path = self._find_happ_target()
            if not target_path:
                return "Не удалось найти приложение Happ.exe."

            hwnd = self._get_window_hwnd(["Happ"], ["happ.exe"])
            was_launched = False

            if not hwnd or not ctypes.windll.user32.IsWindowVisible(hwnd):
                self._launch_target(target_path)
                was_launched = True

            for _ in range(25):
                time.sleep(0.3)
                hwnd = self._get_window_hwnd(["Happ"], ["happ.exe"])
                if hwnd and ctypes.windll.user32.IsWindowVisible(hwnd):
                    break

            if not hwnd:
                return "Не удалось дождаться открытия окна Хапп"

            self._show_and_focus(hwnd)
            time.sleep(1.2 if was_launched else 0.4)

            desired_folder = "disabled" if target_state else "active"
            opposite_folder = "active" if target_state else "disabled"

            # Защита от альцгеймера екарный бабай
            opposite_templates = self._collect_template_paths("happ", subfolder=opposite_folder)
            if opposite_templates:
                if self._find_best_match(opposite_templates, hwnd=hwnd, threshold=0.75):
                    self._minimize(hwnd)
                    return "Хапп уже " + ("включен!" if target_state else "выключен!")

            desired_templates = self._collect_template_paths("happ", subfolder=desired_folder)

            if not desired_templates:
                desired_templates = self._collect_template_paths("happ")

            for _ in range(8):
                coords = self._find_best_match(desired_templates, hwnd=hwnd, threshold=0.75)
                if coords:
                    self._safe_click(coords[0], coords[1])
                    time.sleep(0.3)
                    self._minimize(hwnd)
                    return "Включила Хапп!" if target_state else "Выключила Хапп!"
                time.sleep(0.25)

            self._minimize(hwnd)
            return "Открыла Хапп, но не смогла распознать нужную кнопку"

        except Exception as e:
            return f"Не удалось управлять Хапп: {e}"

    def is_browsec_tunnel_active(self) -> bool:
        """Проверяет, активен ли VPN-туннель Browsec (sing-box/xray)."""
        for proc in psutil.process_iter(['name']):
            try:
                p_name = (proc.info.get('name') or '').lower()
                if p_name in ['browbox.exe', 'browray.exe']:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def is_browsec_app_running(self) -> bool:
        """Проверяет, запущен ли клиент Browsec или его туннели."""
        for proc in psutil.process_iter(['name']):
            try:
                p_name = (proc.info.get('name') or '').lower()
                if p_name in ['browsec.exe', 'browbox.exe', 'browray.exe']:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _ensure_browsec_autoconnect_enabled(self):
        """Гарантирует, что в настройках Browsec включено автоподключение к последнему серверу."""
        try:
            appdata = os.environ.get("APPDATA", "")
            cfg_path = os.path.join(appdata, "browsec-desktop", "config.json")
            if os.path.exists(cfg_path):
                import json
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if not cfg.get("settings-auto-connect-vpn"):
                    cfg["settings-auto-connect-vpn"] = True
                    with open(cfg_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Browsec AutoConnect Config Error]: {e}")

    def connect_browsec(self) -> str:
        """
        Надежное подключение Browsec:
        1. Если туннель browbox уже активен -> Browsec уже включен!
        2. Обеспечивает флаг 'settings-auto-connect-vpn': true в config.json Browsec
        3. Если процесс Browsec висел без туннеля, перезапускает его для мгновенного коннекта
        4. Запускает Browsec.exe
        """
        try:
            if self.is_browsec_tunnel_active():
                return "Browsec уже включен!"

            self._ensure_browsec_autoconnect_enabled()

            target_path = self._find_browsec_target()
            if not target_path:
                return "Не удалось найти приложение Browsec."

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            # Если Browsec висел в фоне без туннеля, перезапускаем для срабатывания автоконнекта
            if self.is_browsec_app_running():
                subprocess.run(["taskkill", "/F", "/IM", "Browsec.exe", "/T"], capture_output=True, creationflags=flags)
                time.sleep(0.3)

            self._launch_target(target_path)
            return "Включила Browsec!"
        except Exception as e:
            return f"Не удалось включить Browsec: {e}"

    def disconnect_browsec(self) -> str:
        """
        Надежное отключение Browsec без графических костылей, падений и UAC:
        - Проверяет активность процессов
        - Мягко закрывает Browsec через taskkill (Electron перехватывает will-quit и выполняет stopVpn)
        - Принудительно глушит туннельные процессы browbox/browray
        """
        try:
            if not self.is_browsec_app_running():
                return "Browsec уже выключен!"

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            # 1. Мягкое закрытие Browsec (вызывает Electron will-quit stopVpn для очистки сетевых настроек)
            subprocess.run(["taskkill", "/IM", "Browsec.exe"], capture_output=True, creationflags=flags)
            time.sleep(0.4)

            # 2. Принудительное завершение туннелей browbox и browray (если остались)
            subprocess.run(["taskkill", "/F", "/IM", "browbox.exe", "/T"], capture_output=True, creationflags=flags)
            subprocess.run(["taskkill", "/F", "/IM", "browray.exe", "/T"], capture_output=True, creationflags=flags)
            subprocess.run(["taskkill", "/F", "/IM", "Browsec.exe", "/T"], capture_output=True, creationflags=flags)

            time.sleep(0.2)
            return "Выключила Browsec!"
        except Exception as e:
            return f"Не удалось выключить Browsec: {e}"