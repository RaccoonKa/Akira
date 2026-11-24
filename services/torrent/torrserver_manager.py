import os
import sys
import time
import re
import json
import shutil
import platform
import urllib.parse
import subprocess
import requests
import tempfile
from core.utils.config import get_resource_path, get_user_data_path
from core.utils.platform_utils import subprocess_no_window_kwargs

TORRSERVER_PORT = 8090
TORRSERVER_URL = f"http://127.0.0.1:{TORRSERVER_PORT}"
GITHUB_RELEASES_API = "https://api.github.com/repos/YouROK/TorrServer/releases/latest"


def _get_linux_torrserver_filename() -> str:
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "TorrServer-linux-arm64"
    return "TorrServer-linux-amd64"


def get_torrserver_bin_path() -> str:
    if sys.platform != "win32":
        bin_name = _get_linux_torrserver_filename()
        user_bin = get_user_data_path("torrserver", bin_name)
        if os.path.isfile(user_bin):
            return user_bin
        sys_bin = shutil.which("torrserver") or shutil.which(bin_name)
        if sys_bin:
            return sys_bin
        return user_bin

    paths_to_check = [
        get_resource_path("assets", "installers", "torrserver.exe"),
        get_resource_path("assets", "bin", "torrserver.exe"),
        get_resource_path("installers", "torrserver.exe"),
        get_resource_path("bin", "torrserver.exe"),
        get_resource_path("torrserver.exe")
    ]
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        paths_to_check.extend([
            os.path.join(exe_dir, "_internal", "assets", "installers", "torrserver.exe"),
            os.path.join(exe_dir, "assets", "installers", "torrserver.exe"),
            os.path.join(exe_dir, "_internal", "assets", "bin", "torrserver.exe"),
            os.path.join(exe_dir, "assets", "bin", "torrserver.exe"),
            os.path.join(exe_dir, "_internal", "torrserver.exe"),
            os.path.join(exe_dir, "torrserver.exe")
        ])
    for p in paths_to_check:
        if p and os.path.exists(p):
            return p
    return paths_to_check[0]


def _natural_sort_key(file_dict: dict):
    path = file_dict.get("path", "")
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', path)]


