import sys

if sys.platform == "win32":
    from services.vpn.adapters.gui_adapter_win import GuiAdapter
else:
    from services.vpn.adapters.gui_adapter_linux import GuiAdapter

__all__ = ["GuiAdapter"]
