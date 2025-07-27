import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .utils import MyError, get_environment_name, init_log, load_env

# Load environment variables
environment = get_environment_name()
load_env(environment)

DB_PATH = os.getenv("TLCR_DB_PATH", "settings.db")
LOGPATH = os.getenv("TLCR_LOGPATH", ".")
LOGLEVEL = os.getenv("TLCR_LOG_LEVEL", 'INFO').upper()
BACKUP_DIR = os.getenv("TLCR_BACKUP_PATH", "static/db.bak")

log = init_log('db_utils', LOGPATH, LOGLEVEL)


def init_db(db_path=DB_PATH, drop_table=True):
    """
    Инициализирует базу данных SQLite.  Выполняет инициализацию только один раз.

    Args:
        db_path (str): Путь к файлу базы данных.
        drop_table (bool): Флаг, указывающий на необходимость удаления существующей таблицы перед созданием новой.
    """
    if hasattr(init_db, "_initialized") and init_db._initialized:  # Check if already initialized
        return

    try:
        with sqlite3.connect(db_path) as conn:
            run_initialization(conn, drop_table, db_path)
        log.info(f"Таблицы базы данных '{db_path}.schedules,chats' успешно {'пересозданы' if drop_table else 'установлены'}")
        init_db._initialized = True # Mark as initialized
    except sqlite3.Error as e:
        log.error(f"Ошибка инициализации БД '{db_path}': %s", str(e))

def run_create_table(arg1, cursor, conn):
    sql = f'''CREATE TABLE {arg1}'''
    cursor.execute(sql)
    conn.commit()

def run_initialization(conn, drop_table, db_path):
    """
    Выполняет инициализацию базы данных.

    Args:
        conn (sqlite3.Connection): Соединение с базой данных.
        drop_table (bool): Флаг, указывающий на необходимость удаления существующей таблицы.
        db_path (str): Путь к файлу базы данных.
    """
    conn.execute("PRAGMA journal_mode=WAL;") # Add WAL mode for better concurrency
    cursor = conn.cursor()
    cursor.execute("PRAGMA encoding = 'UTF-8';")

    if drop_table:
        cursor.execute('DROP TABLE schedules;')
        conn.commit()
        log.info(f'удалена таблица "schedules" из БД "{db_path}"')

    run_create_table(
        f'''{'' if drop_table else 'IF NOT EXISTS'} schedules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cron TEXT NOT NULL,
                        message TEXT NOT NULL,
                        modifier TEXT,
                        last_fired TIMESTAMP,
                        chat_id INTEGER NOT NULL,
                        FOREIGN KEY (chat_id) REFERENCES chats(id)
                    )''',
        cursor,
        conn,
    )
    run_create_table(
        f'''{"" if drop_table else "IF NOT EXISTS"}  chats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        chat_id INTEGER NOT NULL UNIQUE
                    )''',
        cursor,
        conn,
    )


def get_schedules(db_path) -> list:
    """
    Возвращает список расписаний из базы данных.

    Args:
        db_path (str): Путь к файлу базы данных.

    Returns:
        list: Список расписаний.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier, last_fired, chat_id FROM schedules")
            return [{"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3], "last_fired": row[4], "chat_id": row[5]} for row in cursor.fetchall()]
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписаний: %s", str(e))
        return []

def get_schedule(schedule_id, db_path) -> dict or None:
    """
    Возвращает расписание по его ID.

    Args:
        schedule_id (int): ID расписания.
        db_path (str): Путь к файлу базы данных.

    Returns:
        dict or None: Расписание в виде словаря или None, если расписание не найдено.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier, last_fired, chat_id FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3], "last_fired": row[4], "chat_id": row[5]}
            else:
                return None
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписания: %s", str(e))
        return []

def add_schedule(cron, message, modifier, chat_id, db_path):
    """
    Добавляет новое расписание в базу данных.

    Args:
        cron (str): CRON выражение.
        message (str): Сообщение.
        modifier (str): Модификатор.
        chat_id (int): ID чата.
        db_path (str): Путь к файлу базы данных.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Проверяем, есть ли записи в таблице chats
            cursor.execute("SELECT COUNT(*) FROM chats")
            chats_count = cursor.fetchone()[0]
            if chats_count == 0:
                raise MyError("Нельзя добавить расписание: таблица chats пуста. Сначала добавьте хотя бы один чат.")
            cursor.execute("INSERT INTO schedules (cron, message, modifier, chat_id) VALUES (?, ?, ?, ?)", (cron, message, modifier, chat_id))
            conn.commit()
            log.info("Добавлено новое расписание: %s, %s, %s, %s", cron, message, modifier, chat_id)
    except sqlite3.Error as e:
        log.error("Ошибка при добавлении расписания: %s", str(e))
    except MyError as me:
        log.error(str(me))
        raise

def delete_schedule(schedule_id, db_path):
    """
    Удаляет расписание с id=schedule_id из базы данных.

    Args:
        schedule_id (int): ID расписания.
        db_path (str): Путь к файлу базы данных.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            log.info("Удалено расписание с ID: %d", schedule_id)
    except sqlite3.Error as e:
        log.error("Ошибка при удалении расписания: %s", str(e))

