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


def enable_window_acrylic(hwnd: int, hex_color: str = "25080805"):
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.windll.user32
        set_window_composition_attribute = user32.SetWindowCompositionAttribute
        set_window_composition_attribute.restype = c_int
        set_window_composition_attribute.argtypes = [c_void_p, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]

        color_int = int(hex_color, 16)

        accent = ACCENT_POLICY()
        accent.AccentState = 4
        accent.AccentFlags = 2
        accent.GradientColor = color_int
        accent.AnimationId = 0

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19
        data.Data = ctypes.cast(byref(accent), c_void_p)
        data.SizeOfData = sizeof(accent)

        set_window_composition_attribute(c_void_p(hwnd), byref(data))
    except Exception as e:
        try:
            accent = ACCENT_POLICY()
            accent.AccentState = 3
            accent.AccentFlags = 0
            accent.GradientColor = 0
            accent.AnimationId = 0

            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19
            data.Data = ctypes.cast(byref(accent), c_void_p)
            data.SizeOfData = sizeof(accent)

            set_window_composition_attribute(c_void_p(hwnd), byref(data))
        except Exception:
            pass