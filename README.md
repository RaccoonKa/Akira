# 🌟 Akira — AI Voice Assistant & Desktop Studio

<p align="center">
  <img src="assets/icon/png/akira_icon.png" alt="Akira Logo" width="128"/>
</p>

<p align="center">
  <b>Cross-Platform Autonomous AI Voice Assistant & Desktop Studio for Windows and Linux</b><br>
  Combines offline neural TTS with whisper mode, local ONNX vision & biometrics, torrent cinema, Yandex Music crossfade, and Telegram PC hub.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-5.0.0-blueviolet?style=flat-square" alt="Version 5.0.0"/>
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?style=flat-square&logo=python" alt="Python Version"/>
  <img src="https://img.shields.io/badge/GUI-PyQt6-gold?style=flat-square&logo=qt" alt="PyQt6"/>
  <img src="https://img.shields.io/badge/Inference-ONNX%20Runtime%20%7C%20CUDA%20%7C%20DirectML-orange?style=flat-square" alt="ONNX Runtime"/>
  <img src="https://img.shields.io/badge/TTS-Piper%20(INT8)-green?style=flat-square" alt="Piper TTS"/>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-0078D6?style=flat-square&logo=linux" alt="Platform"/>
  <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/"><img src="https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey?style=flat-square" alt="License: CC BY-NC-ND 4.0"/></a>
</p>

---

## EN Version

---

## 📌 About the Project

**Akira** is an intelligent desktop assistant, creative studio, and management hub engineered for comprehensive voice, gesture, and remote smartphone control over your PC, multimedia, home network, and IoT ecosystem.

Unlike traditional cloud assistants, Akira utilizes a **hybrid privacy-first architecture**: critical tasks (STT, intent classification, face biometrics, hand gestures, sentiment analysis, audio ducking, and neural speech synthesis) execute **100% locally via quantized ONNX models**, while complex generative queries, document analysis, and studio dialogs leverage state-of-the-art LLMs (GigaChat API, DeepSeek, OpenAI, Gemini).

---

## ✨ Key Features

### 🎙️ Speech Pipeline, Whisper Mode & Game-Chat Shield
* **Offline STT & JointNLU:** Instant voice transcription using Vosk and an in-house JointNLU encoder with zero cloud lag.
* **Neural TTS with Whisper Mode & Natural Pacing:** Powered by quantized INT8 Piper models accelerated with DirectML/GPU. Features dynamic switching to a specialized whisper voice model for night-time interaction, clause/sentence pause management, and an extensive orthoepic pronunciation dictionary.
* **Game/Discord Anti-False-Trigger Filter:** Incorporates prefix gating and speech-continuity filters to prevent false wake-ups during Discord calls and gaming sessions.
* **Voiceprint & Speaker Verification:** Biometric acoustic identification verifying the owner's voice and filtering out background voices from teammates or speakers.

### 🎨 Akira Studio, Media Generation & Dynamic Model Switching
* **Interactive Desktop Studio:** Modern PyQt6 workspace with smooth inertial scrolling (in both main chat and Studio), unified jitter-free window expansion, dynamic chat history drawer with automatic session ID compaction in SQLite, and real-time title generation.
* **Multi-File Attachments (Up to 10 Files):** Attach **up to 10 files simultaneously** in Studio via paperclip or Drag & Drop (code, PDF, DOCX, logs, images) displayed in a compact Gemini-style chip strip, while the compact main chat supports 1-file quick analysis.
* **AI Image & Art Synthesis:** Text-to-Image and Image-to-Image generation (including multi-image references) powered by RouterAI with a custom 60 FPS "digital ether" loading shimmer, progressive scan-line revelation, and inline media viewer with copy/save actions.
* **Neural Music Generation:** High-fidelity stereo music and song synthesis with an animated real-time soundwave visualizer, built-in mini-player with interactive waveform seek bar, timestamp display, and one-click MP3 export.
* **Multi-LLM Integration & Guards:** Fluid switching between GigaChat, DeepSeek, and Gemini (`Hikari`, `Kasumi`, `Ginga`, `Uchū`), enforced Russian response guard for non-Russian drafts, system prompt leak protection with warm in-character replies, and lazy ONNX tokenization keeping RAM lean.

