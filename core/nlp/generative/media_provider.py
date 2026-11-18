"""
core/nlp/generative/media_provider.py
Сервис генерации изображений и музыки через API RouterAI:
- Модель изображений: google/gemini-nano-banana-2.1 (Text-to-Image, Image-to-Image)
- Модель музыки: google/lyria-3-pro-preview (48kHz стерео, генерация по тексту и визуальному референсу)
"""

import os
import sys
import time
import base64
import json
import re
from datetime import datetime
import requests

from core.utils.config import load_config, get_user_data_path

ROUTERAI_BASE_URL = "https://routerai.ru/api/v1"
IMAGE_MODEL = "google/gemini-nano-banana-2.1"
MUSIC_MODEL = "google/lyria-3-pro-preview"


class MediaProvider:
    """Провайдер генерации медиаконтента (изображения и аудио) через шлюз RouterAI."""

    def __init__(self):
        self.base_url = ROUTERAI_BASE_URL.rstrip("/")

    def _get_api_key(self) -> str:
        cfg = load_config()
        api_keys = cfg.get("api_keys", {})
        key = api_keys.get("routerai", "").strip() or api_keys.get("openrouter", "").strip()
        return key

    def is_available(self) -> bool:
        """Проверяет, подключен ли рабочий ключ RouterAI или OpenRouter."""
        return bool(self._get_api_key())

    def _get_storage_dirs(self) -> tuple[str, str]:
        img_dir = get_user_data_path("generated", "images")
        aud_dir = get_user_data_path("generated", "audio")
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(aud_dir, exist_ok=True)
        return img_dir, aud_dir

    def _encode_image_file(self, file_path: str) -> str:
        """Кодирует файл изображения в Data URI: data:image/...;base64,..."""
        if not file_path or not os.path.exists(file_path):
            return ""
        ext = os.path.splitext(file_path)[1].lower()
        mime = "image/png"
        if ext in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif ext == ".webp":
            mime = "image/webp"
        elif ext == ".gif":
            mime = "image/gif"

        try:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            print(f"[MediaProvider Encode Error]: {e}", flush=True)
            return ""

    def generate_image(self, prompt: str, ref_image_path: str | None = None) -> str:
        """
        Генерация изображения по текстовому промпту (и опциональному референсу).
        Возвращает путь к сохраненному локальному файлу (PNG).
        """
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("Подключи ключ RouterAI в настройках Акиры, чтобы генерировать изображения.")

        clean_prompt = (prompt or "").strip()
        if not clean_prompt and not ref_image_path:
            raise ValueError("Опиши, что нарисовать.")

        img_dir, _ = self._get_storage_dirs()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_filename = f"img_{timestamp}.png"
        target_path = os.path.join(img_dir, target_filename)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/RaccoonKa/Akira",
            "X-Title": "Akira Desktop Studio"
        }

        # 1. Попытка через мультимодальный /chat/completions (нативный для моделей Gemini Nano Banana)
        messages_content = []
        if clean_prompt:
            messages_content.append({"type": "text", "text": clean_prompt})

        if ref_image_path and os.path.exists(ref_image_path):
            data_uri = self._encode_image_file(ref_image_path)
            if data_uri:
                messages_content.append({"type": "image_url", "image_url": {"url": data_uri}})

        chat_payload = {
            "model": IMAGE_MODEL,
            "messages": [{"role": "user", "content": messages_content}],
            "modalities": ["image", "text"]
        }

        chat_url = f"{self.base_url}/chat/completions"
        try:
            resp = requests.post(chat_url, headers=headers, json=chat_payload, timeout=90)
            if resp.status_code == 200:
                data = resp.json()
                saved = self._extract_and_save_image(data, target_path)
                if saved:
                    return target_path
        except Exception as e:
            print(f"[MediaProvider Chat Endpoint Warn]: {e}, пробую эндпоинт /images...", flush=True)

        # 2. Фолбек через эндпоинт /images (стандарт OpenAI Images)
        images_url = f"{self.base_url}/images"
        images_payload = {
            "model": IMAGE_MODEL,
            "prompt": clean_prompt,
            "n": 1,
            "response_format": "b64_json"
        }
        resp = requests.post(images_url, headers=headers, json=images_payload, timeout=90)
        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_json = resp.json()
                err_msg = err_json.get("error", {}).get("message", err_msg)
            except Exception:
                pass
            raise RuntimeError(f"Ошибка генерации изображения ({resp.status_code}): {err_msg}")

        data = resp.json()
        saved = self._extract_and_save_image(data, target_path)
        if not saved:
            raise RuntimeError("API не вернуло данных изображения.")

        return target_path

    def _extract_and_save_image(self, data: dict, target_path: str) -> bool:
        """Извлекает base64 или URL изображения из структуры ответа и сохраняет на диск."""
        # А: data: [ { b64_json / url } ]
        items = data.get("data", [])
        if items and isinstance(items, list):
            first = items[0]
            if "b64_json" in first and first["b64_json"]:
                raw_bytes = base64.b64decode(first["b64_json"])
                with open(target_path, "wb") as f:
                    f.write(raw_bytes)
                return True
            if "url" in first and first["url"]:
                img_resp = requests.get(first["url"], timeout=30)
                if img_resp.status_code == 200:
                    with open(target_path, "wb") as f:
                        f.write(img_resp.content)
                    return True

        # Б: choices / candidates parts (inline_data или data_uri в тексте)
        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            content = msg.get("content", "")
            # Ищем data:image/...;base64,...
            match = re.search(r'data:image/[a-zA-Z]+;base64,([A-Za-z0-9+/=]+)', str(content))
            if match:
                raw_bytes = base64.b64decode(match.group(1))
                with open(target_path, "wb") as f:
                    f.write(raw_bytes)
                return True

            # Ищем прямой URL на картинку в ответе
            url_match = re.search(r'https?://\S+\.(?:png|jpg|jpeg|webp)', str(content))
            if url_match:
                img_resp = requests.get(url_match.group(0), timeout=30)
                if img_resp.status_code == 200:
                    with open(target_path, "wb") as f:
                        f.write(img_resp.content)
                    return True

            # Проверяем вложения / media блоки
            media = msg.get("media", []) or msg.get("images", [])
            if media and isinstance(media, list):
                m0 = media[0]
                if isinstance(m0, str) and len(m0) > 100:
                    raw_bytes = base64.b64decode(m0)
                    with open(target_path, "wb") as f:
                        f.write(raw_bytes)
                    return True

        return False

    def generate_music(self, prompt: str, ref_image_path: str | None = None) -> str:
        """
        Генерация музыки и песен через Google Lyria 3 Pro Preview (48kHz стерео).
        Возвращает путь к сохраненному локальному файлу (MP3).
        """
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("Подключи ключ RouterAI в настройках Акиры, чтобы сочинять музыку.")

        clean_prompt = (prompt or "").strip()
        if not clean_prompt and not ref_image_path:
            raise ValueError("Опиши стиль, жанр или настроение трека.")

        _, aud_dir = self._get_storage_dirs()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_filename = f"track_{timestamp}.mp3"
        target_path = os.path.join(aud_dir, target_filename)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/RaccoonKa/Akira",
            "X-Title": "Akira Desktop Studio"
        }

        messages_content = []
        if clean_prompt:
            messages_content.append({"type": "text", "text": clean_prompt})

        if ref_image_path and os.path.exists(ref_image_path):
            data_uri = self._encode_image_file(ref_image_path)
            if data_uri:
                messages_content.append({"type": "image_url", "image_url": {"url": data_uri}})

        payload = {
            "model": MUSIC_MODEL,
            "messages": [{"role": "user", "content": messages_content}],
            "modalities": ["audio", "text"]
        }

        url = f"{self.base_url}/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=140)
        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_json = resp.json()
                err_msg = err_json.get("error", {}).get("message", err_msg)
            except Exception:
                pass
            raise RuntimeError(f"Ошибка генерации музыки ({resp.status_code}): {err_msg}")

        data = resp.json()
        saved = self._extract_and_save_audio(data, target_path)
        if not saved:
            raise RuntimeError("API не вернуло аудиоданных для трека.")

        return target_path

    def _extract_and_save_audio(self, data: dict, target_path: str) -> bool:
        """Извлекает base64 или URL аудио из структуры ответа и сохраняет на диск."""
        # 1. Проверяем output_audio или audio_data
        output_audio = data.get("output_audio") or data.get("audio")
        if output_audio and isinstance(output_audio, dict):
            b64 = output_audio.get("data")
            if b64:
                with open(target_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                return True

        # 2. Проверяем choices message
        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})

            # Аудио в отдельном поле message.audio
            audio_obj = msg.get("audio")
            if audio_obj and isinstance(audio_obj, dict):
                b64 = audio_obj.get("data")
                if b64:
                    with open(target_path, "wb") as f:
                        f.write(base64.b64decode(b64))
                    return True

            content = msg.get("content", "")
            # Ищем data:audio/...;base64,...
            match = re.search(r'data:audio/[a-zA-Z0-9]+;base64,([A-Za-z0-9+/=]+)', str(content))
            if match:
                with open(target_path, "wb") as f:
                    f.write(base64.b64decode(match.group(1)))
                return True

            # Прямой URL на mp3/wav
            url_match = re.search(r'https?://\S+\.(?:mp3|wav|ogg|m4a)', str(content))
            if url_match:
                aud_resp = requests.get(url_match.group(0), timeout=60)
                if aud_resp.status_code == 200:
                    with open(target_path, "wb") as f:
                        f.write(aud_resp.content)
                    return True

            # Проверяем multipart steps / parts
            steps = data.get("steps", [])
            for step in steps:
                for c in step.get("content", []):
                    if c.get("type") in ("audio", "audio/mp3", "audio/mpeg") and c.get("data"):
                        with open(target_path, "wb") as f:
                            f.write(base64.b64decode(c["data"]))
                        return True

        return False


media_provider = MediaProvider()
