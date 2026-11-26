"""Linux Mint Cinnamon build and packaging (.deb / .tar.gz / .AppImage) for Akira."""

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

from build_common import (
    BASE_DIR,
    DIST_DIR,
    LINUX_IGNORED_SITE_ITEMS,
    MAIN_SCRIPT,
    OUTPUT_APP_DIR,
    apply_runtime_patches,
    clean_distribution,
    copy_project_resources,
    copy_site_packages,
    copy_unittest_stdlib,
    get_app_version,
    get_common_nuitka_flags,
    get_site_packages_dir,
    prepare_dist_folder,
    resolve_python,
    run_cmd,
    step,
    sync_nuitka_dist_to_output,
)

LINUX_ICON_PATH = os.path.join(BASE_DIR, "assets", "icon", "png", "akira_icon.png")
DESKTOP_TEMPLATE_PATH = os.path.join(BASE_DIR, "packaging", "linux", "akira.desktop")

QT6_LINUX_PLUGINS = ("platforms", "multimedia", "imageformats", "iconengines")

DEBIAN_DEPENDS = [
    "vlc",
    "libportaudio2",
    "ffmpeg",
    "libpulse0",
    "wmctrl",
    "xdotool",
    "scrot",
    "libxcb-cursor0",
    "libxkbcommon-x11-0",
    "libgl1",
]


def _get_deb_arch() -> str:
    dpkg = shutil.which("dpkg")
    if dpkg:
        try:
            res = subprocess.run([dpkg, "--print-architecture"], capture_output=True, text=True, timeout=5)
            arch = (res.stdout or "").strip()
            if res.returncode == 0 and arch:
                return arch
        except Exception:
            pass
    mach = platform.machine().lower()
    if mach in ("x86_64", "amd64"):
        return "amd64"
    if mach in ("aarch64", "arm64"):
        return "arm64"
    return "amd64"


def render_desktop_entry(
    exec_cmd: str = "/opt/Akira/Akira %U",
    icon_name: str = "akira",
) -> str:
    if os.path.isfile(DESKTOP_TEMPLATE_PATH) and exec_cmd == "/opt/Akira/Akira %U" and icon_name == "akira":
        with open(DESKTOP_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()

    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        "Name=Akira\n"
        "GenericName=Voice Assistant\n"
        "GenericName[ru]=Голосовой ассистент\n"
        "Comment=Akira AI Desktop Voice Assistant\n"
        "Comment[ru]=Голосовой ИИ-ассистент Акира\n"
        f"Exec={exec_cmd}\n"
        f"Icon={icon_name}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "Keywords=AI;Voice;Assistant;Akira;Акира;Голосовой;\n"
        "StartupNotify=true\n"
        "StartupWMClass=Akira\n"
    )


def build_nuitka_command_linux(
    python_exe: str,
    dist_dir: str = DIST_DIR,
    main_script: str = MAIN_SCRIPT,
    icon_path: str = LINUX_ICON_PATH,
) -> list[str]:
    cmd = [python_exe, "-m", "nuitka"]
    cmd.extend(get_common_nuitka_flags(dist_dir=dist_dir, main_script=main_script))
    cmd.extend([
        "--output-filename=Akira",
        f"--include-qt-plugins={','.join(QT6_LINUX_PLUGINS)}",
        "--nofollow-import-to=pycaw",
        "--nofollow-import-to=comtypes",
        "--nofollow-import-to=winreg",
        "--nofollow-import-to=wmi",
    ])
    if icon_path and os.path.isfile(icon_path):
        cmd.append(f"--linux-icon={icon_path}")
    return cmd


def check_linux_build_prerequisites(python_exe: str) -> list[str]:
    missing = []
    if subprocess.run([python_exe, "-c", "import nuitka"], capture_output=True).returncode != 0:
        missing.append(f"nuitka (установите: {python_exe} -m pip install nuitka)")
    if not shutil.which("gcc"):
        missing.append("gcc (sudo apt install build-essential)")
    if not shutil.which("patchelf"):
        missing.append("patchelf (sudo apt install patchelf)")
    return missing


def copy_qt_plugins_linux(
    site_packages_dir: str,
    output_app_dir: str = OUTPUT_APP_DIR,
):
    if not site_packages_dir:
        return
    src_plugins_root = os.path.join(site_packages_dir, "PyQt6", "Qt6", "plugins")
    if not os.path.isdir(src_plugins_root):
        return

    dst_plugins_root = os.path.join(output_app_dir, "PyQt6", "Qt6", "plugins")
    os.makedirs(dst_plugins_root, exist_ok=True)
    for plugin_group in QT6_LINUX_PLUGINS:
        src_group = os.path.join(src_plugins_root, plugin_group)
        dst_group = os.path.join(dst_plugins_root, plugin_group)
        if os.path.isdir(src_group):
            shutil.copytree(src_group, dst_group, dirs_exist_ok=True, symlinks=True)


