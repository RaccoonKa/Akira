import os
import re
import html
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QRegularExpression
from PyQt6.QtGui import (
    QFont, QColor, QSyntaxHighlighter, QTextCharFormat,
    QGuiApplication
)

try:
    from rich.console import Console
    from rich.markdown import Markdown as RichMarkdown
    _HAS_RICH = True
    _RICH_CONSOLE = Console()
except ImportError:
    _HAS_RICH = False
    _RICH_CONSOLE = None


LANGUAGE_EXTENSIONS = {
    "python": ".py",
    "py": ".py",
    "csharp": ".cs",
    "cs": ".cs",
    "c#": ".cs",
    "cpp": ".cpp",
    "c++": ".cpp",
    "cc": ".cpp",
    "cxx": ".cpp",
    "c": ".c",
    "javascript": ".js",
    "js": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "jsx": ".jsx",
    "tsx": ".tsx",
    "html": ".html",
    "htm": ".html",
    "css": ".css",
    "scss": ".scss",
    "sass": ".sass",
    "json": ".json",
    "xml": ".xml",
    "xaml": ".xaml",
    "svg": ".svg",
    "yaml": ".yaml",
    "yml": ".yml",
    "toml": ".toml",
    "sql": ".sql",
    "sqlite": ".sql",
    "postgres": ".sql",
    "mysql": ".sql",
    "bash": ".sh",
    "sh": ".sh",
    "zsh": ".sh",
    "shell": ".sh",
    "powershell": ".ps1",
    "ps1": ".ps1",
    "pwsh": ".ps1",
    "bat": ".bat",
    "cmd": ".bat",
    "rust": ".rs",
    "rs": ".rs",
    "go": ".go",
    "golang": ".go",
    "java": ".java",
    "kotlin": ".kt",
    "kt": ".kt",
    "swift": ".swift",
    "php": ".php",
    "ruby": ".rb",
    "rb": ".rb",
    "lua": ".lua",
    "r": ".r",
    "dart": ".dart",
    "markdown": ".md",
    "md": ".md",
    "txt": ".txt",
    "text": ".txt",
    "plaintext": ".txt",
    "log": ".log",
    "ini": ".ini",
    "conf": ".conf",
    "cfg": ".cfg",
    "env": ".env",
    "dockerfile": ".dockerfile",
    "docker": ".dockerfile",
}

LANGUAGE_DISPLAY_NAMES = {
    "py": "PYTHON",
    "python": "PYTHON",
    "cs": "C#",
    "csharp": "C#",
    "c#": "C#",
    "cpp": "C++",
    "c++": "C++",
    "js": "JAVASCRIPT",
    "javascript": "JAVASCRIPT",
    "ts": "TYPESCRIPT",
    "typescript": "TYPESCRIPT",
    "ps1": "POWERSHELL",
    "powershell": "POWERSHELL",
    "sh": "BASH",
    "bash": "BASH",
    "md": "MARKDOWN",
    "markdown": "MARKDOWN",
    "plaintext": "TEXT",
    "text": "TEXT",
}


def get_extension_for_language(language: str) -> str:
    """Возвращает расширение файла (с точкой) по названию языка."""
    lang = (language or "").strip().lower()
    return LANGUAGE_EXTENSIONS.get(lang, ".txt")


def get_display_language(language: str) -> str:
    """Форматирует красивое отображаемое имя языка для бейджа."""
    raw = (language or "").strip()
    if not raw:
        return "CODE"
    low = raw.lower()
    return LANGUAGE_DISPLAY_NAMES.get(low, raw.upper())


def suggest_filename(language: str, code: str) -> str:
    """Подбирает осмысленное имя файла по содержимому первых строк кода."""
    ext = get_extension_for_language(language)
    lang_low = (language or "").strip().lower()

    if lang_low in ("md", "markdown"):
        for line in code.splitlines()[:10]:
            m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
            if m:
                clean = re.sub(r"[^\w\s\-а-яА-ЯёЁ]", "", m.group(1)).strip().lower()
                clean = re.sub(r"\s+", "_", clean)[:32]
                if clean:
                    return f"{clean}.md"
        return "akira_note.md"

    patterns = [
        r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)",
        r"^\s*(?:public|private|internal|protected)?\s*(?:static\s+)?(?:partial\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:pub\s+)?(?:fn|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*func\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]

    for line in code.splitlines()[:30]:
        for pat in patterns:
            match = re.match(pat, line)
            if match:
                ident = match.group(1)
                if ident.startswith("__") and ident.endswith("__"):
                    continue
                if lang_low in ("py", "python", "rs", "rust", "sh", "bash"):
                    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", ident).lower()
                    return f"{snake}{ext}"
                return f"{ident}{ext}"

    return f"akira_code{ext}"


