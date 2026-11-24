import os
import re
from gui.ui_helpers import MONO_CSS_FAMILY, get_monospace_font, get_ui_fallback_font
import html
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QRegularExpression, QByteArray
from PyQt6.QtGui import (
    QFont, QColor, QSyntaxHighlighter, QTextCharFormat,
    QGuiApplication, QIcon, QPixmap, QPainter
)
from PyQt6.QtSvg import QSvgRenderer

try:
    from rich.console import Console
    from rich.markdown import Markdown as RichMarkdown
    _HAS_RICH = True
    _RICH_CONSOLE = Console()
except ImportError:
    _HAS_RICH = False
    _RICH_CONSOLE = None


# --- SVG Иконки для кнопок шапки кода (2px line, 24x24) ---
SVG_COPY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
</svg>"""

SVG_CHECK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="20 6 9 17 4 12"></polyline>
</svg>"""

SVG_DOWNLOAD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
  <polyline points="7 10 12 15 17 10"></polyline>
  <line x1="12" y1="15" x2="12" y2="3"></line>
</svg>"""

SVG_WRAP = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="3" y1="6" x2="21" y2="6"></line>
  <path d="M3 12h15a3 3 0 1 1 0 6h-4"></path>
  <polyline points="16 16 14 18 16 20"></polyline>
</svg>"""

SVG_COLLAPSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="4 14 12 6 20 14"></polyline>
</svg>"""

SVG_EXPAND = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="4 10 12 18 20 10"></polyline>
</svg>"""


def _render_svg(svg_xml: str, color: str, size: int = 14) -> QIcon:
    xml = svg_xml.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(xml.encode("utf-8")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


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
    "py": "python",
    "python": "python",
    "cs": "C#",
    "csharp": "C#",
    "c#": "C#",
    "cpp": "C++",
    "c++": "C++",
    "c": "C",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "ps1": "PowerShell",
    "powershell": "PowerShell",
    "sh": "Bash",
    "bash": "Bash",
    "zsh": "Zsh",
    "rust": "Rust",
    "rs": "Rust",
    "go": "Go",
    "golang": "Go",
    "html": "HTML",
    "css": "CSS",
    "json": "JSON",
    "sql": "SQL",
    "md": "Markdown",
    "markdown": "Markdown",
    "plaintext": "Text",
    "text": "Text",
}

# --- Палитра языков (тёмная: мягкий неон, светлая: глубокие насыщенные сапфировые/аметистовые тона) ---
LANGUAGE_PALETTE = {
    "python":     {"dark": "#38bdf8", "light": "#0369a1"},  # Небесно-голубой / сапфировый
    "py":         {"dark": "#38bdf8", "light": "#0369a1"},
    "csharp":     {"dark": "#c084fc", "light": "#7e22ce"},  # Лавандовый / аметистовый
    "cs":         {"dark": "#c084fc", "light": "#7e22ce"},
    "c#":         {"dark": "#c084fc", "light": "#7e22ce"},
    "javascript": {"dark": "#facc15", "light": "#b45309"},  # Золотистый / тёмно-янтарный
    "js":         {"dark": "#facc15", "light": "#b45309"},
    "typescript": {"dark": "#60a5fa", "light": "#1d4ed8"},  # Чистый синий
    "ts":         {"dark": "#60a5fa", "light": "#1d4ed8"},
    "cpp":        {"dark": "#f472b6", "light": "#be185d"},  # Малиново-розовый
    "c++":        {"dark": "#f472b6", "light": "#be185d"},
    "c":          {"dark": "#f472b6", "light": "#be185d"},
    "rust":       {"dark": "#fb923c", "light": "#c2410c"},  # Терракотовый
    "rs":         {"dark": "#fb923c", "light": "#c2410c"},
    "go":         {"dark": "#2dd4bf", "light": "#0f766e"},  # Бирюзовый
    "golang":     {"dark": "#2dd4bf", "light": "#0f766e"},
    "html":       {"dark": "#fb7185", "light": "#e11d48"},  # Кораллово-оранжевый
    "css":        {"dark": "#818cf8", "light": "#4338ca"},  # Индиго
    "scss":       {"dark": "#818cf8", "light": "#4338ca"},
    "json":       {"dark": "#fde047", "light": "#a16207"},  # Песочный
    "sql":        {"dark": "#a78bfa", "light": "#6d28d9"},  # Фиолетовый
    "bash":       {"dark": "#4ade80", "light": "#15803d"},  # Изумрудный
    "sh":         {"dark": "#4ade80", "light": "#15803d"},
    "powershell": {"dark": "#38bdf8", "light": "#0284c7"},
    "ps1":        {"dark": "#38bdf8", "light": "#0284c7"},
    "default":    {"dark": "#ded7c4", "light": "#475569"}   # Кремовый / графитовый
}


