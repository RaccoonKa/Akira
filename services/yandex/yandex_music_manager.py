import os
import sys
import ctypes.util
import difflib
import math
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
            "--network-caching=1200",
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
            old_primary = getattr(self, "player", None)
            old_standby = getattr(self, "_standby_player", None)
            for p in (old_primary, old_standby):
                if p is not None:
                    try:
                        p.stop()
                    except Exception:
                        pass

            self.vlc_instance = vlc.Instance(*self._build_vlc_args())
            if not self.vlc_instance:
                self.player = None
                self._standby_player = None
                return False
            self.player = self.vlc_instance.media_player_new()
            self._standby_player = self.vlc_instance.media_player_new()
            if self.player:
                self.player.audio_set_mute(False)
                self.player.audio_set_volume(self.normal_volume)
                if self._standby_player:
                    self._standby_player.audio_set_mute(False)
                    self._standby_player.audio_set_volume(self.normal_volume)
                return True
            return False
        except Exception as e:
            print(f"[YandexMusic Init VLC Warning]: {e}")
            self.vlc_instance = None
            self.player = None
            self._standby_player = None
            return False

    def __init__(self):
        self.client = None
        self.normal_volume = 100
        self.is_ducked = False
        self._duck_factor = 0.2
        self.vlc_instance = None
        self.player = None
        self._standby_player = None
        self.reinit_vlc()
        self.queue = []
        self.history = []
        self.current_track = None
        self.is_radio = False
        self.watcher_thread = None
        self.stop_watcher = False
        self.is_transitioning = False
        self.is_fading = False
        self.crossfade_auto_sec = 4.5
        self.crossfade_manual_sec = 1.5
        self.crossfade_stop_sec = 0.35
        self._play_lock = threading.RLock()
        self._play_seq = 0
        self._duck_seq = 0
        self._preloaded_next = None
        self._preloading_for_id = None
        self._crossfade_triggered_for_id = None
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
                for attempt in range(2):
                    try:
                        direct = best_info.get_direct_link()
                        if direct:
                            return direct
                    except Exception as e:
                        if attempt == 1:
                            print(f"[YandexMusic get_direct_link Warning]: {e}")
                        else:
                            time.sleep(0.2)

            if hasattr(best_info, 'direct_link') and best_info.direct_link:
                return best_info.direct_link

            # 2. Ручной расчет по протоколу Yandex с валидным SIGN_SALT
            download_url = getattr(best_info, 'download_info_url', None)
            if download_url:
                for attempt in range(2):
                    try:
                        resp = requests.get(download_url, timeout=10)
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
                        if attempt == 1:
                            print(f"[YandexMusic Stream Fetch Retry Error]: {e}")
                        else:
                            time.sleep(0.2)
        except Exception as e:
            print(f"[YandexMusic Stream Error]: {e}")
        return None

    def _effective_volume(self, base_volume: int | None = None) -> int:
        base = self.normal_volume if base_volume is None else max(0, min(100, int(base_volume)))
        if self.is_ducked:
            return max(1, int(round(base * self._duck_factor))) if base > 0 else 0
        return base

    @staticmethod
    def _is_real_vlc_player(player) -> bool:
        if not HAS_VLC or vlc is None or player is None:
            return False
        try:
            return isinstance(player.get_state(), vlc.State)
        except Exception:
            return False

    def _can_crossfade(self, old_player, standby_player) -> bool:
        if not self._is_real_vlc_player(old_player) or not self._is_real_vlc_player(standby_player):
            return False
        if old_player is standby_player:
            return False
        try:
            state = old_player.get_state()
            return state in (vlc.State.Playing, vlc.State.Buffering)
        except Exception:
            return False

    @staticmethod
    def _unwrap_track(track):
        if hasattr(track, 'track') and track.track:
            track = track.track
        if hasattr(track, 'fetch_track') and not hasattr(track, 'get_download_info'):
            track = track.fetch_track()
        return track

    def _commit_active_track(self, track):
        if self.current_track:
            self.history.append(self.current_track)
        self.current_track = track
        self._remember_track(track)
        self._preloaded_next = None
        self._preloading_for_id = None
        self._crossfade_triggered_for_id = None
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

    def _play_single_deck(self, track, stream_url: str, my_seq: int) -> bool:
        with self._play_lock:
            if my_seq != self._play_seq or not HAS_VLC or not self.player or not self.vlc_instance:
                self.is_transitioning = False
                return False
            self._commit_active_track(track)
            target_vol = self._effective_volume()
            self.player.stop()
            media = self.vlc_instance.media_new(stream_url)
            self.player.set_media(media)
            self.player.audio_set_mute(False)
            self.player.audio_set_volume(target_vol)
            self.player.play()
            self.is_fading = False

        # Ждём реального открытия аудиовывода (выхода из Opening) и только затем фиксируем target_vol,
        # чтобы VLC/PulseAudio не оставили громкость 0% или отложенный duck после долгого буфера.
        open_deadline = time.perf_counter() + 6.5
        hold_deadline = None
        while time.perf_counter() < open_deadline:
            if my_seq != self._play_seq or not self.player:
                break
            try:
                st = self.player.get_state()
                if st in (vlc.State.Error, vlc.State.Ended):
                    self.is_transitioning = False
                    return False
                self.player.audio_set_mute(False)
                self.player.audio_set_volume(self._effective_volume())
                if st == vlc.State.Playing:
                    if hold_deadline is None:
                        hold_deadline = time.perf_counter() + 0.45
                    elif time.perf_counter() >= hold_deadline:
                        break
            except Exception:
                pass
            time.sleep(0.025)
        self.is_transitioning = False
        return True

    def _start_first_playable_track(self, tracks: list) -> bool:
        """Пытается запустить первый доступный трек из списка (до 3 попыток, если первый битый/недоступен)."""
        if not tracks:
            self.is_transitioning = False
            return False

        candidates = list(tracks)
        max_tries = min(3, len(candidates))
        for idx in range(max_tries):
            self.queue = candidates[idx + 1:]
            if self._play_track_object(candidates[idx]):
                self._start_watcher()
                return True
        self.is_transitioning = False
        return False

    @staticmethod
    def _clamp_player_silent(player):
        """Удерживает плеер в тишине на этапе открытия аудиопотока libVLC."""
        try:
            if not player.audio_get_mute():
                player.audio_set_mute(True)
        except Exception:
            pass
        try:
            if player.audio_get_volume() != 0:
                player.audio_set_volume(0)
        except Exception:
            pass

    def _crossfade_to_track(
        self,
        track,
        stream_url: str,
        fade_sec: float,
        my_seq: int,
        old_player,
        new_player,
        is_auto: bool = False,
    ) -> bool:
        with self._play_lock:
            if my_seq != self._play_seq or not self.vlc_instance:
                if my_seq == self._play_seq:
                    self.is_transitioning = False
                return False
            try:
                new_player.stop()
            except Exception:
                pass
            media = self.vlc_instance.media_new(stream_url)
            new_player.set_media(media)
            try:
                new_player.audio_set_mute(True)
            except Exception:
                pass
            new_player.audio_set_volume(0)
            new_player.play()

        # Ждём реального старта декодирования/аудиовывода нового трека, непрерывно фиксируя mute=True и volume=0,
        # чтобы libVLC при создании PulseAudio/WASAPI sink-input не пробил на 100% перед началом кроссфейда.
        wait_deadline = time.perf_counter() + 6.5
        started_ok = False
        while time.perf_counter() < wait_deadline:
            self._clamp_player_silent(new_player)
            if my_seq != self._play_seq or self.stop_watcher:
                with self._play_lock:
                    if new_player is not self.player:
                        try:
                            new_player.stop()
                            new_player.audio_set_mute(False)
                        except Exception:
                            pass
                    if my_seq == self._play_seq:
                        self.is_transitioning = False
                return False
            try:
                st = new_player.get_state()
                cur_t = new_player.get_time()
                if st in (vlc.State.Error, vlc.State.Ended):
                    break
                if st == vlc.State.Playing and cur_t is not None and cur_t > 25:
                    # Дополнительная фиксация тишины после открытия аудиовывода
                    for _ in range(3):
                        self._clamp_player_silent(new_player)
                        time.sleep(0.008)
                    started_ok = True
                    break
            except Exception:
                break
            time.sleep(0.008)

        if not started_ok:
            with self._play_lock:
                if new_player is not self.player:
                    try:
                        new_player.stop()
                        new_player.audio_set_mute(False)
                    except Exception:
                        pass
            return self._play_single_deck(track, stream_url, my_seq)

        # Подстраиваем длительность кроссфейда под фактический остаток старого трека
        actual_fade = max(0.35, float(fade_sec))
        old_still_active = False
        try:
            old_state = old_player.get_state()
            old_still_active = old_state not in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error)
        except Exception:
            old_still_active = False

        if is_auto:
            try:
                old_len = old_player.get_length()
                old_time = old_player.get_time()
                if old_still_active and old_len and old_len > 0 and old_time is not None and old_time >= 0:
                    rem_sec = (old_len - old_time) / 1000.0
                    if rem_sec > 0.5:
                        actual_fade = min(actual_fade, max(0.9, rem_sec - 0.12))
                    else:
                        actual_fade = min(actual_fade, 1.2)
                elif not old_still_active:
                    actual_fade = min(actual_fade, 1.2)
            except Exception:
                pass

        with self._play_lock:
            if my_seq != self._play_seq or self.stop_watcher:
                if new_player is not self.player:
                    try:
                        new_player.stop()
                        new_player.audio_set_mute(False)
                    except Exception:
                        pass
                if my_seq == self._play_seq:
                    self.is_transitioning = False
                return False

            try:
                old_start_raw = int(old_player.audio_get_volume())
            except Exception:
                old_start_raw = self._effective_volume()
            old_start_vol = old_start_raw if old_start_raw > 0 else self._effective_volume()

            self._commit_active_track(track)
            self.player = new_player
            self._standby_player = old_player
            self.is_transitioning = False
            self.is_fading = True

            # Снимаем mute только при гарантированно нулевой громкости
            try:
                new_player.audio_set_volume(0)
                new_player.audio_set_mute(False)
                new_player.audio_set_volume(0)
            except Exception:
                pass

        step_dt = 0.04
        steps = max(10, int(round(actual_fade / step_dt)))
        smooth_target = float(self._effective_volume())
        for idx in range(1, steps + 1):
            if my_seq != self._play_seq or self.stop_watcher:
                break
            try:
                if new_player.get_state() == vlc.State.Paused:
                    break
            except Exception:
                pass

            progress = idx / steps
            desired_target = float(self._effective_volume())
            # Плавное следование за изменением target (например, при unduck речи во время кроссфейда)
            smooth_target += (desired_target - smooth_target) * 0.25

            in_gain = math.sin(progress * (math.pi / 2.0)) ** 1.15
            out_gain = math.cos(progress * (math.pi / 2.0)) ** 1.35

            in_vol = int(round(smooth_target * in_gain))
            cap_target = int(round(max(desired_target, smooth_target)))
            if cap_target > 0:
                in_vol = max(0, min(100, min(cap_target, in_vol)))

            old_ceiling = min(old_start_vol, desired_target) if self.is_ducked else old_start_vol
            out_vol = max(0, int(round(old_ceiling * out_gain)))

            try:
                if new_player.audio_get_mute():
                    new_player.audio_set_mute(False)
                new_player.audio_set_volume(in_vol)
            except Exception:
                pass

            try:
                if old_player.get_state() not in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
                    old_player.audio_set_volume(out_vol)
            except Exception:
                pass

            time.sleep(step_dt)

        with self._play_lock:
            if my_seq == self._play_seq:
                try:
                    new_player.audio_set_mute(False)
                    new_player.audio_set_volume(self._effective_volume())
                except Exception:
                    pass
                if old_player is not self.player:
                    try:
                        old_player.audio_set_volume(0)
                        old_player.stop()
                        old_player.audio_set_mute(False)
                    except Exception:
                        pass
                self.is_fading = False
        return True

    def _play_track_object(
        self,
        track,
        fade_duration: float | None = None,
        preloaded_url: str | None = None,
        is_auto: bool = False,
    ):
        if not HAS_VLC or not self.player:
            self.is_transitioning = False
            return False

        try:
            track = self._unwrap_track(track)
            stream_url = preloaded_url or self._get_direct_stream_url(track)
            if not stream_url:
                self.is_transitioning = False
                return False

            with self._play_lock:
                self._play_seq += 1
                my_seq = self._play_seq
                old_player = self.player
                standby_player = self._standby_player

            fade_sec = (
                self.crossfade_manual_sec if fade_duration is None else max(0.0, float(fade_duration))
            )
            if self._can_crossfade(old_player, standby_player) and fade_sec > 0.0:
                return self._crossfade_to_track(
                    track=track,
                    stream_url=stream_url,
                    fade_sec=fade_sec,
                    my_seq=my_seq,
                    old_player=old_player,
                    new_player=standby_player,
                    is_auto=is_auto,
                )

            return self._play_single_deck(track, stream_url, my_seq)
        except Exception as e:
            print(f"[YandexMusic Play Error]: {e}")
            self.is_transitioning = False
            self.is_fading = False
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
        val = max(0, min(100, int(volume)))
        self.normal_volume = val
        if HAS_VLC and self.player and not self.is_fading:
            self.player.audio_set_volume(self._effective_volume())

    def duck(self, factor: float = 0.2):
        self._duck_seq += 1
        if not HAS_VLC or not self.player:
            return
        if not (self.player.is_playing() or self.is_fading or self.is_transitioning):
            return
        if not self.is_ducked:
            if not self.is_fading:
                current = self.player.audio_get_volume()
                if current > 0:
                    self.normal_volume = current
            self._duck_factor = factor
            self.is_ducked = True
            target = self._effective_volume()
            self.player.audio_set_volume(target)
            if self.is_fading and self._standby_player:
                try:
                    if self._standby_player.audio_get_volume() > target:
                        self._standby_player.audio_set_volume(target)
                except Exception:
                    pass
        else:
            self._duck_factor = min(self._duck_factor, factor)
            target = self._effective_volume()
            if target < self.player.audio_get_volume():
                self.player.audio_set_volume(target)

    def unduck(self, level: int = None):
        if not HAS_VLC or not self.player:
            self.is_ducked = False
            return
        if self.is_ducked:
            self._duck_seq += 1
            my_duck_seq = self._duck_seq
            self.is_ducked = False
            restore_vol = self.normal_volume if level is None else max(0, min(100, int(level)))
            if level is not None:
                self.normal_volume = restore_vol
            if self.is_fading:
                return

            player = self.player
            if not self._is_real_vlc_player(player):
                player.audio_set_volume(restore_vol)
                return

            try:
                cur_vol = max(0, int(player.audio_get_volume()))
            except Exception:
                cur_vol = 0
            if cur_vol >= restore_vol or restore_vol <= 0:
                try:
                    player.audio_set_volume(restore_vol)
                except Exception:
                    pass
                return

            def _smooth_restore():
                # Если поток ещё открывается (Opening), сперва ждём открытия аудиовывода
                wait_open_end = time.perf_counter() + 4.5
                while time.perf_counter() < wait_open_end:
                    if my_duck_seq != self._duck_seq or self.is_ducked or self.is_fading or player is not self.player:
                        return
                    try:
                        st = player.get_state()
                        if st in (vlc.State.Playing, vlc.State.Buffering):
                            break
                        if st in (vlc.State.Stopped, vlc.State.Ended, vlc.State.Error):
                            return
                    except Exception:
                        return
                    time.sleep(0.04)

                try:
                    start_v = int(player.audio_get_volume())
                except Exception:
                    start_v = -1
                base_v = cur_vol if start_v < 0 else max(0, min(restore_vol, start_v))

                steps = 10
                for idx in range(1, steps + 1):
                    if my_duck_seq != self._duck_seq or self.is_ducked or self.is_fading:
                        return
                    if player is not self.player:
                        return
                    try:
                        st = player.get_state()
                        if st in (vlc.State.Stopped, vlc.State.Ended, vlc.State.Error):
                            return
                        player.audio_set_mute(False)
                        v = int(round(base_v + (restore_vol - base_v) * (idx / steps)))
                        player.audio_set_volume(v)
                    except Exception:
                        return
                    time.sleep(0.035)

            threading.Thread(target=_smooth_restore, daemon=True).start()

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

        self.stop_watcher = False
        self.is_transitioning = True

        def _async_wave():
            try:
                prev_id = self._track_id_str(self.current_track) or self._wave_last_track_id
                self._wave_station = station
                self.is_radio = True
                self.queue = []

                self._send_rotor_feedback(station, "radioStarted")
                track_items = self._fetch_wave_tracks(station=station, queue_track_id=prev_id)
                if not track_items and prev_id:
                    track_items = self._fetch_wave_tracks(station=station, queue_track_id=None)
                if not track_items:
                    self.is_transitioning = False
                    return

                self._start_first_playable_track(track_items)
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
        self.stop_watcher = False
        self.is_transitioning = True
        self.is_radio = True
        self._wave_station = "user:onyourwave"
        chosen = tracks[:200]

        def _async_fav():
            try:
                self._start_first_playable_track(chosen)
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
        self.stop_watcher = False
        self.is_transitioning = True
        self.is_radio = True
        self._wave_station = "user:onyourwave"
        chosen = tracks[:200]

        def _async_pl():
            try:
                self._start_first_playable_track(chosen)
            except Exception as e:
                print(f"[YandexMusic Playlist Play Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_pl, daemon=True).start()
        return True

    def toggle_pause(self):
        if not HAS_VLC or not self.player:
            return
        if self.is_fading:
            with self._play_lock:
                self._play_seq += 1
                self.is_fading = False
                if self._standby_player:
                    try:
                        self._standby_player.stop()
                    except Exception:
                        pass
                try:
                    self.player.audio_set_volume(self._effective_volume())
                except Exception:
                    pass
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        with self._play_lock:
            self._play_seq += 1
            self.is_fading = False
            self.is_transitioning = False
            self._preloaded_next = None
            self._preloading_for_id = None
            self._crossfade_triggered_for_id = None
            primary = self.player
            standby = self._standby_player

        if standby is not None:
            try:
                standby.stop()
            except Exception:
                pass

        if HAS_VLC and primary:
            if self._is_real_vlc_player(primary) and primary.is_playing() and self.crossfade_stop_sec > 0:
                try:
                    start_vol = max(0, int(primary.audio_get_volume()))
                    if start_vol > 0:
                        for idx in range(5, -1, -1):
                            primary.audio_set_volume(int(round(start_vol * (idx / 6.0))))
                            time.sleep(self.crossfade_stop_sec / 6.0)
                except Exception:
                    pass
            primary.stop()
            if self._is_real_vlc_player(primary):
                try:
                    primary.audio_set_volume(self._effective_volume())
                except Exception:
                    pass

        self.stop_watcher = True
        self.current_track = None
        self.queue = []
        return "Музыка выключена"

    def _pop_next_candidate(self, prev_id: str | None = None):
        if self.queue:
            return self.queue.pop(0)
        if self.is_radio and self._init_client():
            fresh = self._fetch_wave_tracks(
                station=self._wave_station,
                queue_track_id=prev_id,
            )
            if fresh:
                self.queue = fresh[1:]
                return fresh[0]
        return None

    def _prefetch_next_for(self, for_track_id: str):
        def _worker():
            try:
                if self._track_id_str(self.current_track) != for_track_id:
                    return
                candidate = None
                if self.queue:
                    candidate = self.queue[0]
                elif self.is_radio and self._init_client():
                    fresh = self._fetch_wave_tracks(
                        station=self._wave_station,
                        queue_track_id=for_track_id,
                    )
                    if fresh:
                        with self._play_lock:
                            if not self.queue:
                                self.queue = fresh
                                candidate = self.queue[0]
                            else:
                                candidate = self.queue[0]
                if not candidate or self._track_id_str(self.current_track) != for_track_id:
                    return
                candidate = self._unwrap_track(candidate)
                url = self._get_direct_stream_url(candidate)
                if url and self._track_id_str(self.current_track) == for_track_id:
                    self._preloaded_next = (for_track_id, candidate, url)
            except Exception as e:
                print(f"[YandexMusic Prefetch Warning]: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def next_track(self, manual: bool = True, fade_duration: float | None = None, expected_from_id: str | None = None):
        if not HAS_VLC:
            return
        if not manual and self.is_transitioning:
            return

        self.is_transitioning = True
        use_fade = (
            (self.crossfade_manual_sec if manual else self.crossfade_auto_sec)
            if fade_duration is None
            else float(fade_duration)
        )

        def _async_next():
            try:
                prev_id = self._track_id_str(self.current_track) or self._wave_last_track_id
                if expected_from_id and prev_id != expected_from_id:
                    self.is_transitioning = False
                    return

                if self.is_radio and prev_id:
                    self._send_rotor_feedback(
                        self._wave_station,
                        "skip" if manual else "trackFinished",
                        track_id=prev_id,
                        batch_id=self._wave_batch_id,
                    )

                preloaded_url = None
                next_tr = None
                cached = self._preloaded_next
                if cached and cached[0] == prev_id and cached[1] is not None and cached[2]:
                    cached_tid = self._track_id_str(cached[1])
                    if self.queue and self._track_id_str(self.queue[0]) == cached_tid:
                        next_tr = self.queue.pop(0)
                    else:
                        next_tr = cached[1]
                    preloaded_url = cached[2]
                    self._preloaded_next = None

                if next_tr is None:
                    next_tr = self._pop_next_candidate(prev_id=prev_id)

                if next_tr is not None:
                    if self._play_track_object(
                        next_tr,
                        fade_duration=use_fade,
                        preloaded_url=preloaded_url,
                        is_auto=not manual,
                    ):
                        return

                self.is_transitioning = False
            except Exception as e:
                print(f"[YandexMusic Next Track Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_next, daemon=True).start()

    def prev_track(self):
        if not HAS_VLC:
            return

        self.is_transitioning = True

        def _async_prev():
            if self.history:
                prev_tr = self.history.pop()
                if self.current_track:
                    self.queue.insert(0, self.current_track)
                self._play_track_object(prev_tr, fade_duration=self.crossfade_manual_sec)
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
            time.sleep(0.25)
            if not HAS_VLC or not self.player:
                break
            player = self.player
            try:
                state = player.get_state()
            except Exception:
                continue

            if state in (vlc.State.Ended, vlc.State.Error):
                if not self.is_transitioning and not self.is_fading:
                    self.next_track(manual=False, fade_duration=0.0)
                continue

            if state == vlc.State.Playing and not self.is_transitioning and not self.is_fading:
                try:
                    expected_vol = self._effective_volume()
                    if expected_vol > 0:
                        if player.audio_get_mute():
                            player.audio_set_mute(False)
                        cur_vol = player.audio_get_volume()
                        if cur_vol is not None and 0 <= cur_vol < max(1, expected_vol - 5):
                            player.audio_set_volume(expected_vol)
                except Exception:
                    pass
                cur_id = self._track_id_str(self.current_track)
                if not cur_id:
                    continue
                try:
                    total_ms = player.get_length()
                    cur_ms = player.get_time()
                except Exception:
                    continue
                if total_ms is None or cur_ms is None or total_ms < 15000 or cur_ms < 0:
                    continue

                remaining_ms = total_ms - cur_ms
                if remaining_ms <= 16000 and self._preloading_for_id != cur_id:
                    self._preloading_for_id = cur_id
                    self._prefetch_next_for(cur_id)

                trigger_ms = int(self.crossfade_auto_sec * 1000) + 2500
                if (
                    remaining_ms <= trigger_ms
                    and cur_ms >= 3000
                    and self._crossfade_triggered_for_id != cur_id
                    and self._can_crossfade(player, self._standby_player)
                ):
                    self._crossfade_triggered_for_id = cur_id
                    self.next_track(
                        manual=False,
                        fade_duration=self.crossfade_auto_sec,
                        expected_from_id=cur_id,
                    )