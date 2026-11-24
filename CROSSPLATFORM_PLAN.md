# План кроссплатформенности Akira (Windows + Linux Mint Cinnamon)

> **Ключевой принцип:** ни одна существующая функция на Windows не должна пострадать. Платформозависимая логика разделяется на отдельные модули/реализации (`*_win.py` и `*_linux.py`) за едиными фасадами с диспетчеризацией по `sys.platform`. На Linux целевой платформой является **Linux Mint Cinnamon (X11)** (с безопасным fallback для Wayland).

---

## Этап 1. Зависимости, точка входа и пути данных

### 1.1. Зависимости и системные пакеты
- [x] Разделить `requirements.txt` с помощью маркеров окружения (`; sys_platform == 'win32'` / `; sys_platform == 'linux'`):
  - Windows-only: `pycaw>=20230407; sys_platform == 'win32'`, `comtypes>=1.2.0; sys_platform == 'win32'`.
  - Linux-only: `pulsectl; sys_platform == 'linux'` (мягкое управление громкостью и приглушением в PulseAudio/PipeWire), `python-xlib; sys_platform == 'linux'` (активные окна и управление X11-окнами), `mss; sys_platform == 'linux'` (быстрые скриншоты на X11).
  - Ускоритель ONNX на Linux: по умолчанию `onnxruntime>=1.16.0`, с документированной опцией `onnxruntime-gpu` для владельцев NVIDIA GPU (`CUDAExecutionProvider`).
- [x] Подготовить список системных пакетов Linux Mint / Ubuntu (для `apt` и зависимостей `.deb`-пакета):
  `libportaudio2`, `libpulse0`, `pulseaudio-utils` (или `pipewire-pulse`), `wireplumber`, `vlc`, `libvlc5`, `ffmpeg`, `xdotool`, `wmctrl`, `scrot`, `libxcb-cursor0`, `libxkbcommon-x11-0`, `libgl1`, `patchelf`.

### 1.2. Точка входа, автовыбор `.venv` и обработчик падений (`main.py`)
- [x] Исправить автопереключение в `.venv` (`main.py`): на Windows искать `.venv/Scripts/python.exe`, на Linux — `.venv/bin/python` (сравнение путей через `os.path.realpath`, чтобы не зацикливаться на симлинках `python -> python3.12`).
- [x] Защитить блок `os.add_dll_directory(torch_lib)` проверкой `sys.platform == "win32"`; на Linux при необходимости пробрасывать `LD_LIBRARY_PATH` / rpath для `torch/lib`.
- [x] Сделать кроссплатформенным `_global_exception_handler`:
  - Путь к `crash.log` получать через единый резолвер пользовательских данных (а не напрямую из `APPDATA`).
  - На Linux вместо `ctypes.windll.user32.MessageBoxW` показывать ошибку через `QMessageBox` (если инициализирован `QApplication`) или `zenity`/`kdialog` + вывод в `stderr`.
- [x] Разделить иконки и интеграцию с панелью задач:
  - `SetCurrentProcessExplicitAppUserModelID` и `apply_native_windows_icon` вызывать строго при `sys.platform == "win32"`.
  - Заменить `get_ico_path()` на `get_app_icon_path()`: на Windows предпочитать `assets/icon/ico/akira_icon.ico`, на Linux — `assets/icon/png/akira_icon.png`.
  - На Linux вызывать `app.setDesktopFileName("akira")` для корректной иконки окна в панели задач Cinnamon.

### 1.3. Конфигурация, пути данных и исправление багов путей
- [x] Обновить `core/utils/config.py`:
  - На Windows (`frozen`): сохранить `%APPDATA%\Akira` без изменений.
  - На Linux (`frozen` и fallback): использовать XDG-каталог `$XDG_DATA_HOME/Akira` (по умолчанию `~/.local/share/Akira`) вместо `~/Akira`.
