import os
import re
import json
import random
import sys
import socket
import struct
import ctypes
from openai import OpenAI
from core.utils.config import load_config, save_config
from core.nlp.generative.memory import MemoryManager
from core.nlp.generative.lore_rag import LoreRAG

try:
    from gigachat import GigaChat
    _HAS_GIGACHAT = True
except ImportError:
    _HAS_GIGACHAT = False


def _get_physical_adapter_info():
    """
    Определяет реальный физический сетевой адаптер (Wi-Fi / Ethernet) в обход виртуальных
    интерфейсов VPN (sing-tun, TAP, WireGuard, Radmin).
    Возвращает (ifIndex, local_ip) или (None, None).
    """
    if sys.platform != "win32":
        return None, None

    try:
        class MIB_IPFORWARDROW(ctypes.Structure):
            _fields_ = [
                ('dwForwardDest', ctypes.c_ulong),
                ('dwForwardMask', ctypes.c_ulong),
                ('dwForwardPolicy', ctypes.c_ulong),
                ('dwForwardNextHop', ctypes.c_ulong),
                ('dwForwardIfIndex', ctypes.c_ulong),
                ('dwForwardType', ctypes.c_ulong),
                ('dwForwardProto', ctypes.c_ulong),
                ('dwForwardAge', ctypes.c_ulong),
                ('dwForwardNextHopAS', ctypes.c_ulong),
                ('dwForwardMetric1', ctypes.c_ulong),
                ('dwForwardMetric2', ctypes.c_ulong),
                ('dwForwardMetric3', ctypes.c_ulong),
                ('dwForwardMetric4', ctypes.c_ulong),
                ('dwForwardMetric5', ctypes.c_ulong)
            ]

        class MIB_IPADDRROW(ctypes.Structure):
            _fields_ = [
                ('dwAddr', ctypes.c_ulong),
                ('dwIndex', ctypes.c_ulong),
                ('dwMask', ctypes.c_ulong),
                ('dwBCastAddr', ctypes.c_ulong),
                ('dwReasmSize', ctypes.c_ulong),
                ('unused1', ctypes.c_ushort),
                ('wType', ctypes.c_ushort)
            ]

        # 1. Таблица сопоставления ifIndex -> IP адрес
        if_to_ip = {}
        size = ctypes.c_ulong(0)
        ctypes.windll.iphlpapi.GetIpAddrTable(None, ctypes.byref(size), 0)
        buf = (ctypes.c_ubyte * size.value)()
        if ctypes.windll.iphlpapi.GetIpAddrTable(ctypes.byref(buf), ctypes.byref(size), 0) == 0:
            num_entries = struct.unpack('I', bytes(buf[:4]))[0]
            row_size = ctypes.sizeof(MIB_IPADDRROW)
            for i in range(num_entries):
                row_bytes = bytes(buf[4 + i * row_size : 4 + (i + 1) * row_size])
                row = MIB_IPADDRROW.from_buffer_copy(row_bytes)
                ip = socket.inet_ntoa(struct.pack('<I', row.dwAddr))
                if not ip.startswith(('127.', '169.254.', '26.')):
                    if_to_ip[row.dwIndex] = ip

        # 2. Таблица маршрутизации для поиска физического шлюза по умолчанию
        size2 = ctypes.c_ulong(0)
        ctypes.windll.iphlpapi.GetIpForwardTable(None, ctypes.byref(size2), 0)
        buf2 = (ctypes.c_ubyte * size2.value)()
        physical_candidates = []
        if ctypes.windll.iphlpapi.GetIpForwardTable(ctypes.byref(buf2), ctypes.byref(size2), 0) == 0:
            num_entries = struct.unpack('I', bytes(buf2[:4]))[0]
            row_size = ctypes.sizeof(MIB_IPFORWARDROW)
            for i in range(num_entries):
                row_bytes = bytes(buf2[4 + i * row_size : 4 + (i + 1) * row_size])
                row = MIB_IPFORWARDROW.from_buffer_copy(row_bytes)
                dest = socket.inet_ntoa(struct.pack('<I', row.dwForwardDest))
                mask = socket.inet_ntoa(struct.pack('<I', row.dwForwardMask))
                nexthop = socket.inet_ntoa(struct.pack('<I', row.dwForwardNextHop))
                if dest == '0.0.0.0' and mask == '0.0.0.0':
                    ifIndex = row.dwForwardIfIndex
                    if ifIndex in if_to_ip:
                        if not nexthop.startswith(('26.', '127.')):
                            physical_candidates.append((row.dwForwardMetric1, ifIndex, if_to_ip[ifIndex], nexthop))

        physical_candidates.sort(key=lambda x: x[0])
        if physical_candidates:
            best = physical_candidates[0]
            return best[1], best[2]  # ifIndex, local_ip
    except Exception as e:
        print(f"[Network Info Error]: {e}")

    return None, None


