import os
import py_compile
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class Stage5NetworkVpnTests(unittest.TestCase):
    def test_01_py_compile_stage5_files(self):
        files = [
            "core/nlp/generative/llm_provider.py",
            "services/vpn/adapters/core_adapter_win.py",
            "services/vpn/adapters/core_adapter_linux.py",
            "services/vpn/adapters/core_adapter.py",
            "services/vpn/adapters/gui_adapter_win.py",
            "services/vpn/adapters/gui_adapter_linux.py",
            "services/vpn/adapters/gui_adapter.py",
            "services/vpn/vpn_manager.py",
            "services/zapret/zapret_win.py",
            "services/zapret/zapret_linux.py",
            "services/zapret/zapret.py",
            "core/system/actions.py",
            "core/nlp/parser/command_parser.py",
        ]
        for rel in files:
            py_compile.compile(str(PROJECT_ROOT / rel), doraise=True)

    def test_02_all_modules_import_without_any_winreg_stub(self):
        saved_winreg = sys.modules.pop("winreg", None)
        try:
            self.assertNotIn("winreg", sys.modules)
            import core.nlp.generative.llm_provider as llm_mod
            import services.vpn.adapters.core_adapter as ca
            import services.vpn.adapters.gui_adapter as ga
            import services.vpn.vpn_manager as vm
            import services.zapret.zapret as zp
            import core.system.actions  # noqa: F401
            import core.nlp.parser.command_parser  # noqa: F401
            import services.telegram.telegram_bot  # noqa: F401
            import gui.windows.chat_window  # noqa: F401
            import gui.windows.settings_window  # noqa: F401
            import gui.dialogs.onboarding_wizard  # noqa: F401

            self.assertEqual(ca.CoreAdapter.__module__, "services.vpn.adapters.core_adapter_linux")
            self.assertEqual(ga.GuiAdapter.__module__, "services.vpn.adapters.gui_adapter_linux")
            self.assertEqual(zp.ZapretManager.__module__, "services.zapret.zapret_linux")
            self.assertTrue(hasattr(llm_mod, "_get_linux_physical_adapter_info"))
            self.assertEqual(vm.VpnManager.SUPPORTED_VPNS, ("browsec", "sota", "happ"))
        finally:
            if saved_winreg is not None:
                sys.modules["winreg"] = saved_winreg

    def test_03_gigachat_linux_physical_adapter_bypass(self):
        from core.nlp.generative import llm_provider as lp

        fake_route = "\n".join([
            "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask",
            "browbox-tun\t00000000\t0100100A\t0003\t0\t0\t10\t00000000",
            "wg0\t00000000\t00000000\t0001\t0\t0\t20\t00000000",
            "tun0\t00000000\t0108080A\t0003\t0\t0\t50\t00000000",
            "wlan0\t00000000\t0101A8C0\t0003\t0\t0\t600\t00000000",
            "enp3s0\t00000000\t0101A8C0\t0003\t0\t0\t100\t00000000",
        ])
        fake_addrs = {
            "browbox-tun": [types.SimpleNamespace(family=socket.AF_INET, address="10.16.0.2")],
            "tun0": [types.SimpleNamespace(family=socket.AF_INET, address="10.8.8.2")],
            "wlan0": [types.SimpleNamespace(family=socket.AF_INET, address="192.168.1.99")],
            "enp3s0": [types.SimpleNamespace(family=socket.AF_INET, address="192.168.1.50")],
        }
        fake_stats = {
            "browbox-tun": types.SimpleNamespace(isup=True),
            "tun0": types.SimpleNamespace(isup=True),
            "wlan0": types.SimpleNamespace(isup=True),
            "enp3s0": types.SimpleNamespace(isup=True),
        }

        with patch("os.path.isfile", return_value=True), \
             patch("builtins.open", mock_open(read_data=fake_route)), \
             patch("psutil.net_if_addrs", return_value=fake_addrs), \
             patch("psutil.net_if_stats", return_value=fake_stats):
            if_idx, local_ip = lp._get_physical_adapter_info()
            self.assertIsNone(if_idx)
            self.assertEqual(local_ip, "192.168.1.50")

    def test_04_gui_adapter_linux_scale_targets_templates_x11_and_browsec(self):
        from services.vpn.adapters.gui_adapter import GuiAdapter

        ga = GuiAdapter()
        self.assertTrue(os.path.isdir(ga.templates_dir))

        # Масштаб Cinnamon gsettings -> closest folder
        with patch("shutil.which", side_effect=lambda x: "/usr/bin/gsettings" if x == "gsettings" else None), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess(["gsettings"], 0, stdout="uint32 2\n", stderr="")):
            self.assertEqual(ga._get_system_scale(), 200)
            self.assertEqual(ga._get_closest_scale_folder(), "175")

        # Шаблоны кнопок Sota, Browsec, Happ находятся под Linux
        self.assertTrue(len(ga._collect_template_paths("browsec", "off")) >= 1)
        self.assertTrue(len(ga._collect_template_paths("happ", "disabled")) >= 1)
        self.assertTrue(len(ga._collect_template_paths("sota_connect")) >= 1)

        # Поиск .desktop / бинарников Sota, Happ, Browsec
        with tempfile.TemporaryDirectory() as tmpd:
            sota_desk = os.path.join(tmpd, "sota-connect.desktop")
            happ_desk = os.path.join(tmpd, "happ.desktop")
            brow_desk = os.path.join(tmpd, "browsec.desktop")
            for p, name in [(sota_desk, "Sota Connect"), (happ_desk, "Happ"), (brow_desk, "Browsec VPN")]:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(f"[Desktop Entry]\nName={name}\nExec=/bin/true\n")

            with patch("services.vpn.adapters.gui_adapter_linux._DESKTOP_SCAN_DIRS", [tmpd]), \
                 patch("shutil.which", return_value=None), \
                 patch("os.path.isfile", return_value=False):
                self.assertEqual(ga._find_sota_target(), sota_desk)
                self.assertEqual(ga._find_happ_target(), happ_desk)
                self.assertEqual(ga._find_browsec_target(), brow_desk)

        # X11 поиск окна через Xlib Display mock
        mock_disp = MagicMock()
        mock_disp.intern_atom.side_effect = [10, 11, 12, 13, 14, 15]
        mock_root = MagicMock()
        mock_root.get_full_property.return_value = types.SimpleNamespace(value=[777])
        mock_disp.screen.return_value = types.SimpleNamespace(root=mock_root)
        mock_win = MagicMock()
        mock_win.get_full_property.side_effect = [
            types.SimpleNamespace(value=b"Browsec VPN"),
            types.SimpleNamespace(value=[os.getpid()]),
            types.SimpleNamespace(value=[]),
        ]
        mock_win.get_wm_class.return_value = ("browsec", "Browsec")
        mock_win.get_geometry.return_value = types.SimpleNamespace(width=900, height=620)
        mock_win.get_attributes.return_value = types.SimpleNamespace(map_state=2)
        mock_disp.create_resource_object.return_value = mock_win

        with patch.dict(os.environ, {"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}), \
             patch("services.vpn.adapters.gui_adapter_linux.is_wayland", return_value=False), \
             patch("Xlib.display.Display", return_value=mock_disp):
            wid = ga._get_window_hwnd(["Browsec"], ["browsec"])
            self.assertEqual(wid, 777)

        # Browsec tunnel detection по интерфейсу browbox + disconnect без taskkill
        fake_stats = {"browbox-tun": types.SimpleNamespace(isup=True)}
        fake_addrs = {"browbox-tun": [types.SimpleNamespace(family=socket.AF_INET, address="10.10.0.2")]}
        with patch("psutil.process_iter", return_value=[]), \
             patch("psutil.net_if_stats", return_value=fake_stats), \
             patch("psutil.net_if_addrs", return_value=fake_addrs):
            self.assertTrue(ga.is_browsec_tunnel_active())

        fake_proc = MagicMock()
        fake_proc.info = {"name": "browbox"}
        with patch.object(ga, "is_browsec_tunnel_active", side_effect=[True, True, False]), \
             patch.object(ga, "is_browsec_app_running", return_value=True), \
             patch("psutil.process_iter", return_value=[fake_proc]):
            msg = ga.disconnect_browsec()
            fake_proc.kill.assert_called_once()
            self.assertIn("Выключила Browsec", msg)

    def test_05_vpn_manager_linux_only_sota_browsec_happ(self):
        from services.vpn.vpn_manager import VpnManager

        vm = VpnManager()
        with patch.object(vm.gui, "_find_browsec_target", return_value="/usr/bin/browsec"), \
             patch.object(vm.gui, "_find_sota_target", return_value=""), \
             patch.object(vm.gui, "_find_happ_target", return_value="/opt/Happ/happ"), \
             patch.object(vm, "is_process_running", return_value=False):
            installed = vm.detect_installed_vpns()
            self.assertEqual(installed, ["browsec", "happ"])
            self.assertNotIn("wireguard", installed)
            self.assertNotIn("v2ray", installed)

        # Прямой запрос WireGuard / V2Ray на Linux даёт вежливый отказ без падения
        wg_res = vm.connect("wireguard")
        v2_res = vm.disconnect("v2ray")
        self.assertIn("Windows", wg_res)
        self.assertIn("Sota Connect, Browsec или Happ", v2_res)

        # CommandParser: явный запрос WireGuard на Linux показывает предупреждение и не ждёт выбор V2Ray/WG
        from core.nlp.parser.command_parser import CommandParser, vpn_manager as cp_vm
        parser = CommandParser.__new__(CommandParser)
        parser.waiting_for_zapret = False
        parser.waiting_for_vpn = False
        parser.waiting_for_recycle_bin = False
        parser.waiting_for_game_choice = False
        parser.waiting_for_movie_choice = False
        parser.reminder_manager = MagicMock(is_ringing=False)
        parser.city_game = MagicMock(is_active=False)
        parser.believe_game = MagicMock(is_active=False)
        parser.danetki_game = MagicMock(is_active=False)
        parser.offense_level = 0
        parser.ignore_until_timestamp = 0.0
        parser.is_stress_mode = False
        parser.last_emotion = "neutral"
        parser.get_emotion = lambda t: ("neutral", "нейтральный", 0.9)
        parser._is_gibberish = lambda t: False

        resp_wg = parser.process_command("включи wireguard", is_voice=True)
        self.assertIn("Windows", resp_wg["chat"])
        self.assertIn("Sota Connect, Browsec или Happ", resp_wg["voice"])

        with patch.object(cp_vm, "detect_installed_vpns", return_value=[]):
            resp_none = parser.process_command("включи впн", is_voice=False)
            self.assertIn("Browsec, Sota, Happ", resp_none["chat"])
            self.assertNotIn("WireGuard", resp_none["chat"])
            self.assertNotIn("V2Ray", resp_none["chat"])

    def test_06_zapret_linux_strategies_and_pkexec(self):
        from services.zapret.zapret import ZapretManager

        zm = ZapretManager()
        menu = zm.get_strategies_menu()
        self.assertIn("nfqws", menu)
        self.assertIn("zapret", menu)

        # Когда zapret не установлен — понятная подсказка
        with patch.object(zm, "is_installed", return_value=False):
            res_hint = zm.start()
            self.assertIn("install_easy.sh", res_hint)

        # Когда бинарник nfqws найден — запускает и останавливает правила + процесс через pkexec
        with patch.object(zm, "is_installed", return_value=True), \
             patch.object(zm, "_find_nfqws_bin", return_value="/opt/zapret/nfq/nfqws"), \
             patch.object(zm, "_has_systemd_service", return_value=False), \
             patch.object(zm, "_run_pkexec_script", return_value=(True, "")) as mock_pk, \
             patch.object(zm, "is_running", side_effect=[False, True, True]):
            res_start = zm.start_strategy_by_index(2)
            self.assertIn("Запустила #2", res_start)
            script_start = mock_pk.call_args.args[0]
            self.assertIn("--dpi-desync=fake,split2", script_start)
            self.assertIn("akira_zapret", script_start)

            res_stop = zm.stop()
            self.assertEqual(res_stop, "Выключила Запрет")
            script_stop = mock_pk.call_args.args[0]
            self.assertIn("nft delete table inet akira_zapret", script_stop)


if __name__ == "__main__":
    unittest.main(verbosity=2)