- [x] Убрать прямые обращения к `os.environ.get("APPDATA", ...)` в обход `get_user_data_path()` в `core/database/chat_db.py`, `core/vision/presence_manager.py`, `core/system/activity_tracker.py`.
- [x] Исправить неточные пути и битые импорты, критичные для регистрозависимой ФС Linux:
  - `gui/components/tray.py`: перевести поиск иконки на `get_resource_path("assets", "icon", "png", "akira_icon.png")` и `get_resource_path("assets", "icon", "ico", "akira_icon.ico")` (сейчас путь вычисляется относительно `gui/` и ссылается на несуществующий `assets/icon/akira_icon.png`).
  - `gui/dialogs/onboarding_wizard.py`: исправить путь `assets/icon/akira_icon.png` на `assets/icon/png/akira_icon.png`.
  - `core/vision/gesture_detector.py`: учитывать фактическое имя папки `optimized_models/hand_landmaker` (и вариант `hand_landmarker`).
  - Исправить пути импорта `blur` (`core.utils.blur` / `gui.utils.blur` -> `gui.components.blur`) в `gui/windows/chat_window.py`, `gui/windows/mini_window.py`, `gui/dialogs/onboarding_wizard.py`.
- [x] Сделать ленивый/безопасный импорт `pyautogui`: на Linux при `import pyautogui` без переменной `DISPLAY` падает `KeyError: 'DISPLAY'`, поэтому вынести импорт в безопасную обёртку, не ломающую запуск модулей и тестов.

---

## Этап 2. Аудио-подсистема (STT, TTS, громкость, Ducking, визуализатор)

### 2.1. Разделение управления громкостью и приглушения (`pycaw` / `comtypes` vs PulseAudio/PipeWire)
- [x] Убрать безусловные top-level импорты `pycaw` и `comtypes` из `core/system/volume_ducker.py`, `core/system/actions.py`, `gui/windows/chat_window.py`.
- [x] Разделить `VolumeDucker` и управление системной громкостью на `win` и `linux`:
  - **Windows-ветка**: оставить текущий код на `pycaw` + `comtypes` (`CoInitialize`, `AudioUtilities`, `ISimpleAudioVolume`, `IAudioEndpointVolume`) без изменений.
  - **Linux-ветка** (Linux Mint Cinnamon использует PipeWire/PulseAudio):
    - Общая громкость (`volume_up`, `volume_down`, `set_volume`, `mute_volume`, `unmute_volume`): управление через `pulsectl` / `wpctl` (`@DEFAULT_AUDIO_SINK@`) / `pactl` (`@DEFAULT_SINK@`) с fallback на `amixer`.
    - `VolumeDucker` (`duck`, `restore`, `force_restore`): приглушение сторонних потоков (`sink-inputs`) через `pulsectl` или `pactl list sink-inputs` + `pactl set-sink-input-volume` (с исключением собственного PID / `akira` / `python` и точным восстановлением громкости).

### 2.2. Микрофон (Vosk STT) и аудиовизуализатор (`sounddevice` / `soundcard`)
- [x] Доработать `audio/stt.py`:
  - Защитить `_get_default_mic_info()` от исключений `soundcard` (`IndexError`, `RuntimeError` — на Linux воспроизводилось при отсутствии активного источника PulseAudio) с fallback на `sounddevice.query_devices()`.
  - Проверить стабильность переподключения потока (`sd._terminate()` / `sd._initialize()`) под ALSA/PulseAudio/PipeWire на Linux Mint.
- [x] Доработать `AudioVisualizerWorker` в `gui/windows/chat_window.py`:
  - Защитить `CoInitialize()` / `CoUninitialize()` проверкой `sys.platform == "win32"`.
  - Добавить безопасную обработку ошибок `soundcard` loopback (`include_loopback=True` на мониторе PulseAudio/PipeWire в Linux Mint) без спама в лог при отсутствии активного аудиоустройства.

### 2.3. Нейросетевой TTS (Piper + ONNX Runtime) и воспроизведение аудио
- [x] Обновить `get_tts_execution_providers()` и `load_piper_voice()` в `audio/tts.py`:
  - Windows: оставить приоритет `["DmlExecutionProvider", "CPUExecutionProvider"]`.
  - Linux: добавить автодетект `CUDAExecutionProvider` (NVIDIA GPU при установленном `onnxruntime-gpu`) и `ROCMExecutionProvider` с автоматическим откатом на `CPUExecutionProvider`.
