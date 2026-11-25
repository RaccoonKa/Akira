"""Лёгкая обёртка над HuggingFace `tokenizers` без импорта transformers/torch при старте."""

import json
import os
import numpy as np


class FastJsonTokenizer:
    """Минимальный совместимый адаптер над tokenizers.Tokenizer для ONNX-моделей."""

    def __init__(self, tokenizer_json_path: str, tokenizer_config_path: str | None = None):
        from tokenizers import Tokenizer

        self._tok = Tokenizer.from_file(tokenizer_json_path)
        self.pad_token = "[PAD]"
        self.pad_token_id = 0
        self.model_max_length = 512

        if tokenizer_config_path and os.path.exists(tokenizer_config_path):
            try:
                with open(tokenizer_config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if cfg.get("pad_token"):
                    self.pad_token = str(cfg["pad_token"])
                    pid = self._tok.token_to_id(self.pad_token)
                    if pid is not None:
                        self.pad_token_id = int(pid)
                max_len = cfg.get("max_length") or cfg.get("model_max_length")
                if isinstance(max_len, int) and 0 < max_len < 1_000_000:
                    self.model_max_length = max_len
            except Exception:
                pass

    def __call__(
        self,
        text: str,
        *,
        return_offsets_mapping: bool = False,
        return_tensors: str = "np",
        truncation: bool = False,
        max_length: int | None = None,
        padding: bool = False,
    ) -> dict:
        if truncation:
            limit = int(max_length) if max_length else self.model_max_length
            self._tok.enable_truncation(max_length=limit)
        else:
            self._tok.no_truncation()

        if padding:
            self._tok.enable_padding(pad_id=int(self.pad_token_id), pad_token=str(self.pad_token))
        else:
            self._tok.no_padding()

        enc = self._tok.encode(text)
        result = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
            "token_type_ids": np.array([enc.type_ids], dtype=np.int64),
        }
        if return_offsets_mapping:
            result["offset_mapping"] = np.array([enc.offsets], dtype=np.int64)
        return result


def load_fast_tokenizer(model_dir: str):
    """Загружает быстрый токенизатор из tokenizer.json с fallback на AutoTokenizer."""
    tokenizer_json_path = os.path.join(model_dir, "tokenizer.json")
    tokenizer_config_path = os.path.join(model_dir, "tokenizer_config.json")
    if os.path.exists(tokenizer_json_path):
        try:
            return FastJsonTokenizer(
                tokenizer_json_path,
                tokenizer_config_path if os.path.exists(tokenizer_config_path) else None,
            )
        except Exception:
            pass

    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
