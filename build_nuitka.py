# build_nuitka.py
"""
Оптимизированный скрипт сборки Akira через Nuitka и генерации установщика .msi через WiX Toolset v7.
"""
import os
import sys
import shutil
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
OUTPUT_APP_DIR = os.path.join(DIST_DIR, "Akira")
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")
ICON_PATH = os.path.join(BASE_DIR, "assets", "icon", "ico", "akira_icon.ico")
PYTHON_EXE = sys.executable

def step(title: str):
    print("\n" + "=" * 67)
    print(f">> {title}")
    print("=" * 67, flush=True)

def run_cmd(cmd, env=None, check=True):
    print(f"[CMD]: {' '.join(cmd) if isinstance(cmd, list) else cmd}", flush=True)
    res = subprocess.run(cmd, env=env, shell=isinstance(cmd, str))
    if check and res.returncode != 0:
        print(f"[ERROR]: Command failed with exit code {res.returncode}", flush=True)
        sys.exit(res.returncode)
    return res.returncode

def prepare_dist_folder():
    step("1. Подготовка папки dist/Akira")
    os.makedirs(DIST_DIR, exist_ok=True)
    if os.path.exists(OUTPUT_APP_DIR):
        print(f"Очистка существующей директории: {OUTPUT_APP_DIR}")
        try:
            shutil.rmtree(OUTPUT_APP_DIR)
        except Exception as e:
            print(f"Предупреждение при очистке: {e}")
    os.makedirs(OUTPUT_APP_DIR, exist_ok=True)

def run_nuitka():
    step("2. Компиляция проекта через Nuitka")

    cmd = [
        PYTHON_EXE, "-m", "nuitka",
        "--standalone",
        f"--output-dir={DIST_DIR}",
        "--output-filename=Akira.exe",
        f"--main={MAIN_SCRIPT}",
        
        # Компилятор и распараллеливание
        "--mingw64",
        "--assume-yes-for-downloads",
        "--jobs=0",                # Использовать все доступные ядра CPU
        "--lto=no",                 # Отключить LTO для многократного ускорения сборки
        "--progress-bar=auto",      # Визуальный прогресс-бар этапов компиляции
        "--no-deployment-flag=excluded-module-usage",  # Разрешить загрузку внешних site-packages модулей, исключенных из C++ компиляции
        "--update-check=never",     # Отключить сетевой опрос обновлений Nuitka (предотвращает WinError 5)
        
        # Плагины Nuitka
        "--enable-plugin=pyqt6",
        "--enable-plugin=anti-bloat",
        
        # Режим окна Windows без консоли
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={ICON_PATH}",
        
        # Метаданные Windows EXE
        "--windows-company-name=Svetozar (RaccoonKa)",
        "--windows-product-name=Akira",
        "--windows-file-version=5.0.0.0",
        "--windows-product-version=5.0.0.0",
        "--windows-file-description=Akira Desktop Assistant",
        
        # Компилируем собственный код проекта
        "--include-package=core",
        "--include-package=gui",
        "--include-package=services",
        "--include-package=audio",
        
        # Внешние библиотеки не компилируем в C++, а подключаем как бинарные модули из site-packages
        "--nofollow-import-to=torch",
        "--nofollow-import-to=torchaudio",
        "--nofollow-import-to=transformers",
        "--nofollow-import-to=huggingface_hub",
        "--nofollow-import-to=tqdm",
        "--nofollow-import-to=tokenizers",
        "--nofollow-import-to=safetensors",
        "--nofollow-import-to=mediapipe",
        "--nofollow-import-to=cv2",
        "--nofollow-import-to=scipy",
        "--nofollow-import-to=numpy",
        "--nofollow-import-to=dlib",
        "--nofollow-import-to=onnxruntime",
        "--nofollow-import-to=piper",
        "--nofollow-import-to=vosk",
        "--nofollow-import-to=fastembed",
        "--nofollow-import-to=sklearn",
        "--nofollow-import-to=librosa",
        "--nofollow-import-to=rapidocr_onnxruntime",
        "--nofollow-import-to=optimum",
        
        # Исключение тестовых и интерактивных пакетов
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-unittest-mode=nofollow",
        "--noinclude-IPython-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=matplotlib",
    ]

    start_time = time.time()
    run_cmd(cmd)
    elapsed = time.time() - start_time
    print(f"[Nuitka]: Компиляция завершена успешно за {elapsed / 60:.1f} мин.!")