### 🎬 Torrent Streaming Cinema & Media Hub
* **Direct Torrent Streaming:** Instant playback of movies and TV series via TorrServer without waiting for the full file to download.
* **VLC Automation:** Voice-controlled episode switching, subtitle toggles, audio track/dubbing changes, playback speed adjustment, and precise time seeking.
* **Yandex Music & Media Control:** Native Yandex Music integration ("My Wave" without repeats, "Favorites / Liked", launching playlists by name, auto-continuing with "My Wave" after single-track requests), dual-deck equal-power crossfade without startup volume spikes, Spotify, YouTube auto-fullscreen, and global media keys.

### 📱 Remote Telegram Hub & File Bridge
* **Remote Management Hub:** Control your desktop from smartphone via Telegram bot with categorized command keyboards.
* **Download Watcher & Auto-Shutdown:** Tracks network receiving and SSD write activity. Notifies when game/file downloads complete and shuts down the PC after a safety countdown.
* **Phone-to-PC File Drop:** Send any documents, media, or archives directly to the Telegram bot to have them saved immediately to `Downloads/AkiraFiles` on your computer.
* **Multi-User Hub & Owner Administration:** Supports guest pairing via dynamic QR-code with remote moderation panels for the primary owner.

### 👁️ Biometrics & Vision
* **Owner Face ID:** Auto-detects the owner upon sitting in front of the camera and welcomes them back with adaptive greetings.
* **Security Patrol & Intruder Alerts:** Captures webcam snapshots of unrecognized users and sends an alert with a lock-screen button directly to Telegram.
* **Media Gestures:** Touchless MediaPipe gesture control (open palm to pause/play, fist to lock Windows, pointing to skip track).
* **Eye Fatigue & Health Monitoring:** Evaluates blink patterns and prolonged eye closure to suggest rest breaks.

### 🌐 Network & Bypass Controls
* **VPN Client Automation:** Voice-driven connection management for **Browsec**, **Sota Connect**, **Happ**, **V2Ray/Xray**, and **WireGuard**.
* **Zapret (winws) Strategies:** Voice-activated DPI bypass switching with auto-recovery across VPN network changes.

### 🎮 Games, Comfort Modes, Auto-Updates & New Year Easter Egg
* **Voice Games:** Play *Cities*, *Believe or Not* trivia, and detective *Danetki* riddles with interactive LLM refereeing.
* **Persistent Game Mode & Mini Mode:** Game mode persists across restarts until manually disabled; Mini Mode offers a compact floating orb.
* **Alarms, Timers & Reminders:** Natural language date/time parsing with background timers, wake-up alarms, and missed reminder tracking.
* **3-Act New Year Easter Egg:** Triggers at midnight (`Dec 31 -> Jan 1`, including `00:00–00:29` wake-up) or once on first launch during `Jan 1–7`: gently ducks music, launches snowfall & fireworks with chimes, speaks a personalized greeting (separate warm variants for regular users and the developer, with proper Russian ordinal year pronunciation), and fades in a holiday song (stoppable via `"хватит"` / `"стоп"` / `"выключи музыку"`).
* **Cross-Platform Auto-Updater & Data Safety:** Checks GitHub Releases and installs `.msi` on Windows or `.deb` / `.AppImage` / `.tar.gz` on Linux while preserving all user configs and SQLite chats in `%APPDATA%\Akira` / `~/.local/share/Akira`.

---

## 🗣️ Example Voice Commands

| Category | Example Commands |
| :--- | :--- |
| **🎬 Cinema & Torrents** | "Akira, find the movie Interstellar", "Play the next episode", "Switch audio track", "Rewind 30 seconds" |
| **🎵 Music & Media** | "Play My Wave", "Like this track", "Next song", "Turn down the volume", "Toggle fullscreen" |
| **⏳ Downloads & Power** | "Turn off the PC when downloads finish", "Lock screen", "Restart computer", "Shutdown PC" |
| **🌐 VPN & Bypass** | "Connect VPN", "Switch off Browsec", "Launch Zapret", "Set bypass strategy 7" |
| **⏰ Time & Tasks** | "Set an alarm for 7:30 AM", "Set a timer for 15 minutes", "Remind me tomorrow at 2 PM to call the doctor" |
| **🎲 Games & Chat** | "Let's play Cities", "Tell me the rules of Danetki", "Explain this attached document" |

---

## ⚙️ Architecture & Processing Pipeline

