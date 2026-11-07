import os
import sys
import re
import json
import queue
import time
import numpy as np
import sounddevice as sd
import vosk
from PyQt6.QtCore import QThread, pyqtSignal
from core.nlp.asr_corrector import ASRCorrector
from core.utils.config import load_config, get_resource_path
from core.system.actions import ym_manager

try:
    from comtypes import CoInitialize, CoUninitialize
    _HAS_COM = True
except ImportError:
    _HAS_COM = False

try:
    import soundcard as sc
except ImportError:
    sc = None

FAST_PASS_WORDS = {
    "погода", "погоду", "погоде", "градус", "градусов", "температура", "прогноз",
    "музыка", "музыку", "трек", "песня", "песню", "пауза", "стоп", "плей",
    "включи", "выключи", "открой", "закрой", "запусти", "подруби", "вруби",
    "громкость", "тише", "громче", "звук", "запрет", "обход", "компьютер",
    "пк", "дискорд", "впн", "свет", "люстра", "яркость", "ютуб", "спотифай",
    "расскажи", "умеешь", "делаешь", "дела", "привет", "кто", "что", "как", "зачем", "почему"
}

ALLOWED_PREFIXES = {
    "эй", "ну", "а", "слушай", "привет", "здравствуй", "хей", "так", "ок", "ладно"
}

QUERY_WORDS = {
    "кто", "что", "как", "почему", "зачем", "когда", "где", "куда", "откуда",
    "сколько", "какой", "какая", "какое", "какие", "каком", "какую", "каких",
    "расскажи", "объясни", "подскажи", "посоветуй", "помоги", "скажи", "переведи",
    "знаешь", "умеешь", "можешь", "бывает", "правда", "верно", "смысл", "думаешь"
}

COMMAND_ROOTS = [
    "включ", "выключ", "открой", "закрой", "запуст", "постав", "сделай",
    "переключ", "выруб", "вруб", "прибав", "убав", "заблокируй", "залочь",
    "покажи", "смени", "найди", "заведи", "потуши", "зажги", "сыграй",
    "перемотай", "напомни", "пауз", "стоп", "продолжи", "удали", "отмени", "сбрось"
]

SYSTEM_TARGETS = {
    "погода", "погоду", "погоде", "градус", "градусов", "температура", "прогноз",
    "музыка", "музыку", "музыке", "трек", "трека", "треку", "песня", "песню", "песни",
    "громкость", "тише", "громче", "звук", "звука", "запрет", "обход", "компьютер",
    "пк", "комп", "дискорд", "впн", "vpn", "свет", "люстра", "люстру", "лампа", "лампу",
    "розетка", "розетку", "яркость", "ютуб", "спотифай", "таймер", "будильник",
    "напоминание", "фильм", "сериал", "кино", "видео", "игра", "игры", "города", "данетки"
}

CHAT_WORDS = {
    "привет", "здравствуй", "доброе", "добрый", "спокойной", "пока", "до",
    "спасибо", "благодарю", "молодец", "умница", "красотка", "красавица",
    "дура", "тупая", "дурак", "тупой", "люблю", "нравишься", "скучаю",
    "дела", "делишки", "настроение", "жизнь", "создатель", "автор", "свят", "светозар"
}


