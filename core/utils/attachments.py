import json
import os

MAX_STUDIO_ATTACHMENTS = 10


def parse_attached_files(attached) -> list[str]:
    """Нормализует путь, список путей или JSON-список путей с сохранением порядка (до 10 шт.)."""
    if not attached:
        return []

    raw_items = []
    if isinstance(attached, (list, tuple, set)):
        raw_items = list(attached)
    elif isinstance(attached, str):
        stripped = attached.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                decoded = json.loads(stripped)
                raw_items = decoded if isinstance(decoded, list) else [stripped]
            except (json.JSONDecodeError, TypeError, ValueError):
                raw_items = [stripped]
        else:
            raw_items = [stripped]

    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        path_str = str(item).strip()
        if not path_str:
            continue
        norm_key = (
            os.path.normcase(os.path.abspath(path_str))
            if os.path.isabs(path_str)
            else os.path.normcase(path_str)
        )
        if norm_key in seen:
            continue
        seen.add(norm_key)
        result.append(path_str)
        if len(result) >= MAX_STUDIO_ATTACHMENTS:
            break
    return result


def serialize_attached_files(files) -> str:
    """Сериализует список вложений для хранения в БД и передачи в сигналах."""
    normalized = parse_attached_files(files)
    if not normalized:
        return ""
    if len(normalized) == 1:
        return normalized[0]
    return json.dumps(normalized, ensure_ascii=False)