class TorrServerManager:
    def __init__(self):
        self.process = None

    def is_binary_installed(self) -> bool:
        bin_path = get_torrserver_bin_path()
        if not bin_path or not os.path.isfile(bin_path):
            return False
        if sys.platform == "win32":
            return True
        try:
            if os.path.getsize(bin_path) >= 1_000_000:
                return True
            return shutil.which(os.path.basename(bin_path)) is not None and os.access(bin_path, os.X_OK)
        except OSError:
            return False

    def _resolve_linux_download_url(self, bin_name: str) -> str:
        fallback_url = f"https://github.com/YouROK/TorrServer/releases/latest/download/{bin_name}"
        try:
            resp = requests.get(
                GITHUB_RELEASES_API,
                headers={"User-Agent": "Akira-Assistant", "Accept": "application/vnd.github+json"},
                timeout=12.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    if name == bin_name or name.lower() == bin_name.lower():
                        dl = asset.get("browser_download_url")
                        if dl:
                            return dl
        except Exception as e:
            print(f"[TorrServer Release Lookup Warning]: {e}")
        return fallback_url

    def download_linux_binary(self, progress_callback=None) -> tuple[bool, str]:
        """
        Скачивает официальный бинарник TorrServer для Linux (amd64/arm64) в каталог данных пользователя,
        проверяет ELF-заголовок и размер, выставляет chmod +x.
        """
        if sys.platform == "win32":
            path = get_torrserver_bin_path()
            return (os.path.isfile(path), path if os.path.isfile(path) else "torrserver.exe не найден")

        bin_name = _get_linux_torrserver_filename()
        torr_data_dir = get_user_data_path("torrserver")
        os.makedirs(torr_data_dir, exist_ok=True)
        target_path = os.path.join(torr_data_dir, bin_name)
        part_path = f"{target_path}.part"

        if os.path.isfile(target_path) and os.path.getsize(target_path) >= 1_000_000:
            try:
                with open(target_path, "rb") as f:
                    if f.read(4) == b"\x7fELF":
                        os.chmod(target_path, 0o755)
                        return True, target_path
            except OSError:
                pass

        url = self._resolve_linux_download_url(bin_name)
        try:
            with requests.get(
                url,
                stream=True,
                timeout=(15.0, 60.0),
                headers={"User-Agent": "Akira-Assistant"},
                allow_redirects=True,
            ) as resp:
                if resp.status_code != 200:
                    return False, f"GitHub вернул статус {resp.status_code}"

                total_bytes = int(resp.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                header_bytes = b""

                with open(part_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=131072):
                        if not chunk:
                            continue
                        if len(header_bytes) < 4:
                            need = 4 - len(header_bytes)
                            header_bytes += chunk[:need]
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            try:
                                progress_callback(downloaded, total_bytes)
                            except Exception:
                                pass

                if downloaded < 1_000_000:
                    raise ValueError(f"Скачанный файл слишком мал ({downloaded} байт)")
                if total_bytes > 0 and downloaded != total_bytes:
                    raise ValueError(f"Неполная загрузка ({downloaded} из {total_bytes} байт)")
                if header_bytes[:4] != b"\x7fELF":
                    raise ValueError("Загруженный файл не является корректным Linux ELF-бинарником")

            os.chmod(part_path, 0o755)
            os.replace(part_path, target_path)
            print(f"[TorrServer]: Бинарник успешно загружен -> {target_path}", flush=True)
            return True, target_path
        except Exception as e:
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except OSError:
                    pass
            return False, str(e)

    def is_running(self) -> bool:
        try:
            r = requests.get(f"{TORRSERVER_URL}/echo", timeout=1.0)
            return r.status_code == 200
        except Exception:
            return False

    def _ensure_optimal_config(self, torr_data_dir: str):
        settings_file = os.path.join(torr_data_dir, "settings.json")
        try:
            data = {}
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

            bittorr = data.get("BitTorr", {})
            # Оптимальные параметры для моментального старта видео в VLC:
            # 1. Снижаем порог предзагрузки с 50% до 15% (поток стартует за секунды)
            # 2. Увеличиваем лимит соединений с 25 до 80 (быстрый поиск пиров и DHT)
            # 3. Кеш в оперативной памяти 64MB
            bittorr["ConnectionsLimit"] = 80
            bittorr["PreloadCache"] = 15
            bittorr["CacheSize"] = 67108864
            bittorr["ReaderReadAHead"] = 95
            bittorr["ResponsiveMode"] = True
            bittorr["StoreSettingsInJson"] = True
            data["BitTorr"] = bittorr

            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[TorrServer Config Warning]: {e}")

    def _apply_runtime_settings(self):
        try:
            requests.post(
                f"{TORRSERVER_URL}/settings",
                json={
                    "action": "set",
                    "sets": {
                        "ConnectionsLimit": 80,
                        "PreloadCache": 15,
                        "CacheSize": 67108864,
                        "ReaderReadAHead": 95,
                        "ResponsiveMode": True
                    }
                },
                timeout=2.0
            )
        except Exception as e:
            print(f"[TorrServer Settings Warning]: {e}")

    def start_server(self) -> bool:
        if self.is_running():
            self._apply_runtime_settings()
            return True

        bin_path = get_torrserver_bin_path()
        if not os.path.exists(bin_path):
            print(f"[TorrServer Error]: Файл {bin_path} не найден!")
            return False

        torr_data_dir = get_user_data_path("torrserver")
        os.makedirs(torr_data_dir, exist_ok=True)
        self._ensure_optimal_config(torr_data_dir)

        try:
            if sys.platform != "win32":
                try:
                    os.chmod(bin_path, 0o755)
                except OSError:
                    pass

            popen_kwargs = subprocess_no_window_kwargs()
            if sys.platform != "win32":
                popen_kwargs["start_new_session"] = True

            self.process = subprocess.Popen(
                [bin_path, "-p", str(TORRSERVER_PORT), "-d", torr_data_dir],
                cwd=torr_data_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **popen_kwargs,
            )

            for _ in range(25):
                time.sleep(0.2)
                if self.is_running():
                    print(f"[TorrServer]: Локальный сервер запущен на порту {TORRSERVER_PORT}")
                    self._apply_runtime_settings()
                    return True
        except Exception as e:
            print(f"[TorrServer Start Error]: {e}")

        return False

    def _extract_hash(self, magnet_link: str) -> str:
        m = re.search(r'urn:btih:([a-zA-Z0-9]+)', magnet_link)
        return m.group(1).lower() if m else ""

    def get_stream_url(self, magnet_link: str, title: str = "", is_series: bool = False) -> str | None:
        self.start_server()
        torrent_hash = self._extract_hash(magnet_link)

        try:
            requests.post(
                f"{TORRSERVER_URL}/torrents",
                json={"action": "add", "link": magnet_link, "title": title or "Stream", "save_to_db": True},
                timeout=3.0
            )
        except Exception as e:
            print(f"[TorrServer Add Warning]: {e}")

        video_exts = ('.mkv', '.mp4', '.avi', '.ts', '.m4v', '.mov', '.wmv', '.webm')
        video_files = []
        lookup_hash = torrent_hash

        for _ in range(16):
            time.sleep(0.5)
            try:
                r = requests.post(f"{TORRSERVER_URL}/torrents", json={"action": "get", "hash": lookup_hash}, timeout=2.0)
                if r.status_code == 200:
                    data = r.json()
                    lookup_hash = data.get("hash", lookup_hash)
                    file_stats = data.get("file_stats", [])
                    if file_stats:
                        video_files = [f for f in file_stats if any(f.get("path", "").lower().endswith(ext) for ext in video_exts)]
                        if video_files:
                            video_files.sort(key=_natural_sort_key)
                            print(f"[TorrServer]: Метаданные готовы, видеофайлов в раздаче: {len(video_files)}")
                            break
            except Exception:
                pass

        if not video_files:
            print("[TorrServer]: В раздаче не найдено видеофайлов (игры/архивы отсеяны)")
            return None

        final_hash = lookup_hash or torrent_hash
        first_file_id = video_files[0].get("id", 1)

        try:
            requests.post(
                f"{TORRSERVER_URL}/torrent/preload",
                json={"hash": final_hash, "index": first_file_id},
                timeout=2.0
            )
            print(f"[TorrServer]: Предзагрузка буфера для файла ID={first_file_id}...")
            # Опрашиваем статус предзагрузки до готовности первых блоков (до 5 сек)
            for _ in range(10):
                time.sleep(0.4)
                try:
                    st_resp = requests.post(f"{TORRSERVER_URL}/torrent/stat", json={"hash": final_hash}, timeout=1.5)
                    if st_resp.status_code == 200:
                        st = st_resp.json()
                        preload = st.get("preload_size", 0)
                        down_speed = st.get("download_speed", 0)
                        peers = st.get("active_peers", 0) or st.get("connected_seeders", 0)
                        if preload > 1024 * 1024 or (down_speed > 200 * 1024 and preload > 512 * 1024):
                            print(f"[TorrServer]: Буфер готов ({preload // 1024} КБ, пиров: {peers}). Запускаем плеер!")
                            break
                except Exception:
                    pass
        except Exception as e:
            print(f"[TorrServer Preload Warning]: {e}")

        if len(video_files) > 1 or is_series:
            playlist_path = os.path.join(tempfile.gettempdir(), "akira_playlist.m3u")
            with open(playlist_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for vf in video_files:
                    fid = vf.get("id", 1)
                    fpath = vf.get("path", f"Эпизод {fid}")
                    fname = os.path.basename(fpath)
                    disp_name = os.path.splitext(fname)[0]
                    f.write(f"#EXTINF:-1,{disp_name}\n")
                    f.write(f"{TORRSERVER_URL}/stream?link={final_hash}&index={fid}&play\n")
            return playlist_path

        return f"{TORRSERVER_URL}/stream?link={final_hash}&index={first_file_id}&play"


torr_manager = TorrServerManager()