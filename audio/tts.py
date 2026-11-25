import os
import sys
import re
import json
import queue
import random
import threading
import wave
import numpy as np
import sounddevice as sd
import onnxruntime as ort
from PyQt6.QtCore import QThread, pyqtSignal
from piper.voice import PiperVoice
from piper.config import SynthesisConfig
from core.utils.config import get_resource_path, load_config
from core.utils.onnx_runtime import (
    describe_execution_provider,
    get_onnx_execution_providers,
    prepare_onnx_gpu_env,
)
from core.system.actions import ym_manager
from core.utils.text_cleaner import clean_voice_text

ort.set_default_logger_severity(3)
prepare_onnx_gpu_env(ort)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAIN_VOICE_ONNX = get_resource_path("optimized_models", "voice_tts", "aki_voice_int8.onnx")
MAIN_VOICE_JSON = get_resource_path("optimized_models", "voice_tts", "aki_voice_int8.onnx.json")

WHISPER_VOICE_ONNX = get_resource_path("optimized_models", "whisper_tts", "aki_whisper_int8.onnx")
WHISPER_VOICE_JSON = get_resource_path("optimized_models", "whisper_tts", "aki_whisper_int8.onnx.json")

ESPEAK_DATA_PATH = get_resource_path("assets", "espeak-ng-data")

DICT_FILE_PATH = get_resource_path("core", "utils", "pronunciation_dict.json")
CUSTOM_DICTIONARY = {}
COMPILED_DICT_REGEX = None


def _load_pronunciation_dictionary():
    global CUSTOM_DICTIONARY, COMPILED_DICT_REGEX
    if os.path.exists(DICT_FILE_PATH):
        try:
            with open(DICT_FILE_PATH, "r", encoding="utf-8") as f:
                CUSTOM_DICTIONARY = json.load(f)
            sorted_keys = sorted(CUSTOM_DICTIONARY.keys(), key=len, reverse=True)
            escaped_keys = [re.escape(k) for k in sorted_keys]
            COMPILED_DICT_REGEX = re.compile(r'(?<!\w)(' + '|'.join(escaped_keys) + r')(?!\w)', flags=re.IGNORECASE)
        except Exception as e:
            print(f"[Pronunciation Dict Error]: {e}")
            CUSTOM_DICTIONARY = {}
            COMPILED_DICT_REGEX = None


_load_pronunciation_dictionary()

LAUGH_REGEX = re.compile(
    r'(?:'
    r'[*_\[\(]\s*[^*_\[\]\(\)\n]*?(?:сме[еёх]|хихик|усме[хш]|хохо[тч]|хмык|ха[-–—]?ха|ахах|хе[-–—]?хе)[^*_\[\]\(\)\n]*?[*_\]\)]'
    r'|'
    r'(?<![а-яёa-z])(?:[хx][аa][-–—][хx][аa](?:[-–—][хx][аa])*|[хx][еe][-–—][хx][еe](?:[-–—][хx][еe])*|а?хах[ах]*|хех[ех]+)(?![а-яёa-z])'
    r')',
    re.IGNORECASE
)

NON_LAUGH_ACTION_REGEX = re.compile(
    r'(?:'
    r'(?<![*_])[*_](?![*_])\s*[^*_\n]{1,120}\s*(?<![*_])[*_](?![*_])'
    r'|'
    r'\[\s*[^\]\n]{1,120}\s*\]'
    r'|'
    r'\(\s*[^\)\n]*?(?:улыб|вздох|вздых|подмиг|зева|смущ|задум|пауз|машет|молчит|шепч|кива)[^\)\n]*?\)'
    r')',
    re.IGNORECASE
)

_LAUGH_CACHE = {}


