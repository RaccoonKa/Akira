"""
Linux-реализация платформозависимых системных команд (Linux Mint Cinnamon / FreeDesktop).
"""

import os
import shlex
import shutil
import subprocess
import threading
import webbrowser
from core.utils.platform_utils import open_path

_power_lock = threading.Lock()
_pending_power_timer: threading.Timer | None = None
_pending_power_action: str | None = None


def _spawn_detached(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def _run_ok(cmd: list[str], timeout: float = 3.0) -> bool:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode == 0
    except Exception:
        return False


def lock_screen() -> str:
    candidates = [
        ("cinnamon-screensaver-command", ["-l"]),
        ("loginctl", ["lock-session"]),
        ("xdg-screensaver", ["lock"]),
        (
            "dbus-send",
            [
                "--session", "--type=method_call",
                "--dest=org.cinnamon.ScreenSaver", "/org/cinnamon/ScreenSaver",
                "org.cinnamon.ScreenSaver.Lock",
            ],
        ),
        (
            "dbus-send",
            [
                "--session", "--type=method_call",
                "--dest=org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver",
                "org.freedesktop.ScreenSaver.Lock",
            ],
        ),
    ]
    for bin_name, args in candidates:
        exe = shutil.which(bin_name)
        if exe and _run_ok([exe, *args]):
            break
    return "Экран заблокирован"


def sleep_mode() -> str:
    candidates = [
        ("systemctl", ["suspend"]),
        (
            "dbus-send",
            [
                "--system", "--print-reply",
                "--dest=org.freedesktop.login1", "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager.Suspend", "boolean:true",
            ],
        ),
        ("loginctl", ["suspend"]),
    ]
    for bin_name, args in candidates:
        exe = shutil.which(bin_name)
        if exe and _run_ok([exe, *args]):
            break
    return "Перевожу компьютер в спящий режим"


def _execute_power_action(action: str):
    global _pending_power_timer, _pending_power_action
    with _power_lock:
        _pending_power_timer = None
        _pending_power_action = None

    if action == "reboot":
        candidates = [
            ("systemctl", ["reboot"]),
            (
                "dbus-send",
                [
                    "--system", "--print-reply",
                    "--dest=org.freedesktop.login1", "/org/freedesktop/login1",
                    "org.freedesktop.login1.Manager.Reboot", "boolean:true",
                ],
            ),
            ("shutdown", ["-r", "now"]),
        ]
    else:
        candidates = [
            ("systemctl", ["poweroff"]),
            (
                "dbus-send",
                [
                    "--system", "--print-reply",
                    "--dest=org.freedesktop.login1", "/org/freedesktop/login1",
                    "org.freedesktop.login1.Manager.PowerOff", "boolean:true",
                ],
            ),
            ("shutdown", ["-h", "now"]),
        ]

    for bin_name, args in candidates:
        exe = shutil.which(bin_name)
        if exe and _run_ok([exe, *args]):
            return


def schedule_power_action(action: str, delay_seconds: int = 5):
    """Планирует отменяемое выключение ('poweroff') или перезагрузку ('reboot')."""
    global _pending_power_timer, _pending_power_action
    delay = max(0, int(delay_seconds))
    with _power_lock:
        if _pending_power_timer is not None:
            _pending_power_timer.cancel()
            _pending_power_timer = None
        if delay == 0:
            _pending_power_action = None
            threading.Thread(target=_execute_power_action, args=(action,), daemon=True).start()
            return
        _pending_power_action = action
        timer = threading.Timer(float(delay), _execute_power_action, args=(action,))
        timer.daemon = True
        _pending_power_timer = timer
        timer.start()


def shutdown_system(delay_seconds: int = 5):
    schedule_power_action("poweroff", delay_seconds=delay_seconds)


def restart_system(delay_seconds: int = 5) -> str:
    schedule_power_action("reboot", delay_seconds=delay_seconds)
    return "Перезагружаю компьютер"


def cancel_shutdown() -> str:
    global _pending_power_timer, _pending_power_action
    with _power_lock:
        if _pending_power_timer is not None:
            _pending_power_timer.cancel()
            _pending_power_timer = None
        _pending_power_action = None

    shutdown_bin = shutil.which("shutdown")
    if shutdown_bin:
        _run_ok([shutdown_bin, "-c"], timeout=1.5)
    return "Отменила выключение компьютера!"


def _launch_first_available(binaries: list[str], extra_args: list[str] | None = None) -> bool:
    for name in binaries:
        exe = shutil.which(name) if not os.path.isabs(name) else (name if os.access(name, os.X_OK) else None)
        if exe:
            cmd = [exe, *(extra_args or [])]
            if _spawn_detached(cmd):
                return True
    return False


def open_calculator() -> str:
    _launch_first_available(["gnome-calculator", "galculator", "mate-calc", "kcalc", "qalculate-gtk", "xcalc"])
    return "Открываю калькулятор"


def open_task_manager() -> str:
    if not _launch_first_available([
        "gnome-system-monitor",
        "mate-system-monitor",
        "xfce4-taskmanager",
        "plasma-systemmonitor",
        "ksysguard",
    ]):
        for term in ("gnome-terminal", "x-terminal-emulator", "konsole", "xfce4-terminal"):
            term_exe = shutil.which(term)
            tool = shutil.which("btop") or shutil.which("htop") or shutil.which("top")
            if term_exe and tool:
                flag = "--" if term == "gnome-terminal" else "-e"
                if _spawn_detached([term_exe, flag, tool]):
                    break
    return "Открываю диспетчер задач"


def _is_flatpak_installed(app_id: str) -> bool:
    flatpak = shutil.which("flatpak")
    if not flatpak:
        return False
    return _run_ok([flatpak, "info", app_id], timeout=2.0)


def open_discord() -> str:
    if _launch_first_available(["discord", "discord-canary", "vesktop", "/snap/bin/discord"]):
        return "Запускаю Дискорд"
    if _is_flatpak_installed("com.discordapp.Discord"):
        flatpak = shutil.which("flatpak")
        if flatpak and _spawn_detached([flatpak, "run", "com.discordapp.Discord"]):
            return "Запускаю Дискорд"
    webbrowser.open("https://discord.com/app")
    return "Запускаю Дискорд"


def open_telegram() -> str:
    local_bins = [
        "telegram-desktop",
        "Telegram",
        "/snap/bin/telegram-desktop",
        os.path.expanduser("~/.local/share/TelegramDesktop/Telegram"),
        "/opt/telegram/Telegram",
    ]
    if _launch_first_available(local_bins):
        return "Открываю Телеграм"
    if _is_flatpak_installed("org.telegram.desktop"):
        flatpak = shutil.which("flatpak")
        if flatpak and _spawn_detached([flatpak, "run", "org.telegram.desktop"]):
            return "Открываю Телеграм"
    webbrowser.open("https://web.telegram.org")
    return "Открываю Телеграм"


def _launch_desktop_file(desktop_path: str) -> bool:
    gio = shutil.which("gio")
    if gio and _spawn_detached([gio, "launch", desktop_path]):
        return True
    try:
        with open(desktop_path, "r", encoding="utf-8", errors="ignore") as f:
            in_entry = False
            for line in f:
                s = line.strip()
                if s.startswith("["):
                    in_entry = (s == "[Desktop Entry]")
                    continue
                if in_entry and s.startswith("Exec="):
                    raw_exec = s[5:].strip()
                    parts = [p for p in shlex.split(raw_exec) if p not in {"%u", "%U", "%f", "%F", "%i", "%c", "%k"}]
                    if parts:
                        return _spawn_detached(parts)
    except Exception:
        pass
    return open_path(desktop_path)


def launch_mode_items(apps: list[str]):
    for item in apps:
        item = item.strip()
        if not item:
            continue
        if item.startswith(("http://", "https://")):
            webbrowser.open(item)
            continue
        if item.endswith(".desktop") and os.path.exists(item):
            _launch_desktop_file(item)
            continue
        if os.path.exists(item):
            if os.access(item, os.X_OK) and not os.path.isdir(item):
                if _spawn_detached([item]):
                    continue
            if item.endswith(".sh"):
                bash = shutil.which("bash") or "/bin/sh"
                if _spawn_detached([bash, item]):
                    continue
            open_path(item)
            continue
        try:
            parts = shlex.split(item)
            if parts and shutil.which(parts[0]):
                _spawn_detached(parts)
                continue
        except Exception:
            pass
        open_path(item)


def _get_trash_dir() -> str:
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(data_home, "Trash")


def _calc_path_size_bytes(path: str) -> int:
    if os.path.islink(path) or os.path.isfile(path):
        try:
            return os.lstat(path).st_size
        except OSError:
            return 0
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for fn in files:
            try:
                total += os.lstat(os.path.join(root, fn)).st_size
            except OSError:
                pass
        for dn in dirs:
            dp = os.path.join(root, dn)
            if os.path.islink(dp):
                try:
                    total += os.lstat(dp).st_size
                except OSError:
                    pass
    return total


def get_recycle_bin_info() -> dict:
    """Подсчитывает файлы и размер корзины по стандарту FreeDesktop.org Trash."""
    trash_files = os.path.join(_get_trash_dir(), "files")
    if not os.path.isdir(trash_files):
        return {"num_items": 0, "size_bytes": 0, "size_mb": 0.0}

    try:
        entries = os.listdir(trash_files)
        num_items = len(entries)
        size_bytes = sum(_calc_path_size_bytes(os.path.join(trash_files, name)) for name in entries)
        size_mb = round(size_bytes / (1024 * 1024), 1)
        return {"num_items": num_items, "size_bytes": int(size_bytes), "size_mb": size_mb}
    except Exception as e:
        print(f"[RecycleBin Query Error]: {e}")
        return {"num_items": 0, "size_bytes": 0, "size_mb": 0.0}


def empty_recycle_bin() -> dict:
    """Очищает ~/.local/share/Trash (files, info, directorysizes)."""
    try:
        info = get_recycle_bin_info()
        num = info["num_items"]
        size_mb = info["size_mb"]

        trash_dir = _get_trash_dir()
        for sub in ("files", "info"):
            sub_dir = os.path.join(trash_dir, sub)
            if os.path.isdir(sub_dir):
                for entry in os.listdir(sub_dir):
                    target = os.path.join(sub_dir, entry)
                    try:
                        if os.path.islink(target) or os.path.isfile(target):
                            os.unlink(target)
                        else:
                            shutil.rmtree(target)
                    except OSError:
                        pass

        dirsizes = os.path.join(trash_dir, "directorysizes")
        if os.path.isfile(dirsizes):
            try:
                os.unlink(dirsizes)
            except OSError:
                pass

        if num > 0 or size_mb > 0:
            mb_str = f"{int(size_mb)}" if size_mb.is_integer() else f"{size_mb}"
            msg = f"Очистила корзину! Освободила {mb_str} МБ ✨"
        else:
            msg = "Корзина уже была пуста, но я на всякий случай всё перепроверила ✨"

        return {"chat": msg, "voice": msg, "emotion": "happy"}
    except Exception as e:
        err_msg = f"Не удалось очистить корзину: {e}"
        return {"chat": err_msg, "voice": "Не удалось очистить корзину.", "emotion": "sad"}