- [x] Проверить совместимость `piper-tts` и словарей `assets/espeak-ng-data` на Linux (фонемизатор `ru`, конфиги и сэмплы смеха проверены; сами `.onnx`-модели в этом клоне — Git LFS указатели, полная озвучка/шёпот заработают после `git lfs pull`).
- [x] Проверить работу `QSoundEffect` (`core/system/reminder_manager.py`), `QMediaPlayer` (`gui/windows/studio_frame.py`) и `convert_audio_to_wav()` (`gui/windows/settings_window.py`) в Qt6 на Linux Mint (с системным `ffmpeg`).

---

## Этап 3. Системные действия, запуск программ, трекинг активности и автозапуск

### 3.1. Системные команды под Linux Mint Cinnamon (`core/system/actions.py`)
- [x] Вынести платформозависимые методы `SystemActions` в `core/system/platform_win.py` (вся текущая WinAPI/cmd логика без изменений) и `core/system/platform_linux.py`:
  - **Блокировка экрана** (`lock_screen`): `cinnamon-screensaver-command -l` -> `loginctl lock-session` -> `xdg-screensaver lock` -> D-Bus `org.cinnamon.ScreenSaver` / `org.freedesktop.ScreenSaver`.
  - **Спящий режим** (`sleep_mode`): `systemctl suspend` (или D-Bus `org.freedesktop.login1.Manager.Suspend`).
  - **Выключение / Перезагрузка / Отмена** (`shutdown_pc`, `restart_pc`, `cancel_shutdown`): отменяемый фоновый таймер (5 сек или 60 сек для `DownloadWatcher`) + `systemctl poweroff` / `systemctl reboot` (или `shutdown`), чтобы команда отмены реально останавливала запланированное выключение.
  - **Корзина** (`get_recycle_bin_info`, `empty_recycle_bin`): подсчёт и очистка по стандарту FreeDesktop Trash (`~/.local/share/Trash/files` и `~/.local/share/Trash/info`).
  - **Автоопределение города по системной таймзоне** (`get_city_from_system_timezone`): на Linux чтение IANA-таймзоны (`/etc/localtime` symlink, `/etc/timezone`, `timedatectl`) + добавление IANA-ключей (`Europe/Moscow`, `Europe/Kaliningrad` и др.) в `core/utils/timezones.json`.
  - **Быстрый запуск программ и режимов** (`open_calculator`, `open_task_manager`, `open_discord`, `open_telegram`, `mode_work`, `mode_rest`): поиск нативных Linux-приложений (`gnome-calculator`/`galculator`, `gnome-system-monitor`, `nemo`, `xed`, `discord` / Flatpak `com.discordapp.Discord`, `telegram-desktop` / Flatpak `org.telegram.desktop`) с fallback на веб-версии и `xdg-open`.
  - **Скриншоты** (`take_screenshot`): кроссплатформенный хелпер (`mss` / `ImageGrab` на X11 и Windows, `QScreen.grabWindow` / `scrot` / `gnome-screenshot` / `grim` fallback).

### 3.2. Лаунчер приложений (`core/system/app_launcher.py`)
- [x] Разделить `AppLauncher` на Windows-реализацию (`.lnk`/`.url`, `os.startfile`, Win `builtins`) и Linux-реализацию (`app_launcher_linux.py`):
  - Сканирование `.desktop` файлов в `~/.local/share/applications`, `/usr/share/applications`, `/var/lib/flatpak/exports/share/applications`, `/var/lib/snapd/desktop/applications`, `~/Desktop`.
  - Парсинг `Name`, `Name[ru]`, `GenericName`, `Exec` (очистка плейсхолдеров `%u`, `%U`, `%f`, `%F`, `%i`, `%c`, `%k`), фильтрация `NoDisplay=true` / `Hidden=true`.
  - Запуск найденных приложений через `subprocess.Popen` (или `gio launch`), а файлов/ссылок — через кроссплатформенный `open_path()` (`xdg-open` / `QDesktopServices.openUrl`).
  - Кроссплатформенные `builtins` для Cinnamon (`калькулятор` -> `gnome-calculator`, `проводник` -> `nemo`, `блокнот` -> `xed`, `диспетчер задач` -> `gnome-system-monitor`, `терминал` -> `gnome-terminal` / `x-terminal-emulator`, `параметры` -> `cinnamon-settings`).
