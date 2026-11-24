"""Shared build helpers for Akira (Windows and Linux profiles)."""

import os
import re
import shutil
import subprocess
import sys
import sysconfig

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
OUTPUT_APP_DIR = os.path.join(DIST_DIR, "Akira")
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")

COMMON_IGNORED_SITE_ITEMS = {
    "__pycache__", "pip", "setuptools", "nuitka", "PyInstaller", "pkg_resources",
    "pipreqs", "distutils-precedence.pth", "_distutils_hack", "_virtualenv.pth",
    "_virtualenv.py", "_pyinstaller_hooks_contrib", "tests", "jedi", "sympy",
    "IPython", "matplotlib", "mpl_toolkits",
}

LINUX_IGNORED_SITE_ITEMS = {
    "pycaw", "comtypes", "win32", "win32com", "win32comext", "pywin32_system32",
    "pythoncom.py", "pywintypes.py", "wmi.py", "isympy.py",
}

ML_EXTERNAL_MODULES = [
    "torch",
    "torchaudio",
    "transformers",
    "huggingface_hub",
    "tqdm",
    "tokenizers",
    "safetensors",
    "mediapipe",
    "cv2",
    "scipy",
    "numpy",
    "dlib",
    "onnxruntime",
    "piper",
    "vosk",
    "fastembed",
    "sklearn",
    "librosa",
    "rapidocr_onnxruntime",
    "optimum",
    "websockets",
]


