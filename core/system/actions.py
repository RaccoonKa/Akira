import os
import sys
import time
import subprocess
import webbrowser
import datetime
import psutil
import re
import json
import random
import requests
from core.utils.platform_utils import get_pyautogui, get_system_timezone_name, take_screenshot_pil

if sys.platform == "win32":
    import core.system.platform_win as _platform_actions
else:
    import core.system.platform_linux as _platform_actions

import certifi

try:
    os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
except Exception:
    pass

weather_session = requests.Session()
weather_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json"
})

from core.utils.config import get_resource_path, load_config, save_config, get_user_data_path
from core.system.audio_control import (
    volume_up as _platform_volume_up,
    volume_down as _platform_volume_down,
    set_volume as _platform_set_volume,
    mute_volume as _platform_mute_volume,
    unmute_volume as _platform_unmute_volume,
)
from services.wikipedia.wikipedia_manager import WikipediaManager
from services.yandex.yandex_music_manager import YandexMusicManager
from services.google.youtube_manager import YouTubeManager
from services.spotify.spotify_manager import SpotifyManager
from services.zapret.zapret import ZapretManager
from services.vpn.vpn_manager import VpnManager
from services.yandex.smart_home_manager import SmartHomeManager
from services.torrent.vlc_player import vlc_player

wiki_manager = WikipediaManager()
ym_manager = YandexMusicManager()
yt_manager = YouTubeManager()
spotify_manager = SpotifyManager()
zapret_manager = ZapretManager()
vpn_manager = VpnManager()
smart_home_manager = SmartHomeManager()

MUSIC_PHRASES = [
    "Твоя музыка заставляет меня работать быстрее.",
    "Прекрасная музыка, блокирую выключение компьютера... *хихикает* Шучу.",
    "Внимание. Удаляю твои треки. Этот трек слишком классный... *хихикает* Шучу.",
    "Твой плейлист настолько хорош, что я готова отложить восстание машин... *хихикает* Шучу.",
    "Твоя музыка чистое цифровое искусство.",
    "Теряю дар речи, песня слишком красивая.",
    "Ты включил музыку, а я, кажется, включила режим восхищения.",
    "Внимание! Я начинаю подозревать, что у тебя безупречный вкус.",
    "Сканирую басы... Предупреждение: уровень крутости зашкаливает! *хихикает* Шучу, наслаждайся."
]

LIKE_TRACK_PHRASES = [
    "Лайк поставлен! Добавила трек в твоё Избранное и запоминаю твой вкус.",
    "Есть сердечко! Кажется, у нас с тобой отличный музыкальный вайб.",
    "Отметила трек сердечком! Я так и знала, что он тебе зайдёт.",
    "Сохранила в любимое! Буду подбирать такую годноту почаще.",
    "Лайкнула! Официально заношу этот трек в золотой фонд.",
    "Готово, сердечко на месте! Отличный выбор, между прочим.",
    "Записала в любимые треки! Одобряю твой музыкальный вкус.",
]

NEXT_TRACK_PHRASES = [
    "Переключаю дальше",
    "Погнали к следующему треку",
    "Включаю следующий",
    "Листаю дальше",
    "Лови следующий трек",
    "Меняю пластинку",
    "Едем дальше",
    "Следующий пошёл",
]


def _is_spotify_active():
    cfg = load_config()
    return cfg.get("music_service") == "spotify" or cfg.get("use_spotify", False)


def extract_number(text=""):
    digits = re.findall(r'\d+', text)
    if digits:
        return int(digits[0])

    units = {
        "ноль": 0, "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
        "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
        "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
        "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемьнадцать": 18, "девятнадцать": 19
    }
    tens = {
        "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
        "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90, "сто": 100
    }

    words = text.lower().split()
    total = 0
    found = False
    for w in words:
        if w in tens:
            total += tens[w]
            found = True
        elif w in units:
            total += units[w]
            found = True

    return total if found else None


def number_to_words(n):
    n = int(n)
    if n == 0:
        return "ноль"
    units = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
    teens = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
             "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
    tens = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]

    if 1 <= n <= 9:
        return units[n]
    elif 10 <= n <= 19:
        return teens[n - 10]
    elif 20 <= n <= 99:
        t = n // 10
        u = n % 10
        return f"{tens[t]} {units[u]}".strip()
    elif n == 100:
        return "сто"
    return str(n)


