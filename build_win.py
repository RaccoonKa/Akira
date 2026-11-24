"""Windows build and WiX MSI packaging profile for Akira."""

import os
import sys
import time

from build_common import (
    BASE_DIR,
    DIST_DIR,
    MAIN_SCRIPT,
    OUTPUT_APP_DIR,
    apply_runtime_patches,
    clean_distribution,
    copy_project_resources,
    copy_site_packages,
    copy_unittest_stdlib,
    get_app_version,
    get_common_nuitka_flags,
    prepare_dist_folder,
    resolve_python,
    run_cmd,
    step,
    sync_nuitka_dist_to_output,
)

ICON_PATH = os.path.join(BASE_DIR, "assets", "icon", "ico", "akira_icon.ico")


def build_nuitka_command_win(
    python_exe: str,
    dist_dir: str = DIST_DIR,
    main_script: str = MAIN_SCRIPT,
    icon_path: str = ICON_PATH,
    version_str: str | None = None,
) -> list[str]:
    ver = version_str or get_app_version()
    ver_parts = (ver.split(".") + ["0", "0", "0", "0"])[:4]
    win_ver = ".".join(p if p.isdigit() else "0" for p in ver_parts)

    cmd = [python_exe, "-m", "nuitka"]
    cmd.extend(get_common_nuitka_flags(dist_dir=dist_dir, main_script=main_script))
    cmd.extend([
        "--output-filename=Akira.exe",
        "--mingw64",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={icon_path}",
        "--windows-company-name=Svetozar (RaccoonKa)",
        "--windows-product-name=Akira",
        f"--windows-file-version={win_ver}",
        f"--windows-product-version={win_ver}",
        "--windows-file-description=Akira Desktop Assistant",
    ])
    return cmd


def run_nuitka_win(python_exe: str, version_str: str | None = None):
    step("2. Компиляция проекта через Nuitka (Windows)")
    cmd = build_nuitka_command_win(python_exe, version_str=version_str)
    start_time = time.time()
    run_cmd(cmd)
    elapsed = time.time() - start_time
    print(f"[Nuitka]: Компиляция завершена успешно за {elapsed / 60:.1f} мин.!")


def copy_runtime_assets_win(python_exe: str):
    step("3. Копирование библиотек, моделей и ресурсов (Windows)")
    sync_nuitka_dist_to_output("Akira.exe")
    copy_site_packages(python_exe, target_platform="win32")
    copy_unittest_stdlib(python_exe, target_platform="win32")
    copy_project_resources(target_platform="win32", exclude_win_installers=False)


def build_msi(version_str: str | None = None):
    step("4. Сборка установщика .msi через WiX Toolset")
    ver = version_str or get_app_version()
    wxs_file = os.path.join(BASE_DIR, "Package.wxs")
    output_msi = os.path.join(DIST_DIR, f"Akira-Setup-v{ver}.msi")

    if not os.path.exists(wxs_file):
        print(f"[ERROR]: Файл {wxs_file} не найден!")
        sys.exit(1)

    cmd = [
        "wix", "build",
        wxs_file,
        "-arch", "x64",
        "-out", output_msi,
        "--acceptEula", "wix7",
    ]
    run_cmd(cmd)
    print(f"\n[SUCCESS]: Установщик успешно собран: {output_msi}")
    return output_msi


def run_build_win(skip_package: bool = False, dry_run: bool = False, version_str: str | None = None):
    ver = version_str or get_app_version()
    python_exe = resolve_python("win32")
    print("=" * 70)
    print(f"  AKIRA WINDOWS BUILD PIPELINE v{ver} (NUITKA + WIX MSI)")
    print("=" * 70)

    if dry_run:
        cmd = build_nuitka_command_win(python_exe, version_str=ver)
        print("[Dry-Run] Nuitka command:")
        print(" ".join(cmd))
        return

    prepare_dist_folder()
    run_nuitka_win(python_exe, version_str=ver)
    copy_runtime_assets_win(python_exe)
    clean_distribution(target_platform="win32", output_app_dir=OUTPUT_APP_DIR)
    apply_runtime_patches(output_app_dir=OUTPUT_APP_DIR)
    if not skip_package:
        build_msi(version_str=ver)
