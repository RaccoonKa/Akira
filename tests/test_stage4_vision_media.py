import base64
import io
import os
import py_compile
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class Stage4VisionMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Обеспечиваем headless Qt-приложение для QThread-воркеров и виджетов
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_01_py_compile_stage4_files(self):
        files = [
            "core/utils/platform_utils.py",
            "core/vision/vision_provider.py",
            "core/vision/presence_manager.py",
            "services/torrent/torrserver_manager.py",
            "services/torrent/vlc_player.py",
            "services/yandex/yandex_music_manager.py",
            "services/spotify/spotify_manager.py",
            "services/google/youtube_manager.py",
            "services/telegram/notifier.py",
            "services/telegram/telegram_bot.py",
            "core/nlp/parser/command_parser.py",
            "gui/windows/chat_window.py",
        ]
        for rel in files:
            py_compile.compile(str(PROJECT_ROOT / rel), doraise=True)

    def test_02_standalone_stage4_imports_without_winreg(self):
        saved_winreg = sys.modules.pop("winreg", None)
        try:
            import core.utils.platform_utils  # noqa: F401
            import core.vision.vision_provider  # noqa: F401
            import core.vision.presence_manager  # noqa: F401
            import services.torrent.torrserver_manager  # noqa: F401
            import services.torrent.vlc_player  # noqa: F401
            import services.yandex.yandex_music_manager  # noqa: F401
            import services.spotify.spotify_manager  # noqa: F401
            import services.google.youtube_manager  # noqa: F401
        finally:
            if saved_winreg is not None:
                sys.modules["winreg"] = saved_winreg

    def test_03_open_video_capture_platform_selection(self):
        from core.utils import platform_utils as pu

        fake_closed = MagicMock()
        fake_closed.isOpened.return_value = False
        fake_open = MagicMock()
        fake_open.isOpened.return_value = True

        with patch.object(pu, "IS_WINDOWS", False), \
             patch("cv2.VideoCapture", side_effect=[fake_closed, fake_open]) as mock_vc:
            cap = pu.open_video_capture(0)
            self.assertIs(cap, fake_open)
            self.assertEqual(mock_vc.call_count, 2)
            fake_closed.release.assert_called_once()

        with patch.object(pu, "IS_WINDOWS", True), \
             patch("cv2.VideoCapture", return_value=fake_open) as mock_vc, \
             patch("cv2.CAP_DSHOW", 700, create=True):
            cap = pu.open_video_capture(1)
            self.assertIs(cap, fake_open)
            mock_vc.assert_called_once_with(1, 700)

    def test_04_vision_libraries_and_detectors(self):
        from core.utils.platform_utils import ensure_pkg_resources_shim
        ensure_pkg_resources_shim()

        import face_recognition
        import dlib
        import mediapipe  # noqa: F401
        self.assertTrue(hasattr(face_recognition, "face_encodings"))
        self.assertTrue(hasattr(dlib, "get_frontal_face_detector"))

        from core.vision.gesture_detector import GestureDetector
        gd = GestureDetector()
        self.assertIsNotNone(gd.detector)

        # Проверка реального инференса dlib / face_recognition_models на тестовом кадре
        import numpy as np
        blank_rgb = np.zeros((120, 120, 3), dtype=np.uint8)
        locs = face_recognition.face_locations(blank_rgb, model="hog")
        self.assertEqual(locs, [])

        # EyeDetector корректно загружает MediaPipe FaceLandmarker и безопасно переживает LFS/отсутствие eye_state_model.onnx
        from core.vision.eye_detector import EyeDetector
        ed = EyeDetector()
        self.assertIsNotNone(ed.face_landmarker)

    def test_05_torrserver_paths_and_linux_download(self):
        from services.torrent import torrserver_manager as tm

        with tempfile.TemporaryDirectory() as tmpd:
            bin_name = tm._get_linux_torrserver_filename()
            fake_target = os.path.join(tmpd, "torrserver", bin_name)

            with patch.object(tm, "get_user_data_path", side_effect=lambda *parts: os.path.join(tmpd, *parts)), \
                 patch("shutil.which", return_value=None):
                mgr = tm.TorrServerManager()
                self.assertEqual(tm.get_torrserver_bin_path(), fake_target)
                self.assertFalse(mgr.is_binary_installed())

                # Невалидный не-ELF файл не принимается
                bad_resp = MagicMock()
                bad_resp.status_code = 200
                bad_resp.headers = {"Content-Length": "1200000"}
                bad_resp.iter_content.return_value = [b"HTML" * 300000]
                bad_resp.__enter__.return_value = bad_resp

                api_resp = MagicMock()
                api_resp.status_code = 200
                api_resp.json.return_value = {
                    "assets": [{"name": bin_name, "browser_download_url": f"https://example.test/{bin_name}"}]
                }

                with patch("services.torrent.torrserver_manager.requests.get", side_effect=[api_resp, bad_resp]):
                    ok, msg = mgr.download_linux_binary()
                    self.assertFalse(ok)
                    self.assertIn("ELF", msg)
                    self.assertFalse(os.path.exists(fake_target + ".part"))

                # Валидный ELF-бинарник (>1 МБ) скачивается, получает +x и распознаётся
                payload = b"\x7fELF" + b"\x00" * (1_100_000 - 4)
                good_resp = MagicMock()
                good_resp.status_code = 200
                good_resp.headers = {"Content-Length": str(len(payload))}
                good_resp.iter_content.return_value = [payload[:500_000], payload[500_000:]]
                good_resp.__enter__.return_value = good_resp

                progress_ticks = []
                with patch("services.torrent.torrserver_manager.requests.get", side_effect=[api_resp, good_resp]):
                    ok, path = mgr.download_linux_binary(progress_callback=lambda d, t: progress_ticks.append((d, t)))
                    self.assertTrue(ok, path)
                    self.assertEqual(path, fake_target)
                    self.assertTrue(os.access(fake_target, os.X_OK))
                    self.assertTrue(mgr.is_binary_installed())
                    self.assertEqual(progress_ticks[-1], (len(payload), len(payload)))

                # start_server не падает из-за Windows STARTUPINFO
                mgr.is_running = MagicMock(side_effect=[False, False, True])
                mgr._apply_runtime_settings = MagicMock()
                with patch("subprocess.Popen", return_value=MagicMock()) as mock_popen:
                    started = mgr.start_server()
                    self.assertTrue(started)
                    _, kwargs = mock_popen.call_args
                    self.assertNotIn("startupinfo", kwargs)
                    self.assertTrue(kwargs.get("start_new_session"))

    def test_06_vlc_player_linux_find_config_and_mpris(self):
        from services.torrent.vlc_player import VLCPlayer

        with tempfile.TemporaryDirectory() as cfg_dir:
            old_xdg = os.environ.get("XDG_CONFIG_HOME")
            os.environ["XDG_CONFIG_HOME"] = cfg_dir
            try:
                with patch("shutil.which", side_effect=lambda x: "/usr/bin/vlc" if x == "vlc" else f"/usr/bin/{x}" if x in ("dbus-send", "gdbus") else None):
                    player = VLCPlayer()
                    self.assertEqual(player.vlc_path, "/usr/bin/vlc")
                    self.assertTrue(player.is_available())
                    player.setup_vlc_privacy_config()
                    vlcrc_path = os.path.join(cfg_dir, "vlc", "vlcrc")
                    self.assertTrue(os.path.isfile(vlcrc_path))

                    with patch("subprocess.run", return_value=subprocess.CompletedProcess(["dbus-send"], 0, stdout="", stderr="")) as mock_dbus:
                        player.toggle_pause()
                        player.seek("backward", 15)
                        player.next_episode()
                        player.prev_episode()
                        player.toggle_fullscreen()
                        self.assertGreaterEqual(mock_dbus.call_count, 5)
                        cmds = [c.args[0] for c in mock_dbus.call_args_list]
                        self.assertIn("org.mpris.MediaPlayer2.Player.PlayPause", cmds[0])
                        self.assertIn("org.mpris.MediaPlayer2.Player.Seek", cmds[1])
                        self.assertIn("int64:-15000000", cmds[1])
                        self.assertIn("org.mpris.MediaPlayer2.Player.Next", cmds[2])
                        self.assertIn("org.mpris.MediaPlayer2.Player.Previous", cmds[3])
                        self.assertIn("org.freedesktop.DBus.Properties.Get", cmds[4])

                    self.assertTrue(player._is_vlc_proc_name("vlc"))
                    self.assertFalse(player._is_vlc_proc_name("vlc.exe"))
            finally:
                if old_xdg is None:
                    os.environ.pop("XDG_CONFIG_HOME", None)
                else:
                    os.environ["XDG_CONFIG_HOME"] = old_xdg

    def test_07_spotify_and_youtube_linux(self):
        from services.spotify.spotify_manager import SpotifyManager
        from services.google.youtube_manager import YouTubeManager

        sm = SpotifyManager()
        with patch("shutil.which", side_effect=lambda x: "/usr/bin/flatpak" if x == "flatpak" else None), \
             patch("os.path.isfile", return_value=False), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess(["flatpak"], 0)), \
             patch("subprocess.Popen") as mock_popen:
            self.assertEqual(sm._is_spotify_installed(), "flatpak:com.spotify.Client")
            self.assertTrue(sm._launch_app())
            self.assertEqual(mock_popen.call_args.args[0], ["/usr/bin/flatpak", "run", "com.spotify.Client"])

        ym = YouTubeManager()
        with patch("services.google.youtube_manager.is_wayland", return_value=True), \
             patch("services.google.youtube_manager.get_pyautogui") as mock_pag:
            ym._auto_fullscreen(delay=0)
            mock_pag.assert_not_called()

    def test_08_telegram_bot_linux_hardware_media_and_power(self):
        # Временная заглушка winreg только для импорта ещё не перенесённых в Этапе 5 VPN/GigaChat зависимостей через Actions
        had_winreg = "winreg" in sys.modules
        if not had_winreg:
            sys.modules["winreg"] = types.ModuleType("winreg")
        try:
            import services.telegram.telegram_bot as tb
            import services.telegram.notifier as notifier  # noqa: F401

            fake_parts = [
                types.SimpleNamespace(device="/dev/loop0", mountpoint="/snap/core22/1", fstype="squashfs", opts="ro"),
                types.SimpleNamespace(device="tmpfs", mountpoint="/run/user/1000", fstype="tmpfs", opts="rw"),
                types.SimpleNamespace(device="/dev/nvme0n1p1", mountpoint="/boot/efi", fstype="vfat", opts="rw"),
                types.SimpleNamespace(device="/dev/nvme0n1p2", mountpoint="/", fstype="ext4", opts="rw"),
            ]
            fake_usage = types.SimpleNamespace(free=50 * (1024 ** 3), total=100 * (1024 ** 3), percent=50.0)
            with patch("psutil.disk_partitions", return_value=fake_parts), \
                 patch("psutil.disk_usage", return_value=fake_usage), \
                 patch("psutil.cpu_percent", return_value=12.0):
                status_text = tb.get_hardware_status()
                self.assertIn("**Диск /:**", status_text)
                self.assertNotIn("/snap/", status_text)
                self.assertNotIn("/boot/efi", status_text)

            from PIL import Image
            img = Image.new("RGB", (32, 32), color="red")
            with patch("services.telegram.telegram_bot.take_screenshot_pil", return_value=img):
                b64 = tb.take_screenshot_base64()
                raw = base64.b64decode(b64)
                loaded = Image.open(io.BytesIO(raw))
                self.assertEqual(loaded.size, (32, 32))

            with patch.object(tb._platform_power, "cancel_shutdown") as mock_cancel:
                dw = tb.DownloadWatcher()
                dw.cancel_shutdown()
                mock_cancel.assert_called_once()
        finally:
            if not had_winreg:
                sys.modules.pop("winreg", None)

    def test_09_first_movie_torrserver_warning_and_worker(self):
        had_winreg = "winreg" in sys.modules
        if not had_winreg:
            sys.modules["winreg"] = types.ModuleType("winreg")
        try:
            from core.nlp.parser.command_parser import CommandParser
            from services.torrent.torrserver_manager import torr_manager
            from services.torrent.vlc_player import vlc_player
            from gui.windows.chat_window import TorrServerDownloadWorker

            parser = CommandParser.__new__(CommandParser)
            fake_movie = {"title": "Интерстеллар", "magnet": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567", "is_series": False}

            with patch.object(vlc_player, "is_available", return_value=True), \
                 patch.object(vlc_player, "needs_initial_setup", return_value=False), \
                 patch.object(torr_manager, "is_binary_installed", return_value=False):
                resp = parser._start_movie_playback(fake_movie, "Включи фильм Интерстеллар", False, is_choice=False)
                self.assertEqual(resp.get("action"), "download_torrserver_and_play")
                self.assertIn("TorrServer", resp.get("chat", ""))
                self.assertIn("TorrServer", resp.get("voice", ""))
                self.assertEqual(resp["movie_payload"]["title"], "Интерстеллар")

            worker = TorrServerDownloadWorker(resp["movie_payload"])
            ready_events = []
            worker.playback_ready.connect(lambda u, t: ready_events.append((u, t)))
            with patch.object(torr_manager, "download_linux_binary", return_value=(True, "/tmp/TorrServer-linux-amd64")), \
                 patch.object(torr_manager, "start_server", return_value=True), \
                 patch.object(torr_manager, "get_stream_url", return_value="http://127.0.0.1:8090/stream?test"):
                worker.run()
            self.assertEqual(ready_events, [("http://127.0.0.1:8090/stream?test", "Интерстеллар")])
        finally:
            if not had_winreg:
                sys.modules.pop("winreg", None)

    def test_10_vlc_linux_auto_install_and_no_qt_updates_notif(self):
        from core.nlp.parser.command_parser import CommandParser
        from gui.windows.chat_window import VlcInstallWorker
        from services.torrent.torrserver_manager import torr_manager
        from services.torrent.vlc_player import VLCPlayer, vlc_player
        from services.yandex.yandex_music_manager import YandexMusicManager

        # YandexMusic & VLCPlayer must not pass Windows-only --no-qt-updates-notif on Linux
        ym_args = YandexMusicManager._build_vlc_args()
        self.assertNotIn("--no-qt-updates-notif", ym_args)

        player = VLCPlayer()
        with patch.object(player, "is_available", return_value=True), \
             patch.object(player, "setup_vlc_privacy_config"), \
             patch.object(player, "_build_vlc_cmd", side_effect=lambda a: ["vlc", *a]) as mock_cmd, \
             patch("subprocess.Popen"):
            self.assertTrue(player.play("http://127.0.0.1:8090/stream", "Matrix"))
            launched_args = mock_cmd.call_args.args[0]
            self.assertNotIn("--no-qt-updates-notif", launched_args)

        # Linux _install_linux uses pkexec apt-get install vlc libvlc5
        player_missing = VLCPlayer()
        player_missing.vlc_path = None
        with patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}" if x in ("pkexec", "apt-get") else None), \
             patch.object(player_missing, "_find_vlc", return_value="/usr/bin/vlc"), \
             patch.object(player_missing, "setup_vlc_privacy_config"), \
             patch.object(player_missing, "mark_setup_done"), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess(["pkexec"], 0)) as mock_run:
            self.assertTrue(player_missing.install_silent())
            apt_cmd = mock_run.call_args.args[0]
            self.assertEqual(apt_cmd[0], "/usr/bin/pkexec")
            self.assertIn("vlc libvlc5", " ".join(apt_cmd))

        # Movie request when VLC is absent on Linux returns warning + install_vlc_and_play action
        parser = CommandParser.__new__(CommandParser)
        fake_movie = {"title": "Начало", "magnet": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "is_series": False}
        with patch.object(vlc_player, "is_available", return_value=False):
            resp = parser._start_movie_playback(fake_movie, "Включи Начало", False)
            self.assertEqual(resp.get("action"), "install_vlc_and_play")
            self.assertIn("VLC", resp.get("chat", ""))

        # VlcInstallWorker chains to TorrServer when TorrServer is missing
        w_need_ts = VlcInstallWorker(resp["movie_payload"])
        chained = []
        w_need_ts.need_torrserver.connect(lambda p: chained.append(p))
        with patch.object(vlc_player, "is_available", side_effect=[False, True]), \
             patch.object(vlc_player, "install_silent", return_value=True), \
             patch("core.system.actions.ym_manager.reinit_vlc", return_value=True), \
             patch.object(torr_manager, "is_binary_installed", return_value=False):
            w_need_ts.run()
        self.assertEqual(len(chained), 1)
        self.assertEqual(chained[0]["title"], "Начало")

        # VlcInstallWorker goes directly to playback_ready when TorrServer is installed
        w_ready = VlcInstallWorker(resp["movie_payload"])
        ready = []
        w_ready.playback_ready.connect(lambda u, t: ready.append((u, t)))
        with patch.object(vlc_player, "is_available", return_value=True), \
             patch("core.system.actions.ym_manager.reinit_vlc", return_value=True), \
             patch.object(torr_manager, "is_binary_installed", return_value=True), \
             patch.object(torr_manager, "start_server", return_value=True), \
             patch.object(torr_manager, "get_stream_url", return_value="http://127.0.0.1:8090/stream?inception"):
            w_ready.run()
        self.assertEqual(ready, [("http://127.0.0.1:8090/stream?inception", "Начало")])

    def test_11_yandex_music_wave_favorites_playlists_and_phrases(self):
        from core.nlp.parser.command_parser import CommandParser
        from core.system.actions import LIKE_TRACK_PHRASES, NEXT_TRACK_PHRASES, SystemActions, ym_manager
        from services.yandex.yandex_music_manager import YandexMusicManager

        class _InlineThread:
            def __init__(self, target=None, daemon=None):
                self._target = target

            def start(self):
                if self._target:
                    self._target()

        def _mk_track(tid: int, title: str):
            t = MagicMock()
            t.id = str(tid)
            t.title = title
            t.track = None
            return t

        ym = YandexMusicManager()
        ym.vlc_instance = MagicMock()
        ym.player = MagicMock()
        ym.player.audio_get_volume.return_value = 80
        ym.player.is_playing.return_value = True
        fake_client = MagicMock()
        ym.client = fake_client

        # 1. My Wave advances queue=<prev_id>, sends feedback, and skips previously played tracks
        t1, t2, t3 = _mk_track(101, "T1"), _mk_track(102, "T2"), _mk_track(103, "T3")
        rotor1 = MagicMock(batch_id="b1", sequence=[MagicMock(track=t1), MagicMock(track=t2)])
        rotor2 = MagicMock(batch_id="b2", sequence=[MagicMock(track=t1), MagicMock(track=t2), MagicMock(track=t3)])
        fake_client.rotor_station_tracks.side_effect = [rotor1, rotor2]

        with patch("services.yandex.yandex_music_manager.HAS_VLC", True), \
                patch.object(ym, "_ensure_vlc", return_value=True), \
                patch.object(ym, "_get_direct_stream_url", return_value="http://stream.local/1.mp3"), \
                patch.object(ym, "_start_watcher"), \
                patch("services.yandex.yandex_music_manager.threading.Thread", _InlineThread), \
                patch("services.yandex.yandex_music_manager.time.sleep"):
            self.assertIs(ym.play_my_wave(), True)
            self.assertEqual(ym.current_track.id, "101")
            ym.next_track(manual=True)
            self.assertEqual(ym.current_track.id, "102")
            ym.next_track(manual=False)
            self.assertEqual(ym.current_track.id, "103")
            second_call = fake_client.rotor_station_tracks.call_args_list[1]
            self.assertEqual(second_call.kwargs.get("queue"), "102")

            # 2. Specific track auto-continues into My Wave after finishing
            t_song = _mk_track(555, "Кукушка")
            rotor_after = MagicMock(batch_id="b3", sequence=[MagicMock(track=t_song), MagicMock(track=_mk_track(556, "Next"))])
            fake_client.search.return_value = MagicMock(best=MagicMock(type="track", result=t_song))
            fake_client.rotor_station_tracks.side_effect = [rotor_after]
            ym.play_query("кукушка")
            self.assertEqual(ym.current_track.id, "555")
            self.assertTrue(ym.is_radio)
            self.assertEqual(ym._wave_station, "user:onyourwave")
            ym.next_track(manual=False)
            self.assertEqual(ym.current_track.id, "556")

            # 3. Favorites & custom playlist lookup (exact + fuzzy)
            fav1, fav2 = _mk_track(701, "Fav1"), _mk_track(702, "Fav2")
            fake_client.users_likes_tracks.return_value = MagicMock(tracks=[MagicMock(track=fav1), MagicMock(track=fav2)])
            self.assertIs(ym.play_favorites(), True)
            self.assertIn(ym.current_track.id, ("701", "702"))

            pl_track = _mk_track(801, "Cyber")
            user_pl = MagicMock(title="Ночной Киберпанк", kind=7, owner=MagicMock(uid=1))
            user_pl.fetch_tracks.return_value = [MagicMock(track=pl_track)]
            fake_client.users_playlists_list.return_value = [user_pl]
            self.assertIs(ym.play_playlist("киберпанк"), True)
            self.assertEqual(ym.current_track.id, "801")
            self.assertEqual(ym._last_playlist_title, "Ночной Киберпанк")

        # 4. Parser rules + SystemActions phrases & routing
        parser = CommandParser.__new__(CommandParser)
        self.assertEqual(parser._check_rules("добавь в любимое"), "like_yandex_track")
        self.assertEqual(parser._check_rules("убери из любимого"), "unlike_yandex_track")
        self.assertEqual(parser._check_rules("включи моё любимое"), "play_yandex_favorites")
        self.assertEqual(parser._check_rules("включи плейлист киберпанк"), "play_music")

        with patch("core.system.actions._is_spotify_active", return_value=False):
            with patch.object(ym_manager, "current_track", _mk_track(901, "Cool")), \
                    patch.object(ym_manager, "like_current") as mock_like:
                like_reply = SystemActions.like_yandex_track("поставь лайк")
                mock_like.assert_called_once()
                self.assertIn(like_reply, LIKE_TRACK_PHRASES)

            with patch.object(ym_manager, "next_track"):
                next_reply = SystemActions.media_next_track()
                self.assertIn(next_reply, NEXT_TRACK_PHRASES)

            with patch.object(ym_manager, "play_favorites", return_value=True) as mock_fav, \
                    patch.object(ym_manager, "play_my_wave", return_value=True) as mock_wave, \
                    patch.object(ym_manager, "play_playlist", return_value=True) as mock_pl, \
                    patch.object(ym_manager, "play_query", return_value="Ищу") as mock_query:
                ym_manager._last_playlist_title = "Ночной Киберпанк"
                SystemActions.open_yandex_music("включи моё любимое", force_yandex=True)
                mock_fav.assert_called_once()

                SystemActions.open_yandex_music("включи мою волну", force_yandex=True)
                mock_wave.assert_called_once()

                pl_msg = SystemActions.open_yandex_music("включи плейлист ночной киберпанк", force_yandex=True)
                mock_pl.assert_called_once_with("ночной киберпанк")
                self.assertIn("Ночной Киберпанк", pl_msg)

                SystemActions.open_yandex_music("включи мою любимую песню кукушка", force_yandex=True)
                mock_query.assert_called_once_with("мою любимую кукушка")


if __name__ == "__main__":
    unittest.main(verbosity=2)