def get_extension_for_language(language: str) -> str:
    lang = (language or "").strip().lower()
    return LANGUAGE_EXTENSIONS.get(lang, ".txt")


def get_display_language(language: str) -> str:
    raw = (language or "").strip()
    if not raw:
        return "code"
    low = raw.lower()
    return LANGUAGE_DISPLAY_NAMES.get(low, raw)


def get_language_color(language: str, theme: str = "dark") -> str:
    lang = (language or "").strip().lower()
    t = "light" if theme == "light" else "dark"
    pair = LANGUAGE_PALETTE.get(lang, LANGUAGE_PALETTE["default"])
    return pair[t]


def suggest_filename(language: str, code: str) -> str:
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
    """
    Универсальный подсветчик синтаксиса с поддержкой тройных кавычек в Python,
    многострочных комментариев и адаптированных палитр.
    """

    DARK_COLORS = {
        "keyword": "#c792ea",
        "builtin": "#82aaff",
        "function": "#67e8f9",
        "decorator": "#facc15",
        "string": "#ecc48d",
        "number": "#f78c6c",
        "comment": "#637777",
        "operator": "#89ddff",
        "md_heading": "#facc15",
        "md_bold": "#f472b6",
        "md_list": "#38bdf8",
    }

    LIGHT_COLORS = {
        "keyword": "#7c3aed",
        "builtin": "#0284c7",
        "function": "#0f766e",
        "decorator": "#b45309",
        "string": "#15803d",
        "number": "#c2410c",
        "comment": "#64748b",
        "operator": "#0369a1",
        "md_heading": "#b45309",
        "md_bold": "#be185d",
        "md_list": "#0284c7",
    }

    KEYWORDS = [
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else", "except",
        "finally", "for", "from", "global", "if", "import", "in", "is",
        "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
        "while", "with", "yield", "self", "cls",
        "const", "let", "var", "function", "export", "default", "new", "this",
        "super", "typeof", "instanceof", "void", "null", "undefined", "true", "false",
        "public", "private", "protected", "internal", "static", "readonly",
        "override", "virtual", "abstract", "interface", "struct", "enum",
        "namespace", "using", "switch", "case", "throw", "catch", "fn", "mut",
        "pub", "impl", "trait", "match", "func", "package", "defer", "go",
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

        self.triple_single = None
        self.triple_double = None
        self.comment_start = None
        self.comment_end = None
        self.multiline_str_fmt = str_fmt
        self.multiline_comment_fmt = comment_fmt

        if self.language in ("md", "markdown"):
            md_h_fmt = self._make_format(palette["md_heading"], bold=True)
            md_b_fmt = self._make_format(palette["md_bold"], bold=True)
            md_l_fmt = self._make_format(palette["md_list"], bold=True)
            self.rules.append((QRegularExpression(r"^#{1,6}\s+.*$"), md_h_fmt))
            self.rules.append((QRegularExpression(r"\*\*[^*]+\*\*"), md_b_fmt))
            self.rules.append((QRegularExpression(r"^\s*[-*+]\s+"), md_l_fmt))
            self.rules.append((QRegularExpression(r"`[^`]+`"), str_fmt))
            return

        for kw in self.KEYWORDS:
            self.rules.append((QRegularExpression(rf"\b{re.escape(kw)}\b"), kw_fmt))

        for b in self.BUILTINS:
            self.rules.append((QRegularExpression(rf"\b{re.escape(b)}\b"), builtin_fmt))

        self.rules.append((
            QRegularExpression(r"\b(?:def|class|function|fn|struct|interface|enum|func)\s+([A-Za-z_][A-Za-z0-9_]*)"),
            func_fmt
        ))
        self.rules.append((QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_\.]*"), dec_fmt))
        self.rules.append((QRegularExpression(r"\b(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?)\b"), num_fmt))

        if self.language in ("html", "htm", "xml", "xaml", "svg", "jsx", "tsx"):
            self.rules.append((QRegularExpression(r"</?[A-Za-z][A-Za-z0-9\-]*\b[^>]*>"), builtin_fmt))

        # Однострочные строки
        self.rules.append((QRegularExpression(r'(?:[fFrRbBuU])?"(?:\\.|[^"\\])*"'), str_fmt))
        self.rules.append((QRegularExpression(r"(?:[fFrRbBuU])?'(?:\\.|[^'\\])*'"), str_fmt))
        self.rules.append((QRegularExpression(r"`(?:\\.|[^`\\])*`"), str_fmt))

        # Комментарии
        self.rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))
        self.rules.append((QRegularExpression(r"//[^\n]*"), comment_fmt))
        if self.language in ("sql", "sqlite", "postgres", "mysql", "lua"):
            self.rules.append((QRegularExpression(r"--[^\n]*"), comment_fmt))

        # Многострочные докстринги Python (""" и ''')
        if self.language in ("py", "python", ""):
            self.triple_double = QRegularExpression(r'"""')
            self.triple_single = QRegularExpression(r"'''")

        # C-style блочные комментарии /* ... */
        self.comment_start = QRegularExpression(r"/\*")
        self.comment_end = QRegularExpression(r"\*/")

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                group_idx = 1 if match.lastCapturedIndex() >= 1 else 0
                start = match.capturedStart(group_idx)
                length = match.capturedLength(group_idx)
                if start >= 0 and length > 0:
                    self.setFormat(start, length, fmt)

        # Обработка многострочных блоков (состояния: 0=none, 1=/*, 2=""" , 3=''')
        self.setCurrentBlockState(0)

        # 1. Тройные кавычки """ (state=2)
        if self.triple_double:
            self._handle_multiline_state(text, self.triple_double, self.triple_double, 2, self.multiline_str_fmt)
        # 2. Тройные кавычки ''' (state=3)
        if self.triple_single and self.currentBlockState() == 0:
            self._handle_multiline_state(text, self.triple_single, self.triple_single, 3, self.multiline_str_fmt)
        # 3. Блочный комментарий /* ... */ (state=1)
        if self.comment_start and self.currentBlockState() == 0:
            self._handle_multiline_state(text, self.comment_start, self.comment_end, 1, self.multiline_comment_fmt)

    def _handle_multiline_state(self, text, start_re, end_re, state_val, fmt):
        start_idx = 0
        if self.previousBlockState() != state_val:
            match = start_re.match(text)
            start_idx = match.capturedStart() if match.hasMatch() else -1
        else:
            start_idx = 0

        while start_idx >= 0:
            end_match = end_re.match(text, start_idx + (3 if (self.previousBlockState() != state_val and state_val in (2, 3)) else (2 if self.previousBlockState() != state_val else 0)))
            end_idx = end_match.capturedStart() if end_match.hasMatch() else -1
            if end_idx == -1:
                self.setCurrentBlockState(state_val)
                comment_len = len(text) - start_idx
            else:
                comment_len = end_idx - start_idx + end_match.capturedLength()

            self.setFormat(start_idx, comment_len, fmt)
            next_match = start_re.match(text, start_idx + comment_len)
            start_idx = next_match.capturedStart() if next_match.hasMatch() else -1


