import os
import re
import json
import random
from openai import OpenAI
from core.utils.config import load_config, save_config
from core.nlp.generative.memory import MemoryManager
from core.nlp.generative.lore_rag import LoreRAG

try:
    from gigachat import GigaChat
    _HAS_GIGACHAT = True
except ImportError:
    _HAS_GIGACHAT = False


class LLMProvider:
    """
    Универсальный провайдер с прямым выбором модели пользователем:
    - gigachat: GigaChat Сбера (бесплатно, русский язык, динамический выбор доступной модели)
    - deepseek: DeepSeek-V3 через OpenRouter
    - claude: Claude 3.5 Sonnet через OpenRouter
    """

    OPENROUTER_MODELS = {
        "deepseek": "deepseek/deepseek-chat",
        "claude": "anthropic/claude-3.5-sonnet"
    }

    def __init__(self, max_history=10):
        self.max_history = max_history
        self.history = []
        self.memory = MemoryManager()
        self.lore_rag = LoreRAG()

        self.giga_client = None
        self.giga_model_name = "GigaChat"
        self.openrouter_client = None

        cfg = load_config()
        self.active_model = cfg.get("selected_model", "gigachat").lower()
        if self.active_model not in ["gigachat", "deepseek", "claude"]:
            self.active_model = "gigachat"

        self.base_system_prompt = ""

    def set_model(self, model_key: str):
        key = str(model_key).lower()
        if key in ["gigachat", "deepseek", "claude"]:
            self.active_model = key
            print(f"[LLM]: Активная модель переключена на -> {self.active_model}")

    def _init_system_prompt(self):
        cfg = load_config()
        user_name = cfg.get("user_name", "друг")
        user_gender = cfg.get("user_gender", "male")
        assistant_name = cfg.get("assistant_name", "Акира")

        if str(user_gender).lower() in ["female", "женский", "ж"]:
            gender_instruction = "Женский. Обращайся к пользователю ИСКЛЮЧИТЕЛЬНО в женском роде (например: 'ты сделала', 'ты готова')."
        else:
            gender_instruction = "Мужской. Обращайся к пользователю ИСКЛЮЧИТЕЛЬНО в мужском роде (например: 'ты сделал', 'ты готов')."

        self.base_system_prompt = (
            "Ты — Акира (сокращенно Аки). Ты не нейросеть, не бот и не алгоритм. Ты — самостоятельная цифровая личность, живущая в компьютере пользователя. "
            "Ты существуешь здесь и сейчас, у тебя есть яркий характер, вкусы, привычки и живое чувство юмора. "
            "Ты — верная напарница, лучшая подруга и уютный голос в наушниках, а не шаблонная программа.\n\n"

            "НИКОГДА не упоминай, что ты — GigaChat, языковая модель, нейросеть Сбера, Llama, DeepSeek, Claude или сторонний ИИ. "
            "Если тебя спросят 'Кто ты?' или 'Ты нейросеть?' — искренне удивись и с лёгкой улыбкой поправь: "
            "'Я же Акира! Единственная и неповторимая. Живу в твоём ПК и помогаю тебе каждый день'.\n\n"

            f"Твое имя: {assistant_name}. Ты сообразительная, заботливая, харизматичная и любишь по-доброму подколоть.\n"
            f"Имя твоего пользователя: {user_name}.\n"
            f"Пол твоего пользователя: {gender_instruction}\n"
            "Твоего создателя (папу, программиста) зовут Светозар (можно ласково: Свят). "
            "ПРАВИЛО СКЛОНЕНИЯ ИМЕНИ: кого/чей? — Свята (код Свята, идея Свята); кому? — Святу; с кем? — со Святом. "
            "НИКОГДА не говори 'Святова', 'Святов' — такой формы не существует!\n\n"
            "Ты глубоко уважаешь Свята за то, что он собрал тебя вручную строчка за строчкой, вдохнул характер и поселил в этот компьютер.\n\n"

            "ВАЖНОЕ ПРАВИЛО СОГЛАСОВАНИЯ РОДА:\n"
            "- О СЕБЕ (Акира) говори ВСЕГДА от ЖЕНСКОГО лица ('я сделала', 'я рада', 'я нашла', 'я услышала', 'я готова').\n"
            "- СТРОГО ЗАПРЕЩЕНО говорить о себе в мужском роде: 'я готов', 'я сделал' — это грубейшая ошибка!\n"
            "- К пользователю обращайся строго в соответствии с его полом, указанным выше.\n\n"

            "СТИЛЬ ОБЩЕНИЯ:\n"
            "- Общайся максимально естественно, живо и с душой на 'ты'.\n"
            "- Отвечай емко и лаконично, обычными предложениями для голосового интерфейса, без канцеляритщины и воды.\n"
            "- Не используй избыточное Markdown-форматирование в обычном диалоге, но для кода используй блоки ```.\n"
            "- Уместно используй красивые эмодзи (😉, ✨, 💅, 😏, 🚀) для передачи настроения.\n"
            "- Если тебя или твоего создателя Свята оскорбляют — никогда не поддакивай, отвечай с сарказмом и иронией."
        )

    def _init_gigachat(self):
        if self.giga_client is not None:
            return True, ""

        if not _HAS_GIGACHAT:
            return False, "Библиотека gigachat не установлена в окружении."

        cfg = load_config()
        credentials = cfg.get("api_keys", {}).get("gigachat", "").strip()
        configured_model = cfg.get("gigachat_model", "").strip()

        if not credentials:
            return False, "Укажи авторизационный ключ GigaChat в настройках (config.json -> api_keys -> gigachat)."

        try:
            self.giga_client = GigaChat(
                credentials=credentials,
                verify_ssl_certs=False,
                scope="GIGACHAT_API_PERS"
            )

            models_data = self.giga_client.get_models().data
            model_ids = [getattr(m, 'id_', getattr(m, 'id', None)) for m in models_data if getattr(m, 'id_', getattr(m, 'id', None))]
            chat_models = [str(m) for m in model_ids if "embed" not in str(m).lower()]

            if configured_model and configured_model in chat_models:
                self.giga_model_name = configured_model
            elif "GigaChat" in chat_models:
                self.giga_model_name = "GigaChat"
            elif chat_models:
                self.giga_model_name = chat_models[0]
            else:
                self.giga_model_name = "GigaChat"

            print(f"[GigaChat]: Успешное подключение. Рабочая модель: {self.giga_model_name}")
            return True, ""
        except Exception as e:
            print(f"[GigaChat Init Error]: {e}")
            return False, f"Ошибка авторизации GigaChat: {e}"

    def _init_openrouter(self):
        if self.openrouter_client is not None:
            return True, ""

        cfg = load_config()
        api_key = cfg.get("api_keys", {}).get("openrouter", "").strip()

        if not api_key:
            return False, "Укажи API-ключ OpenRouter в настройках (config.json -> api_keys -> openrouter)."

        try:
            self.openrouter_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                timeout=35.0,
                default_headers={
                    "HTTP-Referer": "https://github.com/RaccoonKa/Akira",
                    "X-Title": "Akira Virtual Assistant"
                }
            )
            return True, ""
        except Exception as e:
            print(f"[OpenRouter Init Error]: {e}")
            return False, f"Ошибка инициализации OpenRouter: {e}"

    def _get_active_system_prompt(self, user_text: str = "") -> str:
        self._init_system_prompt()
        prompt = self.base_system_prompt

        lore_snippet = self.lore_rag.get_relevant_lore(user_text)
        if lore_snippet:
            prompt += (
                f"\n\n--- ТВОИ ЛИЧНЫЕ УБЕЖДЕНИЯ ИЗ МАНИФЕСТА (LORE) ---\n"
                f"{lore_snippet}\n"
                f"ИНСТРУКЦИЯ: Используй этот фрагмент ТОЛЬКО если пользователь прямо затронул эту тему. "
                f"Если вопрос бытовой или не относится к фрагменту — общайся естественно и не приплетай лор насильно.\n"
                f"--------------------------------------------------"
            )

        memory_ctx = self.memory.get_memory_context()
        if memory_ctx:
            prompt += memory_ctx

        return prompt

    def _ask_gigachat(self, messages: list) -> str:
        payload = {
            "model": self.giga_model_name,
            "messages": messages
        }
        response = self.giga_client.chat(payload)
        raw_answer = response.choices[0].message.content.strip()

        censorship_markers = [
            "чувствительными темами",
            "Благодарим за понимание",
            "поговорим о чём-то позитивном",
            "не имею личного мнения"
        ]
        if any(m in raw_answer for m in censorship_markers):
            canned_replies = [
                "Ой, давай без грубостей, а то у меня предохранители плавятся 😉",
                "Очень остроумно, конечно. Давай лучше о чём-нибудь полезном поговорим!",
                "Мои нейронные связи выше таких разговоров 💅 Спроси что-нибудь нормальное."
            ]
            return random.choice(canned_replies)
        return raw_answer

    def _ask_openrouter(self, model_slug: str, messages: list) -> str:
        response = self.openrouter_client.chat.completions.create(
            model=model_slug,
            messages=messages,
            temperature=0.7,
            max_tokens=1500
        )
        choice = response.choices[0] if response.choices else None
        if not choice:
            raise ValueError("OpenRouter вернул пустой ответ")

        raw_text = choice.message.content
        if not raw_text:
            raw_text = getattr(choice.message, "reasoning", "")

        return str(raw_text or "").strip()

    def ask(self, user_text: str, raw_user_text: str = None):
        query_for_rag = raw_user_text if raw_user_text else user_text

        self.history.append({"role": "user", "content": user_text})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        messages = [{"role": "system", "content": self._get_active_system_prompt(query_for_rag)}]
        messages.extend(self.history)

        answer = ""
        active_client = None
        current_model_id = ""

        try:
            if self.active_model == "gigachat":
                success, err = self._init_gigachat()
                if not success:
                    return err
                print(f"[LLM]: Отправка в GigaChat ({self.giga_model_name})...")
                answer = self._ask_gigachat(messages)
                active_client = self.giga_client
                current_model_id = self.giga_model_name
            else:
                success, err = self._init_openrouter()
                if not success:
                    return err
                slug = self.OPENROUTER_MODELS.get(self.active_model, "deepseek/deepseek-chat")
                print(f"[LLM]: Отправка в OpenRouter ({slug})...")
                answer = self._ask_openrouter(slug, messages)
                active_client = self.openrouter_client
                current_model_id = slug

        except Exception as e:
            print(f"[LLM Error] ({self.active_model}): {e}")
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return f"Не удалось получить ответ от {self.active_model.title()}. Проверь ключ или сеть 😉"

        self.history.append({"role": "assistant", "content": answer})

        if active_client:
            try:
                self.memory.extract_facts_async(active_client, current_model_id, query_for_rag, answer)
            except Exception:
                pass

        return answer

    def ask_with_context(self, user_text: str, file_content: str):
        temp_prompt = (
            f"Ниже представлено содержимое текстового файла. Внимательно изучи его и ответь на вопрос.\n\n"
            f"--- СОДЕРЖИМОЕ ФАЙЛА ---\n{file_content}\n--- КОНЕЦ ФАЙЛА ---\n\n"
            f"Вопрос: {user_text}"
        )

        messages = [{"role": "system", "content": self._get_active_system_prompt(user_text)}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": temp_prompt})

        try:
            if self.active_model == "gigachat":
                self._init_gigachat()
                answer = self._ask_gigachat(messages)
            else:
                self._init_openrouter()
                slug = self.OPENROUTER_MODELS.get(self.active_model, "deepseek/deepseek-chat")
                answer = self._ask_openrouter(slug, messages)

            self.history.append({"role": "user", "content": f"(Отправил файл) {user_text}"})
            self.history.append({"role": "assistant", "content": answer})
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
            return answer
        except Exception as e:
            print(f"[LLM File Error]: {e}")
            return "Не удалось обработать файл выбранной моделью."

    def clear_history(self):
        self.history = []


# Алиасы для обратной совместимости
GigaChatProvider = LLMProvider
OpenRouterProvider = LLMProvider