```mermaid
flowchart TD
    A["Input Source<br>(Voice / Text / Document / Telegram)"] --> B["Acoustic Verification & STT (Vosk)"]
    B --> C["Game-Chat Noise Filter & Prefix Gate"]
    C --> D["ASR Neural Post-Correction"]
    D --> E["Emotion Classifier & JointNLU (ONNX)"]
    E --> F{"Intelligent Router"}
    F --> G["Local Automation Engine<br>(TorrServer, VLC, WinAPI, IoT, VPN, Vision)"]
    F --> H["Telegram Remote Hub<br>(FastAPI WebSocket Server & Aiogram 3)"]
    F --> I["Generative Intelligence<br>(GigaChat API / DeepSeek / OpenAI / Gemini)"]
    G --> J["Local Piper Neural TTS<br>(DirectML GPU / Normal & Whisper Voice)"]
    I --> J
```

---

## 🔌 Supported Services and Ecosystem

| Category | Services and Modules |
| --- | --- |
| **Neural Intelligence** | Sber GigaChat API, DeepSeek API, OpenAI API, Gemini API, RouterAI (Image & Music Models: Gemini Nano Banana 2.1, Lyria 3 Pro Preview), JointNLU (ONNX), Text Emotion Classifier, RapidOCR |
| **Voice & Audio** | Vosk STT, Piper Neural TTS (INT8 ONNX), DirectML Provider, Volume Ducker, Orthoepic Normalizer |
| **Video & Streaming** | TorrServer Engine, VLC Player Controller, YouTube Data API |
| **Network Clients & VPN** | Browsec, Happ GUI, Sota Connect, WireGuard, V2Ray / Xray, Zapret (WinWS) |
| **Multimedia & IoT** | Yandex Music API, Spotify API, Yandex Smart Home IoT |
| **Vision & Biometrics** | Face ID (Dlib), MediaPipe Gestures, Eye Fatigue & Blink Tracker |
| **Remote Control** | Telegram Bot API (aiogram 3.x), Persistent WebSocket Tunnel |

---

## 📄 License

This project is licensed under the **[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/)** (Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International) License.
* **Non-Commercial:** You may not use the material for commercial purposes without explicit permission.
* **No Derivatives:** If you remix, transform, or build upon the material, you may not distribute the modified material.
* **Attribution:** Mandatory credit must be given to the author (Svetozar / RaccoonKa).

---

## RU Версия

---

## 📌 О проекте

**Akira** — это модульный десктопный ассистент, творческая студия и центр удалённого управления, созданный для полноценного голосового, жестового и мобильного контроля над вашим ПК, мультимедиа, домашней сетью и умными устройствами.

В отличие от стандартных облачных решений, Akira построена на **гибридной архитектуре с акцентом на приватность**: критические задачи (распознавание речи, классификация интентов NLU, верификация голоса, Face ID, жесты, анализ эмоций и нейросетевой синтез речи) выполняются **локально с помощью квантованных ONNX-моделей**, а генеративные диалоги, студийное общение и обработка документов поручены современным LLM-моделям (**GigaChat API**, **DeepSeek**, **OpenAI**, **Gemini**).

---

## ✨ Ключевые возможности

### 🎙️ Речевой конвейер, режим шёпота и размеренная дикция
* **Офлайн STT и JointNLU:** Мгновенное локальное распознавание команд через Vosk и собственную модель JointNLU без сетевых задержек.
* **Нейросетевой TTS с поддержкой шёпота:** Локальный синтез речи на базе моделей Piper (INT8) с аппаратным ускорением DirectML/GPU. Поддерживает автоматический переход на специальную модель шёпота в ночное время, смысловое деление фраз с естественными микропаузами и расширенный словарь орфоэпии.
* **Фильтр разговоров в играх и Discord:** Архитектура Prefix Gate и анализ связности речи отсекают реплики, сказанные в войс-чат тиммейтам, предотвращая случайные вмешательства ассистента.
* **Биометрия голоса (Speaker Verification):** Идентификация тембра владельца, отсекающая посторонние голоса и звуки из колонок.

