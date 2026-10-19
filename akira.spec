import os
import sys
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    collect_dynamic_libs,
    collect_all
)

block_cipher = None
base_dir = os.path.abspath(SPECPATH)

datas = []
binaries = []
hiddenimports = []

critical_packages = [
    'vosk',
    'mediapipe',
    'face_recognition',
    'face_recognition_models',
    'dlib',
    'onnxruntime',
    'piper',
    'piper_phonemize',
    'soundcard'
]

for pkg in critical_packages:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

vpn_templates = os.path.join(base_dir, 'services', 'vpn', 'templates')
if os.path.exists(vpn_templates):
    datas.append((vpn_templates, os.path.join('services', 'vpn', 'templates')))

if os.path.exists(os.path.join(base_dir, 'assets')):
    datas.append((os.path.join(base_dir, 'assets'), 'assets'))

if os.path.exists(os.path.join(base_dir, 'optimized_models')):
    datas.append((os.path.join(base_dir, 'optimized_models'), 'optimized_models'))

# Упаковываем только шаблон конфига, исключая локальные ключи и фото
config_template = os.path.join(base_dir, 'personal_data', 'configs', 'config.template.json')
if os.path.exists(config_template):
    datas.append((config_template, os.path.join('personal_data', 'configs')))

dict_json_path = os.path.join(base_dir, 'core', 'utils', 'pronunciation_dict.json')
if os.path.exists(dict_json_path):
    datas.append((dict_json_path, os.path.join('core', 'utils')))

datas += collect_data_files('transformers')
datas += collect_data_files('torch')
datas += collect_data_files('certifi')

hiddenimports += [
    'pkg_resources',
    'setuptools',
    'scipy.signal',
    'scipy.special',
    'sounddevice',
    'soundfile',
    'cffi',
    'torch',
    'comtypes',
    'pycaw',
    'websockets',
    'librosa',
    'certifi',
    'requests',
    'qrcode',
    'packaging',
    'cv2',
    'pyautogui',
    'psutil',
    'PIL'
]

hiddenimports += collect_submodules('core')
hiddenimports += collect_submodules('gui')
hiddenimports += collect_submodules('services')
hiddenimports += collect_submodules('audio')

a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'notebook', 'IPython', 'matplotlib', 'pytest', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Akira',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(base_dir, 'assets', 'icon', 'ico', 'icon_round.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Akira'
)