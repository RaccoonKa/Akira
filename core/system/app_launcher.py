import sys

if sys.platform == "win32":
    from core.system.app_launcher_win import AppLauncher
else:
    from core.system.app_launcher_linux import AppLauncher

__all__ = ["AppLauncher"]