class STTThread(QThread):
    text_recognized = pyqtSignal(str, bytes)
    listening_state_changed = pyqtSignal(bool)
    wake_word_detected = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path=None, parent=None):
        super().__init__(parent)
        self.followup_timeout = 3.5
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self._running = True
        self.samplerate = 16000
        self.audio_queue = queue.Queue()
        self.manual_trigger_flag = False
        self.is_speaking = False
        self.corrector = None
        self.model_path = model_path if model_path else get_resource_path("optimized_models", "model_vosk")

        cfg = load_config()
        assistant_name = cfg.get("assistant_name", "акира").lower()

        self.wake_words = {
            assistant_name,
            "акир", "акира", "акиру", "акиры", "акире",
            "окиро", "окиру", "окиры", "акиро",
            "акыра", "акыру", "акыры", "акиира", "акирра",
            "кира", "киру", "киры", "киро",
            "аки", "акирка", "акирочка"
        }

    def set_speaking(self, state: bool):
        self.is_speaking = state
        if state:
            with self.audio_queue.mutex:
                self.audio_queue.queue.clear()

    def start_followup(self, timeout=3.0):
        self.followup_timeout = timeout
        self.manual_trigger_flag = True

    def _audio_callback(self, indata, frames, time_info, status):
        audio_data = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
        audio_data = audio_data - np.mean(audio_data)

        peak = np.max(np.abs(audio_data))

        if peak > 10.0:
            target_peak = 20000.0
            gain = min(12.0, max(1.0, target_peak / max(peak, 1.0)))
            boosted = np.clip(audio_data * gain, -32768, 32767).astype(np.int16)
        else:
            boosted = audio_data.astype(np.int16)

        self.audio_queue.put(boosted.tobytes())

    def _is_wake_word(self, word: str) -> bool:
        clean = re.sub(r'[^\w]', '', word.lower())
        if not clean:
            return False
        if clean in self.wake_words:
            return True
        if clean.startswith(("акир", "окир", "акыр")):
            return True
        if clean in ["пакира", "макира", "окира", "покура", "кира", "киру", "киры", "киро", "аки"]:
            return True
        return False

    def _contains_wake_word(self, text: str):
        words = text.lower().split()
        if not words:
            return False, -1

        if self._is_wake_word(words[0]):
            return True, 0

        if len(words) > 1:
            clean_first = re.sub(r'[^\w]', '', words[0])
            if clean_first in ALLOWED_PREFIXES and self._is_wake_word(words[1]):
                return True, 1

        return False, -1

    def _is_likely_command(self, text: str) -> bool:
        words = text.lower().split()
        if not words:
            return False

        if len(words) <= 7:
            return True

        clean_words = [re.sub(r'[^\w]', '', w) for w in words]
        word_set = set(clean_words)

        if word_set & QUERY_WORDS:
            return True
        if word_set & SYSTEM_TARGETS:
            return True
        if word_set & CHAT_WORDS:
            return True
        if any(any(root in w for root in COMMAND_ROOTS) for w in clean_words):
            return True

        return False

    def trigger_manual_listen(self):
        self.manual_trigger_flag = True

    def _smart_correct(self, raw_text: str) -> str:
        clean = raw_text.strip().lower()
        if not clean:
            return ""

        words = clean.split()
        if len(words) <= 8:
            print(f"[STT Фаст-пас]: Короткая фраза ({len(words)} сл.) -> без задержки", flush=True)
            return clean

        word_set = set(re.findall(r'\w+', clean))
        if word_set & FAST_PASS_WORDS:
            print(f"[STT Фаст-пас]: Найдено триггер-слово -> без задержки", flush=True)
            return clean

        if self.corrector is None:
            self.corrector = ASRCorrector()

        t0 = time.perf_counter()
        print(f"[STT]: Запуск корректора на CPU для: '{raw_text}'", flush=True)
        corrected = self.corrector.correct(raw_text)
        print(f"[STT]: Корректор отработал за {time.perf_counter() - t0:.2f}с -> '{corrected}'", flush=True)
        return corrected

    def _get_default_mic_info(self):
        """Определяет актуальный системный микрофон по умолчанию через WASAPI."""
        if sc is None:
            return None, None
        try:
            mic = sc.default_microphone()
            if mic:
                return getattr(mic, 'id', None), getattr(mic, 'name', 'Default Microphone')
        except Exception:
            pass
        return None, None

    def _is_tts_active(self) -> bool:
        """Проверяет, говорит ли Акира сейчас, чтобы не прерывать PortAudio."""
        main_win = self.parent()
        if main_win and hasattr(main_win, 'tts_thread'):
            return main_win.tts_thread.isRunning()
        return getattr(self, 'is_speaking', False)

    def _open_stream(self):
        """Создает и запускает входной аудиопоток с автоматическим ресемплингом в 16 кГц."""
        try:
            stream = sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=4000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback
            )
            stream.start()
            return stream
        except Exception as e:
            print(f"[STT Stream Error]: Не удалось открыть поток микрофона: {e}", flush=True)
            return None

    def run(self):
        if _HAS_COM:
            try:
                CoInitialize()
            except Exception:
                pass

        try:
            vosk.SetLogLevel(-1)
            model = vosk.Model(self.model_path)
            recognizer = vosk.KaldiRecognizer(model, self.samplerate)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка загрузки модели Vosk: {e}")
            if _HAS_COM:
                try:
                    CoUninitialize()
                except Exception:
                    pass
            return

        current_mic_id, current_mic_name = self._get_default_mic_info()
        if current_mic_name:
            print(f"[STT]: Активный микрофон: {current_mic_name}", flush=True)

        stream = self._open_stream()
        if stream is None:
            self.error_occurred.emit("Ошибка микрофона: не удалось инициализировать устройство")

        active_mode = False
        active_start_time = 0.0
        utterance_buffer = bytearray()
        wake_signaled = False
        device_check_counter = 0

        self.listening_state_changed.emit(False)

        try:
            while self._running:
                # 1. Проверка смены устройства и здоровья потока каждые ~1.5 сек
                device_check_counter += 1
                if device_check_counter >= 15:
                    device_check_counter = 0

                    is_stream_dead = (stream is None) or (not stream.active)
                    new_mic_id, new_mic_name = self._get_default_mic_info()
                    mic_changed = (new_mic_id is not None and new_mic_id != current_mic_id)

                    # Переподключаем только когда TTS не выводит звук
                    if (mic_changed or is_stream_dead) and not self._is_tts_active():
                        if stream:
                            try:
                                stream.stop()
                                stream.close()
                            except Exception:
                                pass
                            stream = None

                        try:
                            sd._terminate()
                            sd._initialize()
                        except Exception:
                            pass

                        with self.audio_queue.mutex:
                            self.audio_queue.queue.clear()
                        utterance_buffer.clear()
                        recognizer.Reset()

                        stream = self._open_stream()
                        if stream:
                            current_mic_id = new_mic_id
                            current_mic_name = new_mic_name
                            print(f"[STT]: Микрофон переключен на: {current_mic_name}", flush=True)

                if stream is None:
                    self.msleep(200)
                    continue

                if self.is_speaking:
                    try:
                        self.audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        pass
                    continue

                if self.manual_trigger_flag:
                    self.manual_trigger_flag = False
                    active_mode = True
                    active_start_time = time.time()
                    recognizer.Reset()
                    utterance_buffer.clear()
                    wake_signaled = False
                    ym_manager.duck()
                    self.listening_state_changed.emit(True)

                if active_mode and (time.time() - active_start_time > self.followup_timeout):
                    active_mode = False
                    utterance_buffer.clear()
                    wake_signaled = False
                    ym_manager.unduck(100)
                    self.listening_state_changed.emit(False)

                try:
                    data = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                utterance_buffer.extend(data)

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    phrase_audio = bytes(utterance_buffer)
                    utterance_buffer.clear()
                    wake_signaled = False

                    if not text:
                        continue

                    main_win = self.parent()
                    is_alarm_ringing = False
                    if main_win and hasattr(main_win, 'command_parser'):
                        is_alarm_ringing = main_win.command_parser.reminder_manager.is_ringing

                    if is_alarm_ringing:
                        self.text_recognized.emit(text, phrase_audio)
                        continue

                    has_wake, wake_idx = self._contains_wake_word(text)

                    if has_wake:
                        self.wake_word_detected.emit()
                        self.followup_timeout = 4.5
                        words = text.split()
                        raw_command = " ".join(words[wake_idx + 1:]).strip()
                        if raw_command:
                            if not self._is_likely_command(raw_command):
                                ym_manager.unduck(100)
                                self.listening_state_changed.emit(False)
                                active_mode = False
                                continue

                            ym_manager.duck()
                            command = self._smart_correct(raw_command)
                            self.text_recognized.emit(command, phrase_audio)
                            active_mode = False
                            self.listening_state_changed.emit(False)
                        else:
                            active_mode = True
                            active_start_time = time.time()
                            recognizer.Reset()
                            ym_manager.duck()
                            self.listening_state_changed.emit(True)
                    elif active_mode:
                        if not self._is_likely_command(text):
                            ym_manager.unduck(100)
                            self.listening_state_changed.emit(False)
                            active_mode = False
                            continue

                        command = self._smart_correct(text)
                        self.text_recognized.emit(command, phrase_audio)
                        active_mode = False
                        self.listening_state_changed.emit(False)
                else:
                    partial_res = json.loads(recognizer.PartialResult())
                    partial_text = partial_res.get("partial", "").strip()

                    if active_mode:
                        if partial_text:
                            active_start_time = time.time()
                    else:
                        if partial_text and not wake_signaled:
                            has_wake, _ = self._contains_wake_word(partial_text)
                            if has_wake:
                                wake_signaled = True
                                self.wake_word_detected.emit()
                                ym_manager.duck()
                                self.listening_state_changed.emit(True)
        finally:
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            if _HAS_COM:
                try:
                    CoUninitialize()
                except Exception:
                    pass

    def stop_thread(self):
        self._running = False
        ym_manager.unduck()
        self.wait()