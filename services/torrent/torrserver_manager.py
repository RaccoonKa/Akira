import os
import sys
import time
import re
import urllib.parse
import subprocess
import requests
import tempfile

TORRSERVER_PORT = 8090
TORRSERVER_URL = f"http://127.0.0.1:{TORRSERVER_PORT}"


def get_torrserver_bin_path() -> str:
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    paths_to_check = [
        os.path.join(base_dir, "assets", "bin", "torrserver.exe"),
        os.path.join(base_dir, "bin", "torrserver.exe"),
        os.path.join(base_dir, "torrserver.exe")
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            return p
    return paths_to_check[0]


def _natural_sort_key(file_dict: dict):
    path = file_dict.get("path", "")
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', path)]


class TorrServerManager:
    def __init__(self):
        self.process = None

    def is_running(self) -> bool:
        try:
            r = requests.get(f"{TORRSERVER_URL}/echo", timeout=1.0)
            return r.status_code == 200
        except Exception:
            return False

    def start_server(self) -> bool:
        if self.is_running():
            return True

        bin_path = get_torrserver_bin_path()
        if not os.path.exists(bin_path):
            print(f"[TorrServer Error]: Файл {bin_path} не найден!")
            return False

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            self.process = subprocess.Popen(
                [bin_path, "-p", str(TORRSERVER_PORT)],
                startupinfo=startupinfo,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            for _ in range(25):
                time.sleep(0.2)
                if self.is_running():
                    print("[TorrServer]: Локальный сервер запущен на порту 8090")
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
            time.sleep(2.0)
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