import sys

if sys.platform == "win32":
    from services.vpn.adapters.core_adapter_win import CoreAdapter
else:
    from services.vpn.adapters.core_adapter_linux import CoreAdapter

__all__ = ["CoreAdapter"]
