import logging
import os
import sqlite3
from datetime import datetime

from .utils import MyError, get_environment, init_log, load_env

# Load environment variables
environment = get_environment()
load_env(environment)

DB_PATH = os.getenv("DB_PATH", "settings.db")
LOGPATH = os.getenv("LOGPATH", ".")
LOGLEVEL = os.getenv("LOG_LEVEL", 'INFO').upper()

log = init_log('db_utils', LOGPATH, LOGLEVEL)

def init_db(db_path=DB_PATH, drop_table=True):
    try:
        with sqlite3.connect(db_path) as conn:
            run_initialization(conn, drop_table, db_path)
        log.info(f"Таблица базы данных '{db_path}.schedules' успешно инициализирована")
    except sqlite3.Error as e:
        log.error(f"Ошибка инициализации БД '{db_path}': %s", str(e))


def run_initialization(conn, drop_table, db_path):
    conn.execute("PRAGMA journal_mode=WAL;") # Add WAL mode for better concurrency
    cursor = conn.cursor()
    cursor.execute("PRAGMA encoding = 'UTF-8';")

    if drop_table:
        cursor.execute('DROP TABLE schedules;')
        conn.commit()
        log.info(f'удалена таблица "schedules" из БД "{db_path}"')
    sql = f'''CREATE TABLE {'' if drop_table else 'IF NOT EXIST'} schedules (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                cron TEXT NOT NULL,
                                message TEXT NOT NULL,
                                modifier TEXT,
                                last_fired TIMESTAMP
                            )'''
    cursor.execute(sql)
    conn.commit()

def get_schedules(db_path=DB_PATH):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier, last_fired FROM schedules")
            return [{"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3], "last_fired": row[4]} for row in cursor.fetchall()]
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписаний: %s", str(e))
        return []

def get_schedule(schedule_id, db_path=DB_PATH):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier, last_fired FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3]}
            else:
                return None
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписания: %s", str(e))
        return []

def add_schedule(cron, message, modifier, db_path=DB_PATH):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO schedules (cron, message, modifier) VALUES (?, ?, ?)", (cron, message, modifier))
            conn.commit()
            log.info("Добавлено новое расписание: %s, %s, %s", cron, message, modifier)
    except sqlite3.Error as e:
        log.error("Ошибка при добавлении расписания: %s", str(e))

def delete_schedule(schedule_id, db_path=DB_PATH):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            log.info("Удалено расписание с ID: %d", schedule_id)
    except sqlite3.Error as e:
        log.error("Ошибка при удалении расписания: %s", str(e))

def update_last_fired(schedule_id, db_path=DB_PATH):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now()
            cursor.execute("UPDATE schedules SET last_fired = ? WHERE id = ?", (now, schedule_id))
            conn.commit()
            log.debug(f"last_fired updated for schedule ID: {schedule_id}")
    except sqlite3.Error as e:
        log.error("Ошибка при обновлении last_fired: %s", str(e))

def update_schedule(schedule_id, cron, message, modifier, db_path=DB_PATH) -> MyError or None:
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE schedules SET cron = ?, message = ?, modifier = ? WHERE id = ?", (cron, message, modifier, schedule_id))
            conn.commit()
            log.info("Обновлено расписание с ID: %d", schedule_id)
        return None
    except sqlite3.Error as e:
        log.error("Ошибка при обновлении расписания: %s", str(e))

