import os
import re
import math
from collections import Counter
import numpy as np
from core.utils.config import get_resource_path, get_user_data_path

try:
    from fastembed import TextEmbedding
    _HAS_FASTEMBED = True
except ImportError:
    _HAS_FASTEMBED = False


class LoreRAG:
    """Семантический RAG по цифровой библии Акиры с локальным хранением весов в optimized_models."""

    # Надежная мультиязычная модель
    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, bible_path=None):
        if bible_path:
            self.bible_path = bible_path
        else:
            self.bible_path = get_resource_path("assets", "akira_manifesto.md")
            if not os.path.exists(self.bible_path):
                self.bible_path = get_resource_path("assets", "akira_manifesto.md")
            if not os.path.exists(self.bible_path):
                self.bible_path = get_resource_path("core", "nlp", "akira_manifesto.md")
            if not os.path.exists(self.bible_path):
                self.bible_path = get_resource_path("core", "nlp", "akira_manifesto.md")

        # Папка под саму модель внутри optimized_models
        self.models_dir = get_resource_path("optimized_models", "lore_rag")
        os.makedirs(self.models_dir, exist_ok=True)

        self.cache_path = os.path.join(get_user_data_path(), "lore_embeddings_cache.npz")
        self.chunks = []
        self.chunk_titles = []
        self.embeddings = None
        self.model = None
        self._fastembed_failed = False

        # Для BM25 фолбека
        self._tokenized_corpus = []
        self._doc_lens = []
        self._avg_dl = 0.0
        self._idf = {}

        self._load_and_index()

    def _init_model(self):
        if self._fastembed_failed or not _HAS_FASTEMBED:
            return

        if self.model is None:
            # Снимаем блокировку полосы загрузки
            os.environ.pop("HF_HUB_DISABLE_PROGRESS_BARS", None)

            try:
                # Явно передаем cache_dir в папку optimized_models/lore_rag
                self.model = TextEmbedding(
                    model_name=self.MODEL_NAME,
                    cache_dir=self.models_dir,
                    local_files_only=False
                )
                print(f"[LoreRAG]: Модель загружена из {self.models_dir}")
            except Exception as e:
                print(f"[LoreRAG Warning]: Не удалось инициализировать fastembed: {e}")
                print("[LoreRAG]: Включаем встроенный BM25-поиск.")
                self._fastembed_failed = True

    def _tokenize(self, text: str):
        return re.findall(r'[a-zA-Zа-яА-ЯёЁ0-9]{3,}', text.lower())

    def _build_bm25_index(self):
        self._tokenized_corpus = [self._tokenize(chunk) for chunk in self.chunks]
        self._doc_lens = [len(doc) for doc in self._tokenized_corpus]
        self._avg_dl = sum(self._doc_lens) / max(len(self._doc_lens), 1)

        df = Counter()
        for doc in self._tokenized_corpus:
            for term in set(doc):
                df[term] += 1

        n_docs = len(self._tokenized_corpus)
        self._idf = {}
        for term, freq in df.items():
            self._idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)

    def _score_bm25(self, query_tokens, doc_idx, k1=1.5, b=0.75):
        doc = self._tokenized_corpus[doc_idx]
        doc_len = self._doc_lens[doc_idx]
        tf = Counter(doc)
        score = 0.0

        for term in query_tokens:
            if term in tf:
                term_idf = self._idf.get(term, 0.0)
                term_tf = tf[term]
                numerator = term_tf * (k1 + 1.0)
                denominator = term_tf + k1 * (1.0 - b + b * (doc_len / (self._avg_dl + 1e-6)))
                score += term_idf * (numerator / denominator)
        return score

    def _parse_bible(self):
        """Разбивает манифест на компактные подразделы (#####) для точного поиска."""
        if not os.path.exists(self.bible_path):
            print(f"[LoreRAG Warning]: Файл манифеста не найден по пути: {self.bible_path}")
            return []

        try:
            with open(self.bible_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception as e:
            print(f"[LoreRAG Error]: Ошибка чтения манифеста: {e}")
            return []

        raw_sections = re.split(r'(?=^#{3,5}\s+)', content, flags=re.MULTILINE)
        parsed_chunks = []
        parsed_titles = []

        current_main_topic = "Манифест"

        for sec in raw_sections:
            sec_clean = sec.strip()
            if not sec_clean:
                continue

            lines = sec_clean.splitlines()
            first_line = lines[0].replace("#", "").strip()

            if "Раздел" in first_line:
                current_main_topic = first_line

            chunk_text = f"[{current_main_topic}]\n{sec_clean}"
            parsed_chunks.append(chunk_text)
            parsed_titles.append(f"{current_main_topic} -> {first_line}")

        self.chunks = parsed_chunks
        self.chunk_titles = parsed_titles
        self._build_bm25_index()
        return parsed_chunks

    def _load_and_index(self):
        self._parse_bible()
        if not self.chunks:
            return

        bible_mtime = os.path.getmtime(self.bible_path) if os.path.exists(self.bible_path) else 0

        if os.path.exists(self.cache_path):
            try:
                cached = np.load(self.cache_path, allow_pickle=True)
                cached_mtime = float(cached.get("mtime", 0))
                cached_vectors = cached.get("vectors")

                if cached_mtime >= bible_mtime and cached_vectors is not None and len(cached_vectors) == len(self.chunks):
                    self.embeddings = cached_vectors
                    print(f"[LoreRAG]: Загружен кэш эмбеддингов ({len(self.chunks)} разделов)")
                    return
            except Exception:
                pass

        self._build_embeddings(bible_mtime)

    def _build_embeddings(self, bible_mtime: float):
        self._init_model()
        if self.model is None:
            return

        print(f"[LoreRAG]: Вычисление ONNX-эмбеддингов для {len(self.chunks)} разделов...")
        try:
            vectors_gen = self.model.embed(self.chunks)
            vectors_list = list(vectors_gen)
            self.embeddings = np.array(vectors_list, dtype=np.float32)

            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            np.savez_compressed(self.cache_path, vectors=self.embeddings, mtime=bible_mtime)
            print("[LoreRAG]: Эмбеддинги успешно сохранены в локальный кэш.")
        except Exception as e:
            print(f"[LoreRAG Build Warning]: {e}")
            self.embeddings = None

    def get_relevant_lore(self, query: str, threshold: float = 0.38) -> str:
        clean_query = query.strip()
        if not clean_query or len(clean_query) < 3 or not self.chunks:
            return ""

        ignore_words = {"привет", "здравствуй", "добрый", "да", "нет", "ок", "ладно", "пока", "стоп"}
        if clean_query.lower() in ignore_words:
            return ""

        if self.embeddings is not None and len(self.embeddings) > 0 and not self._fastembed_failed:
            self._init_model()
            if self.model is not None:
                try:
                    q_vec = list(self.model.embed([clean_query]))[0]
                    q_vec = np.array(q_vec, dtype=np.float32)

                    norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(q_vec) + 1e-9
                    similarities = np.dot(self.embeddings, q_vec) / norms

                    best_idx = int(np.argmax(similarities))
                    best_score = float(similarities[best_idx])

                    if best_score >= threshold:
                        print(f"[LoreRAG Hit]: {self.chunk_titles[best_idx]} (score: {best_score:.3f})")
                        return self.chunks[best_idx]
                except Exception as e:
                    print(f"[LoreRAG Search Warning]: {e}")

        query_tokens = self._tokenize(clean_query)
        if query_tokens and self._tokenized_corpus:
            scores = [self._score_bm25(query_tokens, i) for i in range(len(self.chunks))]
            best_idx = int(np.argmax(scores))
            if scores[best_idx] > 1.2:
                print(f"[LoreRAG BM25 Hit]: {self.chunk_titles[best_idx]} (score: {scores[best_idx]:.2f})")
                return self.chunks[best_idx]

        return ""