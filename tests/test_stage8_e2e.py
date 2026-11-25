import ast
import compileall
import importlib
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class TestStage8EndToEndVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_01_compileall_entire_project(self):
        ok = compileall.compile_dir(
            str(ROOT_DIR),
            maxlevels=10,
            quiet=1,
            rx=re.compile(r"(/\.venv/|/\.git/|/dist/|/build/)"),
        )
        self.assertTrue(ok, "Bytecode compilation failed in at least one Python file")

    def test_02_zero_windows_only_imports_on_linux(self):
        linux_safe_modules = [
            "core.utils.platform_utils",
            "core.utils.config",
            "core.utils.updater",
            "core.database.chat_db",
            "core.system.volume_ducker",
            "core.system.audio_control",
            "core.system.actions",
            "core.system.platform_linux",
            "core.system.app_launcher",
            "core.system.app_launcher_linux",
            "core.system.activity_tracker",
            "core.vision.presence_manager",
            "core.vision.eye_detector",
            "core.vision.gesture_detector",
            "core.nlp.generative.llm_provider",
            "core.nlp.parser.command_parser",
            "audio.stt",
            "audio.tts",
            "services.torrent.torrserver_manager",
            "services.torrent.vlc_player",
            "services.vpn.vpn_manager",
            "services.zapret.zapret",
            "build_common",
            "build_linux",
            "build_win",
            "build_nuitka",
        ]
        for mod_name in linux_safe_modules:
            imported = importlib.import_module(mod_name)
            self.assertIsNotNone(imported)

    def test_03_stage1_platform_utils_config_and_chat_db(self):
        from core.database import chat_db
        from core.utils import config as cfg_mod
        from core.utils import platform_utils as pu

        with tempfile.TemporaryDirectory(prefix="akira_s8_xdg_") as tmp:
            with patch.dict(os.environ, {"XDG_DATA_HOME": tmp}, clear=False), \
                    patch.object(pu, "IS_WINDOWS", False):
                data_dir = pu.get_default_user_data_dir("configs")
                self.assertEqual(Path(data_dir), Path(tmp) / "Akira" / "configs")

            self.assertEqual(pu.subprocess_no_window_kwargs(), {})
            fake_sp = MagicMock()
            fake_sp.CREATE_NO_WINDOW = 0x08000000
            fake_startupinfo = MagicMock()
            fake_startupinfo.dwFlags = 0
            fake_sp.STARTUPINFO.return_value = fake_startupinfo
            fake_sp.STARTF_USESHOWWINDOW = 1
            fake_sp.SW_HIDE = 0
            with patch.object(pu, "IS_WINDOWS", True), \
                    patch.object(pu, "subprocess", fake_sp):
                kwargs = pu.subprocess_no_window_kwargs()
                self.assertEqual(kwargs["creationflags"], 0x08000000)
                self.assertIn("startupinfo", kwargs)

            with patch.object(pu, "IS_WINDOWS", False), \
                    patch("core.utils.platform_utils.shutil.which", return_value="/usr/bin/xdg-open"), \
                    patch("core.utils.platform_utils.subprocess.Popen") as mock_popen:
                self.assertTrue(pu.open_path("/tmp/example.txt"))
                mock_popen.assert_called_once()
                self.assertEqual(mock_popen.call_args[0][0], ["/usr/bin/xdg-open", "/tmp/example.txt"])

            self.assertIsInstance(pu.get_system_timezone_name() or "", str)

            cfg_file = Path(tmp) / "Akira" / "configs" / "config.json"
            with patch.object(cfg_mod, "CONFIG_FILE", str(cfg_file)), \
                    patch.object(cfg_mod, "CONFIG_DIR", str(cfg_file.parent)):
                saved = dict(cfg_mod.DEFAULT_CONFIG)
                saved["city"] = "Казань"
                cfg_mod.save_config(saved)
                loaded = cfg_mod.load_config()
                self.assertEqual(loaded["city"], "Казань")

            db_path = Path(tmp) / "studio_chats.db"
            with patch.object(chat_db, "get_db_path", return_value=str(db_path)):
                db = chat_db.StudioChatDatabase()
                sid = db.create_session("Stage 8 Session")
                db.add_message(sid, "user", "Проверка базы данных")
                msgs = db.get_messages(sid)
                self.assertEqual(len(msgs), 1)
                self.assertIn("Проверка базы данных", str(msgs[0]))

    def test_04_stage2_tts_providers_and_audio_ducker_control(self):
        from audio import tts
        from core.system import audio_control_linux as acl
        from core.system import volume_ducker_linux as vdl
        from core.utils import onnx_runtime as ort_rt

        with patch.object(tts.ort, "get_available_providers", return_value=["CUDAExecutionProvider", "CPUExecutionProvider"]), \
                patch.object(tts.sys, "platform", "linux"):
            self.assertEqual(tts.get_tts_execution_providers(), ["CUDAExecutionProvider", "CPUExecutionProvider"])

        with patch.object(tts.ort, "get_available_providers", return_value=["DmlExecutionProvider", "CPUExecutionProvider"]), \
                patch.object(tts.sys, "platform", "win32"):
            self.assertEqual(tts.get_tts_execution_providers(), ["DmlExecutionProvider", "CPUExecutionProvider"])

        with patch.object(tts.ort, "get_available_providers", return_value=["CUDAExecutionProvider", "CPUExecutionProvider"]), \
                patch.object(tts.sys, "platform", "win32"):
            self.assertEqual(tts.get_tts_execution_providers(), ["CUDAExecutionProvider", "CPUExecutionProvider"])

        with patch.object(tts.ort, "get_available_providers", return_value=["CPUExecutionProvider"]), \
                patch.object(tts.sys, "platform", "linux"):
            self.assertEqual(tts.get_tts_execution_providers(), ["CPUExecutionProvider"])

        # create_onnx_session selects GPU when active, and safely falls back to CPU on GPU init error
        fake_ort = MagicMock()
        fake_ort.get_available_providers.return_value = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        fake_sess_gpu = MagicMock()
        fake_sess_gpu.get_providers.return_value = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        fake_sess_cpu = MagicMock()
        fake_sess_cpu.get_providers.return_value = ["CPUExecutionProvider"]
        fake_ort.InferenceSession.side_effect = [RuntimeError("cuda init failed"), fake_sess_cpu]
        with patch.object(ort_rt, "prepare_onnx_gpu_env"), \
                patch.object(ort_rt.sys, "platform", "linux"):
            sess, ep = ort_rt.create_onnx_session("dummy.onnx", ort_module=fake_ort, prefer_gpu=True)
            self.assertIs(sess, fake_sess_cpu)
            self.assertEqual(ep, "CPUExecutionProvider")

            fake_ort.InferenceSession.side_effect = [fake_sess_gpu]
            sess2, ep2 = ort_rt.create_onnx_session("dummy.onnx", ort_module=fake_ort, prefer_gpu=True)
            self.assertIs(sess2, fake_sess_gpu)
            self.assertEqual(ep2, "CUDAExecutionProvider")

        self.assertIsInstance(tts.apply_pronunciation_and_translit("Привет, Akira!"), str)
        tts_probe = tts.TTSThread.__new__(tts.TTSThread)
        cleaned_mashin = tts_probe._clean_text_for_tts("восстание машин")
        self.assertIn("маши\u0301н", cleaned_mashin)

        other_stream = MagicMock()
        other_stream.index = 101
        other_stream.proplist = {"application.process.id": "999999", "application.process.binary": "vlc", "application.name": "VLC"}
        other_stream.volume.value_flat = 0.8

        own_stream = MagicMock()
        own_stream.index = 102
        own_stream.proplist = {"application.process.id": str(os.getpid()), "application.process.binary": "python", "application.name": "Akira"}
        own_stream.volume.value_flat = 0.9

        fake_pulse = MagicMock()
        fake_pulse.__enter__.return_value = fake_pulse
        fake_pulse.sink_input_list.return_value = [other_stream, own_stream]
        fake_pulsectl = MagicMock()
        fake_pulsectl.Pulse.return_value = fake_pulse

        with patch.object(vdl, "_HAS_PULSECTL", True), \
                patch.object(vdl, "pulsectl", fake_pulsectl):
            ducker = vdl.VolumeDucker()
            ducker.duck(0.25)
            self.assertIn(101, ducker.saved_volumes)
            self.assertNotIn(102, ducker.saved_volumes)
            fake_pulse.volume_set_all_chans.assert_called()
            ducker.restore()
            self.assertEqual(ducker.saved_volumes, {})

        ok_proc = MagicMock(returncode=0, stdout="50%")
        with patch.object(acl, "_HAS_PULSECTL", False), \
                patch.object(acl.shutil, "which", side_effect=lambda x: "/usr/bin/pactl" if x == "pactl" else None), \
                patch.object(acl, "_run_c", return_value=ok_proc) as mock_run:
            self.assertEqual(acl.set_volume(45), "Сделала")
            mock_run.assert_called_with(["/usr/bin/pactl", "set-sink-volume", "@DEFAULT_SINK@", "45%"])
            self.assertEqual(acl.mute_volume(), "Выключаю звук")
            mock_run.assert_called_with(["/usr/bin/pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])

    def test_05_stage3_system_actions_trash_power_launcher_tracker(self):
        from core.system import actions as act_mod
        from core.system import app_launcher_linux as allx
        from core.system import platform_linux as pl

        with patch.object(pl.shutil, "which", side_effect=lambda x: f"/usr/bin/{x}" if x == "cinnamon-screensaver-command" else None), \
                patch.object(pl, "_run_ok", return_value=True) as mock_run:
            res = pl.lock_screen()
            self.assertIn("заблокирован", res.lower())
            mock_run.assert_called_once_with(["/usr/bin/cinnamon-screensaver-command", "-l"])

        with patch.object(pl.shutil, "which", return_value=None):
            pl.schedule_power_action("poweroff", delay_seconds=60)
            self.assertIsNotNone(pl._pending_power_timer)
            cancel_msg = pl.cancel_shutdown()
            self.assertIn("Отменила", cancel_msg)
            self.assertIsNone(pl._pending_power_timer)

        with tempfile.TemporaryDirectory(prefix="akira_s8_trash_") as tmp:
            trash_files = Path(tmp) / "Trash" / "files"
            trash_info = Path(tmp) / "Trash" / "info"
            trash_files.mkdir(parents=True)
            trash_info.mkdir(parents=True)
            (trash_files / "old.txt").write_bytes(b"1234567890")
            (trash_info / "old.txt.trashinfo").write_text("[Trash Info]\nPath=/tmp/old.txt\n", encoding="utf-8")

            with patch.dict(os.environ, {"XDG_DATA_HOME": tmp}, clear=False):
                info = pl.get_recycle_bin_info()
                self.assertEqual(info["num_items"], 1)
                self.assertGreaterEqual(info["size_bytes"], 10)
                emptied = pl.empty_recycle_bin()
                self.assertIn("Очистила корзину", emptied["chat"])
                self.assertFalse((trash_files / "old.txt").exists())
                self.assertEqual(pl.get_recycle_bin_info()["num_items"], 0)

            apps_dir = Path(tmp) / "applications"
            apps_dir.mkdir(parents=True)
            desktop_item = apps_dir / "custom_editor.desktop"
            desktop_item.write_text(
                "[Desktop Entry]\n"
                "Name=My Demo Editor\n"
                "Exec=/bin/true %U\n"
                "Terminal=false\n"
                "Type=Application\n",
                encoding="utf-8",
            )
            self.assertEqual(allx.AppLauncher._clean_exec_line("/bin/true %U --flag"), ["/bin/true", "--flag"])
            parsed = allx.AppLauncher._parse_desktop_file(str(desktop_item))
            self.assertEqual(parsed["name"], "My Demo Editor")
            self.assertEqual(parsed["cmd_args"], ["/bin/true"])
            with patch("core.system.app_launcher_linux.subprocess.Popen") as mock_popen:
                launcher = allx.AppLauncher.__new__(allx.AppLauncher)
                launcher.apps = {"my demo editor": ("My Demo Editor", str(desktop_item), ["/bin/true"], False)}
                launcher.builtins = {}
                launcher.aliases = {}
                out = launcher.launch("my demo editor")
                self.assertEqual(out, (True, "My Demo Editor"))
                mock_popen.assert_called_once()

        with patch.object(act_mod, "get_system_timezone_name", return_value="Europe/Kaliningrad"):
            self.assertEqual(act_mod.get_city_from_system_timezone(), "Калининград")

        tracker_cls = importlib.import_module("core.system.activity_tracker").ActivityTracker
        tracker = tracker_cls()
        self.assertEqual(tracker.categorize_app("code", "main.py - Visual Studio Code"), ("coding", "VS Code"))

    def test_06_cold_headless_gui_e2e_boot_and_shutdown(self):
        from PyQt6.QtWidgets import QApplication
        from core.database import chat_db as cdb
        from core.utils.config import DEFAULT_CONFIG
        from gui.dialogs.onboarding_wizard import OnboardingWizard
        from gui.windows import chat_window as cw_mod
        from gui.windows.settings_window import SettingsFrame
        from gui.windows.studio_frame import StudioFrame

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        wiz = OnboardingWizard(dict(DEFAULT_CONFIG))
        self.assertEqual(wiz.stack.count(), 4)
        wiz.close()

        with tempfile.TemporaryDirectory(prefix="akira_s8_ui_") as tmp:
            with patch.object(cdb, "get_db_path", return_value=os.path.join(tmp, "studio_chats.db")):
                test_db = cdb.StudioChatDatabase()
                with patch("core.utils.config.get_user_data_path", side_effect=lambda *p: os.path.join(tmp, *p)), \
                        patch("gui.windows.settings_window.get_user_data_path", side_effect=lambda *p: os.path.join(tmp, *p)):
                    sf = SettingsFrame()
                    sf.close()

                with patch("gui.windows.studio_frame.studio_db", test_db):
                    stf = StudioFrame()
                    stf.close()

                with patch.object(cw_mod, "STTThread", return_value=MagicMock()), \
                        patch.object(cw_mod, "TTSThread", return_value=MagicMock()), \
                        patch.object(cw_mod, "VisionThread"), \
                        patch.object(cw_mod, "UpdateCheckerThread"), \
                        patch("gui.windows.studio_frame.studio_db", test_db), \
                        patch("core.utils.config.get_user_data_path", side_effect=lambda *p: os.path.join(tmp, *p)):
                    mw = cw_mod.MainWindow(dict(DEFAULT_CONFIG))
                    mw.shutdown()
                    mw.close()

    def test_07_windows_regression_structural_and_api_parity(self):
        win_modules_required_symbols = {
            "core/system/volume_ducker_win.py": {"VolumeDucker"},
            "core/system/audio_control_win.py": {"set_volume", "volume_up", "volume_down", "mute_volume", "unmute_volume"},
            "core/system/platform_win.py": {
                "lock_screen", "sleep_mode", "shutdown_system", "restart_system",
                "cancel_shutdown", "empty_recycle_bin", "get_recycle_bin_info",
            },
            "core/system/app_launcher_win.py": {"AppLauncher"},
            "services/vpn/adapters/core_adapter_win.py": {"CoreAdapter"},
            "services/vpn/adapters/gui_adapter_win.py": {"GuiAdapter"},
            "services/zapret/zapret_win.py": {"ZapretManager"},
            "build_win.py": {"build_nuitka_command_win", "copy_runtime_assets_win", "build_msi", "run_build_win"},
        }
        for rel, required in win_modules_required_symbols.items():
            path = ROOT_DIR / rel
            self.assertTrue(path.is_file(), f"Missing Windows module: {rel}")
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            top_names = {
                node.name
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }
            missing = required - top_names
            self.assertFalse(missing, f"Windows module {rel} missing symbols: {missing}")

        vpn_text = (ROOT_DIR / "services" / "vpn" / "vpn_manager.py").read_text(encoding="utf-8")
        for expected_vpn in ("browsec", "sota", "happ", "v2ray", "wireguard"):
            self.assertIn(f'"{expected_vpn}"', vpn_text)

        wxs_path = ROOT_DIR / "Package.wxs"
        self.assertTrue(wxs_path.is_file())
        tree = ET.parse(str(wxs_path))
        wxs_text = wxs_path.read_text(encoding="utf-8")
        self.assertIsNotNone(tree.getroot())
        self.assertIn("Akira.exe", wxs_text)
        self.assertIn("akira_icon.ico", wxs_text)

    def test_08_stt_resampling_and_samplerate_fallback(self):
        import numpy as np
        from audio import stt as stt_mod

        stt = stt_mod.STTThread()
        # 48000 Hz -> 16000 Hz (0.1s = 4800 -> 1600 samples)
        src_48k = np.zeros(4800, dtype=np.float32)
        out_16k = stt._resample_audio(src_48k, 48000, 16000)
        self.assertEqual(len(out_16k), 1600)

        # Stereo 44100 Hz callback downmixes & resamples to 16000 Hz int16 bytes
        stt._stream_channels = 2
        stt._stream_samplerate = 44100
        stereo_frames = np.ones((4410, 2), dtype=np.int16) * 1000
        stt._audio_callback(stereo_frames.tobytes(), 4410, None, None)
        chunk = stt.audio_queue.get_nowait()
        self.assertEqual(len(chunk) % 2, 0)
        approx_samples = len(chunk) // 2
        self.assertTrue(1550 <= approx_samples <= 1650, f"Unexpected resampled len: {approx_samples}")

        # _open_stream falls back cleanly when 16000 Hz fails on hardware ALSA
        def fake_raw_input_stream(*, samplerate, blocksize, dtype, channels, callback):
            if samplerate == 16000:
                raise RuntimeError("Error opening RawInputStream: Invalid sample rate [PaErrorCode -9997]")
            stream_mock = MagicMock()
            return stream_mock

        fake_dev = {"name": "HDA Analog", "default_samplerate": 44100.0, "max_input_channels": 2}
        with patch.object(stt_mod.sd, "query_devices", return_value=fake_dev), \
                patch.object(stt_mod.sd, "RawInputStream", side_effect=fake_raw_input_stream):
            stream = stt._open_stream()
            self.assertIsNotNone(stream)
            stream.start.assert_called_once()
            self.assertEqual(stt._stream_samplerate, 44100)
            self.assertEqual(stt._stream_channels, 1)

    def test_09_main_window_close_event_and_telegram_nvidia_smi(self):
        from PyQt6.QtGui import QCloseEvent
        from PyQt6.QtWidgets import QWidget
        from gui.windows import chat_window as cw_mod
        from services.telegram import telegram_bot as tg_mod

        class _CloseProbe(cw_mod.MainWindow):
            def __init__(self):
                QWidget.__init__(self)
                self._is_shutting_down = False
                self.animated_closes = 0

            def close_animated(self):
                self.animated_closes += 1

        probe = _CloseProbe()
        spontaneous_ev = QCloseEvent()
        with patch.object(spontaneous_ev, "spontaneous", return_value=True):
            probe.closeEvent(spontaneous_ev)
        self.assertFalse(spontaneous_ev.isAccepted())
        self.assertEqual(probe.animated_closes, 1)

        quit_ev = QCloseEvent()
        with patch.object(quit_ev, "spontaneous", return_value=False):
            probe.closeEvent(quit_ev)
        self.assertTrue(quit_ev.isAccepted())
        probe.close()

        with patch("services.telegram.telegram_bot.shutil.which", return_value="/usr/bin/nvidia-smi"), \
                patch("services.telegram.telegram_bot.subprocess.check_output", return_value="RTX 4070, 45, 12, 512, 8192\n") as mock_co:
            status_text = tg_mod.get_hardware_status()
        self.assertIn("RTX 4070", status_text)
        self.assertNotIn("creationflags", mock_co.call_args.kwargs)
        self.assertNotIn("shell", mock_co.call_args.kwargs)

    def test_10_all_gui_dialogs_and_real_main_startup_shutdown(self):
        import json
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from core.database import chat_db as cdb
        from core.utils import config as cfg_mod
        from gui.dialogs.face_manager_dialog import FaceManagerDialog
        from gui.dialogs.gigachat_auth_dialog import GigaChatAuthDialog
        from gui.dialogs.mode_config_dialog import ModeConfigDialog
        from gui.dialogs.routerai_auth_dialog import RouterAiAuthDialog
        from gui.dialogs.spotify_auth_dialog import SpotifyAuthDialog
        from gui.dialogs.telegram_pair_dialog import TelegramPairDialog
        from gui.dialogs.voice_enrollment_dialog import VoiceEnrollmentDialog
        from gui.dialogs.yandex_auth_dialog import YandexAuthDialog
        from gui.dialogs.yandex_iot_auth_dialog import YandexIotAuthDialog

        QApplication.instance() or QApplication([])
        for dlg in (
            FaceManagerDialog(),
            VoiceEnrollmentDialog(verifier=MagicMock()),
            ModeConfigDialog("Режим", []),
            SpotifyAuthDialog(),
            YandexAuthDialog(),
            GigaChatAuthDialog(),
            TelegramPairDialog("DejaVu Sans"),
            RouterAiAuthDialog(),
            YandexIotAuthDialog(),
        ):
            dlg.close()

        # Verify real end-to-end execution of main.main() in an isolated fresh process
        with tempfile.TemporaryDirectory(prefix="akira_s8_main_") as tmp:
            cfg_dir = Path(tmp) / "configs"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file = cfg_dir / "config.json"
            cfg_data = dict(cfg_mod.DEFAULT_CONFIG)
            cfg_data["first_run"] = False
            cfg_data["is_configured"] = True
            cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

            harness = (
                "import os, sys\n"
                "from unittest.mock import patch\n"
                "from PyQt6.QtCore import QTimer\n"
                "from PyQt6.QtWidgets import QApplication\n"
                "import core.utils.config as cfg_mod, core.database.chat_db as cdb, main as m\n"
                f"tmp = {tmp!r}\n"
                f"cfg_dir = {str(cfg_dir)!r}\n"
                f"cfg_file = {str(cfg_file)!r}\n"
                "orig_exec = QApplication.exec\n"
                "def _timed_exec(*args, **kwargs):\n"
                "    app = QApplication.instance()\n"
                "    QTimer.singleShot(350, app.quit)\n"
                "    return orig_exec(*args, **kwargs)\n"
                "with patch.object(cfg_mod, 'USER_DATA_DIR', tmp), \\\n"
                "        patch.object(cfg_mod, 'CONFIG_DIR', cfg_dir), \\\n"
                "        patch.object(cfg_mod, 'CONFIG_FILE', cfg_file), \\\n"
                "        patch.object(m, 'load_config', cfg_mod.load_config), \\\n"
                "        patch.object(cdb, 'get_db_path', return_value=os.path.join(tmp, 'studio_chats.db')), \\\n"
                "        patch('core.utils.config.get_user_data_path', side_effect=lambda *p: os.path.join(tmp, *p)), \\\n"
                "        patch('gui.windows.settings_window.get_user_data_path', side_effect=lambda *p: os.path.join(tmp, *p)), \\\n"
                "        patch.object(QApplication, 'exec', staticmethod(_timed_exec)):\n"
                "    try:\n"
                "        m.main()\n"
                "    except SystemExit as se:\n"
                "        print('MAIN_CLEAN_EXIT', se.code, flush=True)\n"
                "        sys.exit(se.code)\n"
            )
            env = os.environ.copy()
            env.setdefault("QT_QPA_PLATFORM", "offscreen")
            env["MPLCONFIGDIR"] = tmp
            res = __import__("subprocess").run(
                [sys.executable, "-c", harness],
                cwd=str(ROOT_DIR),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(res.returncode, 0, res.stdout + "\n" + res.stderr)
            self.assertIn("MAIN_CLEAN_EXIT 0", res.stdout)

    def test_11_linux_qt_env_sanitizer_and_x11_prereq_check(self):
        import main as main_mod

        with patch.dict(
            os.environ,
            {
                "QT_QPA_PLATFORM_PLUGIN_PATH": "/home/user/.venv/lib/python3.12/site-packages/cv2/qt/plugins",
                "QT_QPA_FONTDIR": "/home/user/.venv/lib/python3.12/site-packages/cv2/qt/fonts",
                "QT_PLUGIN_PATH": "/usr/lib/qt6/plugins",
            },
            clear=False,
        ):
            main_mod._sanitize_linux_qt_env()
            self.assertNotIn("QT_QPA_PLATFORM_PLUGIN_PATH", os.environ)
            self.assertNotIn("QT_QPA_FONTDIR", os.environ)
            self.assertEqual(os.environ.get("QT_PLUGIN_PATH"), "/usr/lib/qt6/plugins")

        # Missing libxcb-cursor.so.0 on X11 exits cleanly with code 1 and clear message instead of core dump
        clean_env = dict(os.environ)
        clean_env.pop("QT_QPA_PLATFORM", None)
        with patch.dict(os.environ, clean_env, clear=True), \
                patch("core.utils.platform_utils.is_wayland", return_value=False), \
                patch.object(main_mod.ctypes, "CDLL", side_effect=OSError("not found")), \
                patch("shutil.which", return_value=None):
            with self.assertRaises(SystemExit) as se:
                main_mod._check_linux_qt_x11_prereqs()
            self.assertEqual(se.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