class CodeBlockWidget(QFrame):
    """
    Монолитная минималистичная карточка кода для Akira Studio:
    - Единая компактная верхняя шапка (язык с цветной подложкой слева; кнопки действий справа).
    - Тонкие SVG-кнопки 24x24: Перенос строк, Сворачивание/Разворачивание, Скачивание, Копирование.
    - Динамическая высота (аккуратный вид для 1 строки, авто-расширение, сворачивание в 1 полоску).
    - Монолитный фон без рамок-в-рамке.
    - Кастомные ультратонкие 4px скроллбары.
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
        self.is_collapsed = False
        self.is_wrapped = False
        self.setObjectName("CodeBlockWidget")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 6, 10, 8)
        self.main_layout.setSpacing(4)

        # 1. Единая верхняя шапка
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(2, 2, 2, 2)
        self.header_layout.setSpacing(6)

        # Индикатор и название языка слева
        self.lang_container = QFrame()
        self.lang_container.setObjectName("LangBadge")
        lang_box = QHBoxLayout(self.lang_container)
        lang_box.setContentsMargins(6, 2, 8, 2)
        lang_box.setSpacing(6)

        self.lang_dot = QLabel()
        self.lang_dot.setFixedSize(6, 6)
        self.lang_dot.setObjectName("LangDot")
        lang_box.addWidget(self.lang_dot)

        display_lang = get_display_language(self.language)
        self.lang_label = QLabel(display_lang)
        self.lang_label.setObjectName("CodeLangLabel")
        self.lang_label.setFont(get_monospace_font(8))
        lang_box.addWidget(self.lang_label)

        self.header_layout.addWidget(self.lang_container, 0, Qt.AlignmentFlag.AlignLeft)
        self.header_layout.addStretch(1)

        # SVG Кнопки справа (24x24 px)
        # А: Перенос строк (Wrap)
        self.wrap_btn = QPushButton()
        self.wrap_btn.setObjectName("CodeToolBtn")
        self.wrap_btn.setFixedSize(24, 24)
        self.wrap_btn.setToolTip("Перенос строк (Word Wrap)")
        self.wrap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wrap_btn.clicked.connect(self._toggle_wrap)
        self.header_layout.addWidget(self.wrap_btn)

        # Б: Свернуть / Развернуть (Collapse)
        self.collapse_btn = QPushButton()
        self.collapse_btn.setObjectName("CodeToolBtn")
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.setToolTip("Свернуть / Развернуть блок")
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        self.header_layout.addWidget(self.collapse_btn)

        # В: Скачать (Download)
        self.download_btn = QPushButton()
        self.download_btn.setObjectName("CodeToolBtn")
        self.download_btn.setFixedSize(24, 24)
        self.download_btn.setToolTip("Скачать код в файл")
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self._download_code)
        self.header_layout.addWidget(self.download_btn)

        # Г: Копировать (Copy)
        self.copy_btn = QPushButton()
        self.copy_btn.setObjectName("CodeToolBtn")
        self.copy_btn.setFixedSize(24, 24)
        self.copy_btn.setToolTip("Копировать код")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self._copy_code)
        self.header_layout.addWidget(self.copy_btn)

        self.main_layout.addLayout(self.header_layout)

        # 2. Монолитная область с кодом
        self.code_edit = QTextEdit()
        self.code_edit.setObjectName("CodeTextEdit")
        self.code_edit.setReadOnly(True)
        self.code_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        self.code_edit.setFont(get_monospace_font(10))
        self.code_edit.setPlainText(self.code)
        self.code_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.code_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        lines_count = len(self.code.splitlines())
        # Динамическая высота: для 1 строки компактно (28px), максимум до 26 строк (около 460px)
        if lines_count <= 1:
            self.ideal_height = 28
        else:
            capped_lines = min(26, lines_count)
            self.ideal_height = capped_lines * 17 + 10

        self.code_edit.setFixedHeight(self.ideal_height)

        self.highlighter = UniversalCodeHighlighter(
            self.code_edit.document(),
            language=self.language,
            theme=self.current_theme
        )
        self.main_layout.addWidget(self.code_edit)

        self.set_theme(self.current_theme)

    def _toggle_wrap(self):
        self.is_wrapped = not self.is_wrapped
        if self.is_wrapped:
            self.code_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        else:
            self.code_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.update_icons()

    def _toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.code_edit.setVisible(False)
            self.collapse_btn.setToolTip("Развернуть блок")
        else:
            self.code_edit.setVisible(True)
            self.code_edit.setFixedHeight(self.ideal_height)
            self.collapse_btn.setToolTip("Свернуть блок")
        self.update_icons()

    def _copy_code(self):
        QGuiApplication.clipboard().setText(self.code)
        is_light = (self.current_theme == "light")
        acc = "#15803d" if is_light else "#4ade80"
        self.copy_btn.setIcon(_render_svg(SVG_CHECK, acc, 14))
        QTimer.singleShot(1600, self.update_icons)

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
            is_light = (self.current_theme == "light")
            acc = "#15803d" if is_light else "#4ade80"
            self.download_btn.setIcon(_render_svg(SVG_CHECK, acc, 14))
            QTimer.singleShot(1600, self.update_icons)
        except Exception as e:
            print(f"[CodeBlock Save Error]: {e}", flush=True)

    def update_icons(self):
        is_light = (self.current_theme == "light")
        icon_col = "#64748b" if is_light else "#a6a092"

        # Иконка переноса строк
        wrap_col = ("#0284c7" if is_light else "#67e8f9") if self.is_wrapped else icon_col
        self.wrap_btn.setIcon(_render_svg(SVG_WRAP, wrap_col, 13))

        # Иконка сворачивания
        col_svg = SVG_EXPAND if self.is_collapsed else SVG_COLLAPSE
        self.collapse_btn.setIcon(_render_svg(col_svg, icon_col, 13))

        # Иконки скачивания и копирования
        self.download_btn.setIcon(_render_svg(SVG_DOWNLOAD, icon_col, 13))
        self.copy_btn.setIcon(_render_svg(SVG_COPY, icon_col, 13))

    def set_theme(self, theme: str):
        self.current_theme = theme
        if hasattr(self, "highlighter"):
            self.highlighter.set_theme(theme)

        is_light = (theme == "light")
        lang_color = get_language_color(self.language, theme)

        if is_light:
            card_bg = "#f8fafc"
            card_border = "rgba(15, 23, 42, 0.08)"
            header_divider = "rgba(15, 23, 42, 0.06)"
            text_color = "#0f172a"
            selection_bg = "#bfdbfe"
            scrollbar_handle = "rgba(15, 23, 42, 0.22)"
            scrollbar_hover = "rgba(15, 23, 42, 0.38)"
            tool_hover = "rgba(15, 23, 42, 0.08)"
        else:
            card_bg = "#090b0f"
            card_border = "rgba(222, 215, 196, 0.14)"
            header_divider = "rgba(222, 215, 196, 0.08)"
            text_color = "#e2e8f0"
            selection_bg = "#334155"
            scrollbar_handle = "rgba(222, 215, 196, 0.22)"
            scrollbar_hover = "rgba(222, 215, 196, 0.40)"
            tool_hover = "rgba(222, 215, 196, 0.12)"

        # Подложка языка: цвет языка с прозрачностью ~10-12%
        c = QColor(lang_color)
        badge_bg = f"rgba({c.red()}, {c.green()}, {c.blue()}, 0.12)"

        self.setStyleSheet(f"""
            QFrame#CodeBlockWidget {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
            }}
            QFrame#LangBadge {{
                background-color: {badge_bg};
                border-radius: 4px;
                border: none;
            }}
            QLabel#LangDot {{
                background-color: {lang_color};
                border-radius: 3px;
                border: none;
            }}
            QLabel#CodeLangLabel {{
                color: {lang_color};
                background: transparent;
                border: none;
                font-weight: 500;
            }}
            QPushButton#CodeToolBtn {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 3px;
            }}
            QPushButton#CodeToolBtn:hover {{
                background-color: {tool_hover};
            }}
            QTextEdit#CodeTextEdit {{
                background-color: transparent;
                color: {text_color};
                border: none;
                padding: 4px 2px 2px 2px;
                selection-background-color: {selection_bg};
            }}
            /* Кастомные тонкие полупрозрачные скроллбары 4px */
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {scrollbar_handle};
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scrollbar_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 4px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {scrollbar_handle};
                border-radius: 2px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {scrollbar_hover};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """)

        self.update_icons()


def detect_code_language(code: str) -> str:
    if not code:
        return "code"
    low = code.lower()
    if re.search(r'\b(def|import|elif|from\s+\w+\s+import|print\s*\()\b', code):
        return "python"
    if re.search(r'\b(const|let|var|function|console\.log|=>)\b', code):
        return "javascript"
    if re.search(r'<\/?(html|div|span|p|head|body|script|style)\b', low):
        return "html"
    if re.search(r'\b(select\s+.+\s+from|insert\s+into|update\s+.+\s+set|create\s+table)\b', low):
        return "sql"
    if re.search(r'\b(namespace|using\s+system|public\s+class|console\.writeline)\b', low):
        return "csharp"
    if re.search(r'\b(fn\s+main|println!|let\s+mut)\b', code):
        return "rust"
    if re.search(r'\b(package\s+main|func\s+main)\b', code):
        return "go"
    if re.search(r'\b(curl|chmod|grep|sudo|apt-get|npm\s+run|pip\s+install)\b', low):
        return "bash"
    return "code"


def parse_message_blocks(raw_text: str) -> list[tuple[str, object]]:
    if not raw_text:
        return []

    # Регулярка для кода, картинок и аудио:
    # 1. ```lang ... ```
    # 2. [AKIRA_IMAGE:filepath]
    # 3. [AKIRA_AUDIO:filepath]
    pattern = re.compile(
        r"(?:```[ \t]*([a-zA-Z0-9_\-\+#\.]*)[ \t]*\r?\n?(.*?)```)|"
        r"(?:\[AKIRA_IMAGE:([^\]]+)\])|"
        r"(?:\[AKIRA_AUDIO:([^\]]+)\])",
        re.DOTALL
    )
    blocks = []
    last_end = 0

    for match in pattern.finditer(raw_text):
        start, end = match.span()
        if start > last_end:
            txt = raw_text[last_end:start].strip()
            if txt:
                blocks.append(("text", txt))

        if match.group(3):
            # [AKIRA_IMAGE:filepath]
            img_path = match.group(3).strip()
            blocks.append(("image", img_path))
        elif match.group(4):
            # [AKIRA_AUDIO:filepath]
            aud_path = match.group(4).strip()
            blocks.append(("audio", aud_path))
        else:
            lang = match.group(1).strip()
            code = match.group(2)
            if not lang or lang.lower() == "code":
                lang = detect_code_language(code)
            blocks.append(("code", (lang, code)))

        last_end = end

    if last_end < len(raw_text):
        rem = raw_text[last_end:].strip()
        if rem:
            unclosed = re.match(r"^```[ \t]*([a-zA-Z0-9_\-\+#\.]*)[ \t]*\r?\n?(.*)$", rem, re.DOTALL)
            if unclosed:
                lang = unclosed.group(1).strip()
                code = unclosed.group(2)
                if not lang or lang.lower() == "code":
                    lang = detect_code_language(code)
                blocks.append(("code", (lang, code)))
            else:
                blocks.append(("text", rem))

    return blocks if blocks else [("text", raw_text)]


def markdown_to_rich_html(text: str, theme: str = "dark") -> str:
    if not text:
        return ""

    is_light = (theme == "light")
    code_bg = "rgba(15, 23, 42, 0.08)" if is_light else "rgba(255, 255, 255, 0.10)"
    code_fg = "#0f766e" if is_light else "#67e8f9"
    heading_fg = "#111318" if is_light else "#ffffff"

    escaped = html.escape(text)
    inline_codes = []

    def _store_inline(m):
        idx = len(inline_codes)
        snippet = m.group(1)
        inline_codes.append(
            f'<span style="font-family: {MONO_CSS_FAMILY}; background-color: {code_bg}; '
            f'color: {code_fg}; padding: 1px 4px; border-radius: 4px;">{snippet}</span>'
        )
        return f"@@INLINE_CODE_{idx}@@"

    escaped = re.sub(r"`([^`\n]+)`", _store_inline, escaped)

    formatted_lines = []
    for line in escaped.splitlines():
        h_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if h_match:
            level = len(h_match.group(1))
            size_pt = 13 if level <= 2 else 12
            formatted_lines.append(
                f'<div style="font-size: {size_pt}pt; '
                f'color: {heading_fg}; margin-top: 4px; margin-bottom: 2px;">{h_match.group(2)}</div>'
            )
            continue

        bullet_match = re.match(r"^\s*[-*•]\s+(.+)$", line)
        if bullet_match:
            formatted_lines.append(f"&nbsp;&nbsp;•&nbsp;{bullet_match.group(1)}")
            continue

        formatted_lines.append(line)

    result = "<br>".join(formatted_lines)
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    result = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", result)

    for idx, html_span in enumerate(inline_codes):
        result = result.replace(f"@@INLINE_CODE_{idx}@@", html_span)

    return result


def print_markdown_console(text: str, speaker: str = "Акира"):
    if not text:
        return

    if _HAS_RICH and _RICH_CONSOLE is not None:
        try:
            _RICH_CONSOLE.print(f"\n[bold cyan]{speaker}:[/bold cyan]")
            _RICH_CONSOLE.print(RichMarkdown(text))
            return
        except Exception:
            pass

    separator = "─" * 52
    print(f"\n\033[96m{speaker}:\033[0m\n{separator}\n{text}\n{separator}", flush=True)
