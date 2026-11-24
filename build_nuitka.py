# build_nuitka.py
"""
Единая точка входа сборки дистрибутива Akira (Windows MSI и Linux Mint .deb / .tar.gz / .AppImage).
"""
import argparse
import sys

from build_common import (
    BASE_DIR,
    DIST_DIR,
    MAIN_SCRIPT,
    OUTPUT_APP_DIR,
    apply_runtime_patches,
    clean_distribution,
    get_app_version,
    prepare_dist_folder,
    resolve_python,
    run_cmd,
    step,
)
from build_win import (
    ICON_PATH,
    build_msi,
    copy_runtime_assets_win,
    run_build_win,
    run_nuitka_win,
)
from build_linux import (
    build_appimage,
    build_deb,
    build_tarball,
    copy_runtime_assets_linux,
    package_linux_release,
    run_build_linux,
    run_nuitka_linux,
)

PYTHON_EXE = resolve_python(sys.platform, verbose=False)


def run_nuitka():
    if sys.platform == "win32":
        run_nuitka_win(PYTHON_EXE)
    else:
        run_nuitka_linux(PYTHON_EXE)


def copy_runtime_assets():
    if sys.platform == "win32":
        copy_runtime_assets_win(PYTHON_EXE)
    else:
        copy_runtime_assets_linux(PYTHON_EXE)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Сборка релиза Akira через Nuitka.")
    parser.add_argument(
        "--platform",
        choices=["auto", "win32", "linux"],
        default="auto",
        help="Целевая платформа сборки (по умолчанию определяется автоматически).",
    )
    parser.add_argument(
        "--format",
        dest="pkg_format",
        choices=["all", "deb", "tar", "appimage", "msi", "none"],
        default="all",
        help="Формат упаковки дистрибутива.",
    )
    parser.add_argument(
        "--skip-package",
        action="store_true",
        help="Только собрать Nuitka-бандл dist/Akira без упаковки в .msi/.deb/.tar.gz.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Проверить окружение и вывести команду Nuitka без запуска сборки.",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Переопределить версию пакета (по умолчанию из core/utils/updater.py).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    target = sys.platform if args.platform == "auto" else args.platform
    ver = args.version or get_app_version()

    if target == "win32":
        skip_pkg = args.skip_package or args.pkg_format == "none"
        run_build_win(skip_package=skip_pkg, dry_run=args.dry_run, version_str=ver)
    else:
        run_build_linux(
            pkg_format=args.pkg_format,
            skip_package=args.skip_package,
            dry_run=args.dry_run,
            version_str=ver,
        )


if __name__ == "__main__":
    main()
