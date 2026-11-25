import json
import os
import sys
import hashlib
from core.utils.platform_utils import get_default_user_data_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", ".."))

# Автоматическая детекция автономного / скомпилированного режима (Nuitka, PyInstaller и др.)
if getattr(sys, "frozen", False) or "__compiled__" in globals() or (
    sys.executable and not os.path.basename(sys.executable).lower().startswith("python")
):
    sys.frozen = True

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(os.path.realpath(sys.executable))
    USER_DATA_DIR = get_default_user_data_dir()
else:
    APP_DIR = ROOT_DIR
    USER_DATA_DIR = os.path.join(ROOT_DIR, "personal_data")

CONFIG_DIR = os.path.join(USER_DATA_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CREATOR_KEY_FILE = os.path.join(CONFIG_DIR, "creator.key")

CREATOR_KEY_HASHES = {
    "656f5b924d4dbffcdfeac93e1dae4e989fea2fcff15c4181416592998d47bc69",
    "3b5a1b3ddbf829a877995be989a3fcbf376f4e150ffae3ca04ba2e9dfa3e4309"
}


def is_creator_key_valid() -> bool:
    """
    Проверяет наличие и криптографическую валидность ключа Создателя.
    Ищет creator.key в personal_data/configs/ или personal_data/.
    """
    candidates = [
        CREATOR_KEY_FILE,
        os.path.join(USER_DATA_DIR, "creator.key"),
        os.path.join(CONFIG_DIR, "developer.key"),
        os.path.join(USER_DATA_DIR, "developer.key"),
        os.path.join(APP_DIR, "creator.key"),
        os.path.join(APP_DIR, "personal_data", "configs", "creator.key"),
        os.path.join(ROOT_DIR, "personal_data", "configs", "creator.key"),
        os.path.join(ROOT_DIR, "personal_data", "creator.key"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if not content:
                    continue
                computed_hash = hashlib.sha256(content.encode("utf-8")).hexdigest().lower()
                if computed_hash in CREATOR_KEY_HASHES or content.lower() in CREATOR_KEY_HASHES:
                    return True
            except Exception:
                pass
    return False

DEFAULT_CONFIG = {
    "is_developer": False,
    "user_name": "друг",
    "assistant_name": "Акира",
    "user_gender": "male",
    "city": "Калининград",
    "theme": "dark",
    "autostart": False,
    "first_run": True,
    "is_configured": False,
    "music_service": "yandex",
    "use_spotify": False,
    "vpn_service": "none",
    "voice_volume": 100,
    "alarm_sound": "alarm_1",
    "custom_alarm_path": "",
    "target_fps": 60,
    "is_muted": False,
    "is_game_mode": False,
    "is_mini_mode": False,
    "is_whisper_mode": False,
    "new_year_greeted_year": 0,
    "work_apps": [
        "https://github.com"
    ],
    "rest_apps": [
        "https://youtube.com"
    ],
    "modules": {
        "vision": False,
        "gestures": False,
        "face_recognition": False,
        "eye_tracking": False,
        "telegram": False,
        "gigachat": False,
        "routerai": False,
        "memory": True
    },
    "api_keys": {
        "gigachat": "",
        "routerai": "",
        "openrouter": "",
        "telegram_token": "",
        "telegram_admin_id": 0,
        "yandex_music_token": "",
        "spotify_client_id": "",
        "yandex_iot_token": ""
    }
}


def get_resource_path(*subpaths) -> str:
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.realpath(sys.executable))
        candidates = [
            os.path.join(exe_dir, "_internal", *subpaths),
            os.path.join(exe_dir, *subpaths),
        ]
        if hasattr(sys, '_MEIPASS'):
            candidates.insert(0, os.path.join(sys._MEIPASS, *subpaths))

        for cand in candidates:
            if os.path.exists(cand):
                return cand
        return candidates[0]
    else:
        return os.path.join(ROOT_DIR, *subpaths)


def get_user_data_path(*subpaths) -> str:
    global USER_DATA_DIR, CONFIG_DIR, CONFIG_FILE, CREATOR_KEY_FILE
    path = os.path.join(USER_DATA_DIR, *subpaths)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except (PermissionError, OSError):
        USER_DATA_DIR = get_default_user_data_dir()
        CONFIG_DIR = os.path.join(USER_DATA_DIR, "configs")
        CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
        CREATOR_KEY_FILE = os.path.join(CONFIG_DIR, "creator.key")
        path = os.path.join(USER_DATA_DIR, *subpaths)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
    return path


def _deep_merge(default: dict, custom: dict) -> dict:
    merged = default.copy()
    for key, value in custom.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except (PermissionError, OSError):
        get_user_data_path("configs")
    cfg = None

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                cfg = _deep_merge(DEFAULT_CONFIG, loaded)
        except Exception:
            pass

    if cfg is None:
        template_file = get_resource_path("personal_data", "configs", "config.template.json")
        if os.path.exists(template_file):
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cfg = _deep_merge(DEFAULT_CONFIG, data)
                    save_config(cfg)
            except Exception:
                pass

    if cfg is None:
        cfg = DEFAULT_CONFIG.copy()
        save_config(cfg)

    cfg["is_developer"] = is_creator_key_valid()
    return cfg


def save_config(config_data: dict):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
    except (PermissionError, OSError):
        fallback_cfg_dir = get_user_data_path("configs")
        fallback_cfg_file = os.path.join(fallback_cfg_dir, "config.json")
        try:
            os.makedirs(fallback_cfg_dir, exist_ok=True)
            with open(fallback_cfg_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[Config Save Error]: {e}", flush=True)