def run_nuitka_linux(python_exe: str):
    step("2. Компиляция проекта через Nuitka (Linux)")
    missing = check_linux_build_prerequisites(python_exe)
    if missing:
        print("[ERROR]: Не хватает зависимостей для Nuitka-сборки на Linux:")
        for item in missing:
            print(f"  - {item}")
        sys.exit(1)

    cmd = build_nuitka_command_linux(python_exe)
    start_time = time.time()
    run_cmd(cmd)
    elapsed = time.time() - start_time
    print(f"[Nuitka]: Компиляция Linux-сборки завершена за {elapsed / 60:.1f} мин.!")


def copy_runtime_assets_linux(python_exe: str):
    step("3. Копирование Linux-библиотек, Qt6-плагинов и ресурсов")
    sync_nuitka_dist_to_output("Akira")
    site_packages = copy_site_packages(
        python_exe,
        target_platform="linux",
        extra_ignored=LINUX_IGNORED_SITE_ITEMS,
    )
    copy_qt_plugins_linux(site_packages)
    copy_unittest_stdlib(python_exe, target_platform="linux")
    # Исключаем Windows-установщики (~110 МБ: vlc_installer.exe, torrserver.exe)
    copy_project_resources(target_platform="linux", exclude_win_installers=True)

    binary_path = os.path.join(OUTPUT_APP_DIR, "Akira")
    if os.path.isfile(binary_path):
        os.chmod(binary_path, 0o755)


def prepare_deb_staging(
    app_dir: str,
    staging_dir: str,
    version_str: str,
    arch: str | None = None,
):
    deb_arch = arch or _get_deb_arch()
    debian_dir = os.path.join(staging_dir, "DEBIAN")
    opt_akira = os.path.join(staging_dir, "opt", "Akira")
    usr_bin = os.path.join(staging_dir, "usr", "bin")
    apps_dir = os.path.join(staging_dir, "usr", "share", "applications")
    icon_dir = os.path.join(staging_dir, "usr", "share", "icons", "hicolor", "256x256", "apps")
    pixmaps_dir = os.path.join(staging_dir, "usr", "share", "pixmaps")

    os.makedirs(debian_dir, exist_ok=True)
    os.makedirs(os.path.dirname(opt_akira), exist_ok=True)
    os.makedirs(usr_bin, exist_ok=True)
    os.makedirs(apps_dir, exist_ok=True)
    os.makedirs(icon_dir, exist_ok=True)
    os.makedirs(pixmaps_dir, exist_ok=True)

    shutil.copytree(app_dir, opt_akira, symlinks=True, dirs_exist_ok=True)
    app_bin = os.path.join(opt_akira, "Akira")
    if os.path.isfile(app_bin):
        os.chmod(app_bin, 0o755)

    # Симлинк /usr/bin/akira -> /opt/Akira/Akira
    symlink_path = os.path.join(usr_bin, "akira")
    if os.path.lexists(symlink_path):
        os.unlink(symlink_path)
    os.symlink("/opt/Akira/Akira", symlink_path)

    desktop_path = os.path.join(apps_dir, "akira.desktop")
    with open(desktop_path, "w", encoding="utf-8") as f:
        f.write(
            render_desktop_entry(
                exec_cmd="/opt/Akira/Akira %U",
                icon_name="/usr/share/icons/hicolor/256x256/apps/akira.png",
            )
        )
    os.chmod(desktop_path, 0o644)

    if os.path.isfile(LINUX_ICON_PATH):
        dst_icon = os.path.join(icon_dir, "akira.png")
        shutil.copy2(LINUX_ICON_PATH, dst_icon)
        os.chmod(dst_icon, 0o644)
        dst_pixmap = os.path.join(pixmaps_dir, "akira.png")
        shutil.copy2(LINUX_ICON_PATH, dst_pixmap)
        os.chmod(dst_pixmap, 0o644)

    depends_line = ", ".join(DEBIAN_DEPENDS)
    control_content = (
        "Package: akira\n"
        f"Version: {version_str}\n"
        "Section: utils\n"
        "Priority: optional\n"
        f"Architecture: {deb_arch}\n"
        "Maintainer: Svetozar (RaccoonKa) <akira@local>\n"
        f"Depends: {depends_line}\n"
        "Description: Akira AI Desktop Voice Assistant\n"
        " Cross-platform AI voice assistant tailored for Linux Mint Cinnamon.\n"
    )
    control_path = os.path.join(debian_dir, "control")
    with open(control_path, "w", encoding="utf-8") as f:
        f.write(control_content)
    os.chmod(control_path, 0o644)

    postinst = (
        "#!/bin/sh\n"
        "set -e\n"
        "if [ -f /opt/Akira/Akira ]; then chmod 0755 /opt/Akira/Akira; fi\n"
        "if command -v update-desktop-database >/dev/null 2>&1; then\n"
        "    update-desktop-database -q /usr/share/applications || true\n"
        "fi\n"
        "if command -v gtk-update-icon-cache >/dev/null 2>&1; then\n"
        "    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true\n"
        "fi\n"
    )
    postinst_path = os.path.join(debian_dir, "postinst")
    with open(postinst_path, "w", encoding="utf-8") as f:
        f.write(postinst)
    os.chmod(postinst_path, 0o755)

    postrm = (
        "#!/bin/sh\n"
        "set -e\n"
        "if command -v update-desktop-database >/dev/null 2>&1; then\n"
        "    update-desktop-database -q /usr/share/applications || true\n"
        "fi\n"
        "if command -v gtk-update-icon-cache >/dev/null 2>&1; then\n"
        "    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true\n"
        "fi\n"
    )
    postrm_path = os.path.join(debian_dir, "postrm")
    with open(postrm_path, "w", encoding="utf-8") as f:
        f.write(postrm)
    os.chmod(postrm_path, 0o755)

    for root, _dirs, _files in os.walk(staging_dir):
        os.chmod(root, 0o755)


