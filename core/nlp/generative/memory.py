import os
import re
import json
import threading
from core.utils.config import get_user_data_path


class MemoryManager:
    def __init__(self):
        self.memory_dir = get_user_data_path("memory")
        self.memory_file = os.path.join(self.memory_dir, "user_memory.json")
        self.lock = threading.Lock()
        self._migrate_old_files()
        self.facts = self._load_facts()

    def _migrate_old_files(self):
        """
        Переносит старые файлы user_memory.json из корневой personal_data или configs
        в выделенную папку personal_data/memory/user_memory.json.
        """
        old_candidates = [
            get_user_data_path("user_memory.json"),
            get_user_data_path("configs", "user_memory.json")
        ]
        os.makedirs(self.memory_dir, exist_ok=True)

        for old_path in old_candidates:
            if os.path.exists(old_path) and os.path.abspath(old_path) != os.path.abspath(self.memory_file):
                try:
                    with open(old_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                    old_facts = old_data if isinstance(old_data, list) else old_data.get("facts", [])
                    if old_facts:
                        current_facts = []
                        if os.path.exists(self.memory_file):
                            try:
                                with open(self.memory_file, "r", encoding="utf-8") as cur_f:
                                    cur_data = json.load(cur_f)
                                current_facts = cur_data if isinstance(cur_data, list) else cur_data.get("facts", [])
                            except Exception:
                                current_facts = []

                        # Объединяем без дубликатов
                        for fact in old_facts:
                            if fact and fact not in current_facts:
                                current_facts.append(fact)

                        with open(self.memory_file, "w", encoding="utf-8") as cur_f:
                            json.dump({"facts": current_facts}, cur_f, ensure_ascii=False, indent=4)

                    os.remove(old_path)
                    print(f"[Memory]: Успешная миграция фактов из '{old_path}' -> '{self.memory_file}'")
                except Exception as e:
                    print(f"[Memory Migration Warning]: {e}")

    def _load_facts(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_facts = data if isinstance(data, list) else data.get("facts", [])
                    cleaned = []
                    for f in raw_facts:
                        item = str(f or "").strip()
                        if item and item not in cleaned:
                            cleaned.append(item)
                    return cleaned
            except Exception as e:
                print(f"[Memory Load Error]: {e}")
        return []

    def _save_facts(self):
        os.makedirs(self.memory_dir, exist_ok=True)
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump({"facts": self.facts}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[Memory Save Error]: {e}")

    def add_fact(self, fact: str):
        fact = str(fact or "").strip().strip(" .\"'«»*")
        if not fact:
            return

        # Первая буква заглавная для единообразия
        fact = fact[0].upper() + fact[1:]

        with self.lock:
            # Проверка дубликатов без учета регистра
            if not any(f.strip().lower() == fact.lower() for f in self.facts):
                self.facts.append(fact)
                if len(self.facts) > 40:
                    self.facts = self.facts[-40:]
                self._save_facts()

    def clear_memory(self):
        with self.lock:
            self.facts = []
            self._save_facts()

    def get_memory_context(self) -> str:
        with self.lock:
            if not self.facts:
                return ""
            formatted_facts = "\n".join([f"- {fact}" for fact in self.facts])
            return (
                f"\n\nФАКТЫ И ВОСПОМИНАНИЯ О ПОЛЬЗОВАТЕЛЕ (ДОЛГОВРЕМЕННАЯ ПАМЯТЬ):\n"
                f"{formatted_facts}\n"
                f"Используй эти факты естественным образом в общении, если это уместно."
            )

    def extract_facts_async(self, client, model_name: str, user_text: str, assistant_reply: str):
        threading.Thread(
            target=self._extract_worker,
            args=(client, model_name, user_text, assistant_reply),
            daemon=True
        ).start()

    def _extract_worker(self, client, model_name: str, user_text: str, assistant_reply: str):
        if not client or len(user_text.strip()) < 6:
            return

        ignore_prefixes = (
            "включи", "выключи", "поставь", "пауза", "громкость",
            "погода", "запусти", "открой", "найди", "сколько время", "покажи"
        )
        low_text = user_text.lower().strip()
        if low_text.startswith(ignore_prefixes) and "запомни" not in low_text:
            return

        extraction_prompt = (
            "Ты — аналитик диалога. В диалоге участвуют: Пользователь и Ассистент (цифровая девушка по имени Акира, сокращенно Аки).\n"
            "Определи, сообщил ли пользователь в своей реплике личную информацию о себе: "
            "своё имя, стек технологий, увлечения, любимые вещи, привычки, факты о своей жизни или своё личное отношение к Акире.\n\n"
            "ПРАВИЛА:\n"
            "1. Если пользователь просто задал вопрос, пошутил или поддержал разговор ни о чём — напиши ровно одно слово: НИЧЕГО\n"
            "2. Если есть реальный факт о пользователе — сформулируй его кратко от 3-го лица в одно предложение (например: 'Пользователь пишет код на Python').\n"
            "3. ОТНОШЕНИЕ К АКИРЕ (АССИСТЕНТУ): Акира (Аки) — это сам собеседник-ассистент, а НЕ сторонняя персона! "
            "Если пользователь называет Акиру 'любимая', 'моя хорошая', признается ей в любви или выражает теплые чувства ('моя любимая, Аки', 'я тебя люблю') — "
            "записывай факт как отношение пользователя к ассистенту: 'Пользователь тепло любит Акиру и считает её своей любимой'. "
            "СТРОГО ЗАПРЕЩЕНО писать 'любимая пользователя — Аки' или говорить об Акире как о постороннем третьем лице или предмете!\n"
            "4. Не пиши вступительных слов, только сам факт или НИЧЕГО.\n\n"
            f"Реплика пользователя: {user_text}\n"
            f"Ответ ассистента: {assistant_reply}\n\n"
            "Результат:"
        )

        try:
            raw_content = ""

            # Ветка 1: GigaChat
            if hasattr(client, "chat") and callable(client.chat):
                res = client.chat({
                    "model": model_name if model_name else "GigaChat",
                    "messages": [{"role": "user", "content": extraction_prompt}]
                })
                if res and getattr(res, "choices", None):
                    raw_content = getattr(res.choices[0].message, "content", "")

            # Ветка 2: RouterAI / OpenAI
            elif hasattr(client, "chat") and hasattr(client.chat, "completions"):
                target_model = model_name if ("/" in model_name or ":" in model_name) else "deepseek/deepseek-v4.1-flash"
                response = client.chat.completions.create(
                    model=target_model,
                    messages=[{"role": "user", "content": extraction_prompt}],
                    temperature=0.2,
                    max_tokens=150
                )
                if response and getattr(response, "choices", None):
                    choice = response.choices[0]
                    raw_content = getattr(choice.message, "content", None)
                    if not raw_content:
                        raw_content = getattr(choice.message, "reasoning", "")

            result = str(raw_content or "").strip()
            clean_res = re.sub(r'^(?:результат|факт):\s*', '', result, flags=re.IGNORECASE).strip(" .\"'«»*\n\r")
            upper_clean = clean_res.upper()

            negative_markers = [
                "НИЧЕГО", "НЕТ", "ФАКТОВ НЕТ", "НЕТ НОВОЙ", "НЕТ ФАКТОВ",
                "НИКАКИХ ФАКТОВ", "ИНФОРМАЦИИ НЕТ", "НЕТ ИНФОРМАЦИИ",
                "ЛИЧНОЙ ИНФОРМАЦИИ НЕТ", "ПОЛЬЗОВАТЕЛЬ НЕ СООБЩИЛ",
                "ПОЛЬЗОВАТЕЛЬ НЕ УПОМЯНУЛ", "НЕ СОДЕРЖИТ", "НЕ ОБНАРУЖЕНО"
            ]

            is_negative = any(m in upper_clean for m in negative_markers) or upper_clean.startswith("НЕТ")

            if clean_res and not is_negative:
                if 5 <= len(clean_res) <= 140:
                    print(f"[Memory]: Новый факт в копилку -> '{clean_res}'", flush=True)
                    self.add_fact(clean_res)

        except Exception as e:
            print(f"[Memory Extract Warning]: {e}", flush=True)