def _load_laugh_samples(target_sr=22050):
    global _LAUGH_CACHE
    if target_sr in _LAUGH_CACHE:
        return _LAUGH_CACHE[target_sr]

    samples = []
    for idx in (1, 2, 3):
        cand_paths = [
            get_resource_path("assets", "sounds", "laugh", f"laugh_{idx}.wav"),
            get_resource_path("assets", "sounds", f"laugh_{idx}.wav")
        ]
        chosen = None
        for p in cand_paths:
            if p and os.path.exists(p):
                chosen = p
                break

        if chosen:
            try:
                with wave.open(chosen, 'rb') as wf:
                    n_channels = wf.getnchannels()
                    orig_sr = wf.getframerate()
                    n_frames = wf.getnframes()
                    raw = wf.readframes(n_frames)

                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                if n_channels > 1:
                    audio = audio.reshape(-1, n_channels).mean(axis=1)

                if orig_sr != target_sr:
                    orig_len = len(audio)
                    target_len = int(round(orig_len * (target_sr / orig_sr)))
                    audio = np.interp(
                        np.linspace(0, orig_len, target_len, endpoint=False),
                        np.arange(orig_len),
                        audio
                    )
                int16_bytes = np.clip(audio, -32768, 32767).astype(np.int16).tobytes()
                samples.append(int16_bytes)
            except Exception as e:
                print(f"[Laugh Load Error] {chosen}: {e}")

    _LAUGH_CACHE[target_sr] = samples
    return samples


def get_random_laugh_bytes(target_sr=22050):
    samples = _load_laugh_samples(target_sr)
    if samples:
        return random.choice(samples)
    return None