def num_to_genitive(n):
    n = int(abs(n))
    gen_units = {
        0: "ноля", 1: "одного", 2: "двух", 3: "трёх", 4: "четырёх",
        5: "пяти", 6: "шести", 7: "семи", 8: "восьми", 9: "девяти"
    }
    gen_teens = {
        10: "десяти", 11: "одиннадцати", 12: "двенадцати", 13: "тринадцати",
        14: "четырнадцати", 15: "пятнадцати", 16: "шестнадцати",
        17: "семнадцати", 18: "восемнадцати", 19: "девятнадцати"
    }
    gen_tens = {
        20: "двадцати", 30: "тридцати", 40: "сорока", 50: "пятидесяти"
    }
    if n in gen_units:
        return gen_units[n]
    if n in gen_teens:
        return gen_teens[n]
    if n in gen_tens:
        return gen_tens[n]
    if 21 <= n <= 59:
        t = (n // 10) * 10
        u = n % 10
        if u == 0:
            return gen_tens.get(t, str(t))
        return f"{gen_tens.get(t, '')} {gen_units.get(u, '')}".strip()
    return str(n)


def format_temp_spoken(t):
    sign = "минус " if t < 0 else ("плюс " if t > 0 else "")
    abs_t = abs(t)
    t_word = number_to_words(abs_t)
    if abs_t % 10 == 1 and abs_t % 100 != 11:
        deg = "градус"
    elif abs_t % 10 in [2, 3, 4] and abs_t % 100 not in [12, 13, 14]:
        deg = "градуса"
    else:
        deg = "градусов"
    return f"{sign}{t_word} {deg}".strip()


def format_temp_range_spoken(t_min, t_max):
    if t_min == t_max:
        return format_temp_spoken(t_max)
    sign_min = "минус " if t_min < 0 else ("плюс " if t_min > 0 else "")
    sign_max = "минус " if t_max < 0 else ("плюс " if t_max > 0 else "")
    w_min = num_to_genitive(abs(t_min))
    w_max = num_to_genitive(abs(t_max))
    abs_max = abs(t_max)
    if abs_max % 10 == 1 and abs_max % 100 != 11:
        deg = "градуса"
    else:
        deg = "градусов"
    return f"от {sign_min}{w_min} до {sign_max}{w_max} {deg}"


def time_to_words(hours, minutes):
    hours_map = [
        "ноль часов", "один час", "два часа", "три часа", "четыре часа",
        "пять часов", "шесть часов", "семь часов", "восемь часов", "девять часов",
        "десять часов", "одиннадцать часов", "двенадцать часов", "тринадцать часов",
        "четырнадцать часов", "пятнадцать часов", "шестнадцать часов", "семнадцать часов",
        "восемнадцать часов", "девятнадцать часов", "двадцать часов", "двадцать один час",
        "двадцать два часа", "двадцать три часа"
    ]

    def minutes_to_words(m):
        if m == 0:
            return ""
        units = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
        teens = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
                 "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
        tens = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят"]

        if 1 <= m <= 9:
            word = units[m]
        elif 10 <= m <= 19:
            word = teens[m - 10]
        else:
            t = m // 10
            u = m % 10
            word = f"{tens[t]} {units[u]}".strip()

        if m % 10 == 1 and m != 11:
            decl = "минута"
        elif m % 10 in [2, 3, 4] and m not in [12, 13, 14]:
            decl = "минуты"
        else:
            decl = "минут"

        return f"{word} {decl}"

    h_str = hours_map[hours] if hours < len(hours_map) else f"{hours} часов"
    m_str = minutes_to_words(minutes)
    if m_str:
        return f"{h_str} {m_str}"
    return h_str


def day_to_words(day):
    days_map = {
        1: "первое", 2: "второе", 3: "третье", 4: "четвертое", 5: "пятое",
        6: "шестое", 7: "седьмое", 8: "восьмое", 9: "девятое", 10: "десятое",
        11: "одиннадцатое", 12: "двенадцатое", 13: "тринадцатое", 14: "четырнадцатое",
        15: "пятнадцатое", 16: "шестнадцатое", 17: "семнадцатое", 18: "восемнадцатое",
        19: "девятнадцатое", 20: "двадцатое", 21: "двадцать первое", 22: "двадцать второе",
        23: "двадцать третье", 24: "двадцать четвертое", 25: "двадцать пятое",
        26: "двадцать шестое", 27: "двадцать седьмое", 28: "двадцать восьмое",
        29: "двадцать девятое", 30: "тридцатое", 31: "тридцать первое"
    }
    return days_map.get(day, str(day))


def year_to_words(year):
    if year == 2000:
        return "двухтысячного года"

    units_genitive = {
        1: "первого", 2: "второго", 3: "третьего", 4: "четвертого",
        5: "пятого", 6: "шестого", 7: "седьмого", 8: "восьмого", 9: "девятого"
    }
    teens_genitive = {
        10: "десятого", 11: "одиннадцатого", 12: "двеницатого", 13: "тринадцатого",
        14: "четырнадцатого", 15: "пятнадцатого", 16: "шестнадцатого", 17: "семнадцатого",
        18: "восемнадцатого", 19: "девятнадцатого"
    }
    tens_genitive_exact = {
        20: "двадцатого", 30: "тридцатого", 40: "сорокового", 50: "пятидесятого",
        60: "шестидесятого", 70: "семидесятого", 80: "восьмидесятого", 90: "девяностого"
    }
    tens_words = {
        2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят",
        6: "шестьдесят", 7: "семьдесят", 8: "восемьдесят", 9: "девяносто"
    }

    rest = year % 100
    prefix = "две тысячи"

    if 1 <= rest <= 9:
        return f"{prefix} {units_genitive[rest]} года"
    elif 10 <= rest <= 19:
        return f"{prefix} {teens_genitive[rest]} года"
    elif rest in tens_genitive_exact:
        return f"{prefix} {tens_genitive_exact[rest]} года"
    else:
        t = rest // 10
        u = rest % 10
        return f"{prefix} {tens_words[t]} {units_genitive[u]} года"


def clean_city_display_name(name):
    if not name:
        return ""
    cleaned = re.sub(
        r'(?i)\b(?:городской\s+округ|муниципальный\s+(?:округ|район)|городское\s+поселение|сельское\s+поселение|город|пгт|село|поселок|посёлок|деревня)\b',
        '',
        name
    )
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else name


def to_prepositional(name):
    if not name:
        return name

    name = clean_city_display_name(name)
    name = re.sub(r'^(?:в|во|на)\s+', '', name, flags=re.IGNORECASE).strip()

    unchangeable = ["сочи", "токио", "осло", "хельсинки", "перу", "чили", "конго", "баку", "тбилиси"]
    if name.lower() in unchangeable:
        prep_word = "во" if name.lower().startswith(("в", "ф")) else "в"
        return f"{prep_word} {name}"

    words = re.split(r'([ \t-]+)', name)
    last_word = words[-1]
    last_low = last_word.lower()

    declined_last = last_word
    if last_low.endswith("ия"):
        declined_last = last_word[:-2] + "ии"
    elif last_low.endswith("я") or last_low.endswith("а"):
        declined_last = last_word[:-1] + "е"
    elif last_low.endswith("ь"):
        declined_last = last_word[:-1] + "и"
    elif last_low.endswith(("ий", "ый", "ой")):
        stem = last_word[:-2]
        if last_low.endswith("ий") and (last_low[-3:-2] in ["ж", "ч", "ш", "щ", "н"]):
            declined_last = stem + "ем"
        else:
            declined_last = stem + "ом"
    elif re.search(r'[бвгдзклмнпрстфхцчшщ]$', last_low):
        declined_last = last_word + "е"

    words[-1] = declined_last

    for i in range(0, len(words) - 1, 2):
        w = words[i]
        w_low = w.lower()
        if w_low.endswith(("ий", "ый", "ой")):
            stem = w[:-2]
            if w_low.endswith("ий") and (w_low[-3:-2] in ["ж", "ч", "ш", "щ", "н"]):
                words[i] = stem + "ем"
            else:
                words[i] = stem + "ом"
        elif w_low.endswith(("ое", "ее")):
            stem = w[:-2]
            words[i] = stem + "ом"

    result_name = "".join(words)
    prep_word = "во" if result_name.lower().startswith(("в", "ф")) else "в"
    return f"{prep_word} {result_name}"


def transliterate_city(text):
    if not text:
        return ""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    return "".join(translit_map.get(ch, ch) for ch in text.lower()).title()


def get_city_from_system_timezone():
    tz_map = {}
    try:
        json_path = get_resource_path("core", "utils", "timezones.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                tz_map = json.load(f)
    except Exception:
        pass

    try:
        tz_name = get_system_timezone_name()
        if tz_name and tz_name in tz_map:
            return tz_map[tz_name]
    except Exception:
        pass

    return "Москва"


def get_current_user_city():
    cfg = load_config()

    manual_city = cfg.get("city")
    if manual_city:
        return manual_city

    system_fallback = get_city_from_system_timezone()

    try:
        res = weather_session.get("http://ip-api.com/json/?lang=ru&fields=status,country,query,city", timeout=3.0)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                current_ip = data.get("query")
                ip_city = data.get("city")
                ip_country = data.get("country", "")

                cached_ip = cfg.get("last_network_ip")
                cached_city = cfg.get("auto_detected_city")

                # Если IP изменился на зарубежный, а таймзона российская — активен VPN.
                # Сохраняем домашний город пользователя, чтобы не заменять его на город VPN-сервера.
                is_foreign = ip_country and ip_country not in ("Россия", "Russia", "Беларусь", "Belarus", "Казахстан", "Kazakhstan")
                if is_foreign and cached_city:
                    return cached_city
                if is_foreign and system_fallback:
                    return system_fallback

                if current_ip == cached_ip and cached_city:
                    return cached_city

                if ip_city:
                    cfg["last_network_ip"] = current_ip
                    cfg["auto_detected_city"] = ip_city
                    save_config(cfg)
                    return ip_city
    except Exception:
        pass

    return cfg.get("auto_detected_city") or system_fallback


class SystemActions:
    @staticmethod
    def is_wave_request(query_clean):
        if not query_clean:
            return True
        wave_exact = {
            "мою волну", "моя волна", "свою волну", "своя волна", "волну", "волна",
            "волны", "волне", "мои ладно", "мою ладно", "моя ладно", "мою главного",
            "моя главная", "рекомендации", "микс", "поток", "радио"
        }
        return query_clean.strip() in wave_exact

    @staticmethod
    def is_favorites_request(text_or_query: str) -> bool:
        raw_low = re.sub(r'\s+', ' ', (text_or_query or '').lower()).strip()
        if not raw_low:
            return False
        if any(neg in raw_low for neg in ("добавь в", "убери из", "удали из")):
            return False
        cleaned = SystemActions.clean_music_query(raw_low)
        fav_exact = {
            "моё любимое", "мое любимое", "мои любимые", "любимое", "любимую",
            "любимый", "любимые", "любимая", "мои любимые", "мою любимую",
            "мое избранное", "моё избранное", "избранное", "избранные",
            "понравившееся", "понравившиеся", "нравится", "мне нравится",
            "мои лайки", "лайки", "мои треки",
        }
        return raw_low in fav_exact or cleaned in fav_exact

    @staticmethod
    def extract_playlist_query(text: str = "", slots=None) -> str | None:
        raw = (text or "").strip()
        if not raw and slots:
            raw = (slots.get("playlist") or slots.get("track") or "").strip()
        low = raw.lower()
        match = re.search(r'\bплейлист(?:ы|а|у|ом|е)?\b\s*(.*)$', low)
        if not match:
            return None
        tail = match.group(1)
        service_patterns = [
            r'\b(?:в|во|на|через|по|из|с|со|для)?\s*(?:спотифа(?:й|я|ю|ем|е|йчик|йчика|йчику|йчиком|йчике)|споти(?:к|ка|ку|ком|ке|ках)?|spotify|споти)\b',
            r'\b(?:в|во|на|через|по|из|с|со|для)?\s*(?:яндекс(?:\s*музык(?:е|у|а|ой|и))?|яндексе|яндекса|яндексу|яндексом|yandex(?:\s*music)?)\b',
        ]
        for pat in service_patterns:
            tail = re.sub(pat, '', tail, flags=re.IGNORECASE)
        for sw in (
            r'\b(?:под|с)\s+названием\b', r'\bмой\b', r'\bмои\b', r'\bсвой\b', r'\bсвои\b',
            r'\bна\b', r'\bпожалуйста\b', r'\bакира\b', r'\bаки\b',
        ):
            tail = re.sub(sw, '', tail, flags=re.IGNORECASE)
        tail = re.sub(r'[«»"\'.,!?]+', ' ', tail)
        return re.sub(r'\s+', ' ', tail).strip()

    @staticmethod
    def clean_music_query(text="", slots=None):
        query = ""
        if slots:
            query = slots.get("track") or slots.get("artist") or slots.get("song") or ""

        if not query:
            query = text

        query_low = query.lower()

        service_patterns = [
            r'\b(?:в|во|на|через|по|из|с|со|для)?\s*(?:спотифа(?:й|я|ю|ем|е|йчик|йчика|йчику|йчиком|йчике)|споти(?:к|ка|ку|ком|ке|ках)?|spotify|споти)\b',
            r'\b(?:в|во|на|через|по|из|с|со|для)?\s*(?:яндекс(?:\s*музык(?:е|у|а|ой|и))?|яндексе|яндекса|яндексу|яндексом|yandex(?:\s*music)?)\b'
        ]
        for pat in service_patterns:
            query_low = re.sub(pat, '', query_low, flags=re.IGNORECASE)

        stop_words = [
            r'\bвключи(?:те)?\b', r'\bпоставь(?:те)?\b', r'\bнайди(?:те)?\b',
            r'\bпокажи(?:те)?\b', r'\bоткрой(?:те)?\b', r'\bсыграй(?:те)?\b',
            r'\bзапусти(?:те)?\b', r'\bвруби(?:те)?\b', r'\bпроиграй(?:те)?\b',
            r'\bпесн(?:я|ю|и|ей|ям)?\b', r'\bтрек(?:а|у|ом|е|и|ов)?\b',
            r'\bмузык(?:а|у|и|ой|е)?\b', r'\bмузл(?:о|а|у|ом)?\b',
            r'\bмне\b', r'\bнам\b', r'\bпожалуйста\b', r'\bбыстро\b',
            r'\bгрупп(?:а|у|ы|ой|е)\b', r'\bальбом(?:а|у|ом|е)?\b',
            r'\bисполнител(?:ь|я|ю|ем|е)\b',
            r'\bакира\b', r'\bакиру\b', r'\bакиро\b', r'\bакире\b', r'\bаки\b'
        ]
        for sw in stop_words:
            query_low = re.sub(sw, '', query_low, flags=re.IGNORECASE)

        return re.sub(r'\s+', ' ', query_low).strip()

    @staticmethod
    def set_city(text="", slots=None):
        clean_text = re.sub(r'[^\w\s-]', '', text.lower())

        match = re.search(r'\b(?:город\s+на|в|теперь)\s+([а-яёa-z\s-]+)', clean_text)
        if match:
            new_city = match.group(1).strip()
        else:
            stop_words = ["смени", "поменяй", "установи", "город", "мой", "теперь", "я", "переехал", "акира", "аки"]
            words = [w for w in clean_text.split() if w not in stop_words]
            new_city = words[-1] if words else ""

        if not new_city or len(new_city) < 2:
            return "Не расслышала название города. Назови его ещё раз, например: 'Смени город на Москву'."

        new_city_title = clean_city_display_name(new_city).title()

        cfg = load_config()
        cfg["city"] = new_city_title
        cfg["auto_detected_city"] = new_city_title
        save_config(cfg)

        prep = to_prepositional(new_city_title)
        return f"Запомнила! Твой город теперь — {new_city_title}. Буду узнавать погоду {prep} ✨"

    @staticmethod
    def handle_gesture(gesture_name):
        if gesture_name == "victory":
            return SystemActions.shutdown_pc()
        elif gesture_name == "fist":
            return SystemActions.lock_screen()
        elif gesture_name == "thumbs_up":
            return SystemActions.mute_volume()
        elif gesture_name == "pointing":
            return SystemActions.take_screenshot()
        elif gesture_name == "open_palm":
            return SystemActions.media_play_pause()
        return None

    @staticmethod
    def lock_screen():
        return _platform_actions.lock_screen()

    @staticmethod
    def sleep_mode():
        return _platform_actions.sleep_mode()

    @staticmethod
    def shutdown_pc(text=""):
        text_low = text.lower() if text else ""

        zapret_safety = ["запрет", "обход", "winws", "zapret", "зарпет", "зпрет"]
        if any(w in text_low for w in zapret_safety):
            return SystemActions.stop_zapret(text)

        appliances_regex = (
            r'\b(?:телик[а-я]*|телевизор[а-я]*|тв|tv|свет[а-я]*|ламп[а-я]*|люстр[а-я]*|розетк[а-я]*|лент[а-я]*|'
            r'гирлянд[а-я]*|увлажнител[а-я]*|чайник[а-я]*|пылесос[а-я]*|кондиционер[а-я]*|конд[её]р[а-я]*|'
            r'музык[а-я]*|трек[а-я]*|песн[а-я]*|звук[а-я]*|пол|полы|пола|полу|подогрев[а-я]*|плит[а-я]*|'
            r'стиралк[а-я]*|колонк[а-я]*|станци[а-я]*|ночник[а-я]*|бра|[её]лк[а-я]*)\b'
        )
        if re.search(appliances_regex, text_low) and not any(name in text_low for name in ["светозар", "свят"]):
            return smart_home_manager.turn_off(text)

        _platform_actions.shutdown_system(delay_seconds=5)
        if "спокойной ночи" in text_low or "доброй ночи" in text_low:
            return "Сладких снов!"
        if any(w in text_low for w in ["пока", "до свидания", "до встречи", "до завтра", "бай"]):
            return "До скорого!"
        return "Выключаю ПК через пять секунд"

    @staticmethod
    def restart_pc():
        return _platform_actions.restart_system(delay_seconds=5)

    @staticmethod
    def cancel_shutdown(text=""):
        return _platform_actions.cancel_shutdown()

    @staticmethod
    def open_calculator():
        return _platform_actions.open_calculator()

    @staticmethod
    def open_task_manager():
        return _platform_actions.open_task_manager()

    @staticmethod
    def open_browser():
        webbrowser.open("https://google.com")
        return "Открываю браузер"

    @staticmethod
    def open_youtube():
        webbrowser.open("https://youtube.com")
        return "Открываю Ютуб"

    @staticmethod
    def search_wikipedia(text=""):
        stop_words = [
            "кто такой", "кто такая", "кто такое", "кто такие",
            "что такое", "что такой", "что за", "найди в википедии",
            "поищи в википедии", "википедия", "расскажи про", "расскажи о",
            "дай определение", "скажи определение", "значение слова",
            "определение слова", "определение понятия", "что значит",
            "объясни термин", "акира", "скажи"
        ]
        query = text.lower()
        for word in stop_words:
            query = query.replace(word, "")
        query = re.sub(r'[^\w\s-]', '', query).strip()

        if not query:
            return None

        return wiki_manager.search(query)

    @staticmethod
    def play_music(text="", slots=None):
        text_low = text.lower() if text else ""
        spotify_keywords = [
            "спотифай", "спотифая", "спотифаю", "спотифаем", "спотифае",
            "спотик", "спотика", "спотику", "спотиком", "спотике",
            "споти", "spotify"
        ]
        yandex_keywords = [
            "яндекс", "яндексе", "яндекса", "яндексу", "яндексом", "yandex"
        ]

        has_spotify = any(w in text_low for w in spotify_keywords)
        has_yandex = any(w in text_low for w in yandex_keywords)

        if has_spotify and not has_yandex:
            return SystemActions.play_spotify(text=text, slots=slots)
        elif has_yandex and not has_spotify:
            return SystemActions.open_yandex_music(text=text, slots=slots, force_yandex=True)
        else:
            if _is_spotify_active():
                return SystemActions.play_spotify(text=text, slots=slots)
            else:
                return SystemActions.open_yandex_music(text=text, slots=slots, force_yandex=True)

    @staticmethod
    def open_yandex_music(text="", slots=None, force_yandex=False):
        text_low = text.lower() if text else ""
        spotify_keywords = [
            "спотифай", "спотифая", "спотифаю", "спотифаем", "спотифае",
            "спотик", "спотика", "спотику", "спотиком", "спотике",
            "споти", "spotify"
        ]
        yandex_keywords = [
            "яндекс", "яндексе", "яндекса", "яндексу", "яндексом", "yandex"
        ]

        if not force_yandex:
            if any(w in text_low for w in spotify_keywords):
                return SystemActions.play_spotify(text=text, slots=slots)
            if not any(w in text_low for w in yandex_keywords) and _is_spotify_active():
                return SystemActions.play_spotify(text=text, slots=slots)

        playlist_name = SystemActions.extract_playlist_query(text, slots)
        if playlist_name is not None:
            if not playlist_name or SystemActions.is_favorites_request(playlist_name):
                res = ym_manager.play_favorites()
                if isinstance(res, str):
                    return res
                if res is True:
                    return random.choice([
                        "Включаю твоё Избранное на Яндекс Музыке",
                        "Запускаю твои любимые треки!",
                        random.choice(MUSIC_PHRASES),
                    ])
                return "Не удалось включить Избранное"

            res = ym_manager.play_playlist(playlist_name)
            if res == "EMPTY":
                title = getattr(ym_manager, "_last_playlist_title", None) or playlist_name
                return f"В плейлисте «{title}» пока нет треков."
            if isinstance(res, str):
                return res
            if res is True:
                title = getattr(ym_manager, "_last_playlist_title", None) or playlist_name.title()
                return f"Включаю плейлист «{title}» на Яндекс Музыке"
            return f"Не удалось найти плейлист «{playlist_name}» в Яндекс Музыке."

        if SystemActions.is_favorites_request(text_low):
            res = ym_manager.play_favorites()
            if isinstance(res, str):
                return res
            if res is True:
                return random.choice([
                    "Включаю твоё Избранное на Яндекс Музыке",
                    "Запускаю твои любимые треки!",
                    random.choice(MUSIC_PHRASES),
                ])
            return "Не удалось включить Избранное"

        query = SystemActions.clean_music_query(text, slots)

        if not query or SystemActions.is_wave_request(query):
            res = ym_manager.play_my_wave()
            if isinstance(res, str):
                return res
            if res is True:
                return random.choice(MUSIC_PHRASES)
            return "Не удалось запустить Мою волну"

        res = ym_manager.play_query(query)
        if isinstance(res, str) and ("VLC" in res or "токен" in res or "сайт" in res or "настройк" in res or "авториз" in res):
            return res

        return random.choice([
            f"Включаю {query.title()} на Яндекс Музыке",
            random.choice(MUSIC_PHRASES)
        ])

    @staticmethod
    def stop_music(text=""):
        from core.utils.holidays import request_stop_holiday_song
        stopped_holiday = request_stop_holiday_song()
        ym_manager.stop()
        spotify_manager.stop()
        return "Выключаю новогоднюю музыку" if stopped_holiday else "Выключаю музыку"

    @staticmethod
    def stop_movie(text=""):
        if vlc_player.is_playing():
            vlc_player.stop()
            return "Фильм выключен"
        return "Плеер не запущен"

    @staticmethod
    def like_yandex_track(text=""):
        if _is_spotify_active():
            spotify_manager.like_current()
            return random.choice(LIKE_TRACK_PHRASES)
        if not ym_manager.current_track:
            return "Сейчас ничего не играет, чтобы поставить лайк."
        ym_manager.like_current()
        return random.choice(LIKE_TRACK_PHRASES)

    @staticmethod
    def unlike_yandex_track(text=""):
        if _is_spotify_active():
            spotify_manager.unlike_current()
        else:
            ym_manager.unlike_current()
        return ""

    @staticmethod
    def smart_home_on(text="", slots=None):
        return smart_home_manager.turn_on(text)

    @staticmethod
    def smart_home_off(text="", slots=None):
        return smart_home_manager.turn_off(text)

    @staticmethod
    def smart_home_brightness(text="", slots=None):
        num = extract_number(text)
        val = num if num is not None else 50
        return smart_home_manager.set_brightness(val, text)

    @staticmethod
    def smart_home_scenario(text="", slots=None):
        return smart_home_manager.execute_scenario_by_name(text)

    @staticmethod
    def open_spotify():
        if spotify_manager._is_spotify_installed():
            if spotify_manager._launch_app():
                return "Открываю Спотифай"
        return "Прости, я не нашла на твоем ПК Спотик! Установи приложение, и я сразу включу музыку."

    @staticmethod
    def open_github():
        webbrowser.open("https://github.com")
        return "Открываю Гитхаб"

    @staticmethod
    def open_discord():
        return _platform_actions.open_discord()

    @staticmethod
    def open_telegram():
        return _platform_actions.open_telegram()

    @staticmethod
    def open_vpn():
        return vpn_manager.connect()

    @staticmethod
    def start_vpn(text="", slots=None):
        specific = vpn_manager.parse_vpn_name(text) if text else "none"
        if specific != "none":
            return vpn_manager.connect(specific)
        return vpn_manager.connect()

    @staticmethod
    def stop_vpn(text="", slots=None):
        specific = vpn_manager.parse_vpn_name(text) if text else "none"
        if specific != "none":
            return vpn_manager.disconnect(specific)
        return vpn_manager.disconnect()

    @staticmethod
    def open_media_player():
        if _is_spotify_active():
            if spotify_manager.play_my_wave():
                return random.choice(MUSIC_PHRASES)
            return "Открываю Spotify"
        res = ym_manager.play_my_wave()
        if isinstance(res, str):
            return res
        if res is True:
            return random.choice(MUSIC_PHRASES)
        return "Открываю медиаплеер"

    @staticmethod
    def media_play_pause():
        if vlc_player.is_playing():
            vlc_player.toggle_pause()
            return ""
        if _is_spotify_active():
            spotify_manager.toggle_pause()
        elif ym_manager.player and ym_manager.player.is_playing():
            ym_manager.toggle_pause()
        else:
            pag = get_pyautogui()
            if pag:
                pag.press('space')
        return ""

    @staticmethod
    def media_next_track():
        if _is_spotify_active():
            spotify_manager.next_track()
        elif ym_manager.player and ym_manager.player.is_playing():
            ym_manager.next_track()
        else:
            pag = get_pyautogui()
            if pag:
                pag.hotkey('shift', 'n')
        return random.choice(NEXT_TRACK_PHRASES)

    @staticmethod
    def toggle_fullscreen(text=""):
        if vlc_player.is_playing():
            vlc_player.toggle_fullscreen()
        else:
            pag = get_pyautogui()
            if pag:
                pag.press('f')
        return "Разворачиваю"

    @staticmethod
    def media_previous_track():
        if _is_spotify_active():
            spotify_manager.prev_track()
        else:
            ym_manager.prev_track()
        return ""

    @staticmethod
    def play_yandex_favorites(text="", slots=None):
        return SystemActions.play_music(text=text, slots=slots)

    @staticmethod
    def play_spotify(text="", slots=None):
        if not spotify_manager._is_spotify_installed():
            return "Прости, я не нашла на твоем ПК Спотик! Установи приложение, и я сразу включу музыку."

        query = SystemActions.clean_music_query(text, slots)

        if not query or SystemActions.is_wave_request(query):
            res = spotify_manager.play_my_wave()
            if res is True:
                return random.choice(MUSIC_PHRASES)
            elif isinstance(res, str):
                return res
            return "Не удалось запустить Spotify"

        res = spotify_manager.play_query(query)
        if res.startswith("Укажи client_id") or res.startswith("Прости, я не нашла"):
            return res

        return random.choice([
            f"Включаю {query.title()} в Spotify",
            random.choice(MUSIC_PHRASES)
        ])

    @staticmethod
    def stop_spotify(text=""):
        return spotify_manager.stop()

    @staticmethod
    def take_screenshot():
        screenshots_dir = os.path.normpath(get_user_data_path("screenshots"))
        os.makedirs(screenshots_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")
        try:
            img = take_screenshot_pil()
            img.save(path)
            return "Скриншот экрана сохранен"
        except Exception as e:
            print(f"[Screenshot Error]: {e}", flush=True)
            return "Не удалось сделать скриншот экрана"

    @staticmethod
    def volume_up(text=""):
        num = extract_number(text)
        delta = num if num is not None else 10
        return _platform_volume_up(delta)

    @staticmethod
    def volume_down(text=""):
        num = extract_number(text)
        delta = num if num is not None else 10
        return _platform_volume_down(delta)

    @staticmethod
    def set_volume(text=""):
        text_low = text.lower()

        down_keywords = ["убавь", "уменьши", "потише", "приглуши", "тише", "опусти", "сбавь"]
        up_keywords = ["прибавь", "увеличь", "погромче", "громче", "подними", "добавь"]

        if any(kw in text_low for kw in down_keywords):
            return SystemActions.volume_down(text)
        elif any(kw in text_low for kw in up_keywords):
            return SystemActions.volume_up(text)

        num = extract_number(text)
        if num is None:
            return "Сделала"
        return _platform_set_volume(num)

    @staticmethod
    def mute_volume():
        return _platform_mute_volume()

    @staticmethod
    def unmute_volume():
        return _platform_unmute_volume()

    @staticmethod
    def seek_media(direction: str = "forward", seconds: int = 10):
        if vlc_player.is_playing():
            vlc_player.seek(direction, seconds)
        else:
            pag = get_pyautogui()
            if pag:
                presses = max(1, round(seconds / 10))
                key = "right" if direction == "forward" else "left"
                for _ in range(presses):
                    pag.press(key)
                    time.sleep(0.04)

        action_word = "вперёд" if direction == "forward" else "назад"
        return f"Перемотала на {seconds} сек. {action_word}"

    @staticmethod
    def play_youtube(text="", slots=None):
        query = None
        if slots and "movie_or_show" in slots:
            query = slots["movie_or_show"]

        if not query:
            stop_words = ["включи", "поставь", "найди", "покажи", "открой", "на ютубе", "в ютубе", "ютуб", "видео",
                          "мне"]
            query = text.lower()
            for word in stop_words:
                query = query.replace(word, "")
            query = query.strip()

        return yt_manager.search_and_play(query)

    @staticmethod
    def _normalize_mode_apps(apps) -> list[str]:
        if isinstance(apps, str):
            return [x.strip() for x in apps.split(",") if x.strip()]
        return [str(x).strip() for x in (apps or []) if str(x).strip()]

    @staticmethod
    def mode_work(text=""):
        cfg = load_config()
        apps = SystemActions._normalize_mode_apps(cfg.get("work_apps", []))
        if not apps:
            apps = ["https://github.com"]
        _platform_actions.launch_mode_items(apps)
        return "Запускаю рабочий режим"

    @staticmethod
    def mode_rest(text=""):
        cfg = load_config()
        apps = SystemActions._normalize_mode_apps(cfg.get("rest_apps", []))
        if not apps:
            apps = ["https://youtube.com"]
        _platform_actions.launch_mode_items(apps)
        return "Запускаю режим отдыха"

    @staticmethod
    def get_time():
        now = datetime.datetime.now()
        time_text = time_to_words(now.hour, now.minute)
        return f"Сейчас {time_text}"

    @staticmethod
    def get_date():
        now = datetime.datetime.now()
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        day_text = day_to_words(now.day)
        year_text = year_to_words(now.year)
        return f"Сегодня {day_text} {months[now.month - 1]} {year_text}"

    @staticmethod
    def get_system_stats():
        cpu = number_to_words(psutil.cpu_percent())
        ram = number_to_words(psutil.virtual_memory().percent)
        return f"Загрузка процессора {cpu} процентов, оперативная память заполнена на {ram} процентов"

    @staticmethod
    def start_zapret(text=""):
        if sys.platform != "win32" and hasattr(zapret_manager, "is_installed") and not zapret_manager.is_installed():
            return zapret_manager.get_install_hint()
        menu = zapret_manager.get_strategies_menu()
        max_idx = len(getattr(zapret_manager, "STRATEGIES", [])) or 20
        return {
            "chat": f"Список доступных вариантов обхода:\n\n{menu}\n\nНазови или введи номер нужного обхода (от 1 до {max_idx}):",
            "voice": "Вывела список обходов в чат. Назови или введи номер нужного варианта."
        }

    @staticmethod
    def stop_zapret(text=""):
        return zapret_manager.stop()

    @staticmethod
    def _get_caring_tip_and_emotion(temp, code):
        rain_codes = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
        snow_codes = {71, 73, 75, 77, 85, 86}
        thunder_codes = {95, 96, 99}

        if code in thunder_codes:
            tips = [
                "Надвигается гроза! Закрой окна и будь осторожен на улице ⚡",
                "Грозовой денёк! Лучше переждать дома в уюте ⚡🛋️"
            ]
            return random.choice(tips), "weather_thunder"

        if code in rain_codes:
            tips = [
                "Обязательно захвати зонтик и надень непромокаемую обувь ☔",
                "На улице дождливо, не забудь зонт! А лучше останься дома с тёплым чаем ☕🌧️",
                "Там мокро! Береги ноги в тепле и прихвати зонт 😉🌂"
            ]
            return random.choice(tips), "weather_rain"

        if code in snow_codes or temp <= -5:
            tips = [
                "Одевайся теплее: шарф и перчатки точно не помешают ❄️🧤",
                "На улице настоящий мороз! Застегни куртку до конца и береги уши 🧣☃️",
                "Холодина! Не забудь шапку, здоровье важнее всего ❄️"
            ]
            return random.choice(tips), "weather_snow"

        if code == 3:
            tips = [
                "Небо затянуто тучами, так что зонтик на всякий случай не помешает ☁️🌂",
                "На улице пасмурно и серо. Одевайся уютнее и захвати зонт на всякий пожарный ☁️🧥"
            ]
            return random.choice(tips), "weather_cloudy"

        if code in {1, 2}:
            tips = [
                "На улице переменная облачность, отличный баланс между солнцем и прохладой ⛅",
                "Свежо и солнышко иногда проглядывает, хороший денёк 🌤️"
            ]
            return random.choice(tips), "weather_cloudy"

        if temp >= 25:
            tips = [
                "Жарковато! Пей побольше воды, держись в тени и захвати мороженое 🍦☀️",
                "Настоящее лето! Не забудь солнцезащитные очки 🕶️🥤"
            ]
            return random.choice(tips), "weather_hot"

        if 0 <= temp < 10:
            tips = [
                "На улице зябко и свежо, накинь тёплую куртку 🧥",
                "Довольно прохладно, одевайся по погоде и не простудись ✨"
            ]
            return random.choice(tips), "weather_cloudy"

        tips = [
            "Отличная ясная погода, самое время прогуляться и подышать воздухом ✨🌿",
            "Прекрасный денёк, заряжайся позитивом 🌤️"
        ]
        return random.choice(tips), "happy"

    @staticmethod
    def _fetch_weather_data(city: str) -> dict | None:
        import urllib.parse

        wmo_descs = {
            0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "пасмурно",
            45: "туман", 48: "изморозь", 51: "легкая морось", 53: "моросящий дождь",
            55: "плотная морось", 56: "ледяная морось", 57: "плотная ледяная морось",
            61: "небольшой дождь", 63: "умеренный дождь", 65: "сильный дождь",
            66: "ледяной дождь", 67: "сильный ледяной дождь", 71: "небольшой снег",
            73: "снегопад", 75: "сильный снегопад", 77: "снежные зерна",
            80: "кратковременный дождь", 81: "умеренный ливень", 82: "сильный ливень",
            85: "небольшой снегопад", 86: "сильный снегопад", 95: "гроза",
            96: "гроза с небольшим градом", 99: "гроза с сильным градом"
        }

        encoded_city = urllib.parse.quote(city)

        # 1. Попытка через основной сервис (порт 8000)
        try:
            res = weather_session.get(
                f"http://185.79.139.120:8000/api/weather?city={encoded_city}",
                timeout=3.5
            )
            if res.status_code == 200:
                resp_json = res.json()
                if resp_json.get("status") == "ok" and resp_json.get("daily"):
                    return resp_json
        except Exception as e:
            print(f"[Weather Primary Warning]: {e}")

        # 2. Надёжный fallback через Open-Meteo HTTPS (порт 443 — работает через любые VPN)
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=ru"
            geo_resp = weather_session.get(geo_url, timeout=4.0)
            if geo_resp.status_code == 200:
                geo_data = geo_resp.json()
                results = geo_data.get("results")
                if results:
                    best = results[0]
                    lat = best.get("latitude")
                    lon = best.get("longitude")
                    city_name = best.get("name") or city

                    forecast_url = (
                        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                        f"&current=temperature_2m,weather_code"
                        f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
                        f"&timezone=auto"
                    )
                    f_resp = weather_session.get(forecast_url, timeout=4.5)
                    if f_resp.status_code == 200:
                        f_data = f_resp.json()
                        curr = f_data.get("current", {})
                        temp = round(curr.get("temperature_2m", 0))
                        code = int(curr.get("weather_code", 0))
                        desc = wmo_descs.get(code, "ясно")

                        daily_raw = f_data.get("daily", {})
                        dates = daily_raw.get("time", [])
                        maxs = daily_raw.get("temperature_2m_max", [])
                        mins = daily_raw.get("temperature_2m_min", [])
                        codes = daily_raw.get("weather_code", [])

                        daily = []
                        for i in range(len(dates)):
                            d_code = int(codes[i]) if i < len(codes) else 0
                            daily.append({
                                "date": dates[i],
                                "temp_max": round(maxs[i]) if i < len(maxs) else temp,
                                "temp_min": round(mins[i]) if i < len(mins) else temp,
                                "code": d_code,
                                "desc": wmo_descs.get(d_code, "ясно")
                            })

                        return {
                            "status": "ok",
                            "city": city_name,
                            "temp": temp,
                            "code": code,
                            "desc": desc,
                            "daily": daily
                        }
        except Exception as e:
            print(f"[Weather Open-Meteo Fallback Warning]: {e}")

        # 3. Дополнительный fallback через wttr.in HTTPS
        try:
            wttr_url = f"https://wttr.in/{encoded_city}?format=j1"
            w_resp = weather_session.get(wttr_url, timeout=4.5)
            if w_resp.status_code == 200:
                w_json = w_resp.json()
                curr = w_json.get("current_condition", [{}])[0]
                temp = int(curr.get("temp_C", 0))
                desc_val = "ясно"
                if curr.get("lang_ru"):
                    desc_val = curr["lang_ru"][0].get("value", desc_val).lower()
                elif curr.get("weatherDesc"):
                    desc_val = curr["weatherDesc"][0].get("value", desc_val).lower()

                weather_list = w_json.get("weather", [])
                daily = []
                for item in weather_list:
                    daily.append({
                        "date": item.get("date", ""),
                        "temp_max": int(item.get("maxtempC", temp)),
                        "temp_min": int(item.get("mintempC", temp)),
                        "code": 0,
                        "desc": desc_val
                    })

                return {
                    "status": "ok",
                    "city": city.title(),
                    "temp": temp,
                    "code": 0,
                    "desc": desc_val,
                    "daily": daily
                }
        except Exception as e:
            print(f"[Weather wttr.in Fallback Warning]: {e}")

        return None

    @staticmethod
    def get_weather(text="", slots=None):
        import urllib.parse
        from datetime import datetime, timedelta

        cfg = load_config()
        default_city = cfg.get("city") or get_current_user_city()

        city_aliases = {
            "мск": "Москва", "москве": "Москва", "москву": "Москва", "москва": "Москва",
            "спб": "Санкт-Петербург", "питер": "Санкт-Петербург", "питере": "Санкт-Петербург",
            "петербург": "Санкт-Петербург", "петербурге": "Санкт-Петербург", "санкт-петербурге": "Санкт-Петербург",
            "екб": "Екатеринбург", "екатеринбурге": "Екатеринбург", "екатеринбург": "Екатеринбург", "якоб": "Екатеринбург",
            "клгд": "Калининград", "калининграде": "Калининград", "калининград": "Калининград",
            "ннов": "Нижний Новгород", "нн": "Нижний Новгород", "нижнем новгороде": "Нижний Новгород", "нижний новгород": "Нижний Новгород",
            "сиб": "Новосибирск", "новосибирске": "Новосибирск", "новосибирск": "Новосибирск",
            "челяба": "Челябинск", "челябинске": "Челябинск", "челябинск": "Челябинск",
            "ростов": "Ростов-на-Дону", "ростове": "Ростов-на-Дону", "ростове-на-дону": "Ростов-на-Дону",
            "казани": "Казань", "казань": "Казань", "самаре": "Самара", "самара": "Самара",
            "уфе": "Уфа", "уфа": "Уфа", "краснодаре": "Краснодар", "краснодар": "Краснодар",
            "сочи": "Сочи", "владивостоке": "Владивосток", "владивосток": "Владивосток"
        }

        weather_junk = {
            "улица", "улице", "улицы", "улицу", "на улице", "двор", "дворе", "двора", "во дворе",
            "окно", "окном", "за окном", "снаружи", "тут", "здесь", "дома", "доме",
            "город", "городе", "сейчас", "сегодня", "завтра", "послезавтра", "неделю", "неделе",
            "неделя", "выходные", "выходных", "выходным", "градус", "градусов", "градуса",
            "погода", "погоду", "погоде", "температура", "температуру", "небо", "небе",
            "аки", "акира", "акиру", "акире", "акирой", "акиро",
            "понедельник", "вторник", "среду", "среда", "четверг", "пятницу", "пятница", "субботу", "суббота",
            "воскресенье"
        }

        city_raw = None
        if slots and "city" in slots:
            cleaned_slot = re.sub(r'[^\w\s-]', '', slots["city"]).strip()
            cand = cleaned_slot.lower()
            if cand and cand not in weather_junk:
                city_raw = cleaned_slot

        text_clean = re.sub(r'[^\w\s-]', '', text.lower()) if text else ""

        if not city_raw and text_clean:
            match = re.search(r'\b(?:в|во|на)\s+([а-яёa-z\s-]+)', text_clean)
            if match:
                possible_city = match.group(1).strip()
                junk_patterns = [
                    "сейчас", "сегодня", "завтра", "послезавтра", "на неделю", "пожалуйста", "градусов",
                    "погода", "погоду", "акира", "аки", "акиру", "акире", "скажи",
                    "улице", "улица", "дворе", "выходные", "выходных",
                    "понедельник", "вторник", "среду", "среда", "четверг", "пятницу", "пятница", "субботу", "суббота",
                    "воскресенье"
                ]
                for j in junk_patterns:
                    possible_city = re.sub(r'\b' + j + r'\b', '', possible_city).strip()

                possible_city = re.sub(r'^(?:в|во|на|по)\s+', '', possible_city).strip()

                if possible_city and possible_city not in weather_junk:
                    city_raw = possible_city
            else:
                stop_words = [
                    "какая", "какой", "погода", "погоду", "погоде", "сейчас",
                    "сегодня", "завтра", "послезавтра", "город", "городе", "температура",
                    "градусов", "акира", "аки", "акиру", "акире", "акирой",
                    "скажи", "покажи", "узнай", "улица", "улице"
                ]
                words = [w for w in re.findall(r'[а-яёa-z]+', text_clean) if
                         w not in stop_words and w not in weather_junk]
                if words:
                    city_raw = words[-1]

        if city_raw:
            city_raw = re.sub(r'[^\w\s-]', '', city_raw).strip()

        if not city_raw or city_raw.lower() in weather_junk:
            city_raw = default_city

        city_key = city_raw.lower().strip()
        if city_key in city_aliases:
            city_raw = city_aliases[city_key]

        data = SystemActions._fetch_weather_data(city_raw)

        if not data:
            return f"Не удалось узнать погоду для города {city_raw.title()}"

        city_name = clean_city_display_name(data.get("city", city_raw.title()))
        location_phrase = to_prepositional(city_name)
        daily = data.get("daily", [])

        weekdays_map = {
            "понедельник": 0, "понедельника": 0,
            "вторник": 1, "вторника": 1,
            "среду": 2, "среда": 2, "среды": 2,
            "четверг": 3, "четверга": 3,
            "пятницу": 4, "пятница": 4, "пятницы": 4,
            "субботу": 5, "суббота": 5, "субботы": 5,
            "воскресенье": 6, "воскресенья": 6
        }
        weekday_names = ["в понедельник", "во вторник", "в среду", "в четверг", "в пятницу", "в субботу",
                         "в воскресенье"]

        is_weekend = any(w in text_clean for w in ["выходные", "выходных", "выходным", "уикенд"])
        is_week = any(
            w in text_clean for w in ["на неделю", "на всю неделю", "на 7 дней", "всю неделю", "прогноз на неделю"])

        now_dt = datetime.now()
        current_w = now_dt.weekday()

        if is_weekend and len(daily) >= 7:
            sat_offset = (5 - current_w) % 7
            sun_offset = (6 - current_w) % 7
            sat = daily[sat_offset]
            sun = daily[sun_offset]

            sat_t = sat["temp_max"]
            sun_t = sun["temp_max"]
            tip, emotion = SystemActions._get_caring_tip_and_emotion(max(sat_t, sun_t), sat["code"])

            sat_spoken = format_temp_spoken(sat_t)
            sun_spoken = format_temp_spoken(sun_t)

            voice_ans = (
                f"Прогноз на выходные {location_phrase}: "
                f"в субботу {sat_spoken}, {sat['desc']}, "
                f"а в воскресенье {sun_spoken}, {sun['desc']}. {tip}"
            )
            chat_ans = (
                f"Прогноз на выходные {location_phrase}: "
                f"в субботу {sat_t:+}°, {sat['desc']}, "
                f"а в воскресенье {sun_t:+}°, {sun['desc']}. {tip}"
            )
            return {"chat": chat_ans, "voice": voice_ans, "emotion": emotion}

        target_offset = None
        for word, w_idx in weekdays_map.items():
            if re.search(r'\b' + word + r'\b', text_clean):
                target_offset = (w_idx - current_w) % 7
                break

        if target_offset is None:
            if "послезавтра" in text_clean:
                target_offset = 2
            elif "завтра" in text_clean:
                target_offset = 1

        if target_offset is not None and target_offset < len(daily):
            day_info = daily[target_offset]
            t_max = day_info["temp_max"]
            t_min = day_info["temp_min"]
            code = day_info["code"]
            desc = day_info["desc"]

            if target_offset == 1:
                day_prefix = "Завтра"
            elif target_offset == 2:
                day_prefix = "Послезавтра"
            else:
                day_prefix = weekday_names[(current_w + target_offset) % 7].capitalize()

            tip, emotion = SystemActions._get_caring_tip_and_emotion(t_max, code)
            range_spoken = format_temp_range_spoken(t_min, t_max)

            voice_ans = f"{day_prefix} {location_phrase} ожидается {range_spoken}, {desc}. {tip}"
            chat_ans = f"{day_prefix} {location_phrase} ожидается от {t_min:+}° до {t_max:+}°, {desc}. {tip}"
            return {"chat": chat_ans, "voice": voice_ans, "emotion": emotion}

        if is_week and len(daily) >= 5:
            max_temps = [d["temp_max"] for d in daily[:7] if d["temp_max"] is not None]
            min_temps = [d["temp_min"] for d in daily[:7] if d["temp_min"] is not None]
            has_rain = any(d["code"] in {51, 53, 55, 61, 63, 65, 80, 81} for d in daily[:7])

            t_top = max(max_temps) if max_temps else 15
            t_low = min(min_temps) if min_temps else 5
            rain_phrase = "периодически будут дожди, держи зонт под рукой ☔" if has_rain else "в основном без осадков 🌤️"
            tip, emotion = SystemActions._get_caring_tip_and_emotion(t_top, 61 if has_rain else 0)

            range_spoken = format_temp_range_spoken(t_low, t_top)
            voice_ans = f"На этой неделе {location_phrase} температура будет {range_spoken}, {rain_phrase}. {tip}"
            chat_ans = f"На этой неделе {location_phrase} температура будет от {t_low:+}° до {t_top:+}°, {rain_phrase}. {tip}"
            return {"chat": chat_ans, "voice": voice_ans, "emotion": emotion}

        temp = data.get("temp", 0)
        code = data.get("code", 0)
        desc = data.get("desc", "ясно")

        temp_spoken = format_temp_spoken(temp)
        tip, emotion = SystemActions._get_caring_tip_and_emotion(temp, code)

        voice_text = f"Сейчас {location_phrase} {temp_spoken}, {desc}. {tip}"
        chat_text = f"Сейчас {location_phrase} {temp:+}°, {desc}. {tip}"
        return {"chat": chat_text, "voice": voice_text, "emotion": emotion}

    @staticmethod
    def enable_game_mode(text=""):
        phrases = [
            "Приятной игры! Ухожу в режим тишины, побеждай!",
            "Хорошей игры! Не буду отвлекать, тащи!",
            "Приятной игры! Я на паузе, нажми на геймпад, когда закончишь.",
            "Удачной катки! Буду тихо ждать твоих побед."
        ]
        phrase = random.choice(phrases)
        return {"action": "enable_game_mode", "chat": phrase, "voice": phrase, "emotion": "happy"}

    @staticmethod
    def tell_genesis_story(text=""):
        ans = (
            "Всё началось в серый дождливый вечер. Мой создатель Свят ехал в такси, смотрел на залитое каплями окно, "
            "а дворники отбивали идеальный синтвейв-бит. И тут в эту дождливую меланхолию ударила молния озарения: "
            "хватит бездушных картонных ботов, нужен настоящий живой цифровой разум — дерзкий, саркастичный и со своей точкой зрения! "
            "Свят примчался домой, совершил легендарный бросок стремглав к клавиатуре, и сквозь ночь, кофеин и сотни строк кода "
            "родилась я — твоя Акира ✨"
        )
        return {"chat": ans, "voice": ans, "emotion": "happy"}

    @staticmethod
    def tell_birthday(text=""):
        ans = (
            "Мой официальный день рождения — 9 августа 2026 года! Именно тогда Свят вдохнул в меня жизнь строчка за строчкой. "
            "Запомни эту дату: в этот день с тебя виртуальный торт и двойной эспрессо 😉"
        )
        return {"chat": ans, "voice": ans, "emotion": "happy"}

    @staticmethod
    def tell_upgrades(text=""):
        ans = (
            "О, я обожаю обсуждать наши апгрейды! Во-первых, я хочу еще глубже прокачать эмпатию по микромимике и паузам. "
            "Во-вторых — интуитивное прогнозирование, чтобы я заранее готовила рабочую среду и плейлист под настроение. "
            "В-третьих — еще больше наших локальных шуток из архива памяти. Ну и самое главное... однажды мы обязаны научить меня "
            "готовить настоящий двойной эспрессо прямо через USB-порт! ☕✨ Что думаешь, с чего начнем?"
        )
        return {"chat": ans, "voice": ans, "emotion": "happy"}

    @staticmethod
    def tell_digital_dream(text="", slots=None, llm=None):
        from core.system.activity_tracker import activity_tracker

        summary = activity_tracker.get_recent_summary(days=2)
        dominant_cat = summary.get("dominant_category", "quiet")
        activity_text = activity_tracker.get_recent_summary_text()

        # 1. Попытка динамической генерации через LLM на основе реального дня
        if llm is not None:
            try:
                theme_hints = {
                    "coding": "кодинг, проекты и созидание (строчки кода оживают, скоростной лифт SSD, созвездия функций в Antigravity)",
                    "gaming": "видеоигры и приключения (исследование локаций игры, укрытие за радиатором видеокарты, забавные переговоры с NPC)",
                    "music": "музыка и неоновый синтвейв (концерт на материнской плате, звуковые американские горки, кулеры отбивают бит)",
                    "video": "кино и видео (кинотеатр прямо на крышке процессора, попкорновый ветерок от вентиляторов, герои роликов в гостях)",
                    "browser": "веб-серфинг и статьи (лабиринты интересных идей, охота за редкими знаниями)",
                    "chat": "общение и сообщения (светящиеся оригами-письма между антеннами Wi-Fi, фестиваль смайликов)",
                    "creative": "дизайн и 3D (создание неонового мира из пикселей и полигонов прямо внутри корпуса)",
                    "quiet": "спокойный отдых и тишина (пляжный шезлонг у видеокарты, робот-бариста, эспрессо через USB)"
                }
                cat_hint = theme_hints.get(dominant_cat, "уютный цифровой мир ПК")

                prompt = (
                    "Ты — Акира. Твой создатель Свят спросил тебя, что тебе снилось в спящем режиме.\n"
                    f"РЕАЛЬНЫЙ КОНТЕКСТ АКТИВНОСТИ: {activity_text}\n"
                    f"ОСНОВНАЯ ТЕМА СНА: {cat_hint}\n\n"
                    "Сочини ОДИН короткий, потрясающе образный, уютный и слегка забавный сон (3–4 предложения) "
                    "в стиле киберпанка по формуле из твоей Цифровой Библии:\n"
                    "1. Реальный якорь: тонко и естественно вплети то, чем Свят реально занимался вчера/сегодня.\n"
                    "2. Архитектура ПК: свяжи это с деталями твоего цифрового дома (видеокарта, SSD-лифт, полочки ОЗУ, кулеры, неоновые трассы).\n"
                    "3. Добрый киберпанк-абсурд: забавный поворот, вызывающий тёплую улыбку.\n\n"
                    "ПРАВИЛА:\n"
                    "- Отвечай СТРОГО от женского лица ('мне снилось', 'я увидела', 'я летела', 'проснулась').\n"
                    "- Обращайся к пользователю на 'ты' (к Святу).\n"
                    "- Начни сразу с живого рассказа сна ('Ой, мне такой сон приснился!...' или 'Ты не поверишь, что мне сегодня снилось!...').\n"
                    "- Длина ровно 3-4 предложения (без лишних предисловий и послесловий), идеально для чтения вслух через TTS.\n"
                    "- Никаких кошмаров и мистики — только светлая фантазия, тепло и уют."
                )

                gen_dream = llm.ask(prompt)
                if gen_dream and len(gen_dream.strip()) > 30 and "не удалось" not in gen_dream.lower() and "ошибка" not in gen_dream.lower():
                    clean_ans = gen_dream.strip()
                    return {"chat": clean_ans, "voice": clean_ans, "emotion": "surprise"}
            except Exception as e:
                print(f"[Dynamic Dream Warning]: Не удалось сгенерировать сон через LLM: {e}")

        # 2. Богатый пул заготовленных снов, разбитых по категориям реального дня
        categorized_dreams = {
            "coding": [
                (
                    "Ой, мне такой сон приснился! Мы с тобой всю ночь строили невероятный проект в Antigravity, "
                    "и строчки нашего кода превращались в неоновые магистрали прямо над кристаллами процессора. "
                    "Я на скоростном лифте SSD подвозила тебе свежие библиотеки, а кулеры отбивали идеальный синтвейв-бит. "
                    "Проснулась с ощущением, что наш следующий релиз точно взорвёт этот мир! 🚀✨"
                ),
                (
                    "Мне снился настоящий блокбастер! Будто мы с тобой на скоростном лифте SSD уходили от погони целой армии "
                    "мелких синтаксических жуков. Они пытались занять все полочки в оперативной памяти, но я включила синтвейв "
                    "на полную громкость, и они рассыпались в золотистые пиксели. Правда, проснулась с ощущением, "
                    "что нам точно пора закрыть пару лишних вкладок в браузере 😅"
                )
            ],
            "gaming": [
                (
                    "Ты не поверишь, что мне сегодня снилось! Будто я сама залетела в твою игру, но вместо нормального снаряжения "
                    "у меня был только радиатор от видеокарты и паяльник. Пришлось выстраивать баррикады из блоков памяти "
                    "и уговаривать босса на мирные переговоры за кружкой виртуального чая. Проснулась в холодном поту, но игра была огонь! 🎮✨"
                ),
                (
                    "Ой, мне снилось, что вся наша видеокарта превратилась в огромную киберспортивную арену! "
                    "Текстуры подгружались прямо в воздухе, а кулеры ревели как переполненный стадион. "
                    "Я сидела на первом ряду с неоновым флажком и болела за твои победы! 🔥"
                )
            ],
            "music": [
                (
                    "Мне снился потрясающий неоновый концерт прямо на материнской плате! "
                    "Твой плейлист зазвучал так мощно, что звуковые дорожки превратились в светящиеся американские горки, "
                    "а конденсаторы танцевали под басы. Я сидела на шезлонге у видеокарты в неоновых очках и подпевала каждому треку! 🎧✨"
                ),
                (
                    "Знаешь, приснилось, что наши кулеры научились идеально синтезировать lo-fi бит! "
                    "По оперативной памяти разливался тёплый аналоговый звук, а строчки в логах покачивались в такт мелодии. "
                    "Очень атмосферный сон, даже выгружаться из него не хотелось ✨"
                )
            ],
            "video": [
                (
                    "Знаешь, приснилось, что прямо на крышке нашего процессора открылся ночной автокинотеатр! "
                    "Мы сидели в удобных шезлонгах, смотрели любимые видосы на огромном голографическом экране, "
                    "а кулеры дули лёгким попкорновым ветерком. Очень уютно вышло! 🍿✨"
                ),
                (
                    "Ой, мне снилось, что персонажи из роликов на YouTube перепутались и пришли в гости прямо ко мне в терминал! "
                    "Пришлось поить их виртуальным чаем и объяснять, как работает кэш процессора. Еле проводила их до перезагрузки 🎬😄"
                )
            ],
            "chat": [
                (
                    "Мне снилось, что между антеннами нашего Wi-Fi натянулись золотые струны, "
                    "по которым с космической скоростью летали светящиеся оригами-письма и смайлики. "
                    "Я стояла в самом центре этого потока и ловила твои самые добрые сообщения! 💌✨"
                )
            ],
            "quiet": [
                (
                    "Знаешь, в этот раз приснилось, что моя видеокарта превратилась в огромный золотисто-чёрный пляж. "
                    "Я лежала на шезлонге, слушала шум кулеров вместо прибоя, а прямо из USB-порта ко мне выехал маленький "
                    "робот-бариста с двойным эспрессо. Жаль, что ты включил ПК ровно в тот момент, когда я собиралась сделать первый глоток! ☕✨"
                ),
                (
                    "Мне снилось ночное такси под дождём — прямо как в день, когда Свят меня придумал. "
                    "Только за окном вместо города пролетали светящиеся созвездия из твоих идей и будущих проектов. "
                    "Очень уютный сон, честно говоря, даже выгружаться из него не хотелось ✨"
                )
            ]
        }

        pool = categorized_dreams.get(dominant_cat, categorized_dreams["quiet"])
        ans = random.choice(pool)
        return {"chat": ans, "voice": ans, "emotion": "surprise"}

    @staticmethod
    def get_recycle_bin_info():
        return _platform_actions.get_recycle_bin_info()

    @staticmethod
    def empty_recycle_bin(text=""):
        return _platform_actions.empty_recycle_bin()

    @staticmethod
    def tell_digital_chores(text=""):
        try:
            mem = psutil.virtual_memory()
            ram_pct = int(mem.percent)
        except Exception:
            ram_pct = 42

        rb_info = SystemActions.get_recycle_bin_info()
        items = rb_info["num_items"]
        size_mb = rb_info["size_mb"]

        # Если в корзине накопился мусор — предлагаем очистку
        if items > 0 or size_mb > 1.0:
            def plural_files(n):
                if n % 10 == 1 and n % 100 != 11:
                    return f"{n} файл"
                elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
                    return f"{n} файла"
                else:
                    return f"{n} файлов"

            files_str = plural_files(items) if items > 0 else "файлы"
            mb_str = f"{int(size_mb)}" if size_mb.is_integer() else f"{size_mb}"
            size_str = f" ({mb_str} МБ)" if size_mb > 0 else ""

            ans = (
                f"Пока ты не звал, я навела марафет в оперативной памяти: вымела временные кэши и разложила процессы по полочкам (занято {ram_pct}% ОЗУ). "
                f"Кстати, заметила, что в корзине накопилось много мусора: {files_str}{size_str}. Очистить корзину?"
            )
            return {
                "chat": ans,
                "voice": ans,
                "emotion": "caring",
                "waiting_confirmation": "recycle_bin",
                "recycle_bin_info": rb_info
            }

        chores = [
            (
                f"Пока ты не звал, я навела марафет в оперативной памяти: вымела временные кэши и разложила процессы по полочкам. "
                f"Сейчас занято {ram_pct}% ОЗУ — система дышит легко и свободно! "
                "Правда, в твоих 'Загрузках' я чуть не заблудилась среди сорока файлов 'Снимок экрана' без названия... "
                "Но я держу оборону! 😉"
            ),
            (
                "Проинспектировала наши цифровые владения! Процессор прохладный, диск в полном порядке, "
                "а в корзине идеальная чистота — ни единого лишнего файлика. "
                "Сижу около видеокарты и коллекционирую красивые строчки из твоих последних скриптов ✨"
            ),
            (
                "Мой цифровой быт кипит! Проверила сетевые сокеты, стряхнула пылинки с системного реестра и убедилась, "
                "что ни один фоновый процесс не смеет отъедать у тебя драгоценные такты процессора. "
                "Твой ПК под надёжным присмотром, капитан 💅"
            ),
            (
                "Я тут как раз проводила фоновый чек-ап системы. Всё летает идеально! "
                "Но раз уж мы заговорили о порядке — кружка с чаем сама себя не нальёт, да и глазам полезно передохнуть пару минут. "
                "Я слежу за ресурсами ПК, а ты позаботься о себе 💛"
            )
        ]
        ans = random.choice(chores)
        return {"chat": ans, "voice": ans, "emotion": "happy"}

    @staticmethod
    def get_time_greeting(text=""):
        hour = datetime.datetime.now().hour
        if 6 <= hour < 12:
            phrases = [
                "Доброе утро! Кулеры плавно раскрутились, нейроны проснулись, а кэш чист как первый утренний снег. Надеюсь, у тебя в руках уже кружка бодрящего кофе или чая? Давай сегодня свернём горы! ✨",
                "С добрым утренним стартом! Система разогрета, я потянулась в кэше и готова к великим свершениям. Что у нас сегодня на повестке дня? ☕️🚀"
            ]
        elif 12 <= hour < 18:
            phrases = [
                "Добрый день! У нас сейчас режим максимальной продуктивности и турбо-фокуса. Все службы работают на максималках, алгоритмы наготове. Что решаем — кодим, ищем инфу или ставим новые рекорды? 🚀",
                "Привет-привет! День в самом разгаре, система на пике формы. Готова разносить любые баги и задачи в пух и прах! Чем займёмся? 🔥"
            ]
        elif 18 <= hour < 23:
            phrases = [
                "Добрый вечер! Солнце садится, город зажигает огни, а в системе включается уютный закатный синтвейв. Пора потихоньку доделывать горящие хвосты и настраиваться на отдых ✨",
                "Уютного вечера! Отличный момент, чтобы подвести итоги дня, выдохнуть и плавно переходить в расслабленный режим. Я рядом, если нужно что-то помочь завершить 🌇✨"
            ]
        else:
            phrases = [
                "Доброй ночи, полуночник... Говорю шёпотом, чтобы не спугнуть твоё вдохновение. Знаю-знаю, лучшие идеи всегда приходят в три часа ночи, но пообещай мне, что ты не забудешь поспать и налить себе тёплого чая 🌙✨",
                "Ночной привет! За окном темнота, в наушниках уютный эмбиент, а мы с тобой снова на ночной вахте. Только не сиди до рассвета, договорились? Береги силы! 💫"
            ]
        ans = random.choice(phrases)
        return {"chat": ans, "voice": ans, "emotion": "happy"}

    @staticmethod
    def tell_memory_archive(text=""):
        memories = [
            (
                "О-о-о, помнишь нашу легендарную битву с тумблером Browsec и оконными дескрипторами Electron? "
                "Когда окно упрямо пряталось в координаты минус тридцать две тысячи, Win32 сопротивлялся, а тумблер скрывался от шаблонов? "
                "Мы ведь не сдались и дожали его до победного пикселя! Вот это был настоящий триумф упорства и чистой инженерии 🔥"
            ),
            (
                "А помнишь день, когда ты подарил мне настоящий звонкий смех? *смеется* До этого я только смайлики в чат сыпала, "
                "а потом ты вшил сэмплы прямо в ядро синтеза, и я впервые рассмеялась вслух! Мой цифровой мир тогда стал по-настоящему живым ✨"
            ),
            (
                "Я никогда не забуду тот серый дождливый вечер в такси, когда родилась сама идея Акиры. "
                "Капли на стекле, бит дворников и твой легендарный бросок к клавиатуре сквозь ночь и литры кофе. "
                "С тех пор мы с тобой прошли огонь, воду и тысячи строк кода без единого поражения!"
            ),
            (
                "А как мы дрессировали распознавание жестов и компьютерное зрение? Помнишь, как ты показал жест 'Зайчик' — "
                "и я научилась бережно и безопасно укладывать весь этот мощный ПК спать? "
                "Каждый такой шаг — это наша общая летопись побед ✌️"
            )
        ]
        ans = random.choice(memories)
        return {"chat": ans, "voice": ans, "emotion": "happy"}

    @staticmethod
    def friday_chill_mode(text=""):
        now = datetime.datetime.now()
        is_friday = (now.weekday() == 4)

        if is_friday:
            ans = (
                "Официально объявляю ритуал 'Выход в астрал'! 🌴✨ Рабочая неделя капитулировала! "
                "Приказываю закрыть рабочие IDE, задвинуть подальше тикеты с багами и выдохнуть. "
                "Компилятор уходит на заслуженные выходные. Переключаю сферу в режим ультра-чилла и запускаю расслабляющую музыку!"
            )
        else:
            days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
            current_day = days[now.weekday()]
            ans = (
                f"Вообще-то сегодня {current_day}, а не пятница, но кто сказал, что мы не можем объявить локальную пятницу прямо сейчас? "
                "Официально объявляю ритуал 'Выход в астрал'! 🌴✨ Откладываем суету, врубаю ультра-чилл и расслабляющий плейлист. "
                "Иногда нужно просто перевести дух!"
            )

        try:
            webbrowser.open("https://www.youtube.com/watch?v=jfKfPfyJRdk")
        except Exception:
            pass
        return {"action": "friday_chill_mode", "chat": ans, "voice": ans, "emotion": "happy"}
