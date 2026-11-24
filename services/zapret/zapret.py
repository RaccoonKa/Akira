import sys

if sys.platform == "win32":
    from services.zapret.zapret_win import ZapretManager
else:
    from services.zapret.zapret_linux import ZapretManager

__all__ = ["ZapretManager"]