def copy_runtime_assets():
    step("3. Копирование библиотек, моделей и ресурсов")

    nuitka_dist = os.path.join(DIST_DIR, "main.dist")
    if not os.path.exists(nuitka_dist):
        alt_dist = os.path.join(DIST_DIR, "Akira.dist")
        if os.path.exists(alt_dist):
            nuitka_dist = alt_dist

    if not os.path.exists(nuitka_dist):
        print(f"[ERROR]: Директория скомпилированного приложения не найдена в {DIST_DIR}!")
        sys.exit(1)

    print(f"Синхронизация скомпилированных файлов из {nuitka_dist} в {OUTPUT_APP_DIR}...")
    for item in os.listdir(nuitka_dist):
        s = os.path.join(nuitka_dist, item)
        d = os.path.join(OUTPUT_APP_DIR, item)
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    exe_src = os.path.join(OUTPUT_APP_DIR, "main.exe")
    exe_dst = os.path.join(OUTPUT_APP_DIR, "Akira.exe")
    if os.path.exists(exe_src) and not os.path.exists(exe_dst):
        os.rename(exe_src, exe_dst)

    # Копирование готовых runtime-пакетов, .libs (DLL) и .pyd файлов из site-packages в дистрибутив
    site_packages = os.path.join(BASE_DIR, ".venv", "Lib", "site-packages")
    ignored_site_items = {
        "__pycache__", "pip", "setuptools", "nuitka", "PyInstaller", "pkg_resources",
        "pipreqs", "distutils-precedence.pth", "_distutils_hack", "_virtualenv.pth",
        "_virtualenv.py", "_pyinstaller_hooks_contrib", "tests", "jedi", "sympy",
        "IPython", "matplotlib", "mpl_toolkits"
    }

    print("Копирование внешних библиотек и бинарных модулей (site-packages, *.libs, *.pyd, *.dll)...")
    copied_count = 0
    for item in os.listdir(site_packages):
        if item in ignored_site_items or item.endswith((".egg-info", ".whl", ".tmp")):
            continue
        src = os.path.join(site_packages, item)
        dst = os.path.join(OUTPUT_APP_DIR, item)
        copied_count += 1
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
    print(f"[Libraries]: Синхронизировано {copied_count} внешних компонентов.")

    # Копирование ресурсов проекта в dist/Akira и dist/Akira/_internal (для обратной совместимости)
    target_locations = [OUTPUT_APP_DIR, os.path.join(OUTPUT_APP_DIR, "_internal")]
    for loc in target_locations:
        os.makedirs(loc, exist_ok=True)
        
        # 1. assets (иконки, звуки, espeak-ng-data)
        src_assets = os.path.join(BASE_DIR, "assets")
        dst_assets = os.path.join(loc, "assets")
        if os.path.exists(src_assets) and not os.path.exists(dst_assets):
            print(f"Копирование assets -> {dst_assets}")
            shutil.copytree(src_assets, dst_assets)

        # 2. optimized_models (модели Vosk, Piper ONNX, NLU, RAG, эмоции, глаза)
        src_models = os.path.join(BASE_DIR, "optimized_models")
        dst_models = os.path.join(loc, "optimized_models")
        if os.path.exists(src_models) and not os.path.exists(dst_models):
            print(f"Копирование optimized_models -> {dst_models}")
            shutil.copytree(src_models, dst_models)

        # 3. services/vpn/templates (шаблоны GUI-автоматизации)
        src_vpn = os.path.join(BASE_DIR, "services", "vpn", "templates")
        dst_vpn = os.path.join(loc, "services", "vpn", "templates")
        if os.path.exists(src_vpn) and not os.path.exists(dst_vpn):
            os.makedirs(os.path.dirname(dst_vpn), exist_ok=True)
            print(f"Копирование vpn templates -> {dst_vpn}")
            shutil.copytree(src_vpn, dst_vpn)

        # 4. core/games
        src_games = os.path.join(BASE_DIR, "core", "games")
        dst_games = os.path.join(loc, "core", "games")
        if os.path.exists(src_games) and not os.path.exists(dst_games):
            os.makedirs(os.path.dirname(dst_games), exist_ok=True)
            print(f"Копирование core/games -> {dst_games}")
            shutil.copytree(src_games, dst_games)

        # 5. core/utils (словари произношения, aliases и конфиги)
        src_utils = os.path.join(BASE_DIR, "core", "utils")
        dst_utils = os.path.join(loc, "core", "utils")
        os.makedirs(dst_utils, exist_ok=True)
        for f in os.listdir(src_utils):
            if f.endswith(".json"):
                shutil.copy2(os.path.join(src_utils, f), os.path.join(dst_utils, f))

        # 6. config.template.json
        src_cfg_tpl = os.path.join(BASE_DIR, "personal_data", "configs", "config.template.json")
        dst_cfg_dir = os.path.join(loc, "personal_data", "configs")
        if os.path.exists(src_cfg_tpl):
            os.makedirs(dst_cfg_dir, exist_ok=True)
            shutil.copy2(src_cfg_tpl, os.path.join(dst_cfg_dir, "config.template.json"))

    print("[Assets]: Все ресурсы и модели успешно скопированы!")

