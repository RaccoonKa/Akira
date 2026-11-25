import os
import sys
import ctypes.util
import difflib
import re
import random
import threading
import time
import hashlib
import xml.etree.ElementTree as ET
from collections import deque
import requests
import webbrowser
from core.utils.config import load_config

if sys.platform == "win32":
    vlc_paths = [
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC"
    ]
    for p in vlc_paths:
        if os.path.exists(p):
            try:
                os.add_dll_directory(p)
            except Exception:
                pass
            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
            plugins_dir = os.path.join(p, "plugins")
            if os.path.exists(plugins_dir):
                os.environ["VLC_PLUGIN_PATH"] = plugins_dir
else:
    if not os.environ.get("VLC_PLUGIN_PATH"):
        for p_dir in ("/usr/lib/x86_64-linux-gnu/vlc/plugins", "/usr/lib/aarch64-linux-gnu/vlc/plugins", "/usr/lib/vlc/plugins"):
            if os.path.isdir(p_dir):
                os.environ["VLC_PLUGIN_PATH"] = p_dir
                break
    ctypes.util.find_library("vlc")

try:
    import vlc
    HAS_VLC = True
except Exception:
    vlc = None
    HAS_VLC = False

from yandex_music import Client


class YandexMusicManager:
    @staticmethod
    def _build_vlc_args() -> list[str]:
        args = [
            "--no-video",
            "--quiet",
            "--network-caching=3000",
            "--no-qt-privacy-ask",
            "--no-qt-error-dialogs",
        ]
        if sys.platform == "win32":
            args.append("--no-qt-updates-notif")
        return args

    def reinit_vlc(self) -> bool:
        global HAS_VLC, vlc
        if sys.platform != "win32":
            if not os.environ.get("VLC_PLUGIN_PATH"):
                for p_dir in (
                    "/usr/lib/x86_64-linux-gnu/vlc/plugins",
                    "/usr/lib/aarch64-linux-gnu/vlc/plugins",
                    "/usr/lib/vlc/plugins",
                ):
                    if os.path.isdir(p_dir):
                        os.environ["VLC_PLUGIN_PATH"] = p_dir
                        break
            ctypes.util.find_library("vlc")

        if not HAS_VLC or vlc is None:
            try:
                import vlc as _vlc
                vlc = _vlc
                HAS_VLC = True
            except Exception:
                HAS_VLC = False

        if not HAS_VLC or vlc is None:
            self.vlc_instance = None
            self.player = None
            return False

        try:
            self.vlc_instance = vlc.Instance(*self._build_vlc_args())
            if not self.vlc_instance:
                self.player = None
                return False
            self.player = self.vlc_instance.media_player_new()
            if self.player:
                self.player.audio_set_volume(self.normal_volume)
                return True
            return False
        except Exception as e:
            print(f"[YandexMusic Init VLC Warning]: {e}")
            self.vlc_instance = None
            self.player = None
            return False

    def __init__(self):
        self.client = None
        self.normal_volume = 100
        self.is_ducked = False
        self.vlc_instance = None
        self.player = None
        self.reinit_vlc()
        self.queue = []
        self.history = []
        self.current_track = None
        self.is_radio = False
        self.watcher_thread = None
        self.stop_watcher = False
        self.is_transitioning = False
        self._recent_track_ids = deque(maxlen=150)
        self._wave_station = "user:onyourwave"
        self._wave_batch_id = None
        self._wave_last_track_id = None
        self._last_playlist_title = None

    def _extract_pure_token(self, raw_token):
        if not raw_token:
            return ""
        if "access_token=" in raw_token:
            match = re.search(r'access_token=([^&]+)', raw_token)
            if match:
                return match.group(1)
        return raw_token.strip()

    def _init_client(self):
        if not HAS_VLC:
            return False

        if self.client is not None:
            return True

        cfg = load_config()
        raw_token = cfg.get("api_keys", {}).get("yandex_music_token", "")
        token = self._extract_pure_token(raw_token)

        if not token:
            return False

        try:
            self.client = Client(token).init()
            return True
        except Exception as e:
            print(f"[YandexMusic Init Error]: {e}")
            return False

    def _get_direct_stream_url(self, track):
        try:
            if hasattr(track, 'track') and track.track:
                track = track.track
            if hasattr(track, 'fetch_track') and not hasattr(track, 'get_download_info'):
                track = track.fetch_track()

            if not hasattr(track, 'get_download_info'):
                return None

            info_list = track.get_download_info()
            if not info_list:
                return None
            info_sorted = sorted(info_list, key=lambda x: getattr(x, 'bitrate_in_kbps', 0), reverse=True)
            best_info = info_sorted[0]

            # 1. Официальный метод yandex_music с валидной криптоподписью
            if hasattr(best_info, 'get_direct_link') and callable(getattr(best_info, 'get_direct_link')):
                try:
                    direct = best_info.get_direct_link()
                    if direct:
                        return direct
                except Exception as e:
                    print(f"[YandexMusic get_direct_link Warning]: {e}")

            if hasattr(best_info, 'direct_link') and best_info.direct_link:
                return best_info.direct_link

            # 2. Ручной расчет по протоколу Yandex с валидным SIGN_SALT
            download_url = getattr(best_info, 'download_info_url', None)
            if download_url:
                resp = requests.get(download_url, timeout=5)
                if resp.status_code == 200:
                    xml_root = ET.fromstring(resp.text)
                    host = xml_root.findtext('host')
                    path = xml_root.findtext('path')
                    ts = xml_root.findtext('ts')
                    s = xml_root.findtext('s')

                    if host and path and ts and s:
                        sign_salt = "XGRlBW9FXlekgbPrRHuSiA"
                        secret = f"{sign_salt}{path[1:]}{s}"
                        md5_hash = hashlib.md5(secret.encode('utf-8')).hexdigest()
                        return f"https://{host}/get-mp3/{md5_hash}/{ts}{path}"
        except Exception as e:
            print(f"[YandexMusic Stream Error]: {e}")
        return None

    def _play_track_object(self, track):
        if not HAS_VLC or not self.player:
            self.is_transitioning = False
            return False

        try:
            if hasattr(track, 'track') and track.track:
                track = track.track
            if hasattr(track, 'fetch_track') and not hasattr(track, 'get_download_info'):
                track = track.fetch_track()

            stream_url = self._get_direct_stream_url(track)
            if not stream_url:
                self.is_transitioning = False
                return False

            if self.current_track:
                self.history.append(self.current_track)

            self.current_track = track
            self._remember_track(track)
            if self.is_radio:
                tid = self._track_id_str(track)
                if tid:
                    self._wave_last_track_id = tid
                    self._send_rotor_feedback(
                        self._wave_station,
                        "trackStarted",
                        track_id=tid,
                        batch_id=self._wave_batch_id,
                    )
            self.player.stop()
            media = self.vlc_instance.media_new(stream_url)
            self.player.set_media(media)
            self.player.audio_set_volume(self.normal_volume)
            self.player.play()
            time.sleep(0.4)
            self.player.audio_set_volume(self.normal_volume)
            self.is_transitioning = False
            return True
        except Exception as e:
            print(f"[YandexMusic Play Error]: {e}")
            self.is_transitioning = False
            return False

    def _ensure_vlc(self):
        """
        Гарантирует доступность VLC:
        - Если VLC не установлен, запускает тихую установку.
        - На Windows при необходимости открывает плеер для первичной настройки; на Linux сразу переинициализирует libvlc.
        Возвращает: True (готов), 'SETUP_NEEDED' (открыт для настройки пользователем) или 'DOWNLOAD_NEEDED' (сбой).
        """
        from services.torrent.vlc_player import vlc_player

        if not vlc_player.is_available():
            installed = vlc_player.install_silent()
            if installed:
                if sys.platform != "win32":
                    if self.reinit_vlc():
                        return True
                vlc_player.open_for_setup()
                return "SETUP_NEEDED"
            return "DOWNLOAD_NEEDED"

        if vlc_player.needs_initial_setup():
            vlc_player.open_for_setup()
            return "SETUP_NEEDED"

        if not HAS_VLC or not self.player:
            vlc_exe = vlc_player.vlc_path or vlc_player._find_vlc()
            if vlc_exe and sys.platform == "win32":
                vlc_dir = os.path.dirname(vlc_exe)
                try:
                    os.add_dll_directory(vlc_dir)
                except Exception:
                    pass
                os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")
                plugins_dir = os.path.join(vlc_dir, "plugins")
                if os.path.exists(plugins_dir):
                    os.environ["VLC_PLUGIN_PATH"] = plugins_dir
            self.reinit_vlc()

        return True if (HAS_VLC and self.player is not None) else "DOWNLOAD_NEEDED"

    def _track_id_str(self, track) -> str:
        if track is None:
            return ""
        inner = getattr(track, "track", None) or track
        tid = getattr(inner, "id", None) or getattr(track, "track_id", None) or getattr(track, "id", None)
        if tid is None:
            return ""
        return str(tid).split(":")[0]

    def _remember_track(self, track):
        tid = self._track_id_str(track)
        if tid and tid not in self._recent_track_ids:
            self._recent_track_ids.append(tid)

    def _filter_unseen_tracks(self, tracks: list) -> list:
        seen_recent = set(self._recent_track_ids)
        cur_id = self._track_id_str(self.current_track)
        if cur_id:
            seen_recent.add(cur_id)
        batch_seen = set()
        fresh = []
        fallback = []
        for tr in tracks:
            if not tr:
                continue
            tid = self._track_id_str(tr)
            if tid:
                if tid in batch_seen:
                    continue
                batch_seen.add(tid)
                if tid not in seen_recent:
                    fresh.append(tr)
                elif tid != cur_id:
                    fallback.append(tr)
            else:
                fresh.append(tr)
        return fresh if fresh else fallback

    def _send_rotor_feedback(self, station: str, event_type: str, track_id: str | None = None, batch_id: str | None = None):
        if not self.client or not station:
            return
        try:
            kwargs = {}
            if track_id:
                kwargs["track_id"] = track_id
            if batch_id:
                kwargs["batch_id"] = batch_id
            self.client.rotor_station_feedback(station, event_type, **kwargs)
        except Exception:
            pass

    def _fetch_wave_tracks(self, station: str = "user:onyourwave", queue_track_id: str | None = None) -> list:
        raw_items = []
        cur_queue = queue_track_id or self._wave_last_track_id
        for attempt in range(2):
            try:
                rotor = self.client.rotor_station_tracks(station, settings2=True, queue=cur_queue)
                if rotor:
                    self._wave_batch_id = getattr(rotor, "batch_id", None)
                    seq = getattr(rotor, "sequence", None) or []
                    batch = []
                    for item in seq:
                        tr = getattr(item, "track", None) or item
                        if tr:
                            batch.append(tr)
                    filtered = self._filter_unseen_tracks(batch)
                    if filtered:
                        return filtered
                    raw_items.extend(batch)
                    if batch and attempt == 0:
                        last_id = self._track_id_str(batch[-1])
                        if last_id and last_id != cur_queue:
                            self._send_rotor_feedback(station, "trackFinished", track_id=last_id, batch_id=self._wave_batch_id)
                            cur_queue = last_id
                            continue
            except Exception as e:
                print(f"[YandexMusic Rotor Station Warning]: {e}")
                break

        if raw_items:
            deduped = self._filter_unseen_tracks(raw_items)
            if deduped:
                return deduped

        # 2. Fallback на плейлист «Мне нравится» (любимые треки)
        try:
            likes = self.client.users_likes_tracks()
            if likes:
                raw_likes = list(likes.tracks) if hasattr(likes, "tracks") else list(likes)
                like_tracks = [getattr(it, "track", None) or it for it in raw_likes if it]
                filtered_likes = self._filter_unseen_tracks(like_tracks)
                if filtered_likes:
                    random.shuffle(filtered_likes)
                    return filtered_likes
        except Exception as e:
            print(f"[YandexMusic Likes Warning]: {e}")

        # 3. Fallback на популярные треки чарта
        try:
            chart = self.client.chart("world")
            if chart and hasattr(chart, "chart") and hasattr(chart.chart, "tracks"):
                chart_tracks = [getattr(ct, "track", None) or ct for ct in chart.chart.tracks if ct]
                filtered_chart = self._filter_unseen_tracks(chart_tracks)
                if filtered_chart:
                    random.shuffle(filtered_chart)
                    return filtered_chart
        except Exception as e:
            print(f"[YandexMusic Chart Warning]: {e}")

        return []

    def _resolve_playlist_tracks(self, raw_items: list) -> list:
        tracks = []
        for it in raw_items or []:
            tr = getattr(it, "track", None) or it
            if tr is not None:
                tracks.append(tr)
        return tracks

    def play_query(self, query):
        vlc_status = self._ensure_vlc()
        if vlc_status == "SETUP_NEEDED":
            return (
                "Я установила VLC плеер и открыла его! Пожалуйста, подтверди начальную настройку в окне плеера "
                "(выбери нужные галочки и нажми «Продолжить»), а затем скажи мне снова включить музыку."
            )
        elif vlc_status != True:
            webbrowser.open("https://www.videolan.org/vlc/")
            return "Для работы Яндекс Музыки нужен плеер. Открываю официальный сайт для скачивания."

        if not self._init_client():
            return "Чтобы я могла включить трек, пожалуйста, авторизуйся в Яндекс Музыке в настройках Акиры!"

        self.is_transitioning = True

        def _async_play():
            try:
                search_result = self.client.search(query)
                track = None
                if search_result:
                    best = getattr(search_result, "best", None)
                    if best and getattr(best, "type", None) == "track" and getattr(best, "result", None):
                        track = best.result
                    elif getattr(search_result, "tracks", None) and getattr(search_result.tracks, "results", None):
                        track = search_result.tracks.results[0]

                if not track:
                    self.is_transitioning = False
                    return

                # После завершения заказанного трека автоматически продолжаем «Моей волной»
                self.is_radio = True
                self._wave_station = "user:onyourwave"
                self._wave_batch_id = None
                self.queue = []
                tid = self._track_id_str(track)
                if tid:
                    self._wave_last_track_id = tid
                if self._play_track_object(track):
                    self._start_watcher()
                else:
                    self.is_transitioning = False
            except Exception as e:
                print(f"[YandexMusic Play Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_play, daemon=True).start()
        return f"Ищу {query}"

    def set_volume(self, volume: int):
        val = max(0, min(100, volume))
        self.normal_volume = val
        if HAS_VLC and self.player:
            self.player.audio_set_volume(val)

    def duck(self, factor: float = 0.2):
        if not HAS_VLC or not self.player or not self.player.is_playing():
            return
        if not self.is_ducked:
            current = self.player.audio_get_volume()
            if current > 0:
                self.normal_volume = current
            self.is_ducked = True
            target = max(1, int(self.normal_volume * factor))
            self.player.audio_set_volume(target)
        else:
            target = max(1, int(self.normal_volume * factor))
            if target < self.player.audio_get_volume():
                self.player.audio_set_volume(target)

    def unduck(self, level: int = None):
        if not HAS_VLC or not self.player:
            self.is_ducked = False
            return
        if self.is_ducked:
            restore_vol = self.normal_volume if level is None else level
            self.player.audio_set_volume(restore_vol)
            self.is_ducked = False

    def play_my_wave(self, station: str = "user:onyourwave"):
        vlc_status = self._ensure_vlc()
        if vlc_status == "SETUP_NEEDED":
            return (
                "Я установила VLC плеер и открыла его! Пожалуйста, подтверди начальную настройку в окне плеера "
                "(выбери нужные галочки и нажми «Продолжить»), а затем скажи мне снова включить музыку."
            )
        elif vlc_status != True:
            webbrowser.open("https://www.videolan.org/vlc/")
            return "Для работы Яндекс Музыки нужен плеер. Открываю официальный сайт для скачивания."

        if not self._init_client():
            return "Чтобы я могла запустить Мою волну, пожалуйста, укажи токен Яндекс Музыки в настройках Акиры!"

        self.is_transitioning = True

        def _async_wave():
            try:
                prev_id = self._track_id_str(self.current_track) or self._wave_last_track_id
                self._wave_station = station
                self.is_radio = True
                self.queue = []

                self._send_rotor_feedback(station, "radioStarted")
                track_items = self._fetch_wave_tracks(station=station, queue_track_id=prev_id)
                if not track_items:
                    self.is_transitioning = False
                    return

                first_track = track_items[0]
                self.queue = track_items[1:]

                if self._play_track_object(first_track):
                    self._start_watcher()
                else:
                    self.is_transitioning = False
            except Exception as e:
                print(f"[YandexMusic Wave Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_wave, daemon=True).start()
        return True

    def play_favorites(self):
        """Включает плейлист «Мне нравится» (Избранное) с продолжением в Мою волну."""
        vlc_status = self._ensure_vlc()
        if vlc_status == "SETUP_NEEDED":
            return (
                "Я установила VLC плеер и открыла его! Пожалуйста, подтверди начальную настройку в окне плеера "
                "(выбери нужные галочки и нажми «Продолжить»), а затем скажи мне снова включить музыку."
            )
        elif vlc_status != True:
            webbrowser.open("https://www.videolan.org/vlc/")
            return "Для работы Яндекс Музыки нужен плеер. Открываю официальный сайт для скачивания."

        if not self._init_client():
            return "Чтобы я могла включить твоё Избранное, пожалуйста, укажи токен Яндекс Музыки в настройках Акиры!"

        try:
            likes = self.client.users_likes_tracks()
            raw_likes = list(likes.tracks) if likes and hasattr(likes, "tracks") else (list(likes) if likes else [])
            tracks = self._resolve_playlist_tracks(raw_likes)
        except Exception as e:
            print(f"[YandexMusic Favorites Error]: {e}")
            return "Не удалось загрузить твой плейлист «Мне нравится» из Яндекс Музыки."

        if not tracks:
            return "В твоём Избранном на Яндекс Музыке пока нет лайкнутых треков."

        random.shuffle(tracks)
        self.is_transitioning = True
        self.is_radio = True
        self._wave_station = "user:onyourwave"
        self.queue = tracks[1:200]

        def _async_fav():
            try:
                if self._play_track_object(tracks[0]):
                    self._start_watcher()
                else:
                    self.is_transitioning = False
            except Exception as e:
                print(f"[YandexMusic Favorites Play Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_fav, daemon=True).start()
        return True

    @staticmethod
    def _normalize_playlist_title(name: str) -> str:
        return re.sub(r'[^\w\sа-яёa-z0-9]', ' ', (name or '').lower()).strip()

    def _find_matching_playlist(self, playlist_name: str):
        target_norm = self._normalize_playlist_title(playlist_name)
        if not target_norm:
            return None

        best_pl = None
        best_score = 0.0

        # 1. Ищем среди личных плейлистов пользователя
        try:
            user_playlists = self.client.users_playlists_list() or []
            for pl in user_playlists:
                title_norm = self._normalize_playlist_title(getattr(pl, "title", ""))
                if not title_norm:
                    continue
                if title_norm == target_norm:
                    return pl
                if target_norm in title_norm or title_norm in target_norm:
                    score = 0.85 + 0.14 * min(len(target_norm), len(title_norm)) / max(len(target_norm), len(title_norm))
                else:
                    score = difflib.SequenceMatcher(None, target_norm, title_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_pl = pl
        except Exception as e:
            print(f"[YandexMusic User Playlists Warning]: {e}")

        if best_pl is not None and best_score >= 0.60:
            return best_pl

        # 2. Fallback: поиск среди публичных/редакционных плейлистов Яндекса
        try:
            search_res = self.client.search(playlist_name, type_="playlist")
            if search_res:
                best = getattr(search_res, "best", None)
                if best and getattr(best, "type", None) == "playlist" and getattr(best, "result", None):
                    return best.result
                pls = getattr(search_res, "playlists", None)
                if pls and getattr(pls, "results", None):
                    return pls.results[0]
        except Exception as e:
            print(f"[YandexMusic Search Playlist Warning]: {e}")

        return None

    def play_playlist(self, playlist_name: str):
        """Находит и запускает плейлист пользователя или публичный плейлист по названию."""
        vlc_status = self._ensure_vlc()
        if vlc_status == "SETUP_NEEDED":
            return (
                "Я установила VLC плеер и открыла его! Пожалуйста, подтверди начальную настройку в окне плеера "
                "(выбери нужные галочки и нажми «Продолжить»), а затем скажи мне снова включить музыку."
            )
        elif vlc_status != True:
            webbrowser.open("https://www.videolan.org/vlc/")
            return "Для работы Яндекс Музыки нужен плеер. Открываю официальный сайт для скачивания."

        if not self._init_client():
            return "Чтобы я могла включить плейлист, пожалуйста, укажи токен Яндекс Музыки в настройках Акиры!"

        matched_pl = self._find_matching_playlist(playlist_name)
        if matched_pl is None:
            return None

        try:
            raw_tracks = []
            if hasattr(matched_pl, "fetch_tracks"):
                raw_tracks = matched_pl.fetch_tracks() or []
            if not raw_tracks and getattr(matched_pl, "tracks", None):
                raw_tracks = list(matched_pl.tracks)
            if not raw_tracks and getattr(matched_pl, "kind", None) is not None:
                owner = getattr(matched_pl, "owner", None)
                uid = getattr(owner, "uid", None) if owner else None
                full_pl = self.client.users_playlists(matched_pl.kind, user_id=uid)
                if isinstance(full_pl, list) and full_pl:
                    full_pl = full_pl[0]
                if full_pl and getattr(full_pl, "tracks", None):
                    raw_tracks = list(full_pl.tracks)
            tracks = self._resolve_playlist_tracks(raw_tracks)
        except Exception as e:
            print(f"[YandexMusic Playlist Fetch Error]: {e}")
            return None

        if not tracks:
            self._last_playlist_title = getattr(matched_pl, "title", None) or playlist_name
            return "EMPTY"

        self._last_playlist_title = getattr(matched_pl, "title", None) or playlist_name
        self.is_transitioning = True
        self.is_radio = True
        self._wave_station = "user:onyourwave"
        self.queue = tracks[1:200]

        def _async_pl():
            try:
                if self._play_track_object(tracks[0]):
                    self._start_watcher()
                else:
                    self.is_transitioning = False
            except Exception as e:
                print(f"[YandexMusic Playlist Play Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_pl, daemon=True).start()
        return True

    def toggle_pause(self):
        if not HAS_VLC or not self.player:
            return
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        if HAS_VLC and self.player:
            self.player.stop()
        self.stop_watcher = True
        self.current_track = None
        self.queue = []
        return "Музыка выключена"

    def next_track(self, manual: bool = True):
        if not HAS_VLC or self.is_transitioning:
            return

        self.is_transitioning = True

        def _async_next():
            try:
                prev_id = self._track_id_str(self.current_track) or self._wave_last_track_id
                if self.is_radio and prev_id:
                    self._send_rotor_feedback(
                        self._wave_station,
                        "skip" if manual else "trackFinished",
                        track_id=prev_id,
                        batch_id=self._wave_batch_id,
                    )

                if self.queue:
                    next_tr = self.queue.pop(0)
                    if self._play_track_object(next_tr):
                        return

                if self.is_radio:
                    if self._init_client():
                        fresh = self._fetch_wave_tracks(
                            station=self._wave_station,
                            queue_track_id=prev_id,
                        )
                        if fresh:
                            self.queue = fresh[1:]
                            self._play_track_object(fresh[0])
                            return
                self.is_transitioning = False
            except Exception as e:
                print(f"[YandexMusic Next Track Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_next, daemon=True).start()

    def prev_track(self):
        if not HAS_VLC or self.is_transitioning:
            return

        self.is_transitioning = True

        def _async_prev():
            if self.history:
                prev_tr = self.history.pop()
                if self.current_track:
                    self.queue.insert(0, self.current_track)
                self._play_track_object(prev_tr)
            else:
                self.is_transitioning = False

        threading.Thread(target=_async_prev, daemon=True).start()

    def like_current(self):
        def _async_like():
            if not self._init_client() or not self.current_track:
                return
            try:
                self.client.users_likes_tracks_add(self.current_track.id)
            except Exception as e:
                print(f"[YandexMusic Like Error]: {e}")

        threading.Thread(target=_async_like, daemon=True).start()

    def unlike_current(self):
        def _async_unlike():
            if not self._init_client() or not self.current_track:
                return
            try:
                self.client.users_likes_tracks_remove(self.current_track.id)
            except Exception as e:
                print(f"[YandexMusic Unlike Error]: {e}")

        threading.Thread(target=_async_unlike, daemon=True).start()

    def _start_watcher(self):
        if self.watcher_thread and self.watcher_thread.is_alive():
            return
        self.stop_watcher = False
        self.watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watcher_thread.start()

    def _watch_loop(self):
        while not self.stop_watcher:
            time.sleep(0.5)
            if not HAS_VLC or not self.player:
                break
            if self.is_transitioning:
                continue
            state = self.player.get_state()
            if state == vlc.State.Ended:
                self.next_track(manual=False)