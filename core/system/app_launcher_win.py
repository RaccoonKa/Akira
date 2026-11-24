"""
Windows-реализация AppLauncher (ярлыки .lnk / .url и встроенные команды Windows).
"""

import os
import re
import difflib
from core.system.app_launcher_aliases import COMMON_APP_ALIASES


class AppLauncher:
    def __init__(self):
        self.apps = {}
        self.builtins = {
            "калькулятор": "calc.exe",
            "блокнот": "notepad.exe",
            "диспетчер задач": "taskmgr.exe",
            "проводник": "explorer.exe",
            "пейнт": "mspaint.exe",
            "панель управления": "control.exe",
            "параметры": "ms-settings:",
            "настройки": "ms-settings:",
            "терминал": "wt.exe",
            "командная строка": "cmd.exe",
        }
        self.aliases = dict(COMMON_APP_ALIASES)
        self.aliases.update({
            "архиватор": "winrar",
            "винрар": "winrar",
            "вин рар": "winrar",
            "7зип": "7-zip",
            "сем зип": "7-zip",
            "зип": "7-zip",
            "тотал командер": "total commander",
            "тотал": "total commander",
            "командер": "total commander",
            "калькулятор": "calculator",
            "кальку": "calculator",
            "проводник": "explorer",
            "эксплорер": "explorer",
            "паинт": "paint",
            "пэйнт": "paint",
            "пейнт": "paint",
            "ножницы": "snipping tool",
            "снип": "snipping tool",
            "диспетчер задач": "taskmgr",
            "таск менеджер": "taskmgr",
            "диспетчер": "taskmgr",
            "командная строка": "cmd",
            "кмд": "cmd",
            "терминал": "windows terminal",
            "павершелл": "powershell",
            "повершелл": "powershell",
            "пуск": "start",
            "настройки": "ms-settings:",
            "параметры": "ms-settings:",
            "панель управления": "control",
            "контрольная панель": "control",
            "медиаплеер": "wmplayer",
            "виндовс медиа": "wmplayer",
        })
        self.rescan()

    def _clean_name(self, text):
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        return re.sub(r"\s+", " ", clean).strip()

    def rescan(self):
        self.apps.clear()
        scan_dirs = [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%Public%\Desktop"),
            os.path.expandvars(r"%UserProfile%\Desktop"),
        ]

        ignore_patterns = ["uninstall", "деинсталл", "readme", "help", "справка", "настройка", "update", "crash"]

        for s_dir in scan_dirs:
            if not os.path.exists(s_dir):
                continue
            for root, _, files in os.walk(s_dir):
                for f in files:
                    if f.lower().endswith((".lnk", ".url")):
                        raw_name = os.path.splitext(f)[0]
                        clean = self._clean_name(raw_name)

                        if any(p in clean for p in ignore_patterns):
                            continue

                        full_path = os.path.join(root, f)
                        if clean not in self.apps:
                            self.apps[clean] = (raw_name, full_path)

    def launch(self, query):
        if not query:
            return False, ""

        clean_query = self._clean_name(query)

        if clean_query in self.builtins:
            cmd = self.builtins[clean_query]
            try:
                os.system(f"start {cmd}")
                return True, clean_query.title()
            except Exception:
                return False, ""

        target_name = self.aliases.get(clean_query, clean_query)

        if target_name in self.apps:
            raw_title, path = self.apps[target_name]
            try:
                os.startfile(path)
                return True, raw_title
            except Exception:
                pass

        for name, (raw_title, path) in self.apps.items():
            if target_name == name or target_name in name.split():
                try:
                    os.startfile(path)
                    return True, raw_title
                except Exception:
                    pass

        candidates = list(self.apps.keys())
        matches = difflib.get_close_matches(target_name, candidates, n=1, cutoff=0.6)
        if matches:
            best = matches[0]
            raw_title, path = self.apps[best]
            try:
                os.startfile(path)
                return True, raw_title
            except Exception:
                pass

        return False, ""