def get_chats(db_path) -> list:
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, chat_id FROM chats")
            return [{"id": row[0], "name": row[1], "chat_id": row[2]} for row in cursor.fetchall()]
    except sqlite3.Error as e:
        log.error("Ошибка при получении чатов: %s", str(e))
        return []

def add_chat(name, chat_id, db_path):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO chats (name, chat_id) VALUES (?, ?)", (name, chat_id))
            conn.commit()
            log.info("Добавлен новый чат: %s, %s", name, chat_id)
    except sqlite3.Error as e:
        log.error("Ошибка при добавлении чата: %s", str(e))

def delete_chat(chat_id, db_path):
    """
    Удаляет чат по ID и все связанные с ним расписания.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Сначала удаляем все связанные расписания
            cursor.execute("DELETE FROM schedules WHERE chat_id = ?", (chat_id,))
            # Затем удаляем сам чат
            cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            conn.commit()
            log.info("Удалён чат с ID: %s и все связанные с ним расписания", chat_id)
    except sqlite3.Error as e:
        log.error("Ошибка при удалении чата: %s", str(e))
        raise MyError(f"Ошибка при удалении чата: {e}")

def update_last_fired(schedule_id, db_path):
    """
    Обновляет поле last_fired для расписания с id=schedule_id.

    Args:
        schedule_id (int): ID расписания.
        db_path (str): Путь к файлу базы данных.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now()
            cursor.execute("UPDATE schedules SET last_fired = ? WHERE id = ?", (now, schedule_id))
            conn.commit()
            log.debug(f"last_fired updated for schedule ID: {schedule_id}")
    except sqlite3.Error as e:
        log.error("Ошибка при обновлении last_fired: %s", str(e))

def update_schedule(schedule_id, cron, message, modifier, chat_id, db_path) -> MyError or None:
    """
    Обновляет расписание в базе данных.

    Args:
        schedule_id (int): ID расписания.
        cron (str): CRON выражение.
        message (str): Сообщение.
        modifier (str): Модификатор.
        chat_id (int): ID чата.
        db_path (str): Путь к файлу базы данных.

    Returns:
        MyError or None: Возвращает MyError, если произошла ошибка, или None в случае успеха.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE schedules SET cron = ?, message = ?, modifier = ?, chat_id = ? WHERE id = ?",
                (cron, message, modifier, chat_id, schedule_id)
            )
            conn.commit()
            log.info("Обновлено расписание с ID: %d", schedule_id)
        return None
    except sqlite3.Error as e:
        log.error("Ошибка при обновлении расписания: %s", str(e))

def backup_database(db_path=DB_PATH, backup_dir=BACKUP_DIR):
    """
    Создает резервную копию базы данных 
    и удаляет старые копии, оставляя только 3 последних

    Args:
        db_path (str): Путь к файлу базы данных
        backup_dir (str): Путь к директории для резервных копий
    """
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_path / f"settings_{timestamp}.db"

    try:
        with sqlite3.connect(db_path) as source:
            with sqlite3.connect(str(backup_file)) as backup:
                source.backup(backup)
                log.info(f"Создана резервная копия БД: {backup_file}")

        # Удаление старых бэкапов, оставляем только 3 последних
        backup_files = sorted(
            list(backup_path.glob("settings_*.db")),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        # Удаляем все файлы, кроме трех последних
        for old_backup in backup_files[3:]:
            try:
                old_backup.unlink()
                log.info(f"Удалена старая резервная копия: {old_backup}")
            except Exception as e:
                log.warning(f"Не удалось удалить старую резервную копию {old_backup}: {e}")

    except sqlite3.Error as e:
        log.error(f"Ошибка при создании резервной копии БД: {e}")
        raise MyError(f"Ошибка при создании резервной копии БД: {e}")
