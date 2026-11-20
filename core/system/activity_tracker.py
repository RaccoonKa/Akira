import os
import sys
import time
import json
import ctypes
import threading
import datetime
import psutil
from core.utils.config import get_user_data_path


class ActivityTracker:
    """
    Фоновый трекер активности пользователя («Дневник впечатлений»).
    Безопасно и легковесно фиксирует активные окна и приложения, группирует их
    по категориям (кодинг, гейминг, музыка, видео/стримы, общение, творчество, тишина),
    чтобы Акира могла осознанно придумывать цифровые сны на основе реального дня
    и ориентироваться в том, чем занимался её создатель.
    """
    _instance = None
    _lock = threading.Lock()

    CATEGORIES = {
        "coding": "Программирование и разработка",
        "gaming": "Видеоигры",
        "music": "Музыка и звук",
        "video": "Видео, кино и стримы",
        "browser": "Веб-серфинг и статьи",
        "chat": "Общение и мессенджеры",
        "creative": "Творчество и дизайн",
        "quiet": "Тишина и отдых"
    }

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        try:
            self.activity_dir = get_user_data_path("activity")
            os.makedirs(self.activity_dir, exist_ok=True)
        except (PermissionError, OSError):
            self.activity_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Akira", "activity")
            os.makedirs(self.activity_dir, exist_ok=True)
        self.file_path = os.path.join(self.activity_dir, "daily_activity.json")

        self.data_lock = threading.Lock()
        self.running = False
        self.thread = None
        self.sample_interval = 5.0   # Опрос каждые 5 секунд
        self.save_interval = 60.0     # Сброс на диск раз в минуту
        self.last_saved_time = time.time()

        self.data = self._load_data()
        self._ensure_today_exists()

    def _load_data(self) -> dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                print(f"[ActivityTracker Warning]: Ошибка чтения {self.file_path}: {e}")
        return {}

    def _ensure_today_exists(self):
        today = datetime.date.today().isoformat()
        if today not in self.data:
            self.data[today] = {
                "categories": {cat: 0 for cat in self.CATEGORIES},
                "apps": {},
                "total_seconds": 0,
                "last_updated": datetime.datetime.now().isoformat()
            }

    def _save_data(self):
        with self.data_lock:
            try:
                # Ограничиваем историю 14 днями
                cutoff_date = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
                cleaned_data = {
                    d: v for d, v in self.data.items() if d >= cutoff_date
                }
                self.data = cleaned_data

                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                self.last_saved_time = time.time()
            except Exception as e:
                print(f"[ActivityTracker Warning]: Ошибка записи {self.file_path}: {e}")

    @classmethod
    def categorize_app(cls, exe_name: str, title: str) -> tuple[str, str]:
        """
        Определяет категорию и понятное имя приложения по exe и заголовку окна.
        """
        exe_low = (exe_name or "").lower()
        title_low = (title or "").lower()

        # 1. Программирование и разработка
        if any(x in exe_low for x in ["antigravity", "cursor"]):
            return "coding", "Antigravity IDE"
        if any(x in exe_low for x in ["code", "vscodium"]):
            return "coding", "VS Code"
        if "pycharm" in exe_low:
            return "coding", "PyCharm"
        if "idea" in exe_low:
            return "coding", "IntelliJ IDEA"
        if "devenv" in exe_low:
            return "coding", "Visual Studio"
        if any(x in exe_low for x in ["clion", "rider", "webstorm", "goland", "rustrover"]):
            return "coding", "JetBrains IDE"
        if any(x in exe_low for x in ["sublime_text", "notepad++", "kate"]):
            return "coding", "Текстовый редактор"
        if any(x in exe_low for x in ["windowsterminal", "cmd", "powershell", "bash", "mintty", "conemu"]):
            return "coding", "Терминал"
        if any(x in exe_low for x in ["githubdesktop", "sourcetree", "gitkraken"]):
            return "coding", "Git клиент"
        if "antigravity" in title_low:
            return "coding", "Antigravity IDE"

        # 2. Музыка и аудио
        if "spotify" in exe_low or "spotify" in title_low:
            return "music", "Spotify"
        if "yandexmusic" in exe_low or "яндекс музыка" in title_low or "yandex music" in title_low:
            return "music", "Яндекс Музыка"
        if any(x in exe_low for x in ["aimp", "foobar2000", "winamp", "musicbee"]):
            return "music", "Музыкальный плеер"
        if any(x in exe_low for x in ["fl64", "fl", "ableton", "reaper", "cubase", "studio one"]):
            return "music", "Музыкальная студия (DAW)"

        # 3. Видео, фильмы и стримы
        if any(x in title_low for x in ["youtube", "ютуб"]):
            return "video", "YouTube"
        if any(x in title_low for x in ["twitch", "твич", "кинопоиск", "kinopoisk", "netflix", "anime", "аниме", "сериал", "фильм"]):
            return "video", "Кино и стримы"
        if any(x in exe_low for x in ["vlc", "mpc-hc", "potplayer", "kmplayer"]):
            return "video", "Видеоплеер"

        # 4. Видеоигры
        if "steam" in exe_low:
            return "gaming", "Steam"
        if "epicgameslauncher" in exe_low:
            return "gaming", "Epic Games"
        game_patterns = [
            ("cyberpunk2077", "Cyberpunk 2077"),
            ("dota2", "Dota 2"),
            ("cs2", "Counter-Strike 2"),
            ("csgo", "CS:GO"),
            ("minecraft", "Minecraft"),
            ("witcher3", "Ведьмак 3"),
            ("gta5", "GTA V"),
            ("genshinimpact", "Genshin Impact"),
            ("honkaistarrail", "Honkai: Star Rail"),
            ("starfield", "Starfield"),
            ("baldursgate3", "Baldur's Gate 3"),
            ("bg3", "Baldur's Gate 3"),
            ("valorant", "Valorant"),
            ("leagueclient", "League of Legends"),
            ("overwatch", "Overwatch"),
            ("apex", "Apex Legends"),
            ("rdr2", "Red Dead Redemption 2"),
            ("eldenring", "Elden Ring"),
            ("hades", "Hades"),
            ("factorio", "Factorio"),
            ("terraria", "Terraria"),
            ("rust", "Rust"),
            ("tarkov", "Escape from Tarkov")
        ]
        for g_exe, g_name in game_patterns:
            if g_exe in exe_low:
                return "gaming", g_name

        # 5. Творчество и дизайн
        if "photoshop" in exe_low:
            return "creative", "Photoshop"
        if "figma" in exe_low or "figma" in title_low:
            return "creative", "Figma"
        if "blender" in exe_low:
            return "creative", "Blender 3D"
        if any(x in exe_low for x in ["premiere", "afterfx", "davinci"]):
            return "creative", "Видеомонтаж"

        # 6. Общение и мессенджеры
        if "telegram" in exe_low or "telegram" in title_low:
            return "chat", "Telegram"
        if "discord" in exe_low or "discord" in title_low:
            return "chat", "Discord"
        if any(x in exe_low for x in ["slack", "vk", "element", "skype"]):
            return "chat", "Мессенджер"

        # 7. Браузеры
        if any(x in exe_low for x in ["chrome", "firefox", "msedge", "opera", "brave", "yandex", "zen"]):
            if any(x in title_low for x in ["github", "gitlab", "stackoverflow", "habr", "хабр", "docs."]):
                return "coding", "Хабр / Документация"
            return "browser", "Браузер"

        # Игнорируемые системные процессы и экран блокировки
        if any(x in exe_low for x in ["explorer", "taskmgr", "lockapp", "shellexperiencehost", "searchhost"]):
            return "quiet", "Рабочий стол"

        clean_name = exe_name.replace(".exe", "").capitalize() if exe_name else "Система"
        return "other", clean_name

    def record_sample(self, exe_name: str, title: str, seconds: float = 5.0):
        """
        Добавляет один квант времени активности к сегодняшнему дню.
        """
        category, app_name = self.categorize_app(exe_name, title)
        today = datetime.date.today().isoformat()

        with self.data_lock:
            self._ensure_today_exists()
            day_record = self.data[today]

            # Накапливаем категорию
            cats = day_record.setdefault("categories", {})
            cats[category] = cats.get(category, 0) + int(seconds)

            # Накапливаем приложение
            if category != "quiet":
                apps = day_record.setdefault("apps", {})
                apps[app_name] = apps.get(app_name, 0) + int(seconds)
                day_record["total_seconds"] = day_record.get("total_seconds", 0) + int(seconds)

            day_record["last_updated"] = datetime.datetime.now().isoformat()

        if time.time() - self.last_saved_time >= self.save_interval:
            self._save_data()

    def get_recent_summary(self, days: int = 2) -> dict:
        """
        Возвращает агрегированную статистику за последние N дней (по умолчанию вчера и сегодня).
        """
        today = datetime.date.today()
        dates_to_check = [(today - datetime.timedelta(days=i)).isoformat() for i in range(days)]

        agg_cats = {}
        agg_apps = {}
        total_sec = 0

        with self.data_lock:
            for d in dates_to_check:
                if d in self.data:
                    record = self.data[d]
                    for cat, sec in record.get("categories", {}).items():
                        agg_cats[cat] = agg_cats.get(cat, 0) + sec
                    for app, sec in record.get("apps", {}).items():
                        agg_apps[app] = agg_apps.get(app, 0) + sec
                    total_sec += record.get("total_seconds", 0)

        # Определяем доминирующую категорию (исключая 'quiet' и 'other' если есть содержательные)
        meaningful_cats = {
            k: v for k, v in agg_cats.items()
            if k not in ["quiet", "other"] and v > 60
        }

        if meaningful_cats:
            dominant_category = max(meaningful_cats, key=meaningful_cats.get)
        elif agg_cats.get("other", 0) > 120:
            dominant_category = "other"
        else:
            dominant_category = "quiet"

        # Топ-3 приложений по времени
        sorted_apps = sorted(agg_apps.items(), key=lambda x: x[1], reverse=True)[:4]

        return {
            "dominant_category": dominant_category,
            "category_times": agg_cats,
            "top_apps": sorted_apps,
            "total_seconds": total_sec
        }

    @staticmethod
    def format_duration(seconds: int) -> str:
        mins = int(seconds // 60)
        hours = int(mins // 60)
        mins = mins % 60
        if hours > 0 and mins > 0:
            return f"{hours} ч {mins} мин"
        if hours > 0:
            return f"{hours} ч"
        return f"{max(mins, 1)} мин"

    def get_recent_summary_text(self) -> str:
        """
        Формирует лаконичный, человекочитаемый текст для подстановки в промпт LLM
        и формулу сна Акиры.
        """
        summary = self.get_recent_summary(days=2)
        dom_cat = summary["dominant_category"]
        top_apps = summary["top_apps"]
        total_sec = summary["total_seconds"]

        if total_sec < 180 or not top_apps:
            return "За последнее время за компьютером было тихо, открытых программ почти не было (время цифровой паузы)."

        dom_name = self.CATEGORIES.get(dom_cat, dom_cat)
        app_strings = [
            f"{app} ({self.format_duration(sec)})"
            for app, sec in top_apps
            if sec >= 60
        ]
        apps_desc = ", ".join(app_strings) if app_strings else "различные программы"

        return (
            f"За последнее время пользователь в основном был занят: {apps_desc}. "
            f"Доминирующая категория активности: {dom_name}."
        )

    def _track_loop(self):
        """Фоновый цикл опроса активного окна Windows."""
        while self.running:
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                title = ""
                exe_name = ""

                if hwnd:
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value

                    pid = ctypes.c_ulong(0)
                    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value > 0:
                        try:
                            proc = psutil.Process(pid.value)
                            exe_name = proc.name().lower()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            exe_name = ""

                self.record_sample(exe_name, title, seconds=self.sample_interval)
            except Exception:
                pass

            time.sleep(self.sample_interval)

    def start(self):
        """Запускает фоновый поток отслеживания."""
        with self.data_lock:
            if self.running:
                return
            self.running = True
            self.thread = threading.Thread(target=self._track_loop, name="ActivityTrackerThread", daemon=True)
            self.thread.start()
            print("[ActivityTracker]: Фоновый трекер активности успешно запущен")

    def stop(self):
        """Останавливает фоновый поток и сбрасывает данные на диск."""
        if not self.running:
            return
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self._save_data()
        print("[ActivityTracker]: Фоновый трекер активности сохранён и остановлен")


# Экземпляр синглтона
activity_tracker = ActivityTracker()
