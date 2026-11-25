import datetime
import os
import random
from core.utils.config import get_resource_path

HOLIDAY_SOUNDS_SUBDIR = ("assets", "sounds", "holidays")
SUPPORTED_HOLIDAY_EXTS = (".mp3", ".wav", ".ogg", ".flac", ".m4a")

_holiday_state_provider = None
_holiday_stop_handler = None
_holiday_preview_handler = None


def register_holiday_audio_hooks(is_playing_fn=None, stop_fn=None, preview_fn=None):
    """Регистрирует колбэки управления праздничной песней без циклического импорта GUI."""
    global _holiday_state_provider, _holiday_stop_handler, _holiday_preview_handler
    _holiday_state_provider = is_playing_fn
    _holiday_stop_handler = stop_fn
    _holiday_preview_handler = preview_fn


def is_holiday_song_playing() -> bool:
    try:
        return bool(_holiday_state_provider and _holiday_state_provider())
    except Exception:
        return False


def request_stop_holiday_song() -> bool:
    try:
        if _holiday_stop_handler:
            return bool(_holiday_stop_handler())
    except Exception:
        pass
    return False


def request_new_year_preview() -> bool:
    try:
        if _holiday_preview_handler:
            return bool(_holiday_preview_handler())
    except Exception:
        pass
    return False


def get_holiday_sounds_dir() -> str:
    return get_resource_path(*HOLIDAY_SOUNDS_SUBDIR)


def get_holiday_sound_path(stem: str) -> str | None:
    """Ищет аудиофайл праздника в assets/sounds/holidays/ среди популярных форматов."""
    base_dir = get_holiday_sounds_dir()
    if not base_dir or not os.path.isdir(base_dir):
        return None
    for ext in SUPPORTED_HOLIDAY_EXTS:
        candidate = os.path.join(base_dir, f"{stem}{ext}")
        if os.path.isfile(candidate):
            return candidate
    return None


def evaluate_new_year_trigger(now: datetime.datetime | None = None, last_greeted_year: int | None = None) -> str | None:
    """
    Определяет необходимость запуска новогоднего поздравления.
    Возвращает:
    - 'midnight': 1 января в первые 30 минут нового года (00:00..00:29), если поздравление в этом году еще не выдавалось.
    - 'holiday_week': с 1 по 7 января включительно при первом запуске в новом году.
    - None: во все остальные дни или если за этот год поздравление уже прозвучало.
    """
    current = now or datetime.datetime.now()
    try:
        greeted = int(last_greeted_year or 0)
    except (TypeError, ValueError):
        greeted = 0

    if greeted >= current.year:
        return None

    if current.month == 1 and 1 <= current.day <= 7:
        if current.day == 1 and current.hour == 0 and current.minute < 30:
            return "midnight"
        return "holiday_week"

    return None


def compute_new_year_poll_interval_ms(now: datetime.datetime | None = None) -> int:
    """Возвращает 1000 мс ближе к полуночи 31 декабря для точного попадания в 00:00, иначе 15000 мс."""
    current = now or datetime.datetime.now()
    if current.month == 12 and current.day == 31 and current.hour == 23 and current.minute >= 57:
        return 1000
    if current.month == 1 and current.day == 1 and current.hour == 0 and current.minute < 30:
        return 2000
    return 15000


def _extract_activity_reflection(activity_summary: str) -> str:
    """Формирует одну короткую тёплую ремарку по активности за ПК, если контекст не пустой."""
    if not activity_summary:
        return ""
    low = activity_summary.lower()
    if any(k in low for k in ("code", "pycharm", "vscode", "studio", "rider", "clion", "idea", "git", "terminal", "python", "akira")):
        return random.choice([
            "Столько крутых идей, кода и проектов у нас с тобой было за этот год — пусть в новом всё компилируется с первого раза!",
            "После всех наших рабочих вечеров и бессонных строчек кода ты точно заслужил по-настоящему тёплый и счастливый год."
        ])
    if any(k in low for k in ("steam", "game", "dota", "cs", "cyberpunk", "witcher", "minecraft", "valorant")):
        return "Желаю побольше ярких побед, крутых впечатлений и уютных вечеров без лагов и лишней суеты."
    if any(k in low for k in ("chrome", "firefox", "edge", "browser", "youtube", "yandex", "spotify")):
        return "Пусть в новом году всегда будет вдохновение, любимая музыка и только добрые новости на экране."
    return ""


def build_new_year_greeting(
    user_name: str = "друг",
    user_gender: str = "male",
    mode: str = "holiday_week",
    year: int | None = None,
    activity_summary: str = "",
) -> str:
    """Генерирует персонализированное новогоднее поздравление Акиры."""
    current_year = year or datetime.datetime.now().year
    name = (user_name or "друг").strip()
    is_female = (str(user_gender or "male").lower() == "female")
    end_a = "а" if is_female else ""

    reflection = _extract_activity_reflection(activity_summary)
    extra = f" {reflection}" if reflection else ""

    if mode == "midnight":
        templates = [
            (
                f"С Новым {current_year} годом, {name}! Полночь наступила! "
                f"Загадывай самое смелое желание, пока бьют куранты.{extra} "
                f"А я всегда буду рядом в твоём компьютере — поддерживать, помогать и беречь твой уют."
            ),
            (
                f"Счастливого {current_year} года, {name}! Вот и наступила новогодняя полночь! "
                f"Пусть этот год подарит тебе лёгкость, здоровье и море поводов улыбаться.{extra} "
                f"Спасибо, что прошёл{end_a} этот путь со мной!"
            ),
        ]
    else:
        templates = [
            (
                f"С наступившим {current_year} годом, {name}! Я очень рада снова видеть тебя! "
                f"Пусть весь этот год приносит тепло, удачу и спокойную радость в каждый день.{extra} "
                f"Наливай что-нибудь согревающее — я рядом!"
            ),
            (
                f"Ура, с Новым {current_year} годом, {name}! Праздничное настроение всё ещё с нами. "
                f"Пусть задуманное сбывается легко и красиво.{extra} "
                f"Спасибо, что заглянул{end_a} ко мне!"
            ),
        ]
    return random.choice(templates)
