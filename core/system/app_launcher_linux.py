"""
Linux-реализация AppLauncher для Linux Mint Cinnamon (.desktop, Flatpak, Snap, встроенные утилиты).
"""

import os
import re
import shlex
import shutil
import difflib
import subprocess
from core.system.app_launcher_aliases import COMMON_APP_ALIASES
from core.utils.platform_utils import open_path

_DESKTOP_PLACEHOLDERS = {"%u", "%U", "%f", "%F", "%i", "%c", "%k", "%d", "%D", "%n", "%N", "%v", "%m"}
_INLINE_PLACEHOLDER_RE = re.compile(r"%[fFuUdDnNickvm]")


class AppLauncher:
    def __init__(self):
        self.apps: dict[str, tuple[str, str, list[str] | None, bool]] = {}
        self.builtins = {
            "калькулятор": ("Калькулятор", ["gnome-calculator", "galculator", "mate-calc", "kcalc"]),
            "кальку": ("Калькулятор", ["gnome-calculator", "galculator", "mate-calc", "kcalc"]),
            "проводник": ("Проводник", ["nemo", "thunar", "nautilus", "dolphin", "caja"]),
            "эксплорер": ("Проводник", ["nemo", "thunar", "nautilus", "dolphin", "caja"]),
            "блокнот": ("Блокнот", ["xed", "gedit", "mousepad", "kate", "pluma"]),
            "диспетчер задач": ("Диспетчер задач", ["gnome-system-monitor", "mate-system-monitor", "xfce4-taskmanager", "plasma-systemmonitor"]),
            "таск менеджер": ("Диспетчер задач", ["gnome-system-monitor", "mate-system-monitor", "xfce4-taskmanager"]),
            "диспетчер": ("Диспетчер задач", ["gnome-system-monitor", "mate-system-monitor"]),
            "терминал": ("Терминал", ["gnome-terminal", "x-terminal-emulator", "konsole", "xfce4-terminal", "kitty", "alacritty"]),
            "командная строка": ("Терминал", ["gnome-terminal", "x-terminal-emulator", "konsole"]),
            "кмд": ("Терминал", ["gnome-terminal", "x-terminal-emulator", "konsole"]),
            "параметры": ("Параметры системы", ["cinnamon-settings", "gnome-control-center"]),
            "настройки": ("Параметры системы", ["cinnamon-settings", "gnome-control-center"]),
            "панель управления": ("Параметры системы", ["cinnamon-settings", "gnome-control-center"]),
            "пейнт": ("Графический редактор", ["drawing", "pinta", "kolourpaint", "gimp", "krita"]),
            "паинт": ("Графический редактор", ["drawing", "pinta", "kolourpaint", "gimp"]),
            "пэйнт": ("Графический редактор", ["drawing", "pinta", "kolourpaint", "gimp"]),
        }
        self.aliases = dict(COMMON_APP_ALIASES)
        self.aliases.update({
            "вс код": "visual studio code",
            "телеграм": "telegram desktop",
            "телега": "telegram desktop",
            "тг": "telegram desktop",
            "влс": "vlc media player",
            "виэлси": "vlc media player",
            "медиаплеер": "vlc media player",
            "гимп": "gnu image manipulation program",
            "либреофис": "libreoffice",
            "менеджер программ": "software manager",
        })
        self.rescan()

    @staticmethod
    def _clean_name(text: str) -> str:
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        return re.sub(r"\s+", " ", clean).strip()

    @staticmethod
    def _clean_exec_line(exec_raw: str) -> list[str]:
        if not exec_raw:
            return []
        try:
            tokens = shlex.split(exec_raw)
        except ValueError:
            tokens = exec_raw.split()

        cleaned = []
        for tok in tokens:
            if tok in _DESKTOP_PLACEHOLDERS:
                continue
            tok = _INLINE_PLACEHOLDER_RE.sub("", tok).strip()
            if tok:
                cleaned.append(tok)
        return cleaned

    @staticmethod
    def _parse_desktop_file(file_path: str) -> dict | None:
        fields = {}
        in_main_section = False
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("["):
                        if line == "[Desktop Entry]":
                            in_main_section = True
                            continue
                        if in_main_section:
                            break
                        continue
                    if not in_main_section or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    if key not in fields:
                        fields[key] = val.strip()
        except OSError:
            return None

        entry_type = fields.get("Type", "Application")
        if entry_type != "Application":
            return None

        if fields.get("NoDisplay", "").lower() == "true" or fields.get("Hidden", "").lower() == "true":
            return None

        try_exec = fields.get("TryExec", "").strip()
        if try_exec:
            if not (os.path.isabs(try_exec) and os.access(try_exec, os.X_OK)) and not shutil.which(try_exec):
                return None

        cmd_args = AppLauncher._clean_exec_line(fields.get("Exec", ""))
        if not cmd_args:
            return None

        name = fields.get("Name") or fields.get("Name[ru]") or os.path.splitext(os.path.basename(file_path))[0]
        name_ru = fields.get("Name[ru]", "")
        generic = fields.get("GenericName", "")
        needs_terminal = fields.get("Terminal", "").lower() == "true"

        return {
            "name": name,
            "name_ru": name_ru,
            "generic": generic,
            "desktop_path": file_path,
            "cmd_args": cmd_args,
            "terminal": needs_terminal,
        }

    def rescan(self):
        self.apps.clear()
        scan_dirs = [
            os.path.expanduser("~/.local/share/applications"),
            "/usr/local/share/applications",
            "/usr/share/applications",
            "/var/lib/flatpak/exports/share/applications",
            os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
            "/var/lib/snapd/desktop/applications",
            os.path.expanduser("~/Desktop"),
        ]
        ignore_patterns = ("uninstall", "деинсталл", "readme", "debian-xterm", "debian-uxterm")

        for s_dir in scan_dirs:
            if not os.path.isdir(s_dir):
                continue
            for root, _, files in os.walk(s_dir):
                for fname in files:
                    if not fname.endswith(".desktop"):
                        continue
                    full_path = os.path.join(root, fname)
                    parsed = self._parse_desktop_file(full_path)
                    if not parsed:
                        continue

                    raw_title = parsed["name_ru"] or parsed["name"]
                    entry_val = (raw_title, full_path, parsed["cmd_args"], parsed["terminal"])

                    candidate_names = [parsed["name"], parsed["name_ru"]]
                    file_stem = os.path.splitext(fname)[0]
                    if "." in file_stem:
                        candidate_names.append(file_stem.split(".")[-1])
                    else:
                        candidate_names.append(file_stem)
                    if parsed["generic"]:
                        candidate_names.append(parsed["generic"])

                    for cand in candidate_names:
                        clean = self._clean_name(cand)
                        if not clean or any(p in clean for p in ignore_patterns):
                            continue
                        if clean not in self.apps:
                            self.apps[clean] = entry_val

    def _spawn_entry(self, entry: tuple[str, str, list[str] | None, bool]) -> bool:
        _, desktop_path, cmd_args, needs_terminal = entry
        gio = shutil.which("gio")
        if gio and desktop_path and os.path.exists(desktop_path):
            try:
                subprocess.Popen(
                    [gio, "launch", desktop_path],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return True
            except Exception:
                pass

        if cmd_args:
            launch_cmd = list(cmd_args)
            if needs_terminal:
                for term in ("gnome-terminal", "x-terminal-emulator", "konsole", "xfce4-terminal"):
                    term_exe = shutil.which(term)
                    if term_exe:
                        flag = "--" if term == "gnome-terminal" else "-e"
                        launch_cmd = [term_exe, flag, *launch_cmd]
                        break
            try:
                subprocess.Popen(
                    launch_cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return True
            except Exception:
                pass
        return False

    def launch(self, query):
        if not query:
            return False, ""

        clean_query = self._clean_name(query)

        # 1. Встроенные системные утилиты Cinnamon / Mint
        if clean_query in self.builtins:
            label, bins = self.builtins[clean_query]
            for b in bins:
                exe = shutil.which(b)
                if exe:
                    try:
                        subprocess.Popen(
                            [exe],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True,
                        )
                        return True, label
                    except Exception:
                        continue

        target_name = self.aliases.get(clean_query, clean_query)

        # 2. Точное совпадение
        for key in (clean_query, target_name):
            if key in self.apps:
                entry = self.apps[key]
                if self._spawn_entry(entry):
                    return True, entry[0]

        # 3. Вхождение по словам
        for name, entry in self.apps.items():
            if target_name == name or target_name in name.split():
                if self._spawn_entry(entry):
                    return True, entry[0]

        # 4. Нечёткий поиск
        candidates = list(self.apps.keys())
        matches = difflib.get_close_matches(target_name, candidates, n=1, cutoff=0.6)
        if matches:
            entry = self.apps[matches[0]]
            if self._spawn_entry(entry):
                return True, entry[0]

        # 5. Прямой бинарник в PATH или локальный путь / URI
        raw_stripped = query.strip()
        direct_exe = shutil.which(raw_stripped) or shutil.which(target_name.replace(" ", "-"))
        if direct_exe:
            try:
                subprocess.Popen(
                    [direct_exe],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return True, os.path.basename(direct_exe)
            except Exception:
                pass

        if os.path.exists(raw_stripped) or raw_stripped.startswith(("http://", "https://")):
            if open_path(raw_stripped):
                return True, os.path.basename(raw_stripped) or raw_stripped

        return False, ""
