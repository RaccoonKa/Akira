import os
import re
import shutil
import subprocess
import sys
import tempfile
import requests
from packaging import version
from PyQt6.QtCore import QThread, pyqtSignal

CURRENT_VERSION = "5.1.0"
GITHUB_REPO = "RaccoonKa/Akira"
_PART_SUFFIX_RE = re.compile(r"^(?P<base>.+?)\.part(?P<num>\d+)$", re.IGNORECASE)


def is_running_in_appimage() -> bool:
    return bool(os.environ.get("APPIMAGE"))


def select_release_assets(
    assets: list[dict],
    target_platform: str | None = None,
    in_appimage: bool | None = None,
) -> tuple[list[str], str | None]:
    """Подбирает URL (один файл или список .part01, .part02...) и базовое имя ассета релиза GitHub."""
    if not assets:
        return [], None

    plat = target_platform or sys.platform
    if plat == "win32":
        preferred_exts = (".msi", ".exe")
    else:
        running_appimage = is_running_in_appimage() if in_appimage is None else in_appimage
        preferred_exts = (
            (".appimage", ".deb", ".tar.gz")
            if running_appimage
            else (".deb", ".appimage", ".tar.gz")
        )

    for ext in preferred_exts:
        for asset in assets:
            name = (asset.get("name") or "").strip()
            url = asset.get("browser_download_url")
            if url and name.lower().endswith(ext):
                return [url], name

        # Поиск многотомного файла формата <base><ext>.part01, .part02, ...
        grouped_parts: dict[str, list[tuple[int, str]]] = {}
        for asset in assets:
            name = (asset.get("name") or "").strip()
            url = asset.get("browser_download_url")
            if not url or not name:
                continue
            m = _PART_SUFFIX_RE.match(name)
            if not m:
                continue
            base_name = m.group("base")
            if base_name.lower().endswith(ext):
                grouped_parts.setdefault(base_name, []).append((int(m.group("num")), url))

        if grouped_parts:
            base_name, parts = next(iter(grouped_parts.items()))
            parts.sort(key=lambda item: item[0])
            return [u for _, u in parts], base_name

    return [], None


def select_release_asset(
    assets: list[dict],
    target_platform: str | None = None,
    in_appimage: bool | None = None,
) -> tuple[str | None, str | None]:
    """Подбирает подходящий файл релиза GitHub (для многотомных частей возвращает URL через \\n)."""
    urls, name = select_release_assets(assets, target_platform=target_platform, in_appimage=in_appimage)
    if not urls:
        return None, None
    return "\n".join(urls), name


def get_update_filename(download_url: str, asset_name: str = "") -> str:
    candidate = (asset_name or download_url.split("?")[0]).lower()
    for ext in (".tar.gz", ".appimage", ".deb", ".msi", ".exe"):
        if candidate.endswith(ext) or ext in candidate:
            suffix = ".AppImage" if ext == ".appimage" else ext
            return f"Akira_Update{suffix}"
    return "Akira_Update.exe" if sys.platform == "win32" else "Akira_Update.deb"


class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str, str)

    def run(self):
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        headers = {"User-Agent": "Akira-Client-App"}
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                latest_tag = data.get("tag_name", "").lstrip("v")
                changelog = data.get("body", "")

                download_url, _asset_name = select_release_asset(data.get("assets", []))

                if latest_tag and version.parse(latest_tag) > version.parse(CURRENT_VERSION):
                    if download_url:
                        self.update_available.emit(latest_tag, changelog, download_url)
        except Exception as e:
            print(f"[Update Checker Warning]: GitHub временно недоступен ({e})")


class DownloaderThread(QThread):
    progress_changed = pyqtSignal(int)
    download_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, download_url: str, asset_name: str = ""):
        super().__init__()
        self.download_url = download_url
        self.asset_name = asset_name

    def run(self):
        try:
            urls = [u.strip() for u in self.download_url.splitlines() if u.strip()]
            if not urls:
                raise ValueError("Пустой URL для загрузки обновления")

            filename = get_update_filename(urls[0], self.asset_name)
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            part_count = len(urls)

            with open(temp_path, "wb") as f:
                for idx, part_url in enumerate(urls):
                    resp = requests.get(part_url, stream=True, timeout=15)
                    resp.raise_for_status()
                    total_size = int(resp.headers.get("content-length", 0))
                    downloaded = 0

                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                part_frac = min(1.0, downloaded / total_size)
                                percent = int(((idx + part_frac) / part_count) * 100)
                                self.progress_changed.emit(min(100, percent))

            if sys.platform != "win32" and temp_path.lower().endswith(".appimage"):
                os.chmod(temp_path, 0o755)

            self.progress_changed.emit(100)
            self.download_finished.emit(temp_path)
        except Exception as e:
            self.error_occurred.emit(str(e))


def _apply_linux_update(installer_path: str):
    abs_path = os.path.abspath(installer_path)
    lower = abs_path.lower()

    if lower.endswith(".deb"):
        pkexec = shutil.which("pkexec")
        apt_cmd = shutil.which("apt") or shutil.which("apt-get")
        if pkexec and apt_cmd:
            subprocess.Popen(
                [pkexec, apt_cmd, "install", "-y", abs_path],
                start_new_session=True,
            )
        else:
            subprocess.Popen(["xdg-open", abs_path], start_new_session=True)
        return

    if lower.endswith(".appimage"):
        os.chmod(abs_path, 0o755)
        current_appimage = os.environ.get("APPIMAGE", "")
        if current_appimage and os.path.isfile(current_appimage) and os.access(os.path.dirname(current_appimage), os.W_OK):
            target_dir = os.path.dirname(os.path.abspath(current_appimage))
            staged_path = os.path.join(target_dir, f".akira_update_{os.getpid()}.AppImage")
            shutil.copy2(abs_path, staged_path)
            os.chmod(staged_path, 0o755)
            os.replace(staged_path, current_appimage)
            subprocess.Popen([current_appimage], start_new_session=True)
        else:
            subprocess.Popen([abs_path], start_new_session=True)
        return

    if lower.endswith(".tar.gz"):
        subprocess.Popen(["xdg-open", os.path.dirname(abs_path)], start_new_session=True)
        return

    os.chmod(abs_path, 0o755)
    subprocess.Popen([abs_path], start_new_session=True)


def apply_update_and_restart(installer_path: str):
    if sys.platform == "win32":
        if installer_path.lower().endswith(".msi"):
            subprocess.Popen(["msiexec.exe", "/i", installer_path])
        else:
            subprocess.Popen([installer_path], shell=True)
        sys.exit(0)

    _apply_linux_update(installer_path)
    sys.exit(0)