class UniversalCodeHighlighter(QSyntaxHighlighter):
    """Универсальный подсветчик синтаксиса с поддержкой тёмной и светлой тем."""

    DARK_COLORS = {
        "keyword": "#c792ea",      # Неоново-фиолетовый
        "builtin": "#82aaff",      # Небесно-голубой
        "function": "#67e8f9",     # Яркий циан
        "decorator": "#facc15",    # Тёплый золотой
        "string": "#ecc48d",       # Янтарно-песочный
        "number": "#f78c6c",       # Коралловый
        "comment": "#637777",      # Приглушённый серо-бирюзовый
        "operator": "#89ddff",     # Голубой акцент
        "md_heading": "#facc15",   # Заголовки MD
        "md_bold": "#f472b6",      # Жирный текст MD
        "md_list": "#38bdf8",      # Маркеры списков MD
    }

    LIGHT_COLORS = {
        "keyword": "#7c3aed",      # Глубокий фиолетовый
        "builtin": "#0284c7",      # Насыщенный синий
        "function": "#0f766e",     # Изумрудно-бирюзовый
        "decorator": "#b45309",    # Тёмно-янтарный
        "string": "#15803d",       # Лесной зелёный
        "number": "#c2410c",       # Терракотовый
        "comment": "#64748b",      # Сланцево-серый
        "operator": "#0369a1",     # Тёмно-голубой
        "md_heading": "#b45309",   # Заголовки MD
        "md_bold": "#be185d",      # Жирный текст MD
        "md_list": "#0284c7",      # Маркеры списков MD
    }

    KEYWORDS = [
        # Python / общие
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else", "except",
        "finally", "for", "from", "global", "if", "import", "in", "is",
        "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
        "while", "with", "yield", "self", "cls",
        # JS / TS / C# / C++ / Rust / Go
        "const", "let", "var", "function", "export", "default", "new", "this",
        "super", "typeof", "instanceof", "void", "null", "undefined", "true", "false",
        "public", "private", "protected", "internal", "static", "readonly",
        "override", "virtual", "abstract", "interface", "struct", "enum",
        "namespace", "using", "switch", "case", "throw", "catch", "fn", "mut",
        "pub", "impl", "trait", "match", "func", "package", "defer", "go",
        # SQL
        "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET",
        "DELETE", "CREATE", "TABLE", "ALTER", "DROP", "JOIN", "LEFT", "RIGHT",
        "INNER", "ON", "GROUP", "BY", "ORDER", "LIMIT", "AND", "OR", "NOT", "NULL",
    ]

    BUILTINS = [
        "int", "float", "str", "bool", "list", "dict", "set", "tuple", "bytes",
        "object", "Exception", "ValueError", "TypeError", "RuntimeError",
        "print", "len", "range", "enumerate", "zip", "map", "filter", "isinstance",
        "open", "super", "property", "staticmethod", "classmethod",
        "string", "double", "decimal", "char", "byte", "Task", "List", "Dictionary",
        "console", "Promise", "Array", "Object", "String", "Number", "Boolean",
    ]

    def __init__(self, document, language: str = "", theme: str = "dark"):
        super().__init__(document)
        self.language = (language or "").strip().lower()
        self.current_theme = theme
        self.rules = []
        self._build_rules()

    def set_theme(self, theme: str):
        if self.current_theme != theme:
            self.current_theme = theme
            self._build_rules()
            self.rehighlight()

    def _make_format(self, color_hex: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color_hex))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def _build_rules(self):
        palette = self.LIGHT_COLORS if self.current_theme == "light" else self.DARK_COLORS
        self.rules.clear()

        kw_fmt = self._make_format(palette["keyword"], bold=True)
        builtin_fmt = self._make_format(palette["builtin"])
        func_fmt = self._make_format(palette["function"], bold=True)
        dec_fmt = self._make_format(palette["decorator"])
        num_fmt = self._make_format(palette["number"])
        str_fmt = self._make_format(palette["string"])
        comment_fmt = self._make_format(palette["comment"], italic=True)

        if self.language in ("md", "markdown"):
            md_h_fmt = self._make_format(palette["md_heading"], bold=True)
            md_b_fmt = self._make_format(palette["md_bold"], bold=True)
            md_l_fmt = self._make_format(palette["md_list"], bold=True)
            self.rules.append((QRegularExpression(r"^#{1,6}\s+.*$"), md_h_fmt))
            self.rules.append((QRegularExpression(r"\*\*[^*]+\*\*"), md_b_fmt))
            self.rules.append((QRegularExpression(r"^\s*[-*+]\s+"), md_l_fmt))
            self.rules.append((QRegularExpression(r"`[^`]+`"), str_fmt))
            self.comment_start = None
            self.comment_end = None
            self.multiline_comment_fmt = comment_fmt
            return

        # 1. Ключевые слова и встроенные типы
        for kw in self.KEYWORDS:
            self.rules.append((QRegularExpression(rf"\b{re.escape(kw)}\b"), kw_fmt))

        for b in self.BUILTINS:
            self.rules.append((QRegularExpression(rf"\b{re.escape(b)}\b"), builtin_fmt))

        # 2. Имена функций и классов после объявления
        self.rules.append((
            QRegularExpression(r"\b(?:def|class|function|fn|struct|interface|enum|func)\s+([A-Za-z_][A-Za-z0-9_]*)"),
            func_fmt
        ))

        # 3. Декораторы и атрибуты
        self.rules.append((QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_\.]*"), dec_fmt))

        # 4. Числа (целые, дробные, hex)
        self.rules.append((QRegularExpression(r"\b(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?)\b"), num_fmt))

        # 5. HTML / XML теги
        if self.language in ("html", "htm", "xml", "xaml", "svg", "jsx", "tsx"):
            self.rules.append((QRegularExpression(r"</?[A-Za-z][A-Za-z0-9\-]*\b[^>]*>"), builtin_fmt))

        # 6. Строковые литералы (перекрывают ключевые слова и числа внутри себя)
        self.rules.append((QRegularExpression(r'(?:[fFrRbBuU])?"(?:\\.|[^"\\])*"'), str_fmt))
        self.rules.append((QRegularExpression(r"(?:[fFrRbBuU])?'(?:\\.|[^'\\])*'"), str_fmt))
        self.rules.append((QRegularExpression(r"`(?:\\.|[^`\\])*`"), str_fmt))

        # 7. Однострочные комментарии (перекрывают всё в конце строки)
        self.rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))
        self.rules.append((QRegularExpression(r"//[^\n]*"), comment_fmt))
        if self.language in ("sql", "sqlite", "postgres", "mysql", "lua"):
            self.rules.append((QRegularExpression(r"--[^\n]*"), comment_fmt))

        self.comment_start = QRegularExpression(r"/\*")
        self.comment_end = QRegularExpression(r"\*/")
        self.multiline_comment_fmt = comment_fmt

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                # Если в паттерне есть группа захвата (например, имя функции), красим её, иначе весь матч
                group_idx = 1 if match.lastCapturedIndex() >= 1 else 0
                start = match.capturedStart(group_idx)
                length = match.capturedLength(group_idx)
                if start >= 0 and length > 0:
                    self.setFormat(start, length, fmt)

        # Многострочные комментарии /* ... */
        if self.comment_start is None or self.comment_end is None:
            return

        self.setCurrentBlockState(0)
        start_idx = 0
        if self.previousBlockState() != 1:
            match = self.comment_start.match(text)
            start_idx = match.capturedStart() if match.hasMatch() else -1

        while start_idx >= 0:
            end_match = self.comment_end.match(text, start_idx)
            end_idx = end_match.capturedStart()
            if end_idx == -1:
                self.setCurrentBlockState(1)
                comment_len = len(text) - start_idx
            else:
                comment_len = end_idx - start_idx + end_match.capturedLength()

            self.setFormat(start_idx, comment_len, self.multiline_comment_fmt)
            next_match = self.comment_start.match(text, start_idx + comment_len)
            start_idx = next_match.capturedStart() if next_match.hasMatch() else -1


