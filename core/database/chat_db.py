import os
import sqlite3
import threading
from datetime import datetime


def get_db_path() -> str:
    """Возвращает фиксированный путь к БД внутри папки personal_data проекта."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    data_dir = os.path.join(base_dir, "personal_data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "studio_chats.db")


class StudioChatDatabase:
    """Потокобезопасная локальная SQLite база данных для чатов Студии."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path = get_db_path()
        self.db_lock = threading.Lock()
        self._init_db()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA foreign_keys=ON;")

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        model TEXT NOT NULL DEFAULT 'hikari',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        attached_file TEXT,
                        emotion TEXT DEFAULT 'neutral',
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                    );
                """)

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);")
                conn.commit()
            finally:
                conn.close()

    def create_session(self, title: str = "Новый диалог", model: str = "hikari") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (title, model, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (title, model, now, now)
                )
                conn.commit()
                new_id = cursor.lastrowid
                print(f"[StudioDB] Создан новый диалог #{new_id} ({title})")
                return new_id
            finally:
                conn.close()

    def get_sessions(self) -> list:
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, model, created_at, updated_at,
                           (SELECT COUNT(*) FROM messages WHERE session_id = sessions.id) as msg_count
                    FROM sessions
                    ORDER BY updated_at DESC
                """)
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_session(self, session_id: int):
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def update_session_title(self, session_id: int, title: str):
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (title.strip(), session_id))
                conn.commit()
                print(f"[StudioDB] Диалог #{session_id} переименован в '{title.strip()}'")
            finally:
                conn.close()

    def delete_session(self, session_id: int):
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                conn.commit()
                print(f"[StudioDB] Диалог #{session_id} удалён")
            finally:
                conn.close()

    def add_message(self, session_id: int, role: str, content: str, attached_file: str = None, emotion: str = "neutral") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO messages (session_id, role, content, attached_file, emotion, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, role, content, attached_file, emotion, now))
                cursor.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_messages(self, session_id: int) -> list:
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
                return [dict(r) for r in cursor.fetchall()]
            finally:
                conn.close()

    def get_message_count(self, session_id: int) -> int:
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
                res = cursor.fetchone()
                return res[0] if res else 0
            finally:
                conn.close()


studio_db = StudioChatDatabase()