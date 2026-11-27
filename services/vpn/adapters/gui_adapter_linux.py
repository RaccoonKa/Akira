"""
Linux-адаптер GUI VPN-клиентов (Linux Mint Cinnamon / X11) для Sota Connect, Browsec и Happ.
Использует Xlib/wmctrl для управления окнами, gsettings/DPI для масштаба, OpenCV для поиска кнопок.
"""

import json
import os
import sys
import re
import shlex
import shutil
import subprocess
import time
import cv2
import numpy as np
import psutil

from core.utils.config import get_resource_path
from core.utils.platform_utils import get_pyautogui, is_wayland, take_screenshot_pil

_DESKTOP_SCAN_DIRS = [
    os.path.expanduser("~/.local/share/applications"),
    "/usr/local/share/applications",
    "/usr/share/applications",
    "/var/lib/flatpak/exports/share/applications",
    "/var/lib/snapd/desktop/applications",
]

_PLACEHOLDER_RE = re.compile(r"%[fFuUdDnNickvm]")


class GuiAdapter:
    def __init__(self):
        cand_list = [
            get_resource_path("services", "vpn", "templates"),
            get_resource_path("templates"),
        ]
        if getattr(sys, "frozen", False):
            base_app = os.path.dirname(os.path.abspath(sys.executable))
            cand_list.extend([
                os.path.join(base_app, "_internal", "services", "vpn", "templates"),
                os.path.join(base_app, "services", "vpn", "templates"),
                os.path.join(base_app, "_internal", "templates"),
                os.path.join(base_app, "templates"),
            ])
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cand_list.append(os.path.join(base_dir, "templates"))

        self.templates_dir = cand_list[0]
        for c in cand_list:
            if c and os.path.exists(c):
                self.templates_dir = c
                break

        self._cached_sota_target = None
        self._cached_happ_target = None
        self._cached_browsec_target = None

    def _get_system_scale(self) -> int:
        # 1. Cinnamon GSettings scaling-factor (uint32 1 -> 100%, 2 -> 200%)
        gsettings = shutil.which("gsettings")
        if gsettings:
            try:
                res = subprocess.run(
                    [gsettings, "get", "org.cinnamon.desktop.interface", "scaling-factor"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                )
                if res.returncode == 0:
                    m = re.search(r"(?:uint32\s+)?(\d+)\s*$", res.stdout.strip())
                    if m and int(m.group(1)) > 0:
                        return int(m.group(1)) * 100
            except Exception:
                pass

        # 2. Xft.dpi через xrdb -query
        xrdb = shutil.which("xrdb")
        if xrdb and os.environ.get("DISPLAY"):
            try:
                res = subprocess.run([xrdb, "-query"], capture_output=True, text=True, timeout=1.5)
                if res.returncode == 0:
                    m = re.search(r"Xft\.dpi:\s*([0-9.]+)", res.stdout)
                    if m:
                        return int(round(float(m.group(1)) / 96.0 * 100))
            except Exception:
                pass

        # 3. Qt DPI fallback
        try:
            from PyQt6.QtGui import QGuiApplication
            app = QGuiApplication.instance()
            if app and app.primaryScreen():
                dpi = app.primaryScreen().logicalDotsPerInch()
                if dpi > 0:
                    return int(round(dpi / 96.0 * 100))
        except Exception:
            pass

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

        d1 = os.path.join(self.templates_dir, scale_folder, app_name)
        if subfolder:
            d1 = os.path.join(d1, subfolder)
        candidates.append(d1)

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

    def _get_window_rect(self, wid: int) -> tuple[int, int, int, int] | None:
        if not wid or is_wayland() or not os.environ.get("DISPLAY"):
            return None
        try:
            from Xlib.display import Display
            disp = Display()
            try:
                root = disp.screen().root
                win = disp.create_resource_object("window", wid)
                geom = win.get_geometry()
                coords = win.translate_coords(root, 0, 0)
                left, top = int(coords.x), int(coords.y)
                right = left + int(geom.width)
                bottom = top + int(geom.height)
                return (left, top, right, bottom)
            finally:
                disp.close()
        except Exception:
            return None

    def _is_window_visible(self, wid: int) -> bool:
        if not wid or is_wayland() or not os.environ.get("DISPLAY"):
            return False
        try:
            from Xlib import X
            from Xlib.display import Display
            disp = Display()
            try:
                win = disp.create_resource_object("window", wid)
                attrs = win.get_attributes()
                if attrs.map_state != X.IsViewable:
                    return False
                atom_state = disp.intern_atom("_NET_WM_STATE")
                atom_hidden = disp.intern_atom("_NET_WM_STATE_HIDDEN")
                prop = win.get_full_property(atom_state, X.AnyPropertyType)
                if prop and prop.value and atom_hidden in prop.value:
                    return False
                return True
            finally:
                disp.close()
        except Exception:
            return False

    def _find_best_match(self, template_paths: list, hwnd: int = 0, threshold: float = 0.78,
                         bottom_only: bool = False, multiscale: bool = False):
        if not template_paths:
            return None

        offset_x, offset_y = 0, 0
        screen = None

        rect = self._get_window_rect(hwnd)
        if rect:
            left, top, right, bottom = rect
            w, h = right - left, bottom - top
            if w > 100 and h > 100:
                try:
                    if bottom_only:
                        top_bound = bottom - int(h * 0.28)
                        bbox = (left, top_bound, right, bottom)
                        offset_x, offset_y = left, top_bound
                    else:
                        bbox = (left, top, right, bottom)
                        offset_x, offset_y = left, top
                    screen = np.array(take_screenshot_pil(bbox=bbox))
                except Exception:
                    screen = None

        if screen is None:
            try:
                screen = np.array(take_screenshot_pil())
                offset_x, offset_y = 0, 0
            except Exception:
                return None

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)

        best_score = -1.0
        best_coords = None
        scales = [0.85, 0.95, 1.0, 1.05, 1.15, 1.25] if multiscale else [1.0]

        for tpl_path in template_paths:
            base_template = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
            if base_template is None:
                continue

            for scale in scales:
                template = base_template if scale == 1.0 else cv2.resize(base_template, (0, 0), fx=scale, fy=scale)
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
        pag = get_pyautogui()
        if not pag:
            return
        pag.mouseDown(x, y)
        time.sleep(0.08)
        pag.mouseUp(x, y)

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
        if is_wayland() or not os.environ.get("DISPLAY"):
            return 0
        try:
            from Xlib import X
            from Xlib.display import Display
            disp = Display()
        except Exception:
            return 0

        candidates = []
        try:
            root = disp.screen().root
            atom_clients = disp.intern_atom("_NET_CLIENT_LIST")
            atom_net_name = disp.intern_atom("_NET_WM_NAME")
            atom_utf8 = disp.intern_atom("UTF8_STRING")
            atom_pid = disp.intern_atom("_NET_WM_PID")
            atom_state = disp.intern_atom("_NET_WM_STATE")
            atom_hidden = disp.intern_atom("_NET_WM_STATE_HIDDEN")

            client_prop = root.get_full_property(atom_clients, X.AnyPropertyType)
            if not client_prop or not client_prop.value:
                return 0

            proc_targets = [p.lower().removesuffix(".exe") for p in (process_names or [])]

            for wid in client_prop.value:
                try:
                    win = disp.create_resource_object("window", int(wid))
                    name_prop = win.get_full_property(atom_net_name, atom_utf8) or win.get_full_property(atom_net_name, X.AnyPropertyType)
                    title = ""
                    if name_prop and name_prop.value:
                        val = name_prop.value
                        title = val.decode("utf-8", errors="ignore") if isinstance(val, bytes) else str(val)
                    if not title:
                        wm_name = win.get_wm_name()
                        if wm_name:
                            title = wm_name.decode("utf-8", errors="ignore") if isinstance(wm_name, bytes) else str(wm_name)

                    wm_class = win.get_wm_class() or ()
                    class_joined = " ".join(str(c).lower() for c in wm_class)

                    pid_val = 0
                    pid_prop = win.get_full_property(atom_pid, X.AnyPropertyType)
                    if pid_prop and pid_prop.value:
                        pid_val = int(pid_prop.value[0])

                    proc_matched = False
                    if proc_targets and pid_val > 0:
                        try:
                            pname = (psutil.Process(pid_val).name() or "").lower()
                            if any(pt in pname for pt in proc_targets):
                                proc_matched = True
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    if proc_targets and not proc_matched:
                        if any(pt in class_joined for pt in proc_targets):
                            proc_matched = True

                    title_low = title.lower()
                    title_matched = any(kw.lower() in title_low for kw in (title_keywords or []))

                    if title_matched or proc_matched:
                        geom = win.get_geometry()
                        attrs = win.get_attributes()
                        state_prop = win.get_full_property(atom_state, X.AnyPropertyType)
                        is_hidden = bool(state_prop and state_prop.value and atom_hidden in state_prop.value)
                        score = 0
                        if title_matched:
                            score += 50
                        if proc_matched:
                            score += 40
                        if attrs.map_state == X.IsViewable and not is_hidden:
                            score += 20
                        if geom.width > 150 and geom.height > 150:
                            score += 30
                        if title:
                            score += 15
                        candidates.append((score, int(wid)))
                except Exception:
                    continue
        finally:
            try:
                disp.close()
            except Exception:
                pass

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return 0

    def _show_and_focus(self, hwnd: int):
        if not hwnd or is_wayland() or not os.environ.get("DISPLAY"):
            return

        wmctrl = shutil.which("wmctrl")
        if wmctrl:
            try:
                subprocess.run([wmctrl, "-i", "-a", str(hwnd)], capture_output=True, timeout=1.5)
                time.sleep(0.08)
                return
            except Exception:
                pass

        try:
            from Xlib import X, protocol
            from Xlib.display import Display
            disp = Display()
            try:
                root = disp.screen().root
                win = disp.create_resource_object("window", hwnd)
                win.map()
                win.raise_window()
                atom_active = disp.intern_atom("_NET_ACTIVE_WINDOW")
                ev = protocol.event.ClientMessage(
                    window=win,
                    client_type=atom_active,
                    data=(32, [2, X.CurrentTime, 0, 0, 0]),
                )
                root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                disp.sync()
                time.sleep(0.08)
            finally:
                disp.close()
        except Exception:
            pass

    def _minimize(self, hwnd: int):
        if not hwnd or is_wayland() or not os.environ.get("DISPLAY"):
            return
        time.sleep(0.2)

        wmctrl = shutil.which("wmctrl")
        if wmctrl:
            try:
                if subprocess.run([wmctrl, "-i", "-r", str(hwnd), "-b", "add,hidden"], capture_output=True, timeout=1.5).returncode == 0:
                    return
            except Exception:
                pass

        xdotool = shutil.which("xdotool")
        if xdotool:
            try:
                subprocess.run([xdotool, "windowminimize", str(hwnd)], capture_output=True, timeout=1.5)
                return
            except Exception:
                pass

    def _find_linux_app_target(self, binaries: list[str], desktop_keywords: list[str], extra_paths: list[str]) -> str:
        for b in binaries:
            found = shutil.which(b)
            if found:
                return found

        for ep in extra_paths:
            if ep and os.path.isfile(ep) and os.access(ep, os.X_OK):
                return ep

        for d_dir in _DESKTOP_SCAN_DIRS:
            if not os.path.isdir(d_dir):
                continue
            for root, _, files in os.walk(d_dir):
                for fname in files:
                    if not fname.endswith(".desktop"):
                        continue
                    f_low = fname.lower()
                    full_p = os.path.join(root, fname)
                    if any(kw in f_low for kw in desktop_keywords):
                        return full_p
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                            head = f.read(800).lower()
                        if any(f"name={kw}" in head or kw in head for kw in desktop_keywords):
                            return full_p
                    except OSError:
                        pass
        return ""

    def _find_sota_target(self) -> str:
        if self._cached_sota_target and os.path.exists(self._cached_sota_target):
            return self._cached_sota_target
        res = self._find_linux_app_target(
            binaries=["sota-connect", "sotaconnect", "sota", "sotaconnectclient"],
            desktop_keywords=["sota connect", "sota-connect", "sotaconnect"],
            extra_paths=[
                "/opt/Sota Connect/sotaconnect",
                "/opt/Sota Connect/sota-connect",
                "/opt/sota-connect/sota-connect",
                "/usr/bin/sota-connect",
            ],
        )
        if res:
            self._cached_sota_target = res
        return res

    def _find_happ_target(self) -> str:
        if self._cached_happ_target and os.path.exists(self._cached_happ_target):
            return self._cached_happ_target
        res = self._find_linux_app_target(
            binaries=["happ", "happ-desktop"],
            desktop_keywords=["happ"],
            extra_paths=[
                "/opt/Happ/happ",
                "/opt/Happ/Happ",
                "/opt/happ/happ",
                "/usr/bin/happ",
            ],
        )
        if res:
            self._cached_happ_target = res
        return res

    def _find_browsec_target(self) -> str:
        if self._cached_browsec_target and os.path.exists(self._cached_browsec_target):
            return self._cached_browsec_target
        res = self._find_linux_app_target(
            binaries=["browsec", "browsec-desktop", "browsec-vpn"],
            desktop_keywords=["browsec"],
            extra_paths=[
                "/opt/Browsec/browsec",
                "/opt/browsec-desktop/browsec-desktop",
                "/usr/bin/browsec",
            ],
        )
        if res:
            self._cached_browsec_target = res
        return res

    def _launch_target(self, target_path: str):
        if not target_path:
            return
        if target_path.endswith(".desktop"):
            gio = shutil.which("gio")
            if gio:
                subprocess.Popen(
                    [gio, "launch", target_path],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
            try:
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("Exec="):
                            raw = _PLACEHOLDER_RE.sub("", line[5:].strip()).strip()
                            cmd = shlex.split(raw)
                            if cmd:
                                subprocess.Popen(
                                    cmd,
                                    stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    start_new_session=True,
                                )
                                return
            except Exception:
                pass
            return

        subprocess.Popen(
            [target_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def connect_sota(self):
        return self.toggle_sota()

    def disconnect_sota(self):
        return self.toggle_sota()

    def toggle_sota(self):
        try:
            proc_candidates = ["sota connect", "sotaconnect", "sota", "sotaconnectclient", "sota-connect"]
            hwnd = self._get_window_hwnd(["Sota Connect", "Sota"], proc_candidates)

            if not hwnd:
                target_path = self._find_sota_target()
                if target_path:
                    self._launch_target(target_path)
                    for _ in range(15):
                        time.sleep(0.25)
                        hwnd = self._get_window_hwnd(["Sota Connect", "Sota"], proc_candidates)
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
                return "Не удалось найти приложение Happ."

            proc_candidates = ["happ", "happ-desktop"]
            hwnd = self._get_window_hwnd(["Happ"], proc_candidates)
            was_launched = False

            if not hwnd or not self._is_window_visible(hwnd):
                self._launch_target(target_path)
                was_launched = True

            for _ in range(25):
                time.sleep(0.3)
                hwnd = self._get_window_hwnd(["Happ"], proc_candidates)
                if hwnd and self._is_window_visible(hwnd):
                    break

            if not hwnd:
                return "Не удалось дождаться открытия окна Хапп"

            self._show_and_focus(hwnd)
            time.sleep(1.2 if was_launched else 0.4)

            desired_folder = "disabled" if target_state else "active"
            opposite_folder = "active" if target_state else "disabled"

            opposite_templates = self._collect_template_paths("happ", subfolder=opposite_folder)
            if opposite_templates:
                if self._find_best_match(opposite_templates, hwnd=hwnd, threshold=0.75):
                    self._minimize(hwnd)
                    return "Хапп уже " + ("включен!" if target_state else "выключен!")

            desired_templates = self._collect_template_paths("happ", subfolder=desired_folder) or self._collect_template_paths("happ")

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
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    p_name = (proc.info.get('name') or '').lower()
                    if p_name in ("browbox", "browray"):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

        try:
            import socket
            stats = psutil.net_if_stats()
            for iface, if_stat in stats.items():
                if "browbox" in iface.lower() and getattr(if_stat, "isup", False):
                    addrs = psutil.net_if_addrs().get(iface, [])
                    if any(getattr(a, "family", None) == socket.AF_INET for a in addrs):
                        return True
        except Exception:
            pass

        return False

    def is_browsec_app_running(self) -> bool:
        for proc in psutil.process_iter(['name']):
            try:
                p_name = (proc.info.get('name') or '').lower()
                if p_name in ("browsec", "browsec-desktop", "browbox", "browray"):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _ensure_browsec_autoconnect_enabled(self):
        try:
            cfg_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
            cfg_path = os.path.join(cfg_home, "browsec-desktop", "config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if not cfg.get("settings-auto-connect-vpn"):
                    cfg["settings-auto-connect-vpn"] = True
                    with open(cfg_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Browsec AutoConnect Config Error]: {e}")

    def connect_browsec(self) -> str:
        return self._set_browsec_state(target_state=True)

    def disconnect_browsec(self) -> str:
        try:
            if not self.is_browsec_tunnel_active() and not self.is_browsec_app_running():
                return "Browsec уже выключен!"

            target_names = {"browbox", "browray", "browsec", "browsec-desktop"}
            for proc in psutil.process_iter(['name']):
                try:
                    p_name = (proc.info.get('name') or '').lower()
                    if p_name in target_names:
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            for _ in range(15):
                time.sleep(0.2)
                if not self.is_browsec_tunnel_active():
                    return "Выключила Browsec!"

            return "Выключила Browsec!"
        except Exception as e:
            return f"Не удалось выключить Browsec: {e}"

    def _set_browsec_state(self, target_state: bool) -> str:
        try:
            is_active = self.is_browsec_tunnel_active()
            if target_state and is_active:
                return "Browsec уже включен!"
            if not target_state and not is_active:
                return "Browsec уже выключен!"

            target_path = self._find_browsec_target()
            proc_candidates = ["browsec", "browsec-desktop"]
            hwnd = self._get_window_hwnd(["Browsec"], proc_candidates)
            was_launched = False

            if not hwnd or not self._is_window_visible(hwnd):
                if not target_path:
                    return "Не удалось найти приложение Browsec."
                self._launch_target(target_path)
                was_launched = True

            for _ in range(25 if was_launched else 10):
                time.sleep(0.25)
                hwnd = self._get_window_hwnd(["Browsec"], proc_candidates)
                if hwnd and self._is_window_visible(hwnd):
                    break

            if not hwnd:
                return "Не удалось дождаться открытия окна Browsec"

            self._show_and_focus(hwnd)
            time.sleep(1.0 if was_launched else 0.4)

            if target_state and self.is_browsec_tunnel_active():
                self._minimize(hwnd)
                return "Включила Browsec!"

            desired_sub = "on" if not target_state else "off"
            templates = self._collect_template_paths("browsec", subfolder=desired_sub) or self._collect_template_paths("browsec")

            clicked = False
            for _ in range(8):
                coords = self._find_best_match(templates, hwnd=hwnd, threshold=0.68, multiscale=True)
                if coords:
                    self._safe_click(coords[0], coords[1])
                    clicked = True
                    break
                time.sleep(0.2)

            if not clicked:
                rect = self._get_window_rect(hwnd)
                if rect:
                    left, top, right, bottom = rect
                    w, h = right - left, bottom - top
                    if w > 200 and h > 200:
                        self._safe_click(left + int(w * 0.46), top + int(h * 0.44))

            for _ in range(16):
                time.sleep(0.25)
                if self.is_browsec_tunnel_active() == target_state:
                    self._minimize(hwnd)
                    return "Включила Browsec!" if target_state else "Выключила Browsec!"

            rect = self._get_window_rect(hwnd)
            if rect:
                left, top, right, bottom = rect
                w, h = right - left, bottom - top
                if w > 200 and h > 200:
                    self._safe_click(left + int(w * 0.46), top + int(h * 0.44))

            for _ in range(12):
                time.sleep(0.25)
                if self.is_browsec_tunnel_active() == target_state:
                    self._minimize(hwnd)
                    return "Включила Browsec!" if target_state else "Выключила Browsec!"

            self._minimize(hwnd)
            if self.is_browsec_tunnel_active() == target_state:
                return "Включила Browsec!" if target_state else "Выключила Browsec!"

            return "Открыла Browsec, но не смогла переключить VPN"
        except Exception as e:
            return f"Не удалось управлять Browsec: {e}"
