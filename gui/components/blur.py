import sys
import ctypes
from ctypes import c_int, c_void_p, Structure, sizeof, byref


class ACCENT_POLICY(Structure):
    _fields_ = [
        ('AccentState', c_int),
        ('AccentFlags', c_int),
        ('GradientColor', c_int),
        ('AnimationId', c_int)
    ]


class WINDOWCOMPOSITIONATTRIBDATA(Structure):
    _fields_ = [
        ('Attribute', c_int),
        ('Data', c_void_p),
        ('SizeOfData', c_int)
    ]


ACCENT_DISABLED = 0
ACCENT_ENABLE_GRADIENT = 1
ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4


def _apply_accent_policy(hwnd: int, accent_state: int, accent_flags: int = 0, color_int: int = 0) -> bool:
    if sys.platform != "win32" or not hwnd:
        return False

    try:
        user32 = ctypes.windll.user32
        set_window_composition_attribute = user32.SetWindowCompositionAttribute
        set_window_composition_attribute.restype = c_int
        set_window_composition_attribute.argtypes = [c_void_p, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]

        accent = ACCENT_POLICY()
        accent.AccentState = accent_state
        accent.AccentFlags = accent_flags
        accent.GradientColor = color_int
        accent.AnimationId = 0

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.cast(byref(accent), c_void_p)
        data.SizeOfData = sizeof(accent)

        res = set_window_composition_attribute(c_void_p(hwnd), byref(data))
        return bool(res)
    except Exception:
        return False


def enable_window_acrylic(hwnd: int, hex_color: str = "25080805"):
    if sys.platform != "win32" or not hwnd:
        return

    try:
        color_int = int(hex_color, 16)
    except (ValueError, TypeError):
        color_int = 0

    success = _apply_accent_policy(
        hwnd=hwnd,
        accent_state=ACCENT_ENABLE_ACRYLICBLURBEHIND,
        accent_flags=2,
        color_int=color_int
    )

    if not success:
        _apply_accent_policy(
            hwnd=hwnd,
            accent_state=ACCENT_ENABLE_BLURBEHIND,
            accent_flags=0,
            color_int=0
        )


def disable_window_acrylic(hwnd: int):
    if sys.platform != "win32" or not hwnd:
        return

    _apply_accent_policy(
        hwnd=hwnd,
        accent_state=ACCENT_DISABLED,
        accent_flags=0,
        color_int=0
    )