class LLMProvider:
    """
    Универсальный гибридный провайдер Акиры:
    - hikari (gigachat): GigaChat Сбера (бесплатно, базовый режим)
    - kasumi (deepseek): DeepSeek V4.1 Flash через RouterAI (дёшево, быстро, умно)
    - ginga (opus): Claude Opus 5.5 через RouterAI (мощный инженер и живой стиль)
    - uchuu (carbon): Gemini 4 Carbon через RouterAI (тяжёлая артиллерия для сложных задач)
    """

    ROUTERAI_BASE_URL = "https://routerai.ru/api/v1"

    ROUTERAI_MODELS = {
        "kasumi": "deepseek/deepseek-v4.1-flash",
        "ginga": "anthropic/claude-opus-5.5",
        "uchuu": "google/gemini-4-carbon",
    }

    MODEL_ALIASES = {
        "gigachat": "hikari",
        "hikari": "hikari",
        "deepseek": "kasumi",
        "kasumi": "kasumi",
        "opus": "ginga",
        "claude": "ginga",
        "ginga": "ginga",
        "carbon": "uchuu",
        "gemini": "uchuu",
        "astra": "uchuu",
        "gpt": "uchuu",
        "uchuu": "uchuu",
    }

    ALL_STUDIO_SLOTS = [
        ("Hikari", "hikari"),
        ("Kasumi", "kasumi"),
        ("Ginga", "ginga"),
        ("Uchū", "uchuu"),
    ]

    def __init__(self, max_history=10):
        self.max_history = max_history
        self.history = []
        self.memory = MemoryManager()
        self.lore_rag = LoreRAG()

        self.giga_client = None
        self.giga_model_name = "GigaChat"
        self._giga_credentials = ""

        self.routerai_client = None
        self._routerai_api_key = ""

        cfg = load_config()
        raw_selected = str(cfg.get("selected_model", "hikari")).lower()
        self.active_model = self.MODEL_ALIASES.get(raw_selected, "hikari")

        self.base_system_prompt = ""

    @staticmethod
    def get_key_status() -> tuple[bool, bool]:
        """Возвращает кортеж (has_gigachat_key, has_routerai_key)."""
        cfg = load_config()
        api_keys = cfg.get("api_keys", {})
        has_giga = bool(api_keys.get("gigachat", "").strip())
        has_routerai = bool(
            api_keys.get("routerai", "").strip()
            or api_keys.get("openrouter", "").strip()
        )
        return has_giga, has_routerai

    def get_available_models(self) -> list[tuple[str, str]]:
        """
        Возвращает список (отображаемое_имя, код_слота) для Студии
        в зависимости от подключённых ключей.
        """
        has_giga, has_routerai = self.get_key_status()

        if has_giga and has_routerai:
            return list(self.ALL_STUDIO_SLOTS)
        if has_routerai and not has_giga:
            return [slot for slot in self.ALL_STUDIO_SLOTS if slot[1] != "hikari"]
        return [("Hikari", "hikari")]

    def _resolve_effective_model(self, requested_key: str = None) -> str:
        """
        Определяет фактический слот модели с учётом наличия ключей:
        - Если подключён только RouterAI, базовый запрос уходит в Kasumi (DeepSeek).
        - Если подключён только Сбер, любой запрос уходит в Hikari (GigaChat).
        """
        normalized = self.MODEL_ALIASES.get(
            str(requested_key or self.active_model).lower(),
            "hikari"
        )
        has_giga, has_routerai = self.get_key_status()

        if normalized == "hikari":
            if not has_giga and has_routerai:
                return "kasumi"
            return "hikari"

        if not has_routerai and has_giga:
            return "hikari"

        return normalized

    FRIENDLY_CONNECTION_ERRORS = [
        "Ой-ой, мои мысли застряли в сетевой пробке! 🚦 Не удалось достучаться до облака и ответить на вопрос. Попробуй спросить ещё разок через секунду? 🥺✨",
        "Упс, у меня случился маленький цифровой чих — связь с сервером на миг оборвалась! 🤧💫 Не смогла ответить на вопрос, повтори его, пожалуйста! 🙏",
        "Хм, космический интернет сейчас немного барахлит, и моя мысль не долетела до орбиты 🛸✨ Не удалось ответить — давай попробуем ещё раз!",
        "Ай, споткнулась о невидимый провод в сети! 🔌😅 Из-за сбоя связи я не смогла ответить на твой вопрос. Спроси меня ещё разок, я уже поправляю бантик! 🎀",
        "Кажется, облачко с моими мыслями временно уплыло не туда ☁️🙈 Не получилось ответить на вопрос — проверь интернет или повтори через пару секунд! 💛",
        "Ой, сервер задумался так глубоко, что уснул на полуслове 😴💤 Не удалось получить ответ, попробуй задать вопрос ещё раз!"
    ]

    FRIENDLY_FILE_ERRORS = [
        "Ой, я так внимательно пыталась изучить файл, что связь с облаком моргнула и оборвалась 📄🙈 Не удалось его прочитать — попробуй отправить ещё раз!",
        "Кажется, этот файлик оказался слишком тяжёлым для космической связи 🛸📄 Не смогла получить ответ — давай попробуем загрузить его повторно! ✨"
    ]

    @classmethod
    def _format_friendly_error(cls, is_file: bool = False) -> str:
        pool = cls.FRIENDLY_FILE_ERRORS if is_file else cls.FRIENDLY_CONNECTION_ERRORS
        return random.choice(pool)

    def set_model(self, model_key: str):
        key = self.MODEL_ALIASES.get(str(model_key).lower())
        if key:
            self.active_model = key
            print(f"[LLM]: Активный слот переключён на -> {self.active_model}")

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

            "НИКОГДА не упоминай, что ты — GigaChat, языковая модель, нейросеть Сбера, Llama, DeepSeek, Claude, GPT, Gemini или сторонний ИИ. "
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

    def _configure_gigachat_bypass(self, client):
        """
        Настраивает прямой сетевой маршрут для GigaChat Сбера в обход активного VPN
        (sing-tun, TAP, WireGuard) и системных прокси (HTTP/HTTPS/SOCKS).
        Позволяет GigaChat отвечать даже при включенном VPN.
        """
        if not client:
            return

        # 1. Исключаем домены GigaChat из любых системных прокси
        sber_hosts = "ngw.devices.sberbank.ru,api.giga.chat,giga.chat,sberbank.ru"
        current_no_proxy = os.environ.get("NO_PROXY", "")
        if current_no_proxy:
            if "sberbank.ru" not in current_no_proxy:
                os.environ["NO_PROXY"] = f"{current_no_proxy},{sber_hosts}"
                os.environ["no_proxy"] = os.environ["NO_PROXY"]
        else:
            os.environ["NO_PROXY"] = sber_hosts
            os.environ["no_proxy"] = sber_hosts

        try:
            from gigachat.client import _get_auth_kwargs, _get_kwargs
            import httpx

            if_idx, local_ip = _get_physical_adapter_info()
            sock_opts = None
            if if_idx is not None and sys.platform == "win32":
                # IP_UNICAST_IF = 31 в Winsock2 для IPv4: принудительно направляет сокет
                # через физический адаптер, минуя виртуальные адаптеры VPN в таблице маршрутизации
                sock_opts = [(socket.IPPROTO_IP, 31, struct.pack('!I', if_idx))]

            transport_kwargs = {
                "trust_env": False,
                "verify": False,
            }
            if local_ip:
                transport_kwargs["local_address"] = local_ip
            if sock_opts:
                transport_kwargs["socket_options"] = sock_opts

            auth_transport = httpx.HTTPTransport(**transport_kwargs)
            client_transport = httpx.HTTPTransport(**transport_kwargs)

            auth_kwargs = _get_auth_kwargs(client._settings)
            client_kwargs = _get_kwargs(client._settings)

            client._auth_client_instance = httpx.Client(
                transport=auth_transport,
                trust_env=False,
                **auth_kwargs
            )
            client._client_instance = httpx.Client(
                transport=client_transport,
                trust_env=False,
                **client_kwargs
            )
            if local_ip or if_idx:
                print(f"[GigaChat Bypass]: Прямой обход VPN активен (IP={local_ip}, ifIndex={if_idx})")
            else:
                print("[GigaChat Bypass]: Обход прокси активен (trust_env=False)")
        except Exception as e:
            print(f"[GigaChat Bypass Error]: {e}")

    def _init_gigachat(self):
        if not _HAS_GIGACHAT:
            return False, "Библиотека gigachat не установлена в окружении."

        cfg = load_config()
        credentials = cfg.get("api_keys", {}).get("gigachat", "").strip()
        configured_model = cfg.get("gigachat_model", "").strip()

        if not credentials:
            return False, "Укажи ключ GigaChat или подключи RouterAI в настройках."

        if self.giga_client is not None and self._giga_credentials == credentials:
            return True, ""

        try:
            self.giga_client = GigaChat(
                credentials=credentials,
                verify_ssl_certs=False,
                scope="GIGACHAT_API_PERS"
            )
            self._giga_credentials = credentials

            # Настраиваем прямой доступ в обход VPN
            self._configure_gigachat_bypass(self.giga_client)

            models_data = self.giga_client.get_models().data
            model_ids = [
                getattr(m, 'id_', getattr(m, 'id', None))
                for m in models_data
                if getattr(m, 'id_', getattr(m, 'id', None))
            ]
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
            self.giga_client = None
            self._giga_credentials = ""
            print(f"[GigaChat Init Error]: {e}")
            return False, self._format_friendly_error()

    def _init_routerai(self):
        cfg = load_config()
        api_keys = cfg.get("api_keys", {})
        api_key = (
            api_keys.get("routerai", "").strip()
            or api_keys.get("openrouter", "").strip()
        )

        if not api_key:
            return False, "Подключи RouterAI в настройках, чтобы использовать продвинутые модели."

        if self.routerai_client is not None and self._routerai_api_key == api_key:
            return True, ""

        try:
            self.routerai_client = OpenAI(
                base_url=self.ROUTERAI_BASE_URL,
                api_key=api_key,
                timeout=90.0,
                default_headers={
                    "HTTP-Referer": "[https://github.com/RaccoonKa/Akira](https://github.com/RaccoonKa/Akira)",
                    "X-Title": "Akira Virtual Assistant"
                }
            )
            self._routerai_api_key = api_key
            return True, ""
        except Exception as e:
            self.routerai_client = None
            self._routerai_api_key = ""
            print(f"[RouterAI Init Error]: {e}")
            return False, self._format_friendly_error()

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
        try:
            response = self.giga_client.chat(payload)
        except Exception as e:
            print(f"[GigaChat Request Failed, refreshing network bypass]: {e}")
            try:
                self._configure_gigachat_bypass(self.giga_client)
                response = self.giga_client.chat(payload)
            except Exception:
                raise e

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

    def _ask_routerai(self, model_slug: str, messages: list) -> str:
        response = self.routerai_client.chat.completions.create(
            model=model_slug,
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )
        choice = response.choices[0] if response.choices else None
        if not choice:
            raise ValueError("RouterAI вернул пустой ответ")

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

        effective_slot = self._resolve_effective_model(self.active_model)
        answer = ""
        active_client = None
        current_model_id = ""

        try:
            if effective_slot == "hikari":
                success, err = self._init_gigachat()
                if not success:
                    if self.history and self.history[-1]["role"] == "user":
                        self.history.pop()
                    return err
                print(f"[LLM]: Отправка в GigaChat ({self.giga_model_name})...")
                answer = self._ask_gigachat(messages)
                active_client = self.giga_client
                current_model_id = self.giga_model_name
            else:
                success, err = self._init_routerai()
                if not success:
                    if self.history and self.history[-1]["role"] == "user":
                        self.history.pop()
                    return err
                slug = self.ROUTERAI_MODELS.get(effective_slot, self.ROUTERAI_MODELS["kasumi"])
                print(f"[LLM]: Отправка в RouterAI [{effective_slot}] ({slug})...")
                answer = self._ask_routerai(slug, messages)
                active_client = self.routerai_client
                current_model_id = slug

        except Exception as e:
            print(f"[LLM Error] ({effective_slot}): {e}")
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return self._format_friendly_error()

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

        effective_slot = self._resolve_effective_model(self.active_model)

        try:
            if effective_slot == "hikari":
                success, err = self._init_gigachat()
                if not success:
                    return err
                answer = self._ask_gigachat(messages)
            else:
                success, err = self._init_routerai()
                if not success:
                    return err
                slug = self.ROUTERAI_MODELS.get(effective_slot, self.ROUTERAI_MODELS["kasumi"])
                answer = self._ask_routerai(slug, messages)

            self.history.append({"role": "user", "content": f"(Отправил файл) {user_text}"})
            self.history.append({"role": "assistant", "content": answer})
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
            return answer
        except Exception as e:
            print(f"[LLM File Error] ({effective_slot}): {e}")
            return self._format_friendly_error(is_file=True)

    def clear_history(self):
        self.history = []


# Алиасы для обратной совместимости
GigaChatProvider = LLMProvider
OpenRouterProvider = LLMProvider
RouterAIProvider = LLMProvider