def build_deb(
    app_dir: str = OUTPUT_APP_DIR,
    dist_dir: str = DIST_DIR,
    version_str: str | None = None,
) -> str | None:
    step("4.1. Сборка пакета .deb для Linux Mint / Ubuntu")
    dpkg_deb = shutil.which("dpkg-deb")
    if not dpkg_deb:
        print("[DEB Warning]: Утилита dpkg-deb не найдена, пропуск сборки .deb.")
        return None

    ver = version_str or get_app_version()
    arch = _get_deb_arch()
    os.makedirs(dist_dir, exist_ok=True)
    output_deb = os.path.join(dist_dir, f"akira_{ver}_{arch}.deb")

    with tempfile.TemporaryDirectory(prefix="akira_deb_") as staging_dir:
        prepare_deb_staging(app_dir, staging_dir, ver, arch=arch)
        fakeroot = shutil.which("fakeroot")
        if fakeroot:
            cmd = [fakeroot, dpkg_deb, "--build", staging_dir, output_deb]
        else:
            cmd = [dpkg_deb, "--root-owner-group", "--build", staging_dir, output_deb]
        run_cmd(cmd)

    print(f"[SUCCESS]: Пакет .deb собран: {output_deb}")
    return output_deb


def _render_install_sh() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'if [ "${1:-}" = "--user" ]; then\n'
        '    TARGET_DIR="$HOME/.local/opt/Akira"\n'
        '    BIN_LINK="$HOME/.local/bin/akira"\n'
        '    DESKTOP_DIR="$HOME/.local/share/applications"\n'
        '    ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"\n'
        "    SUDO=\"\"\n"
        "else\n"
        '    TARGET_DIR="/opt/Akira"\n'
        '    BIN_LINK="/usr/bin/akira"\n'
        '    DESKTOP_DIR="/usr/share/applications"\n'
        '    ICON_DIR="/usr/share/icons/hicolor/256x256/apps"\n'
        '    if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; else SUDO=""; fi\n'
        "fi\n"
        '$SUDO mkdir -p "$(dirname "$TARGET_DIR")" "$(dirname "$BIN_LINK")" "$DESKTOP_DIR" "$ICON_DIR"\n'
        '$SUDO rm -rf "$TARGET_DIR"\n'
        '$SUDO cp -a "$SCRIPT_DIR/Akira" "$TARGET_DIR"\n'
        '$SUDO chmod +x "$TARGET_DIR/Akira"\n'
        '$SUDO ln -sf "$TARGET_DIR/Akira" "$BIN_LINK"\n'
        'sed -e "s|Exec=/opt/Akira/Akira|Exec=$TARGET_DIR/Akira|g" -e "s|^Icon=akira$|Icon=$ICON_DIR/akira.png|" "$SCRIPT_DIR/akira.desktop" | $SUDO tee "$DESKTOP_DIR/akira.desktop" >/dev/null\n'
        'if [ -f "$SCRIPT_DIR/Akira/assets/icon/png/akira_icon.png" ]; then\n'
        '    $SUDO cp "$SCRIPT_DIR/Akira/assets/icon/png/akira_icon.png" "$ICON_DIR/akira.png"\n'
        "fi\n"
        'echo "Akira installed to $TARGET_DIR"\n'
    )


