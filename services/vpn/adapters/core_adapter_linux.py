"""
Linux-заглушка CoreAdapter: Windows CLI/реестровые сервисы (WireGuard, V2Ray, winreg proxy)
намеренно исключены из Linux-версии в пользу нативных GUI-клиентов Sota Connect, Browsec и Happ.
"""

import psutil


class CoreAdapter:
    UNSUPPORTED_WG_MSG = "WireGuard не поддерживается в Linux-версии Акиры (используй Sota Connect, Browsec или Happ)."
    UNSUPPORTED_V2RAY_MSG = "V2Ray не поддерживается в Linux-версии Акиры (используй Sota Connect, Browsec или Happ)."

    def __init__(self):
        pass

    def set_system_proxy(self, enable: bool, host: str = "127.0.0.1", port: int = 10809):
        pass

    def is_process_running(self, process_name: str) -> bool:
        target = (process_name or "").lower()
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == target:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def kill_process(self, process_name: str):
        target = (process_name or "").lower()
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == target:
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def connect_wireguard(self, tunnel_name: str = ""):
        return self.UNSUPPORTED_WG_MSG

    def disconnect_wireguard(self, tunnel_name: str = ""):
        return self.UNSUPPORTED_WG_MSG

    def connect_v2ray(self, v2ray_exe_path: str = "", config_path: str = ""):
        return self.UNSUPPORTED_V2RAY_MSG

    def disconnect_v2ray(self):
        return self.UNSUPPORTED_V2RAY_MSG