def get_app_version() -> str:
    updater_path = os.path.join(BASE_DIR, "core", "utils", "updater.py")
    try:
        with open(updater_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'CURRENT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return "5.0.0"


def step(title: str):
    print("\n" + "=" * 67)
    print(f">> {title}")
    print("=" * 67, flush=True)


def run_cmd(cmd, env=None, check=True, cwd=None):
    print(f"[CMD]: {' '.join(cmd) if isinstance(cmd, list) else cmd}", flush=True)
    res = subprocess.run(cmd, env=env, shell=isinstance(cmd, str), cwd=cwd)
    if check and res.returncode != 0:
        print(f"[ERROR]: Command failed with exit code {res.returncode}", flush=True)
        sys.exit(res.returncode)
    return res.returncode


def _has_nuitka(python_exe: str) -> bool:
    try:
        res = subprocess.run(
            [python_exe, "-c", "import nuitka"],
            capture_output=True,
            timeout=10,
        )
        return res.returncode == 0
    except Exception:
        return False


def resolve_python(target_platform: str | None = None, verbose: bool = True) -> str:
    """Resolve the Python interpreter (preferring project .venv with Nuitka)."""
    plat = target_platform or sys.platform

    if plat == "win32":
        try:
            import nuitka  # noqa: F401
            return sys.executable
        except ImportError:
            pass

        project_venv = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
        if os.path.isfile(project_venv) and _has_nuitka(project_venv):
            if verbose:
                print(
                    f"[Nuitka Env]: Используется Python с Nuitka из .venv проекта:\n"
                    f"             {project_venv}"
                )
            return project_venv
        return sys.executable

    candidates = [
        os.path.join(BASE_DIR, ".venv", "bin", "python"),
        os.path.join(BASE_DIR, ".venv", "bin", "python3"),
    ]
    for venv_py in candidates:
        if os.path.isfile(venv_py) and _has_nuitka(venv_py):
            if verbose:
                print(f"[Nuitka Env]: Используется Python с Nuitka из .venv: {venv_py}")
            return venv_py

    try:
        import nuitka  # noqa: F401
        return sys.executable
    except ImportError:
        pass

    for venv_py in candidates:
        if os.path.isfile(venv_py):
            if verbose:
                print(f"[Nuitka Env]: Используется Python из .venv: {venv_py}")
            return venv_py

    return sys.executable


def get_site_packages_dir(python_exe: str, target_platform: str | None = None) -> str:
    plat = target_platform or sys.platform
    if python_exe and os.path.isfile(python_exe):
        try:
            res = subprocess.run(
                [python_exe, "-c", "import sysconfig; print(sysconfig.get_path('purelib') or '')"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            path = (res.stdout or "").strip()
            if res.returncode == 0 and path and os.path.isdir(path):
                return path
        except Exception:
            pass

    if plat == "win32":
        win_sp = os.path.join(BASE_DIR, ".venv", "Lib", "site-packages")
        if os.path.isdir(win_sp):
            return win_sp
    else:
        venv_lib = os.path.join(BASE_DIR, ".venv", "lib")
        if os.path.isdir(venv_lib):
            for entry in sorted(os.listdir(venv_lib), reverse=True):
                if entry.startswith("python"):
                    cand = os.path.join(venv_lib, entry, "site-packages")
                    if os.path.isdir(cand):
                        return cand

    return sysconfig.get_path("purelib") or ""


def get_unittest_dir(python_exe: str, target_platform: str | None = None) -> str:
    plat = target_platform or sys.platform
    if python_exe and os.path.isfile(python_exe):
        try:
            res = subprocess.run(
                [python_exe, "-c", "import os, unittest; print(os.path.dirname(unittest.__file__))"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            path = (res.stdout or "").strip()
            if res.returncode == 0 and path and os.path.isdir(path):
                return path
        except Exception:
            pass

    if plat == "win32":
        return os.path.join(sys.base_prefix, "Lib", "unittest")

    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return os.path.join(sys.base_prefix, "lib", py_ver, "unittest")


def get_common_nuitka_flags(
    dist_dir: str = DIST_DIR,
    main_script: str = MAIN_SCRIPT,
) -> list[str]:
    flags = [
        "--standalone",
        f"--output-dir={dist_dir}",
        f"--main={main_script}",
        "--jobs=0",
        "--lto=no",
        "--progress-bar=auto",
        "--no-deployment-flag=excluded-module-usage",
        "--update-check=never",
        "--enable-plugin=pyqt6",
        "--enable-plugin=anti-bloat",
        "--include-package=core",
        "--include-package=gui",
        "--include-package=services",
        "--include-package=audio",
    ]
    for mod in ML_EXTERNAL_MODULES:
        flags.append(f"--nofollow-import-to={mod}")
    flags.extend([
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-IPython-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=matplotlib",
    ])
    return flags


def prepare_dist_folder(dist_dir: str = DIST_DIR, output_app_dir: str = OUTPUT_APP_DIR):
    step("1. Подготовка папки dist/Akira")
    os.makedirs(dist_dir, exist_ok=True)
    if os.path.exists(output_app_dir):
        print(f"Очистка существующей директории: {output_app_dir}")
        try:
            shutil.rmtree(output_app_dir)
        except Exception as e:
            print(f"Предупреждение при очистке: {e}")
    os.makedirs(output_app_dir, exist_ok=True)


def sync_nuitka_dist_to_output(
    output_binary_name: str,
    dist_dir: str = DIST_DIR,
    output_app_dir: str = OUTPUT_APP_DIR,
):
    nuitka_dist = os.path.join(dist_dir, "main.dist")
    if not os.path.exists(nuitka_dist):
        alt_dist = os.path.join(dist_dir, "Akira.dist")
        if os.path.exists(alt_dist):
            nuitka_dist = alt_dist

    if not os.path.exists(nuitka_dist):
        print(f"[ERROR]: Директория скомпилированного приложения не найдена в {dist_dir}!")
        sys.exit(1)

    print(f"Синхронизация скомпилированных файлов из {nuitka_dist} в {output_app_dir}...")
    for item in os.listdir(nuitka_dist):
        s = os.path.join(nuitka_dist, item)
        d = os.path.join(output_app_dir, item)
        if os.path.isdir(s) and not os.path.islink(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d, follow_symlinks=False)

    fallback_name = "main.exe" if output_binary_name.endswith(".exe") else "main"
    bin_src = os.path.join(output_app_dir, fallback_name)
    bin_dst = os.path.join(output_app_dir, output_binary_name)
    if os.path.exists(bin_src) and not os.path.exists(bin_dst):
        os.rename(bin_src, bin_dst)

    if sys.platform != "win32" and os.path.exists(bin_dst):
        os.chmod(bin_dst, 0o755)


def copy_site_packages(
    python_exe: str,
    target_platform: str | None = None,
    output_app_dir: str = OUTPUT_APP_DIR,
    extra_ignored: set[str] | None = None,
) -> str:
    site_packages = get_site_packages_dir(python_exe, target_platform)
    if not site_packages or not os.path.isdir(site_packages):
        print(f"[Libraries Warning]: Директория site-packages не найдена: {site_packages}")
        return site_packages

    ignored = set(COMMON_IGNORED_SITE_ITEMS)
    if extra_ignored:
        ignored.update(extra_ignored)

    print(f"Копирование внешних библиотек из {site_packages}...")
    copied_count = 0
    for item in os.listdir(site_packages):
        item_lower = item.lower()
        if item in ignored or item_lower in {x.lower() for x in ignored}:
            continue
        if item.endswith((".egg-info", ".dist-info", ".whl", ".tmp")):
            continue
        src = os.path.join(site_packages, item)
        dst = os.path.join(output_app_dir, item)
        copied_count += 1
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
        else:
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
    print(f"[Libraries]: Синхронизировано {copied_count} внешних компонентов.")
    return site_packages


def copy_unittest_stdlib(
    python_exe: str,
    target_platform: str | None = None,
    output_app_dir: str = OUTPUT_APP_DIR,
):
    src_unittest = get_unittest_dir(python_exe, target_platform)
    dst_unittest = os.path.join(output_app_dir, "unittest")
    if src_unittest and os.path.exists(src_unittest) and not os.path.exists(dst_unittest):
        print(f"Копирование unittest ({src_unittest}) -> {dst_unittest}")
        shutil.copytree(src_unittest, dst_unittest)


def _create_relative_symlink(target_abs: str, link_abs: str):
    if not os.path.exists(target_abs):
        return
    if os.path.lexists(link_abs):
        if os.path.islink(link_abs) or os.path.isfile(link_abs):
            os.unlink(link_abs)
        else:
            shutil.rmtree(link_abs)
    os.makedirs(os.path.dirname(link_abs), exist_ok=True)
    rel_target = os.path.relpath(target_abs, start=os.path.dirname(link_abs))
    os.symlink(rel_target, link_abs)


def _copy_asset_tree_filtered(src_assets: str, dst_assets: str, exclude_win_installers: bool):
    def _ignore_assets(dir_path: str, names: list[str]) -> set[str]:
        if not exclude_win_installers:
            return set()
        ignored = set()
        rel_dir = os.path.relpath(dir_path, src_assets).replace("\\", "/")
        if rel_dir == "." and "installers" in names:
            ignored.add("installers")
        for n in names:
            if n.lower().endswith((".exe", ".msi", ".dll", ".sys", ".bat", ".ps1")):
                ignored.add(n)
        return ignored

    shutil.copytree(src_assets, dst_assets, ignore=_ignore_assets, dirs_exist_ok=True)


def copy_project_resources(
    target_platform: str | None = None,
    output_app_dir: str = OUTPUT_APP_DIR,
    exclude_win_installers: bool = False,
    base_dir: str = BASE_DIR,
):
    plat = target_platform or sys.platform
    internal_dir = os.path.join(output_app_dir, "_internal")

    # На Windows копируем ресурсы в оба каталога; на Linux храним один экземпляр
    # в OUTPUT_APP_DIR и делаем относительные симлинки внутри _internal без дублирования объёма.
    locations = [output_app_dir, internal_dir] if plat == "win32" else [output_app_dir]

    for loc in locations:
        os.makedirs(loc, exist_ok=True)

        src_assets = os.path.join(base_dir, "assets")
        dst_assets = os.path.join(loc, "assets")
        if os.path.exists(src_assets) and not os.path.exists(dst_assets):
            print(f"Копирование assets -> {dst_assets}")
            _copy_asset_tree_filtered(src_assets, dst_assets, exclude_win_installers)

        src_models = os.path.join(base_dir, "optimized_models")
        dst_models = os.path.join(loc, "optimized_models")
        if os.path.exists(src_models) and not os.path.exists(dst_models):
            print(f"Копирование optimized_models -> {dst_models}")
            shutil.copytree(src_models, dst_models, symlinks=True)

        src_vpn = os.path.join(base_dir, "services", "vpn", "templates")
        dst_vpn = os.path.join(loc, "services", "vpn", "templates")
        if os.path.exists(src_vpn) and not os.path.exists(dst_vpn):
            os.makedirs(os.path.dirname(dst_vpn), exist_ok=True)
            print(f"Копирование vpn templates -> {dst_vpn}")
            shutil.copytree(src_vpn, dst_vpn)

        src_games = os.path.join(base_dir, "core", "games")
        dst_games = os.path.join(loc, "core", "games")
        if os.path.exists(src_games) and not os.path.exists(dst_games):
            os.makedirs(os.path.dirname(dst_games), exist_ok=True)
            print(f"Копирование core/games -> {dst_games}")
            shutil.copytree(src_games, dst_games)

        src_utils = os.path.join(base_dir, "core", "utils")
        dst_utils = os.path.join(loc, "core", "utils")
        if os.path.exists(src_utils):
            os.makedirs(dst_utils, exist_ok=True)
            for f in os.listdir(src_utils):
                if f.endswith(".json"):
                    shutil.copy2(os.path.join(src_utils, f), os.path.join(dst_utils, f))

        src_cfg_tpl = os.path.join(base_dir, "personal_data", "configs", "config.template.json")
        dst_cfg_dir = os.path.join(loc, "personal_data", "configs")
        if os.path.exists(src_cfg_tpl):
            os.makedirs(dst_cfg_dir, exist_ok=True)
            shutil.copy2(src_cfg_tpl, os.path.join(dst_cfg_dir, "config.template.json"))

    if plat != "win32":
        os.makedirs(internal_dir, exist_ok=True)
        rel_subdirs = [
            "assets",
            "optimized_models",
            os.path.join("services", "vpn", "templates"),
            os.path.join("core", "games"),
            os.path.join("core", "utils"),
            os.path.join("personal_data", "configs"),
        ]
        for sub in rel_subdirs:
            _create_relative_symlink(
                os.path.join(output_app_dir, sub),
                os.path.join(internal_dir, sub),
            )

    print("[Assets]: Все ресурсы и модели успешно скопированы!")


def clean_distribution(
    target_platform: str | None = None,
    dist_dir: str = DIST_DIR,
    output_app_dir: str = OUTPUT_APP_DIR,
):
    plat = target_platform or sys.platform
    step("3.1. Очистка дистрибутива от лишних файлов и тестов")

    unused_dev_pkgs = ["jedi", "sympy", "IPython", "matplotlib", "mpl_toolkits"]
    for pkg in unused_dev_pkgs:
        p = os.path.join(output_app_dir, pkg)
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)
            print(f"Исключен пакет: {pkg}")

    for f in ["pylab.py", "isympy.py"]:
        p = os.path.join(output_app_dir, f)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    deleted_dirs = 0
    for root, dirs, files in list(os.walk(output_app_dir, topdown=False)):
        folder_name = os.path.basename(root).lower()
        if folder_name in ("tests", "test", "testing", "__pycache__", "include", "docs", "htmlcov"):
            norm_root = root.replace("\\", "/")
            if "optimized_models" in norm_root or "assets" in norm_root or "torch/testing" in norm_root:
                continue
            shutil.rmtree(root, ignore_errors=True)
            deleted_dirs += 1

    remove_exts = (".whl", ".pdb") if plat == "win32" else (".whl", ".pdb", ".pyd", ".exe", ".dll", ".sys")
    deleted_files = 0
    for root, dirs, files in os.walk(output_app_dir):
        norm_root = root.replace("\\", "/")
        if "optimized_models" in norm_root or "assets" in norm_root:
            continue
        for f in files:
            if f.lower().endswith(remove_exts):
                try:
                    os.remove(os.path.join(root, f))
                    deleted_files += 1
                except Exception:
                    pass

    for intermediate in ["main.dist", "main.build", "Akira.dist", "Akira.build"]:
        inter_path = os.path.join(dist_dir, intermediate)
        if os.path.exists(inter_path) and inter_path != output_app_dir:
            shutil.rmtree(inter_path, ignore_errors=True)

    total_files = sum(len(files) for _, _, files in os.walk(output_app_dir))
    print(f"[Cleanup]: Удалено {deleted_dirs} каталогов и {deleted_files} лишних файлов.")
    print(f"[Cleanup]: Итоговое число файлов в сборке: {total_files}.")


def apply_runtime_patches(output_app_dir: str = OUTPUT_APP_DIR):
    step("3.2. Применение патчей стабильности рантайма (PyTorch / Transformers)")

    # 1. Защита от сбоя GradBucket в torch.distributed
    target_torch_dist = os.path.join(output_app_dir, "torch", "distributed", "__init__.py")
    if os.path.exists(target_torch_dist):
        try:
            with open(target_torch_dist, "r", encoding="utf-8") as f:
                content = f.read()
            old_str = 'if is_available() and not torch._C._c10d_init():\n    raise RuntimeError("Failed to initialize torch.distributed")'
            new_str = 'if is_available() and not hasattr(getattr(torch._C, "_distributed_c10d", None), "GradBucket"):\n    if not torch._C._c10d_init():\n        raise RuntimeError("Failed to initialize torch.distributed")'
            if old_str in content:
                content = content.replace(old_str, new_str)
                with open(target_torch_dist, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[Patch]: Успешно пропатчен torch.distributed для предотвращения GradBucket crash.")
            else:
                print("[Patch]: torch.distributed уже пропатчен или не требует изменений.")
        except Exception as e:
            print(f"[Patch Warning]: Не удалось пропатчить torch.distributed: {e}")

    # 2. Защита от циклического импорта в torch.nested (AttributeError: autograd)
    target_nested = os.path.join(output_app_dir, "torch", "nested", "_internal", "nested_tensor.py")
    if os.path.exists(target_nested):
        try:
            with open(target_nested, "r", encoding="utf-8") as f:
                content = f.read()
            if "_AutogradFunction" not in content:
                content = content.replace("import torch\n", "import torch\nfrom torch.autograd import Function as _AutogradFunction\n", 1)
                content = content.replace("class ViewBufferFromNested(torch.autograd.Function):", "class ViewBufferFromNested(_AutogradFunction):")
                content = content.replace("class ViewNestedFromBuffer(torch.autograd.Function):", "class ViewNestedFromBuffer(_AutogradFunction):")
                with open(target_nested, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[Patch]: Успешно пропатчен torch.nested для предотвращения circular import.")
            else:
                print("[Patch]: torch.nested уже пропатчен или не требует изменений.")
        except Exception as e:
            print(f"[Patch Warning]: Не удалось пропатчить torch.nested: {e}")

    # 3. Предварительная привязка core-модулей в torch.__init__ до импорта подпакетов
    target_torch_init = os.path.join(output_app_dir, "torch", "__init__.py")
    if os.path.exists(target_torch_init):
        try:
            with open(target_torch_init, "r", encoding="utf-8") as f:
                content = f.read()
            old_torch_init = "set_grad_enabled as set_grad_enabled,\n)\n\nfrom torch import ("
            new_torch_init = 'set_grad_enabled as set_grad_enabled,\n)\n\ntry:\n    for _i, _h in enumerate(sys.path_hooks):\n        if "FileFinder" in str(_h):\n            sys.path_hooks.insert(0, sys.path_hooks.pop(_i))\n            break\n    sys.path_importer_cache.clear()\nexcept Exception:\n    pass\n\nfor _mod in ("autograd", "nn", "optim", "nested"):\n    try:\n        _m = importlib.import_module(f"torch.{_mod}")\n        if __name__ in sys.modules:\n            setattr(sys.modules[__name__], _mod, _m)\n    except Exception:\n        pass\n\nfrom torch import ('
            if old_torch_init in content:
                content = content.replace(old_torch_init, new_torch_init, 1)
                with open(target_torch_init, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[Patch]: Успешно пропатчен torch.__init__ для предварительной привязки autograd/nn/optim.")
            else:
                print("[Patch]: torch.__init__ уже пропатчен или не требует изменений.")
        except Exception as e:
            print(f"[Patch Warning]: Не удалось пропатчить torch.__init__: {e}")

    # 4. Защита от циклического импорта в torch.optim (AttributeError: nn)
    target_optim = os.path.join(output_app_dir, "torch", "optim", "optimizer.py")
    if os.path.exists(target_optim):
        try:
            with open(target_optim, "r", encoding="utf-8") as f:
                content = f.read()
            if "import torch.nn.parameter" not in content:
                content = content.replace("import torch\n", "import torch\nimport torch.nn.parameter\n", 1)
                with open(target_optim, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[Patch]: Успешно пропатчен torch.optim для предварительного импорта nn.parameter.")
            else:
                print("[Patch]: torch.optim уже пропатчен или не требует изменений.")
        except Exception as e:
            print(f"[Patch Warning]: Не удалось пропатчить torch.optim: {e}")

    # 5. Защита torch._guards от отсутствия unittest.mock
    target_guards = os.path.join(output_app_dir, "torch", "_guards.py")
    if os.path.exists(target_guards):
        try:
            with open(target_guards, "r", encoding="utf-8") as f:
                content = f.read()
            old_mock = "import unittest.mock"
            new_mock = (
                "try:\n"
                "    import unittest.mock\n"
                "except ImportError:\n"
                "    import types\n"
                "    _dummy_mock = types.ModuleType('unittest.mock')\n"
                "    _dummy_mock.patch = lambda *a, **kw: (lambda f: f)\n"
                "    class _DummyMockObj:\n"
                "        def __init__(self, *a, **kw): pass\n"
                "        def __enter__(self): return self\n"
                "        def __exit__(self, *a): pass\n"
                "        def __getattr__(self, name): return self\n"
                "    _dummy_mock.patch.object = lambda *a, **kw: _DummyMockObj()\n"
                "    _dummy_mock.Mock = _DummyMockObj\n"
                "    _dummy_mock.MagicMock = _DummyMockObj\n"
                "    sys.modules['unittest.mock'] = _dummy_mock\n"
                "    if 'unittest' in sys.modules:\n"
                "        sys.modules['unittest'].mock = _dummy_mock\n"
                "    import unittest.mock"
            )
            if old_mock in content and "class _DummyMockObj:" not in content:
                content = content.replace(old_mock, new_mock, 1)
                with open(target_guards, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[Patch]: Успешно пропатчен torch._guards для безопасного импорта unittest.mock.")
            else:
                print("[Patch]: torch._guards уже пропатчен или не требует изменений.")
        except Exception as e:
            print(f"[Patch Warning]: Не удалось пропатчить torch._guards: {e}")

    # 6. Патч unittest/__init__.py для автоматического экспорта mock
    target_unittest_init = os.path.join(output_app_dir, "unittest", "__init__.py")
    if os.path.exists(target_unittest_init):
        try:
            with open(target_unittest_init, "r", encoding="utf-8") as f:
                content = f.read()
            if "from . import mock" not in content:
                content += "\ntry:\n    from . import mock\nexcept Exception:\n    pass\n"
                with open(target_unittest_init, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[Patch]: Успешно пропатчен unittest.__init__ для автоэкспорта mock.")
            else:
                print("[Patch]: unittest.__init__ уже пропатчен или не требует изменений.")
        except Exception as e:
            print(f"[Patch Warning]: Не удалось пропатчить unittest.__init__: {e}")