def clean_distribution():
    step("3.1. Очистка дистрибутива от лишних файлов и тестов (для лимита компонентов WiX)")

    # 1. Удаление неиспользуемых пакетов интерактивной разработки
    unused_dev_pkgs = ["jedi", "sympy", "IPython", "matplotlib", "mpl_toolkits"]
    for pkg in unused_dev_pkgs:
        p = os.path.join(OUTPUT_APP_DIR, pkg)
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)
            print(f"Исключен пакет: {pkg}")

    for f in ["pylab.py", "isympy.py"]:
        p = os.path.join(OUTPUT_APP_DIR, f)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    # 2. Удаление папок тестов, C/C++ заголовочных файлов и кэша
    # (кроме torch/testing, который требуется для torch.autograd)
    deleted_dirs = 0
    for root, dirs, files in list(os.walk(OUTPUT_APP_DIR, topdown=False)):
        folder_name = os.path.basename(root).lower()
        if folder_name in ("tests", "test", "testing", "__pycache__", "include", "docs", "htmlcov"):
            norm_root = root.replace("\\", "/")
            if "optimized_models" in norm_root or "assets" in norm_root or "torch/testing" in norm_root:
                continue
            shutil.rmtree(root, ignore_errors=True)
            deleted_dirs += 1

    # 3. Удаление тяжелых файлов отладки (.pdb) и архивов колес (.whl)
    deleted_files = 0
    for root, dirs, files in os.walk(OUTPUT_APP_DIR):
        norm_root = root.replace("\\", "/")
        if "optimized_models" in norm_root or "assets" in norm_root:
            continue
        for f in files:
            f_lower = f.lower()
            if f_lower.endswith((".whl", ".pdb")):
                try:
                    os.remove(os.path.join(root, f))
                    deleted_files += 1
                except Exception:
                    pass

    # 4. Удаление промежуточных сборочных каталогов Nuitka (main.dist, main.build),
    # чтобы в dist оставалась только готовая сборка dist/Akira и установщик .msi
    for intermediate in ["main.dist", "main.build", "Akira.dist", "Akira.build"]:
        inter_path = os.path.join(DIST_DIR, intermediate)
        if os.path.exists(inter_path) and inter_path != OUTPUT_APP_DIR:
            shutil.rmtree(inter_path, ignore_errors=True)

    total_files = sum(len(files) for _, _, files in os.walk(OUTPUT_APP_DIR))
    print(f"[Cleanup]: Удалено {deleted_dirs} каталогов и {deleted_files} dev-файлов.")
    print(f"[Cleanup]: Итоговое число компонентов для WiX: {total_files} (лимит MSI: 65536).")

def build_msi():
    step("4. Сборка установщика .msi через WiX Toolset")
    wxs_file = os.path.join(BASE_DIR, "Package.wxs")
    output_msi = os.path.join(DIST_DIR, "Akira-Setup-v5.0.0.msi")

    if not os.path.exists(wxs_file):
        print(f"[ERROR]: Файл {wxs_file} не найден!")
        sys.exit(1)

    cmd = [
        "wix", "build",
        wxs_file,
        "-arch", "x64",
        "-out", output_msi,
        "--acceptEula", "wix7"
    ]

    run_cmd(cmd)
    print(f"\n[SUCCESS]: Установщик успешно собран: {output_msi}")

def main():
    print("=" * 70)
    print("  AKIRA NUITKA & WIX BUILD PIPELINE (FAST & OPTIMIZED)")
    print("=" * 70)
    prepare_dist_folder()
    run_nuitka()
    copy_runtime_assets()
    clean_distribution()
    build_msi()

if __name__ == "__main__":
    main()
