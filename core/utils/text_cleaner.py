import re

# Регулярное выражение для поиска любых ремарок, эмоций и действий в тексте от LLM:
# - *радостно хихикает*, *смеется*, *весело улыбается*, _подмигивает_
# - [смеется и машет рукой]
# - (тихо вздыхает), (смущенно улыбнулась)
CHAT_ACTION_TAG_REGEX = re.compile(
    r'(?:'
    r'(?<![*_])[*_](?![*_])\s*[^*_\n]{1,120}\s*(?<![*_])[*_](?![*_])'
    r'|'
    r'\[\s*[^\]\n]{1,120}\s*\]'
    r'|'
    r'\(\s*[^\)\n]*?(?:сме[еёх]|хихик|усме[хш]|хохо[тч]|хмык|улыб|вздох|вздых|подмиг|зева|смущ|задум|пауз|машет|молчит|шепч|кива)[^\)\n]*?\)'
    r')',
    re.IGNORECASE
)


def clean_chat_display_text(text: str) -> str:
    """
    Очищает текст ответа нейросети перед выводом в чат и мессенджеры:
    - Полностью удаляет сценические ремарки и теги действий (*смеется*, *радостно хихикает* и т.д.)
    - Сохраняет блоки кода (```...```) и инлайн-код (`...`) нетронутыми
    - Сохраняет Markdown-жирность (**важно**) и пунктуацию
    - Убирает лишние пробелы и пустые строки
    """
    if not text:
        return ""

    code_snippets = []

    def _store_code(m):
        idx = len(code_snippets)
        code_snippets.append(m.group(0))
        return f"@@@CODEBLOCK{idx}@@@"

    # Защищаем блоки кода и инлайн-код
    protected = re.sub(r'```[\s\S]*?```|`[^`\n]+`', _store_code, text)

    lines = []
    for line in protected.splitlines():
        line_clean = CHAT_ACTION_TAG_REGEX.sub(" ", line)
        line_clean = re.sub(r'^[,\s!?:;.\-]+', '', line_clean)
        line_clean = re.sub(r'[ \t]+', ' ', line_clean)
        line_clean = re.sub(r'\s+([,.:!?])', r'\1', line_clean).strip()
        lines.append(line_clean)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # Восстанавливаем сохраненный код
    for idx, snippet in enumerate(code_snippets):
        cleaned = cleaned.replace(f"@@@CODEBLOCK{idx}@@@", snippet)

    return cleaned.strip()
