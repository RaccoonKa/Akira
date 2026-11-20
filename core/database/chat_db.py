import os
import shutil
import sqlite3
import threading
from datetime import datetime
from core.utils.config import get_user_data_path


def get_db_path() -> str:
    """Возвращает путь к БД внутри sql папки пользовательских данных."""
    sql_dir = get_user_data_path("sql")
    try:
        os.makedirs(sql_dir, exist_ok=True)
    except (PermissionError, OSError):
        sql_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Akira", "sql")
        os.makedirs(sql_dir, exist_ok=True)

    new_path = os.path.join(sql_dir, "studio_chats.db")
    old_path = get_user_data_path("studio_chats.db")

    if os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            shutil.move(old_path, new_path)
            for suffix in ("-wal", "-shm"):
                if os.path.exists(old_path + suffix):
                    shutil.move(old_path + suffix, new_path + suffix)
        except Exception:
            pass

    return new_path


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
        conn.execute("PRAGMA foreign_keys = ON;")
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
                        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE ON UPDATE CASCADE
                    );
                """)

                # Миграция: проверяем поддержку ON UPDATE CASCADE для старых БД
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='messages'")
                msg_table_row = cursor.fetchone()
                if msg_table_row and "ON UPDATE CASCADE" not in msg_table_row[0]:
                    cursor.execute("PRAGMA foreign_keys=OFF;")
                    cursor.execute("ALTER TABLE messages RENAME TO messages_old;")
                    cursor.execute("""
                        CREATE TABLE messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            session_id INTEGER NOT NULL,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            attached_file TEXT,
                            emotion TEXT DEFAULT 'neutral',
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE ON UPDATE CASCADE
                        );
                    """)
                    cursor.execute("""
                        INSERT INTO messages (id, session_id, role, content, attached_file, emotion, created_at)
                        SELECT id, session_id, role, content, attached_file, emotion, created_at FROM messages_old;
                    """)
                    cursor.execute("DROP TABLE messages_old;")
                    cursor.execute("PRAGMA foreign_keys=ON;")

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);")

                # Очистка сиротских сообщений от ранее некорректно удалённых диалогов
                cursor.execute("DELETE FROM messages WHERE session_id NOT IN (SELECT id FROM sessions);")

                # Если сессий нет вовсе, сбрасываем и счетчики автоинкремента
                cursor.execute("SELECT COUNT(*) FROM sessions;")
                if cursor.fetchone()[0] == 0:
                    cursor.execute("DELETE FROM messages;")
                    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('sessions', 'messages');")

                conn.commit()
            finally:
                conn.close()

    def resequence_sessions(self):
        """Сбрасывает последовательность автоинкремента, если база диалогов пуста."""
        with self.db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sessions")
                if cursor.fetchone()[0] == 0:
                    cursor.execute("DELETE FROM messages")
                    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('sessions', 'messages')")
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
                cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

                cursor.execute("SELECT COUNT(*) FROM sessions")
                remaining_count = cursor.fetchone()[0]
                if remaining_count == 0:
                    cursor.execute("DELETE FROM messages")
                    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('sessions', 'messages')")
                    print(f"[StudioDB] Диалог #{session_id} удалён. Все диалоги очищены, счетчик ID сброшен на 1")
                else:
                    print(f"[StudioDB] Диалог #{session_id} и его история удалены (осталось диалогов: {remaining_count})")
                conn.commit()
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