- [x] Обновить фильтр выбора файлов в `gui/dialogs/mode_config_dialog.py` под Linux (`*.desktop *.sh *.AppImage` и все файлы).
- [x] Заменить `os.startfile(self.image_path)` в `gui/windows/studio_frame.py` на кроссплатформенный `open_path()`.

### 3.3. Трекер активности (`core/system/activity_tracker.py`)
- [x] Разделить `_track_loop` на получение активного окна под Windows (`user32`) и под Linux X11 (`python-xlib`: чтение `_NET_ACTIVE_WINDOW`, `_NET_WM_NAME`/`WM_NAME`, `_NET_WM_PID` + `psutil.Process`, без постоянного спавна CLI-процессов каждые 5 секунд; на Wayland — безопасный fallback).
- [x] Расширить `categorize_app()` типичными Linux-приложениями (`gnome-terminal`, `konsole`, `kitty`, `nemo`, `xed`, `telegram-desktop`, `code`, игры без суффикса `.exe`).

### 3.4. Автозапуск (`gui/windows/settings_window.py`, `gui/dialogs/onboarding_wizard.py`)
- [x] Убрать top-level `import winreg` из `gui/windows/settings_window.py`.
- [x] Переименовать `_apply_windows_autostart` в `_apply_autostart(enabled)`:
  - Windows: оставить `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
  - Linux Mint Cinnamon: создавать/удалять `~/.config/autostart/akira.desktop` с корректным `Exec=` для текущего режима запуска (`.venv`, Nuitka-бинарник или установленный пакет).
- [x] Обновить текст в мастере первого запуска (`gui/dialogs/onboarding_wizard.py`): «Автоматический запуск вместе с системой».

---

## Этап 4. Компьютерное зрение, кинотеатр (TorrServer + VLC), музыка и Telegram

### 4.1. Камера и биометрия
- [x] Заменить жёсткий `cv2.CAP_DSHOW` на платформозависимый выбор (`cv2.CAP_DSHOW` на Windows, `cv2.CAP_V4L2` с fallback на `cv2.CAP_ANY` на Linux) в `core/vision/vision_provider.py`, `services/telegram/telegram_bot.py` и `services/telegram/notifier.py`.
- [x] Проверить работу `face_recognition` (`dlib`), `mediapipe` и `eye_state_model.onnx` на Linux (`dlib`/`face_recognition` с `pkg_resources`-шимом и MediaPipe Landmarker проверены; `eye_state_model.onnx` в текущем клоне — Git LFS указатель, безопасно обрабатывается до `git lfs pull`).

### 4.2. Торрент-кинотеатр: автоскачивание TorrServer по требованию + VLC
- [x] Адаптировать `services/torrent/torrserver_manager.py`:
  - На Windows сохранить поиск `torrserver.exe` в комплекте поставки без изменений.
  - На Linux **не вшивать бинарник TorrServer в дистрибутив**, а хранить/искать в `get_user_data_path("torrserver", "TorrServer-linux-amd64")` (или системный `torrserver` в `PATH`).
  - Реализовать метод `download_linux_binary(progress_callback=...)`, скачивающий официальный релиз `TorrServer-linux-amd64` (или `arm64`) с GitHub Releases (`YouROK/TorrServer`), выставляющий `chmod +x` и проверяющий целостность файла.
  - Убрать безусловный вызов `subprocess.STARTUPINFO()` / `STARTF_USESHOWWINDOW` / `CREATE_NO_WINDOW` (на Linux этот код падает с `AttributeError`) — применять только при `sys.platform == "win32"`.
- [x] Добавить сценарий первого запуска кинотеатра на Linux (`core/nlp/parser/command_parser.py` + `gui/windows/chat_window.py`):
  - Если пользователь просит фильм/сериал, а бинарника TorrServer на Linux ещё нет, Акира **сначала предупреждает в чат и голосом** (например: *«Для потокового просмотра фильмов на Linux мне нужно скачать движок TorrServer. Сейчас загружу его и сразу включу кино!»*).
  - Фоновый поток (`TorrServerDownloadWorker`) скачивает TorrServer без зависания интерфейса, запускает сервер и сразу переходит к буферизации и запуску фильма/сериала в VLC (с понятным сообщением в чат, если возникла ошибка сети).
- [x] Адаптировать `services/torrent/vlc_player.py` и `services/yandex/yandex_music_manager.py`:
  - `_find_vlc()`: на Windows оставить `winreg` и `Program Files`; на Linux искать `shutil.which("vlc")`, `/usr/bin/vlc`, Flatpak (`org.videolan.VLC`), Snap.
  - Конфиг `vlcrc`: на Windows `%APPDATA%\vlc\vlcrc`, на Linux `$XDG_CONFIG_HOME/vlc/vlcrc` (`~/.config/vlc/vlcrc`).
  - `install_silent()`: на Windows оставить `vlc_installer.exe`; на Linux без `.exe` предлагать/запускать системную установку (`pkexec apt install -y vlc` / `flatpak`) или открывать сайт/инструкцию.
  - Управление VLC (`is_playing`, `stop`, `toggle_pause`, `toggle_fullscreen`, `seek`, `next_episode`, `prev_episode`, `next_audio_track`, `toggle_subtitles`, `speed_*`):
    - На Windows оставить `vlc.exe` + `_focus_vlc` + `pyautogui`.
    - На Linux искать процесс `"vlc"`, управлять приоритетно через **MPRIS D-Bus** (`org.mpris.MediaPlayer2.vlc` — без перехвата фокуса!) + X11-фокус (`python-xlib`/`wmctrl`/`xdotool`) и `pyautogui` для хоткеев дорожек/субтитров/скорости.
  - В `yandex_music_manager.py`: использовать `os.add_dll_directory()` только на Windows; на Linux опираться на системную `libvlc.so` (`ctypes.util.find_library("vlc")`).

### 4.3. Spotify, YouTube и Telegram-бот
- [x] В `services/spotify/spotify_manager.py`: убрать top-level `import winreg`; на Linux определять установленный Spotify через `shutil.which("spotify")`, Flatpak (`com.spotify.Client`), Snap (`/snap/bin/spotify`) и запускать напрямую или через `xdg-open spotify:` (вместо `cmd /c start spotify:`).
- [x] В `services/google/youtube_manager.py`: безопасно вызывать `pyautogui.press('f')` при наличии X11 `DISPLAY` (без падений на Wayland/headless).
- [x] В `services/telegram/telegram_bot.py`:
  - Использовать единый кроссплатформенный модуль питания вместо `shutdown /s`, `shutdown /r`, `shutdown /a`.
  - В `get_hardware_status()` на Linux фильтровать виртуальные и служебные разделы (`squashfs`, `tmpfs`, `overlay`, `/snap/*`, `/boot/efi`), корректно выводить имена точек монтирования (`/`, `/home`).
  - Перевести `take_screenshot_base64()` на кроссплатформенный скриншотер.

---

## Этап 5. Сеть: VPN (Sota, Browsec, Happ), Zapret и обход для GigaChat

### 5.1. Обход VPN для GigaChat (`core/nlp/generative/llm_provider.py`)
- [x] Сохранить Win32 `_get_physical_adapter_info()` (`iphlpapi`) и `IP_UNICAST_IF` для Windows.
- [x] Добавить Linux-реализацию `_get_physical_adapter_info()`: чтение `/proc/net/route` (исключая виртуальные интерфейсы `tun*`, `wg*`, `sing*`, `browbox*`, `docker*`, `lo`) + `psutil.net_if_addrs()` для бинда сокета к IP физического адаптера (`local_address` в `httpx.HTTPTransport`).

### 5.2. VPN Manager на Linux: только Sota Connect, Browsec и Happ (`services/vpn/*`)
- [x] Разделить адаптеры в `services/vpn/adapters/` на Windows-реализацию (полностью сохранить текущие `CoreAdapter` и `GuiAdapter` с поддержкой `Browsec`, `Sota`, `Happ`, `V2Ray/Xray`, `WireGuard` без потерь!) и Linux-реализацию (`gui_adapter_linux.py`):
  - **Убрать из Linux-версии** Windows/CLI-сервисы `WireGuard` (`wireguard.exe`), `V2Ray/Xray` (`C:\v2ray\v2ray.exe`) и настройку прокси через `winreg`.
  - **Сосредоточиться на нативных Linux-клиентах Sota Connect, Browsec и Happ** (все три распространяются как `.deb` для Ubuntu/Linux Mint):
    - Поиск установленных клиентов на Linux: проверка `.desktop` файлов (`/usr/share/applications`, `~/.local/share/applications`), `/opt/...`, `shutil.which`, запущенных процессов `psutil`.
    - Управление окнами в Linux Mint Cinnamon (X11): поиск окна (`python-xlib` по `WM_CLASS`, `_NET_WM_NAME`, `_NET_WM_PID`), активация/фокусировка (`_NET_ACTIVE_WINDOW` / `wmctrl`), минимизация, определение системного масштаба Cinnamon (`gsettings org.cinnamon.desktop.interface scaling-factor` / `Xft.dpi`), захват экрана/окна (`mss` / `QScreen`) и мультимасштабный OpenCV-клик по тумблеру.
    - Подключить существующие шаблоны в `services/vpn/templates/` с мультимасштабным подбором (при визуальных отличиях конкретных Linux `.deb`-сборок Sota/Browsec/Happ шаблоны можно дополнить после живой проверки в Этапе 8).
    - Корректное отключение **Browsec** на Linux (`browbox`, `browray`, `browsec` через `psutil` без `.exe` и `taskkill`).
- [x] В `services/vpn/vpn_manager.py` и `core/nlp/parser/command_parser.py`:
  - На Linux определять, детектировать и предлагать пользователю только `Browsec`, `Sota` и `Happ` (если пользователь на Linux явно попросит WireGuard или V2Ray — вежливо отвечать, что эти клиенты поддерживаются только в Windows-версии, либо не включать их в список доступных на Linux).
  - Убрать top-level `import winreg` и `from ctypes import wintypes` из общих модулей VPN.

### 5.3. Ускоритель обхода DPI Zapret (`services/zapret/zapret.py`)
- [x] Разделить `ZapretManager` на `ZapretManagerWin` (текущая реализация `winws.exe` + `.bat` + `ShellExecuteW(..., "runas", ...)` — без изменений) и `ZapretManagerLinux`:
  - Реализовать управление нативным Linux `zapret` (`nfqws` / `tpws` + `nftables`/`iptables` или systemd-сервис `zapret` / скрипты стратегий в `~/zapret`, `/opt/zapret`, `/usr/share/zapret`), который работает на Linux Mint и даёт реальный прирост/обход блокировок.
  - Повышение привилегий при запуске/смене стратегии/остановке через `pkexec` (графический запрос пароля Polkit), с корректным снятием правил при `stop()`.
  - Если `zapret` не установлен в Linux-системе — понятное сообщение с подсказкой по установке нативного `zapret` для Linux.

---

## Этап 6. Графический интерфейс PyQt6 под Linux Mint Cinnamon

### 6.1. DWM, Blur, анимации и перетаскивание окон
- [x] Изолировать Windows-специфичный код (`_dwmapi`, `_DwmSetWindowAttribute`, `_DwmSetIconicThumbnail`, `_DwmInvalidateIconicBitmaps`, `_user32`, `nativeEvent`) в `gui/windows/chat_window.py` проверкой `sys.platform == "win32"`.
- [x] Проверить и доработать `show_animated()` и `_animate_down_and_do()` в `gui/windows/chat_window.py`:
  - На X11 (Linux Mint Cinnamon) убедиться, что slide-анимация окна с `FramelessWindowHint` + `WA_TranslucentBackground` не клипируется и не застревает у нижней панели Cinnamon.
  - На Wayland автоматически переключать slide-анимацию `pos` на плавную fade-анимацию (`windowOpacity`), а перетаскивание `MiniWindow` и диалогов — на `windowHandle().startSystemMove()`.
- [x] Обновить `gui/components/blur.py`: сохранить Win32 Acrylic для Windows, на Linux X11 (при поддержке композитором) добавить опциональный `_KDE_NET_WM_BLUR_BEHIND_REGION` и корректный no-op на Cinnamon, где фон красиво рисуется через `WA_TranslucentBackground`.

### 6.2. Системный трей и шрифты
- [x] Адаптировать `gui/components/tray.py` под Linux Mint Cinnamon (корректный PNG-значок, локализованное контекстное меню, надёжное восстановление окна из скрытого/свёрнутого состояния).
- [x] Задать кроссплатформенные fallback-шрифты вместо голого `"Consolas"` / `"Arial"` в `gui/styles.py`, `gui/widgets/code_formatter.py`, `gui/windows/chat_window.py`, `gui/dialogs/onboarding_wizard.py` (`"JetBrains Mono"`, `"DejaVu Sans Mono"`, `"Liberation Mono"`, `"Noto Sans"`, `"Ubuntu"` / `QFontDatabase.FixedFont`).

---

## Этап 7. Сборка, упаковка дистрибутива и автообновление

### 7.1. Пайплайн сборки (`build_nuitka.py`)
- [x] Разделить `build_nuitka.py` на общую подготовку ресурсов и два платформенных профиля (или `build_win.py` / `build_linux.py` с единой точкой входа `build_nuitka.py`):
  - **Windows**: полностью сохранить текущую сборку (`--mingw64`, `Akira.exe`, `Package.wxs` + `wix build` -> `.msi`, runtime-патчи `torch`/`unittest`).
  - **Linux**:
    - Автоопределение `.venv/bin/python`, `.venv/lib/pythonX.Y/site-packages`, `sys.base_prefix/lib/pythonX.Y/unittest`.
    - Компиляция Nuitka под Linux (`gcc`, `--output-filename=Akira`, `--linux-icon=assets/icon/png/akira_icon.png`, без `--mingw64` и `--windows-*`, с Qt6-плагинами `platforms`, `multimedia`, `imageformats`, `iconengines`).
    - Исключение из Linux-дистрибутива Windows-зависимостей (`pycaw`, `comtypes`) и Windows-бинарников (`assets/installers/vlc_installer.exe`, `assets/installers/torrserver.exe` — минус ~110 МБ, а также TorrServer не кладётся внутрь, т.к. скачивается по требованию).
    - Проверка актуальности runtime-патчей `torch`/`unittest` для Linux Nuitka-сборки.

### 7.2. Упаковка релиза под Linux Mint Cinnamon (`.deb` + `.AppImage` / `.tar.gz`)
- [x] Создать `.desktop`-файл (`akira.desktop`) с иконкой и `StartupWMClass=Akira`.
- [x] Реализовать сборку **`.deb`** пакета (родной формат Linux Mint — двойной клик в файловом менеджере, автоматическая подтяжка системных зависимостей `vlc`, `libportaudio2`, `ffmpeg`, `libpulse0`, `wmctrl`, `xdotool`, `scrot`, установка в `/opt/Akira` и симлинк `/usr/bin/akira`).
- [x] Реализовать сборку переносимого **`.tar.gz`** архива (с `install.sh`) и/или **`.AppImage`** (при наличии `appimagetool`).

### 7.3. Кроссплатформенное автообновление (`core/utils/updater.py`)
- [x] Обновить `UpdateCheckerThread` и `DownloaderThread`:
  - На Windows искать `.msi` / `.exe`.
  - На Linux искать `.deb` (или `.AppImage` при запуске из AppImage).
- [x] Обновить `apply_update_and_restart()`: на Windows оставить `msiexec.exe` / `.exe`; на Linux запускать установку `.deb` (`pkexec apt install -y <file>` / `xdg-open` в менеджер пакетов) или замену AppImage.

---

## Этап 8. Тестирование и верификация

### 8.1. Проверка на Linux Mint Cinnamon
- [ ] Холодный запуск из `.venv`: Onboarding Wizard, хранение конфигов/БД в `~/.local/share/Akira`, кастомные шрифты, прозрачность окна, трей Cinnamon.
- [ ] Голосовой конвейер: Vosk STT -> NLU -> Piper TTS (обычный/шёпот/смех, CPU и при наличии `onnxruntime-gpu` — CUDA) -> VolumeDucker (приглушение музыки в системе).
- [ ] Системные команды: громкость, `AppLauncher` (`.desktop` приложения), `ActivityTracker` (X11), корзина FreeDesktop, блокировка экрана Cinnamon, отменяемое выключение, погода по таймзоне.
- [ ] Кинотеатр и медиа: первое обращение к фильму -> предупреждение Акиры -> скачивание TorrServer -> запуск фильма в VLC + управление (пауза, перемотка, дорожки, субтитры), Яндекс Музыка (`libvlc.so`), Spotify, YouTube.
- [ ] Сеть: VPN-клиенты **Sota Connect**, **Browsec** и **Happ**, `Zapret` (`nfqws` через `pkexec`), GigaChat при активном VPN.
- [ ] Зрение и Telegram-бот: веб-камера `V4L2`, Face ID, жесты, скриншот, статус ПК (без виртуальных разделов `/snap`/`loop`).
- [ ] Сборка Linux-релиза через Nuitka + установка `.deb` пакета на Linux Mint Cinnamon и проверка запуска из меню приложений.

### 8.2. Регрессионная проверка на Windows
- [ ] Проверка, что все Windows-модули работают без изменений (`pycaw`, `winreg`, `DWM/Acrylic`, `AppLauncher`, `ActivityTracker`, `VpnManager` со всеми 5 клиентами, `ZapretManager` с `winws.exe`, `TorrServer` + `VLC`, `GigaChat` bypass). *(На Linux выполнена автоматическая проверка структуры AST, экспортов и валидности `Package.wxs` в `tests/test_stage8_e2e.py`; живой прогон требуется на ПК с Windows.)*
- [ ] Тестовая сборка `build_nuitka.py` + `Package.wxs` -> `Akira-Setup-v*.msi` на Windows.

### 8.3. Автоматическая верификация в `.venv` (выполнено на Linux)
- [x] Полная компиляция байткода всего репозитория (`compileall` без ошибок).
- [x] Импорт всех Linux-модулей без стабов `winreg` / `pycaw` / `comtypes`.
- [x] Прохождение сквозного автонабора тестов Этапов 1–8 (`QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p "test_stage*.py" -v` — **42/42 OK**):
  - `tests/test_stage4_vision_media.py` (10/10): камеры `V4L2`/`DSHOW`, `MediaPipe`/`dlib`/`pkg_resources`-шим, автозагрузка `TorrServer-linux-amd64` + предупреждение перед скачиванием, автоустановка/скачивание VLC (`VlcInstallWorker` с предупреждением, `apt-get`/`flatpak`/`snap`, без `--no-qt-updates-notif` на Linux), `VLC`/MPRIS, Spotify/YouTube, Telegram-бот.
  - `tests/test_stage5_network_vpn.py` (6/6): `GigaChat` bypass через `/proc/net/route`, GUI-адаптер Sota/Browsec/Happ + `gsettings` scale, `VpnManager` на Linux, `Zapret` (`nfqws` + `pkexec`).
  - `tests/test_stage6_gui.py` (8/8): шрифты без голого `Consolas`, drag X11/Wayland, `blur.py` Cinnamon/KDE, `SystemTray`, `CodeBlockWidget`, `MiniWindow`/`MainWindow` анимации X11/Wayland.
  - `tests/test_stage7_build_updater.py` (7/7): команды Nuitka Win/Linux, исключение Windows-инсталляторов (`~110 МБ`), симлинки `_internal`, runtime-патчи `torch`/`unittest`, реальная сборка `.deb` (`fakeroot dpkg-deb`) и `.tar.gz`, `AppDir`, автообновление `updater.py`.
  - `tests/test_stage8_e2e.py` (11/11): `compileall`, XDG-конфиги и SQLite `StudioChatDatabase`, TTS GPU/CPU провайдеры, `VolumeDucker`/`audio_control`, корзина FreeDesktop, блокировка экрана Cinnamon, отменяемое выключение, `.desktop` `AppLauncher`, `ActivityTracker`, авто-ресемплинг/fallback частоты `STTThread` (`44100/48000 -> 16000 Гц`), корректное закрытие `MainWindow.closeEvent` по `app.quit()`, `nvidia-smi` в Telegram-боте, все диалоги GUI, полный холодный запуск/выход `main.main()`, очистка Qt5-переменных OpenCV (`cv2/qt`) и проверка `libxcb-cursor.so.0` перед `QApplication`, плюс структурная/API-проверка Windows-модулей.
