import os
import sys

if sys.platform == "win32":
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

    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMWCP_DEFAULT = 0
    DWMWCP_DONOTROUND = 1
    DWMWCP_ROUND = 2

    def _apply_win11_corner_preference(hwnd: int, preference: int) -> bool:
        if not hwnd:
            return False
        try:
            dwmapi = ctypes.WinDLL("dwmapi")
            pref = c_int(int(preference))
            res = dwmapi.DwmSetWindowAttribute(
                c_void_p(hwnd),
                DWMWA_WINDOW_CORNER_PREFERENCE,
                byref(pref),
                sizeof(pref),
            )
            return res == 0
        except Exception:
            return False

    def _apply_accent_policy(hwnd: int, accent_state: int, accent_flags: int = 0, color_int: int = 0) -> bool:
        if not hwnd:
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
else:
    from core.utils.platform_utils import is_wayland


def _apply_linux_kde_blur(win_id: int, enable: bool) -> bool:
    """
    Опциональный X11-blur для KDE/KWin (_KDE_NET_WM_BLUR_BEHIND_REGION).
    На Cinnamon / Muffin (где композитинг работает через WA_TranslucentBackground) безопасно пропускается.
    """
    if sys.platform == "win32" or not win_id or is_wayland() or not os.environ.get("DISPLAY"):
        return False

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" not in desktop and "plasma" not in desktop:
        return False

    try:
        from Xlib import Xatom
        from Xlib.display import Display
        disp = Display()
        try:
            atom_blur = disp.intern_atom("_KDE_NET_WM_BLUR_BEHIND_REGION")
            win = disp.create_resource_object("window", int(win_id))
            if enable:
                win.change_property(atom_blur, Xatom.CARDINAL, 32, [0])
            else:
                win.delete_property(atom_blur)
            disp.sync()
            return True
        finally:
            disp.close()
    except Exception:
        return False


def enable_window_acrylic(hwnd: int, hex_color: str = "25080805"):
    if not hwnd:
        return
    if sys.platform != "win32":
        _apply_linux_kde_blur(hwnd, enable=True)
        return

    try:
        color_int = int(hex_color, 16)
    except (ValueError, TypeError):
        color_int = 0

    _apply_win11_corner_preference(hwnd, DWMWCP_ROUND)

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
    if not hwnd:
        return
    if sys.platform != "win32":
        _apply_linux_kde_blur(hwnd, enable=False)
        return

    _apply_accent_policy(
        hwnd=hwnd,
        accent_state=ACCENT_DISABLED,
        accent_flags=0,
        color_int=0
    )
    _apply_win11_corner_preference(hwnd, DWMWCP_DEFAULT)