def _render_uninstall_sh() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'if [ "${1:-}" = "--user" ]; then\n'
        '    rm -rf "$HOME/.local/opt/Akira" "$HOME/.local/bin/akira" "$HOME/.local/share/applications/akira.desktop" "$HOME/.local/share/icons/hicolor/256x256/apps/akira.png"\n'
        "else\n"
        '    if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; else SUDO=""; fi\n'
        '    $SUDO rm -rf /opt/Akira /usr/bin/akira /usr/share/applications/akira.desktop /usr/share/icons/hicolor/256x256/apps/akira.png\n'
        "fi\n"
        'echo "Akira uninstalled"\n'
    )


def build_tarball(
    app_dir: str = OUTPUT_APP_DIR,
    dist_dir: str = DIST_DIR,
    version_str: str | None = None,
) -> str:
    step("4.2. Сборка переносимого архива .tar.gz")
    ver = version_str or get_app_version()
    os.makedirs(dist_dir, exist_ok=True)
    archive_name = f"Akira-Linux-x86_64-v{ver}.tar.gz"
    output_tar = os.path.join(dist_dir, archive_name)
    root_folder = f"Akira-v{ver}"

    with tempfile.TemporaryDirectory(prefix="akira_tar_") as tmp_dir:
        bundle_root = os.path.join(tmp_dir, root_folder)
        os.makedirs(bundle_root, exist_ok=True)
        shutil.copytree(app_dir, os.path.join(bundle_root, "Akira"), symlinks=True)

        desktop_path = os.path.join(bundle_root, "akira.desktop")
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(render_desktop_entry())

        install_path = os.path.join(bundle_root, "install.sh")
        with open(install_path, "w", encoding="utf-8") as f:
            f.write(_render_install_sh())
        os.chmod(install_path, 0o755)

        uninstall_path = os.path.join(bundle_root, "uninstall.sh")
        with open(uninstall_path, "w", encoding="utf-8") as f:
            f.write(_render_uninstall_sh())
        os.chmod(uninstall_path, 0o755)

        with tarfile.open(output_tar, "w:gz") as tar:
            tar.add(bundle_root, arcname=root_folder)

    print(f"[SUCCESS]: Архив .tar.gz собран: {output_tar}")
    return output_tar


def prepare_appdir(app_dir: str, appdir_root: str):
    opt_akira = os.path.join(appdir_root, "opt", "Akira")
    os.makedirs(os.path.dirname(opt_akira), exist_ok=True)
    shutil.copytree(app_dir, opt_akira, symlinks=True, dirs_exist_ok=True)

    app_bin = os.path.join(opt_akira, "Akira")
    if os.path.isfile(app_bin):
        os.chmod(app_bin, 0o755)

    apprun_path = os.path.join(appdir_root, "AppRun")
    apprun_script = (
        "#!/bin/sh\n"
        'HERE="$(dirname "$(readlink -f "$0")")"\n'
        'export LD_LIBRARY_PATH="$HERE/opt/Akira:$HERE/opt/Akira/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
        'exec "$HERE/opt/Akira/Akira" "$@"\n'
    )
    with open(apprun_path, "w", encoding="utf-8") as f:
        f.write(apprun_script)
    os.chmod(apprun_path, 0o755)

    desktop_path = os.path.join(appdir_root, "akira.desktop")
    with open(desktop_path, "w", encoding="utf-8") as f:
        f.write(render_desktop_entry(exec_cmd="Akira %U", icon_name="akira"))

    if os.path.isfile(LINUX_ICON_PATH):
        icon_root = os.path.join(appdir_root, "akira.png")
        shutil.copy2(LINUX_ICON_PATH, icon_root)
        dir_icon = os.path.join(appdir_root, ".DirIcon")
        shutil.copy2(LINUX_ICON_PATH, dir_icon)