def get_tts_execution_providers():
    prepare_onnx_gpu_env(ort)
    available = ort.get_available_providers()
    if sys.platform == "win32":
        for gpu_provider in ("DmlExecutionProvider", "CUDAExecutionProvider"):
            if gpu_provider in available:
                return [gpu_provider, "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]
    for gpu_provider in ("CUDAExecutionProvider", "ROCMExecutionProvider"):
        if gpu_provider in available:
            return [gpu_provider, "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def load_piper_voice(model_path, config_path, espeak_data_dir=None):
    data_dir = espeak_data_dir or ESPEAK_DATA_PATH
    providers = get_tts_execution_providers()
    primary = providers[0] if providers else "CPUExecutionProvider"

    sess_opts = ort.SessionOptions()
    sess_opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_opts.log_severity_level = 3

    voice = None
    active_provider = "CPUExecutionProvider"

    # Сначала создаём сессию напрямую с приоритетом GPU (без двойной загрузки на CPU)
    try:
        from pathlib import Path
        from piper.config import PiperConfig

        with open(config_path, "r", encoding="utf-8") as cf:
            cfg = PiperConfig.from_dict(json.load(cf))

        session = None
        if primary != "CPUExecutionProvider":
            try:
                session = ort.InferenceSession(str(model_path), sess_options=sess_opts, providers=providers)
                active_list = list(session.get_providers() or [])
                if active_list and active_list[0] != "CPUExecutionProvider":
                    active_provider = active_list[0]
                else:
                    session = None
            except Exception as e:
                label = describe_execution_provider(primary)
                print(f"[TTS Warning]: {label} недоступен для {os.path.basename(model_path)} ({e}). Откат на CPU.")
                session = None

        if session is None:
            session = ort.InferenceSession(str(model_path), sess_options=sess_opts, providers=["CPUExecutionProvider"])
            active_provider = "CPUExecutionProvider"

        voice_kwargs = {"session": session, "config": cfg}
        if data_dir and os.path.exists(data_dir):
            voice_kwargs["espeak_data_dir"] = Path(data_dir)
        voice = PiperVoice(**voice_kwargs)
    except Exception:
        if not os.path.exists(data_dir):
            voice = PiperVoice.load(model_path=model_path, config_path=config_path)
        else:
            voice = PiperVoice.load(model_path=model_path, config_path=config_path, espeak_data_dir=data_dir)
        active_list = list(getattr(voice.session, "get_providers", lambda: ["CPUExecutionProvider"])() or [])
        active_provider = active_list[0] if active_list else "CPUExecutionProvider"

    if active_provider != "CPUExecutionProvider":
        label = describe_execution_provider(active_provider)
        print(f"[TTS]: Модель {os.path.basename(model_path)} запущена на GPU ({label})")
    else:
        if sys.platform == "win32":
            print(f"[TTS]: GPU-провайдер (DirectML/CUDA) не найден. {os.path.basename(model_path)} работает на CPU.")
        else:
            print(f"[TTS]: GPU-провайдер ONNX (CUDA/ROCm) не найден. {os.path.basename(model_path)} работает на CPU.")

    return voice


def apply_pronunciation_and_translit(text: str) -> str:
    if not text:
        return ""

    if COMPILED_DICT_REGEX:
        def dict_sub(match):
            key = match.group(0).lower()
            return CUSTOM_DICTIONARY.get(key, match.group(0))
        text = COMPILED_DICT_REGEX.sub(dict_sub, text)

    def translit_fallback(match):
        w = match.group(0).lower()
        replacements = [
            ("sh", "ш"), ("ch", "ч"), ("th", "т"), ("ph", "ф"),
            ("zh", "ж"), ("kh", "х"), ("ts", "ц"), ("ee", "и"),
            ("oo", "у"), ("ea", "и"), ("ck", "к"), ("qu", "кв"),
            ("ya", "я"), ("yo", "ё"), ("yu", "ю"), ("x", "кс"),
            ("w", "в"), ("j", "дж"), ("c", "к"), ("q", "к")
        ]
        for lat, cyr in replacements:
            w = w.replace(lat, cyr)

        char_map = {
            'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е',
            'z': 'з', 'i': 'и', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н',
            'o': 'о', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у',
            'f': 'ф', 'h': 'х', 'y': 'и'
        }
        return "".join(char_map.get(ch, ch) for ch in w)

    return re.sub(r'[a-zA-Z]+', translit_fallback, text)


class TTSThread(QThread):
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    warmup_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_voice = None
        self.whisper_voice = None

        self.text_to_speak = ""
        self.is_whisper = False
        self._stopped = False
        self._is_warmup = False
        self._play_cached_flag = False

        self.greeting_to_precache = ""
        self.cached_greeting_audio = None
        self.cached_greeting_sr = 22050
        self.warmup_text = "готов"
        self._audio_queue = None

    def _init_models(self):
        if self.main_voice is None and os.path.exists(MAIN_VOICE_ONNX):
            try:
                self.main_voice = load_piper_voice(MAIN_VOICE_ONNX, MAIN_VOICE_JSON)
            except Exception as e:
                print(f"[Main Piper Init Error]: {e}")

        if self._stopped:
            return

        if self.whisper_voice is None and os.path.exists(WHISPER_VOICE_ONNX):
            try:
                self.whisper_voice = load_piper_voice(WHISPER_VOICE_ONNX, WHISPER_VOICE_JSON)
            except Exception as e:
                print(f"[Whisper Piper Init Error]: {e}")

    def _clean_text_for_tts(self, text, is_clause=False):
        if not text:
            return ""

        def _expand_time(m):
            h = int(m.group(1))
            minute = int(m.group(2))
            if minute == 0:
                return f"{h} часов"
            elif minute < 10:
                return f"{h} ноль {minute}"
            else:
                return f"{h} {minute}"

        text = re.sub(r'\b(\d{1,2}):(\d{2})\b', _expand_time, text)

        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U000025B6"
            "\U0001F900-\U0001F9FF"
            "\U0001FA70-\U0001FAFF"
            "\u2600-\u26FF"
            "\u2700-\u27BF"
            "]+", flags=re.UNICODE
        )
        cleaned = emoji_pattern.sub("", text)
        cleaned = re.sub(r'[:;=]-?[()DOPpP|/\\]|<3', '', cleaned)
        cleaned = apply_pronunciation_and_translit(cleaned)

        cleaned = re.sub(r'\+([аеёиоуыэюяАЕЁИОУЫЭЮЯ])', r'\1' + '\u0301', cleaned)
        cleaned = re.sub(r'([аеёиоуыэюяАЕЁИОУЫЭЮЯ])\+', r'\1' + '\u0301', cleaned)

        cleaned = cleaned.lower().strip()
        cleaned = cleaned.replace('!', '.').replace(';', ',').replace('—', '-')
        cleaned = re.sub(r'\.+', '.', cleaned)
        cleaned = re.sub(r'[^\w\s\.,!?\-\u0301]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if cleaned and re.search(r'[a-zа-яё0-9]', cleaned):
            if is_clause:
                cleaned = cleaned.rstrip('.,!? ') + ','
            elif not cleaned.endswith(('.', '?')):
                cleaned += '.'
            return cleaned

        return ""

    def _get_volume_factor(self, is_whisper=False):
        cfg = load_config()
        vol_percent = cfg.get("voice_volume", 100)
        vol_factor = max(0.0, min(1.0, vol_percent / 100.0))
        if is_whisper:
            vol_factor *= 0.65
        return vol_factor

    def _get_synthesis_config(self, is_whisper=False):
        cfg = load_config()
        # length_scale > 1.0 замедляет темп речи (1.09 дает ~9% более размеренную и четкую артикуляцию)
        length_scale = float(cfg.get("voice_length_scale", 1.09))
        if is_whisper:
            length_scale = max(1.0, length_scale * 0.98)
        return SynthesisConfig(length_scale=length_scale)

    def _split_into_speech_phrases(self, text: str):
        if not text:
            return []

        # Нормализация многоточий, переносов строк и частых сокращений
        text = re.sub(r'\.{3,}|…', '.', text)
        text = re.sub(r'[\r\n]+', '. ', text)
        text = re.sub(r'\bт\.\s*д\.', 'и так далее', text, flags=re.IGNORECASE)
        text = re.sub(r'\bт\.\s*п\.', 'и тому подобное', text, flags=re.IGNORECASE)
        text = re.sub(r'\bт\.\s*е\.', 'то есть', text, flags=re.IGNORECASE)
        text = re.sub(r'\bт\.\s*к\.', 'так как', text, flags=re.IGNORECASE)

        raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if not raw_sentences:
            raw_sentences = [text.strip()]

        conj_pattern = re.compile(
            r',\s+(?=(?:чтобы|потому что|так как|хотя|если|когда|который|которая|которое|которые|при этом|в то время как|но|а|дабы|зато|также|однако)\b)',
            re.IGNORECASE
        )

        phrases = []
        for sent in raw_sentences:
            if not sent:
                continue
            words = sent.split()
            # Короткие предложения читаем целиком
            if len(words) <= 11:
                phrases.append(('sentence', sent))
                continue

            # Длинное предложение: сначала разбиваем по знакам препинания (; : —)
            sub_parts = [p.strip() for p in re.split(r'(?<=[;:])\s+|(?<=\s[—–-])\s*', sent) if p.strip()]

            refined_parts = []
            for sp in sub_parts:
                sp_words = sp.split()
                if len(sp_words) > 11:
                    c_parts = [cp.strip() for cp in conj_pattern.split(sp) if cp.strip()]
                    if len(c_parts) > 1:
                        refined_parts.extend(c_parts)
                    else:
                        refined_parts.append(sp)
                else:
                    refined_parts.append(sp)

            if len(refined_parts) > 1:
                for i, p in enumerate(refined_parts):
                    is_last = (i == len(refined_parts) - 1)
                    phrases.append(('sentence' if is_last else 'clause', p))
            else:
                phrases.append(('sentence', sent))

        return phrases

    def _parse_speech_and_laugh_segments(self, raw_text: str):
        if not raw_text:
            return []

        # 1. Заменяем явные маркеры смеха (*хихикает*, *смеется* и т.д.) на токен смеха ДО clean_voice_text,
        # так как clean_voice_text иначе вырежет их как сценические ремарки в звездочках.
        marked = LAUGH_REGEX.sub(" @@@AKIRALAUGH@@@ ", raw_text)

        # 2. Автоматически добавляем смех перед шутливыми фразами («Шучу», «Пошутила» и т.п.)
        joke_pattern = re.compile(r'(?:(?<=[.!?…—–\n])\s*|\b|^)([Шш]учу\b|[Пп]ошутила\b|[Шш]утка\b)')
        marked = joke_pattern.sub(r' @@@AKIRALAUGH@@@ \1', marked)

        # 3. Схлопываем идущие подряд токены смеха в один
        marked = re.sub(r'(?:\s*@@@AKIRALAUGH@@@\s*)+', ' @@@AKIRALAUGH@@@ ', marked).strip()

        # 4. Вырезаем любые оставшиеся действия/ремарки (*улыбается*, [вздыхает]), не связанные со смехом
        marked = NON_LAUGH_ACTION_REGEX.sub(" ", marked)

        tokens = marked.split("@@@AKIRALAUGH@@@")
        raw_items = []
        for idx, token in enumerate(tokens):
            clean_tok = clean_voice_text(token).strip()
            clean_tok = re.sub(r'^[,\s!?:;.\-]+', '', clean_tok).strip()
            if clean_tok:
                # Разбиваем текст на фразы и предложения с естественными границами
                phrases = self._split_into_speech_phrases(clean_tok)
                for p_type, p_text in phrases:
                    is_clause = (p_type == 'clause')
                    cleaned_p = self._clean_text_for_tts(p_text, is_clause=is_clause)
                    if cleaned_p and re.search(r'[a-zа-яё0-9]', cleaned_p):
                        raw_items.append((p_type, cleaned_p))
            if idx < len(tokens) - 1:
                raw_items.append(('laugh', None))

        # Убираем дублирование смеха подряд
        items = []
        for itype, ival in raw_items:
            if itype == 'laugh' and items and items[-1][0] == 'laugh':
                continue
            items.append((itype, ival))
        return items

    def _play_stream(self, voice, raw_text, is_whisper=False):
        vol_factor = self._get_volume_factor(is_whisper=is_whisper)
        sample_rate = voice.config.sample_rate

        ym_manager.duck()
        self.speaking_started.emit()

        segments = self._parse_speech_and_laugh_segments(raw_text)
        if not segments:
            cleaned = self._clean_text_for_tts(raw_text)
            if cleaned and re.search(r'[a-zа-яё0-9]', cleaned):
                segments = [('sentence', cleaned)]

        # Естественные паузы:
        # Между завершенными предложениями (.!?) — ~350 мс
        sentence_pause_bytes = np.zeros(int(sample_rate * 0.35), dtype=np.int16).tobytes()
        # Между частями сложного предложения (clauses) — связующая микропауза ~150 мс
        clause_pause_bytes = np.zeros(int(sample_rate * 0.15), dtype=np.int16).tobytes()
        laugh_pause_bytes = np.zeros(int(sample_rate * 0.20), dtype=np.int16).tobytes()
        silence_padding = np.zeros(int(sample_rate * 0.15), dtype=np.int16).tobytes()

        syn_config = self._get_synthesis_config(is_whisper=is_whisper)

        audio_queue = queue.Queue(maxsize=300)
        self._audio_queue = audio_queue

        def producer():
            for idx, (seg_type, seg_content) in enumerate(segments):
                if self._stopped:
                    break

                if seg_type == 'laugh':
                    laugh_chunk = get_random_laugh_bytes(sample_rate)
                    if laugh_chunk:
                        # Небольшая пауза перед смехом, если перед ним была речь
                        if idx > 0 and segments[idx - 1][0] in ('sentence', 'clause'):
                            audio_queue.put(laugh_pause_bytes)
                        audio_queue.put(laugh_chunk)
                        # Пауза после смеха перед последующей речью
                        if idx < len(segments) - 1 and segments[idx + 1][0] in ('sentence', 'clause'):
                            audio_queue.put(laugh_pause_bytes)
                else:
                    phrase_text = seg_content
                    for chunk in voice.synthesize(phrase_text, syn_config=syn_config):
                        if self._stopped:
                            break
                        chunk_bytes = chunk.audio_int16_bytes
                        if chunk_bytes:
                            audio_queue.put(chunk_bytes)

                    if idx < len(segments) - 1 and not self._stopped:
                        if seg_type == 'clause':
                            audio_queue.put(clause_pause_bytes)
                        else:
                            audio_queue.put(sentence_pause_bytes)

            audio_queue.put(None)

        producer_thread = threading.Thread(target=producer, daemon=True)
        producer_thread.start()

        try:
            with sd.RawOutputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
                while not self._stopped:
                    try:
                        chunk_bytes = audio_queue.get(timeout=0.06)
                    except queue.Empty:
                        if not producer_thread.is_alive():
                            break
                        continue

                    if chunk_bytes is None or self._stopped:
                        break

                    if abs(vol_factor - 1.0) > 0.01:
                        data_np = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)
                        scaled_bytes = (data_np * vol_factor).astype(np.int16).tobytes()
                        stream.write(scaled_bytes)
                    else:
                        stream.write(chunk_bytes)

                if not self._stopped:
                    stream.write(silence_padding)
        finally:
            self._audio_queue = None
            ym_manager.unduck()
            self.speaking_finished.emit()

    def stop(self):
        self._stopped = True
        if self._audio_queue:
            try:
                while not self._audio_queue.empty():
                    self._audio_queue.get_nowait()
                self._audio_queue.put(None)
            except Exception:
                pass

        ym_manager.unduck()
        if self.isRunning():
            self.wait(1200)

    def start_warmup(self, greeting_text=None, phrase=None, is_whisper=False):
        self.stop()
        self._is_warmup = True
        self._play_cached_flag = False
        self.is_whisper = is_whisper
        if phrase:
            self.warmup_text = phrase
        if greeting_text:
            self.greeting_to_precache = greeting_text
        self.start()

    def play_cached_greeting(self):
        if self.cached_greeting_audio is not None:
            self.stop()
            self._stopped = False
            self._is_warmup = False
            self._play_cached_flag = True
            self.start()
        else:
            self.say(self.greeting_to_precache if self.greeting_to_precache else "Привет!")

    def say(self, text, is_whisper=False, speaker=None):
        self.stop()
        self._is_warmup = False
        self._play_cached_flag = False
        self.text_to_speak = text
        self.is_whisper = is_whisper
        self.start()

    def run(self):
        self._stopped = False
        try:
            if self.main_voice is None or self.whisper_voice is None:
                self._init_models()

            if self._is_warmup:
                if self._stopped:
                    return
                cleaned_warmup = self._clean_text_for_tts(self.warmup_text)
                syn_cfg = self._get_synthesis_config(is_whisper=self.is_whisper)
                for v in (self.main_voice, self.whisper_voice):
                    if self._stopped:
                        return
                    if v and cleaned_warmup:
                        for _ in v.synthesize(cleaned_warmup, syn_config=syn_cfg):
                            break

                if self.greeting_to_precache and not self._stopped:
                    cleaned_greeting = self._clean_text_for_tts(self.greeting_to_precache)
                    target_voice = self.whisper_voice if (self.is_whisper and self.whisper_voice) else self.main_voice

                    if target_voice and cleaned_greeting:
                        target_sr = target_voice.config.sample_rate
                        greeting_phrases = self._split_into_speech_phrases(self.greeting_to_precache)
                        if not greeting_phrases:
                            greeting_phrases = [('sentence', cleaned_greeting)]

                        audio_parts = []
                        sent_pause_np = np.zeros(int(target_sr * 0.35), dtype=np.float32)
                        clause_pause_np = np.zeros(int(target_sr * 0.15), dtype=np.float32)
                        vol_factor = self._get_volume_factor(is_whisper=self.is_whisper)

                        for g_idx, (g_type, g_sent) in enumerate(greeting_phrases):
                            if self._stopped:
                                return
                            cleaned_g = self._clean_text_for_tts(g_sent, is_clause=(g_type == 'clause'))
                            if not cleaned_g:
                                continue
                            g_chunks = b"".join(c.audio_int16_bytes for c in target_voice.synthesize(cleaned_g, syn_config=syn_cfg))
                            if g_chunks:
                                part_np = np.frombuffer(g_chunks, dtype=np.int16).astype(np.float32) / 32768.0
                                audio_parts.append(part_np * vol_factor)
                                if g_idx < len(greeting_phrases) - 1:
                                    audio_parts.append(clause_pause_np if g_type == 'clause' else sent_pause_np)

                        if audio_parts:
                            padding = np.zeros(int(target_sr * 0.15), dtype=np.float32)
                            self.cached_greeting_audio = np.concatenate(audio_parts + [padding]).astype(np.float32)
                            self.cached_greeting_sr = target_sr

                self.warmup_finished.emit()
                return

            if self._play_cached_flag:
                self._play_cached_flag = False
                if self.cached_greeting_audio is not None and not self._stopped:
                    ym_manager.duck()
                    self.speaking_started.emit()
                    sd.play(self.cached_greeting_audio, self.cached_greeting_sr)
                    while sd.get_stream() and sd.get_stream().active:
                        if self._stopped:
                            sd.stop()
                            break
                        sd.sleep(40)
                    ym_manager.unduck()
                    self.speaking_finished.emit()
                return

            raw_text = self.text_to_speak
            if not raw_text or self._stopped:
                return

            target_voice = self.whisper_voice if (self.is_whisper and self.whisper_voice) else self.main_voice
            if not target_voice:
                return

            self._play_stream(target_voice, raw_text, is_whisper=self.is_whisper)

        except Exception as e:
            print(f"[TTS Stream Error]: {e}")
            self.error_occurred.emit(str(e))
            if self._is_warmup:
                self.warmup_finished.emit()
        finally:
            if not self._is_warmup and not self._play_cached_flag:
                ym_manager.unduck()