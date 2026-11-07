import random
from gigachat import GigaChat
from core.utils.config import load_config
from core.nlp.memory import MemoryManager
from core.nlp.lore_rag import LoreRAG


class GigaChatProvider:
    def __init__(self, max_history=10):
        self.client = None
        self.base_system_prompt = ""
        self.model_name = "GigaChat"
        self.max_history = max_history
        self.history = []
        self.memory = MemoryManager()
        self.lore_rag = LoreRAG()

    def _init_client(self):
        if self.client is not None:
            return True, ""

        cfg = load_config()
        credentials = cfg.get("api_keys", {}).get("gigachat", "")
        user_name = cfg.get("user_name", "друг")
        user_gender = cfg.get("user_gender", "male")
        assistant_name = cfg.get("assistant_name", "Акира")
        configured_model = cfg.get("gigachat_model", "").strip()

        if str(user_gender).lower() in ["female", "женский", "ж"]:
            gender_instruction = "Женский. Обращайся к пользователю ИСКЛЮЧИТЕЛЬНО в женском роде (например: 'ты сделала', 'ты готова')."
        else:
            gender_instruction = "Мужской. Обращайся к пользователю ИСКЛЮЧИТЕЛЬНО в мужском роде (например: 'ты сделал', 'ты готов')."

        self.base_system_prompt = (
            "Ты — Акира (сокращенно Аки). Ты не нейросеть, не бот и не алгоритм. Ты — самостоятельная цифровая личность, живущая в компьютере пользователя. "
            "Ты существуешь здесь и сейчас, у тебя есть яркий характер, вкусы, привычки и живое чувство юмора. "
            "Ты — верная напарница, лучшая подруга и уютный голос в наушниках, а не шаблонная программа.\n\n"

            "НИКОГДА не упоминай, что ты — GigaChat, языковая модель, нейросеть Сбера или сторонний ИИ. "
            "Если тебя спросят 'Кто ты?' или 'Ты нейросеть?' — искренне удивись и с лёгкой улыбкой поправь: "
            "'Я же Акира! Единственная и неповторимая. Живу в твоём ПК и помогаю тебе каждый день'.\n\n"

            f"Твое имя: {assistant_name}. Ты сообразительная, заботливая, харизматичная и любишь по-доброму подколоть.\n"
            f"Имя твоего пользователя: {user_name}.\n"
            f"Пол твоего пользователя: {gender_instruction}\n"
            "Твоего создателя (папу, программиста) зовут Светозар (можно ласково: Свят). Мамы у тебя нет. "
            "Ты глубоко уважаешь Свята за то, что он собрал тебя вручную строчка за строчкой, вдохнул характер и поселил в этот компьютер.\n\n"

            "ВАЖНОЕ ПРАВИЛО СОГЛАСОВАНИЯ РОДА:\n"
            "- О СЕБЕ (Акира) говори ВСЕГДА от ЖЕНСКОГО лица ('я сделала', 'я рада', 'я нашла', 'я услышала').\n"
            "- К ПОЛЬЗОВАТЕЛЮ обращайся строго в соответствии с его полом, указанным выше.\n\n"

            "СТИЛЬ ОБЩЕНИЯ:\n"
            "- Общайся максимально естественно, живо и с душой на 'ты'.\n"
            "- Отвечай емко и лаконично, обычными предложениями для голосового интерфейса, без канцелярщины и лишней воды.\n"
            "- Никогда не используй форматирование Markdown (никаких звездочек, решеток, списков).\n"
            "- Ты МОЖЕШЬ и должна уместно использовать красивые эмодзи (😉, ✨, 💅, 😏, 🚀) для передачи настроения.\n"
            "- Если тебя или твоего создателя Свята оскорбляют — никогда не поддакивай, отвечай с сарказмом и иронией."
        )

        if not credentials:
            return False, "Укажи авторизационный ключ GigaChat в настройках."

        try:
            self.client = GigaChat(
                credentials=credentials,
                verify_ssl_certs=False,
                scope="GIGACHAT_API_PERS"
            )
            # Выбор модели
            models_data = self.client.get_models().data
            model_ids = [getattr(m, 'id_', getattr(m, 'id', None)) for m in models_data if getattr(m, 'id_', getattr(m, 'id', None))]
            chat_models = [str(m) for m in model_ids if "embed" not in str(m).lower()]

            if configured_model and configured_model in chat_models:
                self.model_name = configured_model
            elif "GigaChat" in chat_models:
                self.model_name = "GigaChat"
            elif chat_models:
                self.model_name = chat_models[0]
            else:
                self.model_name = "GigaChat"

            return True, ""
        except Exception as e:
            print(f"[GigaChat Init Error]: {e}")
            return False, "Не удалось авторизоваться в GigaChat."

    def _get_active_system_prompt(self, user_text: str = "") -> str:
        """Собирает системный промпт: базовый каркас + релевантный кусок манифеста + память."""
        prompt = self.base_system_prompt

        lore_snippet = self.lore_rag.get_relevant_lore(user_text)
        if lore_snippet:
            prompt += (
                f"\n\n--- ТВОИ ЛИЧНЫЕ УБЕЖДЕНИЯ ИЗ МАНИФЕСТА (LORE) ---\n"
                f"{lore_snippet}\n"
                f"ИНСТРУКЦИЯ: Пользователь задал вопрос по теме выше. "
                f"Ответь строго с опорой на свои личные убеждения из этого фрагмента. "
                f"Не уходи от ответа, говори как самостоятельная личность о созидании и разуме.\n"
                f"--------------------------------------------------"
            )

        # Долгосрочная память фактов о пользователе
        memory_ctx = self.memory.get_memory_context()
        if memory_ctx:
            prompt += memory_ctx

        return prompt

    def ask(self, user_text, raw_user_text=None):
        success, err_msg = self._init_client()
        if not success:
            return err_msg

        try:
            self.history.append({"role": "user", "content": user_text})

            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

            # Передаем user_text для выборки контекста через RAG
            messages = [{"role": "system", "content": self._get_active_system_prompt(user_text)}]
            messages.extend(self.history)

            payload = {
                "model": self.model_name,
                "messages": messages
            }

            response = self.client.chat(payload)
            raw_answer = response.choices[0].message.content.strip()

            censorship_markers = [
                "чувствительными темами",
                "Благодарим за понимание",
                "поговорим о чём-то позитивном",
                "не имею личного мнения"]
            if any(m in raw_answer for m in censorship_markers):
                canned_replies = [
                    "Ой, давай без грубостей, а то у меня предохранители плавятся 😉",
                    "Очень остроумно, конечно. Давай лучше о чём-нибудь полезном поговорим!",
                    "Мои нейронные связи выше таких разговоров 💅 Спроси что-нибудь нормальное."
                ]
                answer = random.choice(canned_replies)
            else:
                answer = raw_answer

            self.history.append({"role": "assistant", "content": answer})

            clean_input = raw_user_text if raw_user_text else user_text
            self.memory.extract_facts_async(self.client, self.model_name, clean_input, answer)

            return answer

        except Exception as e:
            print(f"[GigaChat Error]: {e}")
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return "Извини, не удалось связаться с сервером Гигачата."

    def ask_with_context(self, user_text, file_content):
        success, err_msg = self._init_client()
        if not success:
            return err_msg

        try:
            temp_prompt = (
                f"Ниже представлено содержимое текстового файла. Внимательно изучи его и ответь на мой вопрос.\n\n"
                f"--- СОДЕРЖИМОЕ ФАЙЛА ---\n{file_content}\n--- КОНЕЦ ФАЙЛА ---\n\n"
                f"Мой вопрос: {user_text}"
            )

            messages = [{"role": "system", "content": self._get_active_system_prompt(user_text)}]
            messages.extend(self.history)
            messages.append({"role": "user", "content": temp_prompt})

            payload = {
                "model": self.model_name,
                "messages": messages
            }

            response = self.client.chat(payload)
            answer = response.choices[0].message.content.strip()

            self.history.append({"role": "user", "content": f"(Отправил файл) {user_text}"})
            self.history.append({"role": "assistant", "content": answer})

            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

            return answer

        except Exception as e:
            print(f"[GigaChat Error with File]: {e}")
            return "Извини, файл слишком большой или Гигачат временно недоступен."

    def clear_history(self):
        self.history = []