def build_appimage(
    app_dir: str = OUTPUT_APP_DIR,
    dist_dir: str = DIST_DIR,
    version_str: str | None = None,
) -> str | None:
    step("4.3. Сборка AppImage")
    appimagetool = shutil.which("appimagetool")
    if not appimagetool:
        print("[AppImage Info]: Утилита appimagetool не найдена в PATH, пропуск AppImage.")
        return None

    ver = version_str or get_app_version()
    os.makedirs(dist_dir, exist_ok=True)
    output_appimage = os.path.join(dist_dir, f"Akira-x86_64-v{ver}.AppImage")

    with tempfile.TemporaryDirectory(prefix="akira_appdir_") as appdir_root:
        prepare_appdir(app_dir, appdir_root)
        env = os.environ.copy()
        env.setdefault("ARCH", "x86_64")
        run_cmd([appimagetool, appdir_root, output_appimage], env=env)
        if os.path.isfile(output_appimage):
            os.chmod(output_appimage, 0o755)

    print(f"[SUCCESS]: AppImage собран: {output_appimage}")
    return output_appimage


GITHUB_RELEASE_CHUNK_BYTES = 1850 * 1024 * 1024  # ~1.81 GiB (< 2 GiB GitHub Releases limit)


def split_file_for_github_release(
    file_path: str,
    max_bytes: int = GITHUB_RELEASE_CHUNK_BYTES,
) -> list[str]:
    """Разбивает файл > max_bytes на части .part01, .part02... для лимита GitHub Releases (2 ГБ)."""
    if not file_path or not os.path.isfile(file_path):
        return []
    if os.path.getsize(file_path) <= max_bytes:
        return [file_path]

    parts: list[str] = []
    chunk_buf = 8 * 1024 * 1024
    with open(file_path, "rb") as src:
        idx = 1
        while True:
            part_path = f"{file_path}.part{idx:02d}"
            written = 0
            with open(part_path, "wb") as dst:
                while written < max_bytes:
                    to_read = min(chunk_buf, max_bytes - written)
                    data = src.read(to_read)
                    if not data:
                        break
                    dst.write(data)
                    written += len(data)
            if written == 0:
                if os.path.exists(part_path):
                    os.remove(part_path)
                break
            parts.append(part_path)
            idx += 1
            if written < max_bytes:
                break
    return parts


def package_linux_release(
    pkg_format: str = "all",
    app_dir: str = OUTPUT_APP_DIR,
    dist_dir: str = DIST_DIR,
    version_str: str | None = None,
    split_large: bool = True,
) -> dict[str, str | None]:
    results: dict[str, str | None] = {}
    fmt = (pkg_format or "all").lower()
    if fmt in ("all", "deb"):
        results["deb"] = build_deb(app_dir, dist_dir, version_str)
    if fmt in ("all", "tar"):
        results["tar"] = build_tarball(app_dir, dist_dir, version_str)
    if fmt in ("all", "appimage"):
        results["appimage"] = build_appimage(app_dir, dist_dir, version_str)

    if split_large:
        for key, path in list(results.items()):
            if path and os.path.isfile(path) and os.path.getsize(path) > GITHUB_RELEASE_CHUNK_BYTES:
                parts = split_file_for_github_release(path)
                print(f"[GitHub Release Split] {os.path.basename(path)} -> {len(parts)} частей (.part01..):")
                for p in parts:
                    print(f"  - {p}")
    return results


def run_build_linux(
    pkg_format: str = "all",
    skip_package: bool = False,
    dry_run: bool = False,
    version_str: str | None = None,
):
    ver = version_str or get_app_version()
    python_exe = resolve_python("linux")
    print("=" * 70)
    print(f"  AKIRA LINUX MINT BUILD PIPELINE v{ver} (NUITKA + DEB/TAR/APPIMAGE)")
    print("=" * 70)

    if dry_run:
        cmd = build_nuitka_command_linux(python_exe)
        missing = check_linux_build_prerequisites(python_exe)
        print("[Dry-Run] Nuitka command:")
        print(" ".join(cmd))
        if missing:
            print("[Dry-Run] Missing prerequisites:", ", ".join(missing))
        return

    prepare_dist_folder()
    run_nuitka_linux(python_exe)
    copy_runtime_assets_linux(python_exe)
    clean_distribution(target_platform="linux", output_app_dir=OUTPUT_APP_DIR)
    apply_runtime_patches(output_app_dir=OUTPUT_APP_DIR)
    if not skip_package and pkg_format != "none":
        package_linux_release(pkg_format=pkg_format, version_str=ver)