### 🎨 Студия Акиры, генерация медиа и выбор нейросетей
* **Интерактивное рабочее пространство:** Современный интерфейс на PyQt6 с плавным инерционным скроллом (в основном чате и Студии), плавным единым раскрытием окна без мерцаний, боковой шторкой истории с авто-упорядочиванием ID диалогов в SQLite и нейросетевой генерацией заголовков.
* **Мульти-прикрепление до 10 файлов:** В Студии к одному сообщению можно прикрепить **до 10 файлов сразу** (скрепкой `📎` или Drag & Drop: код, PDF, DOCX, логи, изображения) в компактной ленте чипов, а в обычном чате доступен быстрый разбор 1 файла.
* **Генерация артов и иллюстраций:** Создание изображений по текстовому промпту (Text-to-Image) и по нескольким референсам (Image-to-Image) через RouterAI с 60 FPS эффектом «цифрового эфира», сканирующей анимацией проявления и карточкой просмотра.
* **Нейросетевая генерация музыки:** Создание 48 kHz стереокомпозиций с живым волновым эквалайзером в цвет текущей эмоции Акиры, встроенным мини-плеером с перемоткой по аудиоволне и экспортом в MP3.
* **Мульти-LLM ядро и защита диалога:** Переключение между GigaChat, DeepSeek и Gemini (`Hikari`, `Kasumi`, `Ginga`, `Uchū`), контроль русского языка в ответах, защита от выдачи системного промпта с тёплой реакцией Акиры, а также ленивый ONNX-токенизатор для экономии ОЗУ.

### 🎬 Торрент-кинотеатр и мультимедиа
* **Потоковый просмотр торрентов:** Воспроизведение фильмов и сериалов через TorrServer без необходимости предварительного скачивания файлов на диск.
* **Управление плеером VLC:** Голосовое переключение серий, выбор аудиодорожек и озвучек, управление субтитрами, регулировка скорости и точная перемотка.
* **Яндекс Музыка и стриминг:** Запуск «Моей волны» без повторов, плейлиста «Избранное / Моё любимое», любых плейлистов по названию, продолжение «Моей волной» после заказанного трека, плавный кроссфейд между треками без скачков громкости, а также Spotify и авторазворачивание YouTube на весь экран.

### 📱 Удалённый Telegram-хаб и передача файлов
* **Центр управления в смартфоне:** Удобная навигация по категориям (Мониторинг, Питание, Закачки, Возможности) через Telegram-бота.
* **Сторож закачек и автовыключение:** Мониторинг входящего интернет-трафика и активности записи на диск. После завершения скачивания и распаковки присылает пуш-уведомление и безопасно выключает ПК по таймеру.
* **Быстрый сброс файлов на ПК:** Отправьте любой документ, фото, видео или архив боту в Telegram — Акира мгновенно сохранит его в папку `Загрузки/AkiraFiles` на вашем компьютере.
* **Многопользовательский режим и администрирование:** Привязка ПК по динамическому QR-коду и панель создателя для просмотра статуса сети и модерации доступа.

### 👁️ Биометрия и компьютерное зрение
* **Face ID владельца:** Приветствие при возвращении за рабочее место с адаптивными репликами в зависимости от времени отсутствия.
* **Охранный режим:** Автоматическая фиксация посторонних перед веб-камерой и отправка фото-тревоги в Telegram с кнопкой мгновенной блокировки ПК.
* **Бесконтактные жесты:** Управление мультимедиа через MediaPipe (пауза ладонью, блокировка экрана кулаком, переключение трека указательным пальцем).
* **Контроль усталости глаз:** Отслеживание частоты моргания и закрытия глаз с предупреждениями об отдыхе.

### 🌐 Сеть, VPN и обход блокировок
* **Автоматизация VPN-клиентов:** Голосовое подключение и управление туннелями для **Browsec**, **Sota Connect**, **Happ**, **V2Ray/Xray** и **WireGuard**.
* **Стратегии Zapret (winws):** Быстрое переключение конфигураций обхода DPI с автоматическим сохранением стабильного соединения при смене сетевых маршрутов.

### 🎮 Игры, режимы комфорта, автообновление и пасхалки
* **Голосовые игры:** Полноценные сессии в «Города», «Верю — не верю» и «Данетки» с судейством через LLM.
* **Сохраняемый игровой режим и мини-режим:** Игровой режим сохраняется даже после перезапуска программы, пока вы сами его не выключите; мини-режим сворачивает окно в компактную сферу.
* **Будильники, таймеры и напоминания:** Распознавание естественной речи для установки будильников, таймеров и задач с сохранением пропущенных напоминаний после включения ПК.
* **Новогодняя пасхалка в 3 актах:** Срабатывает ровно в полночь (`31.12 -> 01.01`, включая пробуждение в `00:00–00:29`) либо при первом запуске `1–7 января` раз в год: приглушает фоновую музыку, запускает снегопад и салют с переливом сферы, включает куранты (`assets/sounds/holidays/`), произносит персональное поздравление (отдельное для обычных пользователей и разработчика, с правильным склонением года в речи) и плавно включает новогоднюю мелодию (останавливается словами «хватит» / «стоп» / «выключи музыку»).
* **Кроссплатформенное автообновление:** Проверка релизов на GitHub и установка `.msi` на Windows или `.deb` / `.AppImage` / `.tar.gz` на Linux без потери настроек и переписок (`%APPDATA%\Akira` / `~/.local/share/Akira`).

