import ctypes
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL, CoInitialize
from core.utils.platform_utils import get_pyautogui


def _get_endpoint_volume():
    try:
        CoInitialize()
    except Exception:
        pass
    devices = AudioUtilities.GetSpeakers()
    if hasattr(devices, "EndpointVolume"):
        return devices.EndpointVolume
    if hasattr(devices, "Activate"):
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
    if hasattr(devices, "_device") and hasattr(devices._device, "Activate"):
        interface = devices._device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
    return None


def volume_up(delta: int = 10) -> str:
    try:
        volume = _get_endpoint_volume()
        if volume:
            current_level = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            new_level = min(100, current_level + delta)
            volume.SetMasterVolumeLevelScalar(new_level / 100.0, None)
            return "Сделала"
    except Exception:
        pass

    pag = get_pyautogui()
    if pag:
        steps = max(1, delta // 2)
        for _ in range(steps):
            pag.press("volumeup")
    return "Сделала"


def volume_down(delta: int = 10) -> str:
    try:
        volume = _get_endpoint_volume()
        if volume:
            current_level = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            new_level = max(0, current_level - delta)
            volume.SetMasterVolumeLevelScalar(new_level / 100.0, None)
            return "Сделала"
    except Exception:
        pass

    pag = get_pyautogui()
    if pag:
        steps = max(1, delta // 2)
        for _ in range(steps):
            pag.press("volumedown")
    return "Сделала"


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    try:
        volume = _get_endpoint_volume()
        if volume:
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return "Сделала"
    except Exception:
        return "Сделала"


def mute_volume() -> str:
    pag = get_pyautogui()
    if pag:
        pag.press("volumemute")
    return "Выключаю звук"


def unmute_volume() -> str:
    pag = get_pyautogui()
    if pag:
        pag.press("volumemute")
    return "Включаю звук"