class CodeBlockWidget(QFrame):
    """
    Отдельная монолитная рамка с кодом:
    - сверху справа: название языка программирования;
    - по центру: код с подсветкой синтаксиса;
    - снизу справа: кнопки «Скачать» и «Копировать».
    """

    def __init__(
        self,
        language: str,
        code: str,
        font_family: str = "Arial",
        theme: str = "dark",
        parent=None
    ):
        super().__init__(parent)
        self.language = (language or "").strip()
        self.code = code.strip("\n")
        self.font_family = font_family
        self.current_theme = theme
        self.setObjectName("CodeBlockWidget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 1. Верхняя панель: язык программирования строго сверху справа
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addStretch(1)

        display_lang = get_display_language(self.language)
        self.lang_label = QLabel(display_lang)
        self.lang_label.setObjectName("CodeLangLabel")
        self.lang_label.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        header.addWidget(self.lang_label, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(header)

        # 2. Центральная область с кодом и подсветкой синтаксиса
        self.code_edit = QTextEdit()
        self.code_edit.setObjectName("CodeTextEdit")
        self.code_edit.setReadOnly(True)
        self.code_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        mono_font = QFont("Consolas", 10)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_edit.setFont(mono_font)
        self.code_edit.setPlainText(self.code)
        self.code_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.code_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        lines_count = max(2, min(26, len(self.code.splitlines())))
        self.code_edit.setFixedHeight(lines_count * 18 + 16)

        self.highlighter = UniversalCodeHighlighter(
            self.code_edit.document(),
            language=self.language,
            theme=self.current_theme
        )
        layout.addWidget(self.code_edit)

        # 3. Нижняя панель: кнопки «Скачать» и «Копировать» строго снизу справа
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.setSpacing(6)
        footer.addStretch(1)

        self.download_btn = QPushButton("Скачать")
        self.download_btn.setObjectName("CodeDownloadBtn")
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.download_btn.setFixedHeight(22)
        self.download_btn.clicked.connect(self._download_code)
        footer.addWidget(self.download_btn, 0, Qt.AlignmentFlag.AlignRight)

        self.copy_btn = QPushButton("Копировать")
        self.copy_btn.setObjectName("CodeCopyBtn")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setFont(QFont(self.font_family, 8, QFont.Weight.Bold))
        self.copy_btn.setFixedHeight(22)
        self.copy_btn.clicked.connect(self._copy_code)
        footer.addWidget(self.copy_btn, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(footer)

        self.set_theme(self.current_theme)

    def _copy_code(self):
        QGuiApplication.clipboard().setText(self.code)
        self.copy_btn.setText("✓ Скопировано")
        QTimer.singleShot(1800, lambda: self.copy_btn.setText("Копировать"))

    def _download_code(self):
        default_name = suggest_filename(self.language, self.code)
        ext = get_extension_for_language(self.language)
        disp = get_display_language(self.language)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить код в файл",
            default_name,
            f"{disp} (*{ext});;Все файлы (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.code + "\n")
            self.download_btn.setText("✓ Скачано")
            QTimer.singleShot(1800, lambda: self.download_btn.setText("Скачать"))
        except Exception as e:
            print(f"[CodeBlock Save Error]: {e}", flush=True)
            self.download_btn.setText("Ошибка")
            QTimer.singleShot(1800, lambda: self.download_btn.setText("Скачать"))

    def set_theme(self, theme: str):
        self.current_theme = theme
        if hasattr(self, "highlighter"):
            self.highlighter.set_theme(theme)

        is_light = (theme == "light")
        if is_light:
            card_bg = "rgba(241, 245, 249, 0.96)"
            card_border = "rgba(15, 23, 42, 0.16)"
            edit_bg = "#ffffff"
            edit_fg = "#0f172a"
            badge_bg = "rgba(15, 23, 42, 0.07)"
            badge_fg = "#334155"
            btn_bg = "rgba(15, 23, 42, 0.06)"
            btn_hover = "rgba(15, 23, 42, 0.13)"
            btn_border = "rgba(15, 23, 42, 0.18)"
            btn_fg = "#0f172a"
        else:
            card_bg = "rgba(13, 15, 20, 0.94)"
            card_border = "rgba(222, 215, 196, 0.22)"
            edit_bg = "#090b0f"
            edit_fg = "#e2e8f0"
            badge_bg = "rgba(222, 215, 196, 0.10)"
            badge_fg = "#ded7c4"
            btn_bg = "rgba(222, 215, 196, 0.08)"
            btn_hover = "rgba(222, 215, 196, 0.18)"
            btn_border = "rgba(222, 215, 196, 0.25)"
            btn_fg = "#ded7c4"

        self.setStyleSheet(f"""
            QFrame#CodeBlockWidget {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel#CodeLangLabel {{
                background-color: {badge_bg};
                color: {badge_fg};
                border: 1px solid {card_border};
                border-radius: 5px;
                padding: 2px 8px;
                letter-spacing: 0.9px;
            }}
            QTextEdit#CodeTextEdit {{
                background-color: {edit_bg};
                color: {edit_fg};
                border: 1px solid {card_border};
                border-radius: 7px;
                padding: 6px;
                selection-background-color: {'#bfdbfe' if is_light else '#334155'};
            }}
            QPushButton#CodeDownloadBtn, QPushButton#CodeCopyBtn {{
                background-color: {btn_bg};
                color: {btn_fg};
                border: 1px solid {btn_border};
                border-radius: 6px;
                padding: 0px 10px;
            }}
            QPushButton#CodeDownloadBtn:hover, QPushButton#CodeCopyBtn:hover {{
                background-color: {btn_hover};
                border: 1px solid {'#0f172a' if is_light else '#ded7c4'};
                color: {'#000000' if is_light else '#ffffff'};
            }}
        """)


def parse_message_blocks(raw_text: str) -> list[tuple[str, object]]:
    """
    Разбирает ответ Акиры на последовательность текстовых блоков и блоков кода:
    [("text", "..."), ("code", ("python", "...")), ...]
    """
    if not raw_text:
        return []

    pattern = re.compile(r"```([a-zA-Z0-9_\-\+#\.]*)[ \t]*\r?\n?(.*?)```", re.DOTALL)
    blocks = []
    last_end = 0

    for match in pattern.finditer(raw_text):
        start, end = match.span()
        if start > last_end:
            txt = raw_text[last_end:start].strip()
            if txt:
                blocks.append(("text", txt))
        lang = match.group(1).strip() or "code"
        code = match.group(2)
        blocks.append(("code", (lang, code)))
        last_end = end

    if last_end < len(raw_text):
        rem = raw_text[last_end:].strip()
        if rem:
            # Если нейросеть не закрыла тройные кавычки в конце ответа
            unclosed = re.match(r"^```([a-zA-Z0-9_\-\+#\.]*)[ \t]*\r?\n(.*)$", rem, re.DOTALL)
            if unclosed:
                lang = unclosed.group(1).strip() or "code"
                blocks.append(("code", (lang, unclosed.group(2))))
            else:
                blocks.append(("text", rem))

    return blocks if blocks else [("text", raw_text)]


def markdown_to_rich_html(text: str, theme: str = "dark") -> str:
    """
    Преобразует базовый Markdown в безопасный HTML для QLabel в Студии:
    заголовки, **жирный**, *курсив*, `inline-код`, списки.
    """
    if not text:
        return ""

    is_light = (theme == "light")
    code_bg = "rgba(15, 23, 42, 0.08)" if is_light else "rgba(255, 255, 255, 0.10)"
    code_fg = "#0f766e" if is_light else "#67e8f9"
    heading_fg = "#111318" if is_light else "#ffffff"

    escaped = html.escape(text)

    # 1. Прячем `inline-code` в плейсхолдеры, чтобы внутри них не срабатывали звёздочки
    inline_codes = []

    def _store_inline(m):
        idx = len(inline_codes)
        snippet = m.group(1)
        inline_codes.append(
            f'<span style="font-family: Consolas, monospace; background-color: {code_bg}; '
            f'color: {code_fg}; padding: 1px 4px; border-radius: 4px;">{snippet}</span>'
        )
        return f"@@INLINE_CODE_{idx}@@"

    escaped = re.sub(r"`([^`\n]+)`", _store_inline, escaped)

    # 2. Обработка построчных конструкций (заголовки и списки)
    formatted_lines = []
    for line in escaped.splitlines():
        h_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if h_match:
            level = len(h_match.group(1))
            size_pt = 13 if level <= 2 else 12
            formatted_lines.append(
                f'<div style="font-size: {size_pt}pt; font-weight: bold; '
                f'color: {heading_fg}; margin-top: 4px; margin-bottom: 2px;">{h_match.group(2)}</div>'
            )
            continue

        bullet_match = re.match(r"^\s*[-*•]\s+(.+)$", line)
        if bullet_match:
            formatted_lines.append(f"&nbsp;&nbsp;•&nbsp;{bullet_match.group(1)}")
            continue

        formatted_lines.append(line)

    result = "<br>".join(formatted_lines)

    # 3. **жирный** и *курсив*
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    result = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", result)

    # 4. Возвращаем inline-код обратно
    for idx, html_span in enumerate(inline_codes):
        result = result.replace(f"@@INLINE_CODE_{idx}@@", html_span)

    return result


def print_markdown_console(text: str, speaker: str = "Акира"):
    """Красиво выводит Markdown-ответ (включая таблицы и блоки кода) в консоль."""
    if not text:
        return

    if _HAS_RICH and _RICH_CONSOLE is not None:
        try:
            _RICH_CONSOLE.print(f"\n[bold cyan]{speaker}:[/bold cyan]")
            _RICH_CONSOLE.print(RichMarkdown(text))
            return
        except Exception:
            pass

    # Аккуратный ANSI-фолбек, если rich не установлен
    separator = "─" * 52
    print(f"\n\033[96m{speaker}:\033[0m\n{separator}\n{text}\n{separator}", flush=True)