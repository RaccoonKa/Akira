"""
Windows-реализация платформозависимых системных команд.
Сохраняет историческое поведение WinAPI/cmd без каких-либо изменений.
"""

import os
import ctypes
import subprocess
import webbrowser


def lock_screen() -> str:
    os.system("rundll32.exe user32.dll,LockWorkStation")
    return "Экран заблокирован"


def sleep_mode() -> str:
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return "Перевожу компьютер в спящий режим"


def shutdown_system(delay_seconds: int = 5):
    os.system(f"shutdown /s /t {int(delay_seconds)}")


def restart_system(delay_seconds: int = 5) -> str:
    os.system(f"shutdown /r /t {int(delay_seconds)}")
    return "Перезагружаю компьютер"


def cancel_shutdown() -> str:
    os.system("shutdown /a")
    return "Отменила выключение компьютера!"


def open_calculator() -> str:
    subprocess.Popen("calc.exe")
    return "Открываю калькулятор"


def open_task_manager() -> str:
    subprocess.Popen("taskmgr.exe")
    return "Открываю диспетчер задач"


def open_discord() -> str:
    try:
        subprocess.Popen(["cmd", "/c", "start", "discord:"], shell=True)
    except Exception:
        discord_exe = os.path.expanduser(r"~\AppData\Local\Discord\Update.exe")
        if os.path.exists(discord_exe):
            subprocess.Popen([discord_exe, "--processStart", "Discord.exe"])
        else:
            webbrowser.open("https://discord.com/app")
    return "Запускаю Дискорд"


def open_telegram() -> str:
    telegram_exe = os.path.expanduser(r"~\AppData\Roaming\Telegram Desktop\Telegram.exe")
    if os.path.exists(telegram_exe):
        subprocess.Popen(telegram_exe)
    else:
        try:
            subprocess.Popen(["cmd", "/c", "start", "telegram:"], shell=True)
        except Exception:
            webbrowser.open("https://web.telegram.org")
    return "Открываю Телеграм"


def launch_mode_items(apps: list[str]):
    for item in apps:
        item = item.strip()
        if not item:
            continue
        if item.startswith("http://") or item.startswith("https://"):
            webbrowser.open(item)
        else:
            try:
                subprocess.Popen(item, shell=True)
            except Exception:
                pass


def get_recycle_bin_info() -> dict:
    try:
        from ctypes import wintypes

        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("i64Size", ctypes.c_int64),
                ("i64NumItems", ctypes.c_int64),
            ]

        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if res == 0:
            size_mb = round(info.i64Size / (1024 * 1024), 1)
            return {"num_items": int(info.i64NumItems), "size_bytes": int(info.i64Size), "size_mb": size_mb}
    except Exception as e:
        print(f"[RecycleBin Query Error]: {e}")
    return {"num_items": 0, "size_bytes": 0, "size_mb": 0.0}


def empty_recycle_bin() -> dict:
    try:
        info = get_recycle_bin_info()
        num = info["num_items"]
        size_mb = info["size_mb"]
        flags = 7  # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)

        if num > 0 or size_mb > 0:
            mb_str = f"{int(size_mb)}" if size_mb.is_integer() else f"{size_mb}"
            msg = f"Очистила корзину! Освободила {mb_str} МБ ✨"
        else:
            msg = "Корзина уже была пуста, но я на всякий случай всё перепроверила ✨"

        return {"chat": msg, "voice": msg, "emotion": "happy"}
    except Exception as e:
        err_msg = f"Не удалось очистить корзину: {e}"
        return {"chat": err_msg, "voice": "Не удалось очистить корзину.", "emotion": "sad"}
