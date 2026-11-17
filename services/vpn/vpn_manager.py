import os
import re
import shutil
import psutil
from core.utils.config import load_config, save_config
from services.vpn.adapters.core_adapter import CoreAdapter
from services.vpn.adapters.gui_adapter import GuiAdapter


class VpnManager:
    VPN_ALIASES = {
        "browsec": [
            "browsec", "броусек", "браусек", "бросек", "браусик", "броусик",
            "browsec vpn", "броусек впн", "браусек впн", "бросек впн",
            "бровсек", "бровзек", "browzec"
        ],
        "sota": [
            "сота", "sota", "соту", "соте", "сотой", "соты", "сотовый",
            "sota vpn", "sota connect", "сота впн", "соту впн", "соте впн",
            "сото", "сома", "сона", "сопа", "с0та", "сота вп", "соточка",
            "сотка", "соты впн", "сота коннект", "сота соединение",
            "сота интернет", "салат", "салата", "салату", "салате",
            "салатом", "салаты", "салатик", "салату впн", "салат впн",
            "сорту", "сотру"
        ],
        "happ": [
            "happ", "хапп", "хэпп", "хепп", "хап", "хэп", "хеп", "хат",
            "хаппа", "хаппе", "хаппом", "хаппу", "happ vpn", "хапп впн", "хэпп впн",
            "хаб", "хабб", "хаппи", "хэппи", "хепи", "хапи", "хап впн",
            "хэп впн", "хеп впн", "хапп соединение", "хапп интернет",
            "хапп сервис"
        ],
        "v2ray": [
            "v2ray", "xray", "в2рей", "в2рай", "иксрей", "ви ту рэй", "ви ту рей",
            "виту рэй", "витурей", "витурэй", "v2ray vpn", "в2рей впн",
            "втурай", "втурэй", "витурай", "витурэй", "виту рай",
            "виту рей", "витурай впн", "витурэй впн", "втурея",
            "втурей", "втурый"
        ],
        "wireguard": [
            "wireguard", "вайргард", "вирегуард", "варгвард", "варгард", "варгарт",
            "вайргарда", "вайргарду", "вайргардом", "wireguard vpn",
            "вайргард впн", "вайргард сервис", "вайргард подключение",
            "вайргард интернет", "вайргуард", "вайргвард", "вайргарт",
            "вайргорд", "виргард", "виргуард", "вайргард соединение"
        ]
    }

    VPN_DISPLAY_NAMES = {
        "browsec": "Browsec",
        "sota": "Sota",
        "happ": "Happ",
        "v2ray": "V2Ray",
        "wireguard": "WireGuard"
    }

    GENERIC_VPN_TRIGGERS = [
        "впн", "vpn", "вэ пэ эн", "вэпээн", "випиэн", "ви пи эн", "впээн", "вэпэн",
        "вэпээн", "випиэн", "вэпэн", "випэн", "впнн", "вппн", "ввпн", "впм",
        "вбн", "фпн", "впэен", "впиэн"
    ]

    def __init__(self):
        self.core = CoreAdapter()
        self.gui = GuiAdapter()
        self.last_active_vpn = None

    def is_process_running(self, process_names: list) -> bool:
        """Проверяет, запущен ли хотя бы один процесс из списка."""
        low_names = [p.lower() for p in process_names]
        for proc in psutil.process_iter(['name']):
            try:
                pname = (proc.info['name'] or '').lower()
                if any(pname == target for target in low_names):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def detect_installed_vpns(self) -> list[str]:
        """Определяет, какие VPN-клиенты установлены в системе у пользователя."""
        installed = []

        # 1. Browsec
        try:
            if self.gui._find_browsec_target() or self.is_process_running(["browsec.exe", "browbox.exe", "browray.exe"]):
                installed.append("browsec")
        except Exception:
            pass

        # 2. Sota
        try:
            if self.gui._find_sota_target() or self.is_process_running(["sota connect.exe", "sotaconnect.exe", "sota.exe", "sotaconnectclient.exe"]):
                installed.append("sota")
        except Exception:
            pass

        # 3. Happ
        try:
            if self.gui._find_happ_target() or self.is_process_running(["happ.exe"]):
                installed.append("happ")
        except Exception:
            pass

        # 4. V2Ray / Xray
        try:
            if (os.path.exists(r"C:\v2ray\v2ray.exe")
                    or shutil.which("v2ray.exe")
                    or shutil.which("xray.exe")
                    or self.is_process_running(["v2ray.exe", "xray.exe"])):
                installed.append("v2ray")
        except Exception:
            pass

        # 5. WireGuard
        try:
            prog_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
            wg_path = os.path.join(prog_files, "WireGuard", "wireguard.exe")
            if (os.path.exists(wg_path)
                    or shutil.which("wireguard.exe")
                    or self.is_process_running(["wireguard.exe"])):
                installed.append("wireguard")
        except Exception:
            pass

        return installed

    def get_running_vpns(self) -> list[str]:
        """Возвращает список VPN-клиентов, которые запущены прямо сейчас."""
        running = []
        checks = [
            ("browsec", ["browsec.exe", "browbox.exe", "browray.exe"]),
            ("sota", ["sota connect.exe", "sotaconnect.exe", "sota.exe", "sotaconnectclient.exe"]),
            ("happ", ["happ.exe"]),
            ("v2ray", ["v2ray.exe", "xray.exe"]),
            ("wireguard", ["wireguard.exe"])
        ]
        for key, procs in checks:
            if key == "browsec" and self.gui.is_browsec_tunnel_active():
                running.append(key)
            elif self.is_process_running(procs):
                running.append(key)
        return running

    def get_configured_vpn(self) -> str:
        cfg = load_config()
        return cfg.get("vpn_service", "none").lower()

    def set_configured_vpn(self, vpn_type: str):
        cfg = load_config()
        cfg["vpn_service"] = vpn_type
        try:
            save_config(cfg)
        except Exception as e:
            print(f"[VpnManager Save Error]: {e}")

    def parse_vpn_name(self, text: str) -> str:
        text_low = text.lower().strip()
        for vpn_key, triggers in self.VPN_ALIASES.items():
            for trig in triggers:
                pattern = r'\b' + re.escape(trig) + r'\b' if ' ' not in trig else re.escape(trig)
                if re.search(pattern, text_low):
                    return vpn_key
        return "none"

    def is_generic_vpn_mention(self, text: str) -> bool:
        text_low = text.lower().strip()
        return any(re.search(r'\b' + re.escape(w) + r'\b', text_low) for w in self.GENERIC_VPN_TRIGGERS)

    def connect(self, specific_vpn: str = None) -> str:
        target = specific_vpn
        if not target or target == "none":
            installed = self.detect_installed_vpns()
            if len(installed) == 1:
                target = installed[0]
            else:
                target = self.get_configured_vpn()

        if target == "browsec":
            res = self.gui.connect_browsec()
            self.last_active_vpn = "browsec"
            return res
        elif target == "sota":
            res = self.gui.connect_sota()
            self.last_active_vpn = "sota"
            return res
        elif target == "happ":
            res = self.gui.connect_happ()
            self.last_active_vpn = "happ"
            return res
        elif target == "v2ray":
            res = self.core.connect_v2ray("C:\\v2ray\\v2ray.exe")
            self.last_active_vpn = "v2ray"
            return res
        elif target == "wireguard":
            res = self.core.connect_wireguard()
            self.last_active_vpn = "wireguard"
            return res
        else:
            return "none"

    def disconnect(self, specific_vpn: str = None) -> str:
        target = specific_vpn or self.last_active_vpn
        if not target or target == "none":
            running = self.get_running_vpns()
            if len(running) == 1:
                target = running[0]
            else:
                installed = self.detect_installed_vpns()
                if len(installed) == 1:
                    target = installed[0]
                else:
                    target = self.get_configured_vpn()

        if target == "browsec":
            res = self.gui.disconnect_browsec()
            self.last_active_vpn = None
            return res
        elif target == "sota":
            res = self.gui.disconnect_sota()
            self.last_active_vpn = None
            return res
        elif target == "happ":
            res = self.gui.disconnect_happ()
            self.last_active_vpn = None
            return res
        elif target == "v2ray":
            res = self.core.disconnect_v2ray()
            self.last_active_vpn = None
            return res
        elif target == "wireguard":
            res = self.core.disconnect_wireguard()
            self.last_active_vpn = None
            return res
        else:
            return "none"