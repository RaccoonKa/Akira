import os
import re
import shutil
import subprocess
from core.utils.platform_utils import get_pyautogui

try:
    import pulsectl
    _HAS_PULSECTL = True
except ImportError:
    pulsectl = None
    _HAS_PULSECTL = False


def _run_c(cmd: list[str]) -> subprocess.CompletedProcess | None:
    try:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=2.0)
    except Exception:
        return None


def _change_volume_delta(delta: int) -> bool:
    if _HAS_PULSECTL:
        try:
            with pulsectl.Pulse("akira-volume") as pulse:
                sink_name = pulse.server_info().default_sink_name
                sink = pulse.get_sink_by_name(sink_name)
                cur = float(getattr(sink.volume, "value_flat", 0.5))
                target = max(0.0, min(1.0, cur + delta / 100.0))
                pulse.volume_set_all_chans(sink, target)
                return True
        except Exception:
            pass

    wpctl = shutil.which("wpctl")
    if wpctl:
        res = _run_c([wpctl, "get-volume", "@DEFAULT_AUDIO_SINK@"])
        if res and res.returncode == 0:
            m = re.search(r"Volume:\s*([0-9.]+)", res.stdout)
            if m:
                cur_pct = int(round(float(m.group(1)) * 100))
                new_pct = max(0, min(100, cur_pct + delta))
                set_res = _run_c([wpctl, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{new_pct}%"])
                if set_res and set_res.returncode == 0:
                    return True

    pactl = shutil.which("pactl")
    if pactl:
        res = _run_c([pactl, "get-sink-volume", "@DEFAULT_SINK@"])
        if res and res.returncode == 0:
            pcts = re.findall(r"(\d+)%", res.stdout)
            if pcts:
                cur_pct = int(pcts[0])
                new_pct = max(0, min(100, cur_pct + delta))
                set_res = _run_c([pactl, "set-sink-volume", "@DEFAULT_SINK@", f"{new_pct}%"])
                if set_res and set_res.returncode == 0:
                    return True

    amixer = shutil.which("amixer")
    if amixer:
        sign = "+" if delta >= 0 else "-"
        res = _run_c([amixer, "sset", "Master", f"{abs(delta)}%{sign}"])
        if res and res.returncode == 0:
            return True

    return False


def volume_up(delta: int = 10) -> str:
    if not _change_volume_delta(abs(delta)):
        pag = get_pyautogui()
        if pag:
            steps = max(1, delta // 2)
            for _ in range(steps):
                pag.press("volumeup")
    return "Сделала"


def volume_down(delta: int = 10) -> str:
    if not _change_volume_delta(-abs(delta)):
        pag = get_pyautogui()
        if pag:
            steps = max(1, delta // 2)
            for _ in range(steps):
                pag.press("volumedown")
    return "Сделала"


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    if _HAS_PULSECTL:
        try:
            with pulsectl.Pulse("akira-volume") as pulse:
                sink_name = pulse.server_info().default_sink_name
                sink = pulse.get_sink_by_name(sink_name)
                pulse.volume_set_all_chans(sink, level / 100.0)
                return "Сделала"
        except Exception:
            pass

    wpctl = shutil.which("wpctl")
    if wpctl:
        res = _run_c([wpctl, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{level}%"])
        if res and res.returncode == 0:
            return "Сделала"

    pactl = shutil.which("pactl")
    if pactl:
        res = _run_c([pactl, "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        if res and res.returncode == 0:
            return "Сделала"

    amixer = shutil.which("amixer")
    if amixer:
        _run_c([amixer, "sset", "Master", f"{level}%"])
    return "Сделала"


def _set_mute(muted: bool) -> bool:
    if _HAS_PULSECTL:
        try:
            with pulsectl.Pulse("akira-volume") as pulse:
                sink_name = pulse.server_info().default_sink_name
                sink = pulse.get_sink_by_name(sink_name)
                pulse.mute(sink, mute=muted)
                return True
        except Exception:
            pass

    wpctl = shutil.which("wpctl")
    if wpctl:
        res = _run_c([wpctl, "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if muted else "0"])
        if res and res.returncode == 0:
            return True

    pactl = shutil.which("pactl")
    if pactl:
        res = _run_c([pactl, "set-sink-mute", "@DEFAULT_SINK@", "1" if muted else "0"])
        if res and res.returncode == 0:
            return True

    amixer = shutil.which("amixer")
    if amixer:
        res = _run_c([amixer, "sset", "Master", "mute" if muted else "unmute"])
        if res and res.returncode == 0:
            return True

    return False


def mute_volume() -> str:
    if not _set_mute(True):
        pag = get_pyautogui()
        if pag:
            pag.press("volumemute")
    return "Выключаю звук"


def unmute_volume() -> str:
    if not _set_mute(False):
        pag = get_pyautogui()
        if pag:
            pag.press("volumemute")
    return "Включаю звук"