---

## 🗣️ Примеры голосовых команд

| Категория | Примеры команд |
| --- | --- |
| **🎬 Кинотеатр и видео** | "Акира, найди фильм Интерстеллар", "Следующая серия", "Смени озвучку", "Перемотай на 20 секунд назад" |
| **🎵 Музыка и звук** | "Включи мою волну", "Лайкни этот трек", "Следующая песня", "Сделай потише", "Разверни на весь экран" |
| **⏳ Закачки и питание** | "Выключи компьютер, когда всё скачается", "Заблокируй экран", "Перезагрузи ПК", "Выключи компьютер" |
| **🌐 VPN и обход** | "Включи VPN", "Выключи Browsec", "Запусти Zapret", "Выбери седьмой обход" |
| **⏰ Время и задачи** | "Поставь будильник на 7:30 утра", "Поставь таймер на 15 минут", "Напомни завтра в два часа дня сходить в банк" |
| **🎲 Игры и файлы** | "Давай сыграем в Данетки", "Расскажи правила игры в Города", "Изучи прикреплённый документ" |

---

## ⚙️ Архитектура и конвейер обработки

```mermaid
flowchart TD
    A["Входной сигнал<br>(Голос / Текст / Файл / Telegram)"] --> B["Верификация голоса и STT (Vosk)"]
    B --> C["Фильтр игрового шума и Prefix Gate"]
    C --> D["Нейросетевая коррекция ASR"]
    D --> E["Классификатор эмоций и JointNLU (ONNX)"]
    E --> F{"Интеллектуальный маршрутизатор"}
    F --> G["Локальная автоматизация<br>(TorrServer, VLC, WinAPI, IoT, VPN, Vision)"]
    F --> H["Удалённый Telegram-хаб<br>(FastAPI WebSocket сервер и Aiogram 3)"]
    F --> I["Генеративный интеллект<br>(GigaChat API / DeepSeek / OpenAI / Gemini)"]
    G --> J["Локальный нейро-TTS Piper<br>(DirectML GPU / Обычный голос и Шёпот)"]
    I --> J
```

---

## 🔌 Поддерживаемые сервисы и экосистема

| Категория | Сервисы и модули |
| --- | --- |
| **Нейросетевой интеллект** | Sber GigaChat API, DeepSeek API, OpenAI API, Gemini API, RouterAI (Генерация изображений и музыки: Gemini Nano Banana 2.1, Lyria 3 Pro Preview), JointNLU (ONNX), Text Emotion Classifier, RapidOCR |
| **Голос и синтез** | Vosk STT, Piper Neural TTS (INT8 ONNX), DirectML Provider, Volume Ducker, Orthoepic Normalizer |
| **Видео и стриминг** | Движок TorrServer, контроллер плеера VLC, YouTube Data API |
| **Сетевые клиенты и VPN** | Browsec, Happ GUI, Sota Connect, WireGuard, V2Ray / Xray, Zapret (WinWS) |
| **Мультимедиа и IoT** | Yandex Music API, Spotify API, Умный дом с Алисой (IoT) |
| **Зрение и биометрия** | Face ID (Dlib), жесты MediaPipe, трекинг моргания и усталости глаз |
| **Удалённый доступ** | Telegram Bot API (aiogram 3.x), постоянный WebSocket-туннель |

---

## 🛡️ Приватность и локальность данных

* **Локальная биометрия:** Распознавание лица, голосовые отпечатки владельца, трекинг глаз и жестовое управление производятся строго локально. Видео- и аудиопотоки не передаются на внешние серверы.
* **Изолированное хранение данных:** Токены, конфигурации и пользовательские файлы хранятся на локальном диске в каталогах `personal_data/` и `Downloads/AkiraFiles/`.

---

## 📄 Лицензия

Проект распространяется под юридической лицензией **[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/)** (Creative Commons С указанием авторства — Некоммерческая — Без производных 4.0 Международная).
* **Некоммерческое использование:** Запрещено использовать проект и его части в коммерческих целях без предварительного согласия автора.
* **Без производных произведений:** Запрещено распространять изменённые версии, форки с модификациями или переработанные файлы проекта.
* **Указание авторства:** Обязательно сохранение указания авторства (Светозар / RaccoonKa).
