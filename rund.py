import os
import time
import requests
import pytz
from datetime import datetime
import multiprocessing
import shutil
import subprocess
from pathlib import Path

from lib.cron_utils import VCron
from lib.db_utils import (
    update_last_fired, get_chats, get_schedules as db_get_schedules,
    DB_PATH, LOGPATH, LOGLEVEL, backup_database
)
from lib.utils import get_environment_name, init_log, load_env

# Load environment variables
environment = get_environment_name()
load_env(environment)

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TLCR_TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TLCR_TELEGRAM_CHAT_ID")
TIMEZONE = os.getenv("TLCR_TZ", "UTC")
CHECK_MINUTES = int(os.getenv("TLCR_CHECK_MINUTES", "60"))
BACKUP_HOURS = int(os.getenv("TLCR_BACKUP_INTERVAL", "24"))
BACKUP_DIR = os.getenv("TLCR_BACKUP_PATH", "/static/db.bak")

# Initialize logger
log = init_log('rmndr', LOGPATH, LOGLEVEL)

# Initialize VCron
myVCron = VCron(TIMEZONE)

def send_telegram_message(message, chat_id):
    """
    Отправляет сообщение в Telegram.

    Args:
        message (str): Текст сообщения.
        chat_id (int): ID чата Telegram.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        log.debug(f"Сообщение успешно отправлено chat_id={chat_id}: {message}")
    except requests.exceptions.RequestException as e:
        log.error("Ошибка при отправке сообщения: %s, ошибка: %s", message, e)


def get_chat_id(chat_id_from_schedule):
    chats = get_chats(DB_PATH)
    return next(
        (
            chat['chat_id']
            for chat in chats
            if chat['id'] == chat_id_from_schedule
        ),
        None,
    )


def check_and_send(schedule, myVCron, timezone):
    """
    Проверяет расписание и отправляет уведомление, если необходимо.
    Эта функция предназначена для запуска в отдельном процессе.
    """
    now = datetime.now(timezone)
    cron_expr = schedule["cron"]
    message = schedule["message"]
    modifier = schedule.get("modifier", "")
    record_key = schedule["id"]

    if myVCron.check_cron(cron_expr, now) and myVCron.check_modifier(modifier, now):
        log.info("Телеграфирую: %s", message)
        chat_id = get_chat_id(schedule["chat_id"])
        if chat_id is None:
            log.error(f"Не найден chat_id для schedule_id={record_key}")
            return

        send_telegram_message(message, chat_id)
        update_last_fired(record_key, DB_PATH)
        print(f"{now} уведомление по расписанию № {record_key}")
    else:
        log.debug(f"Сообщение не отправлено: {message} (не соответствует условиям CRON:{cron_expr}({modifier})")


def main():
    """Основная функция скрипта."""
    timezone = pytz.timezone(TIMEZONE)
    myVCron = VCron(TIMEZONE)
    last_backup_time = time.time()  # Время последнего бэкапа

    while True:
        now = datetime.now(timezone)
        log.info(f"Проверка расписаний ({now.strftime('%d-%m-%Y %H:%M:%S')})")

        # Проверяем необходимость создания резервной копии
        current_time = time.time()
        work_time = int(current_time - last_backup_time)
        if work_time >= BACKUP_HOURS * 3600 or work_time == 0:
            try:
                backup_database(backup_dir=BACKUP_DIR,db_path=DB_PATH)
                last_backup_time = current_time
            except Exception as e:
                log.error(f"Ошибка при создании резервной копии: {e}")

        if schedules := db_get_schedules(DB_PATH):
            processes = []
            for schedule in schedules:
                p = multiprocessing.Process(target=check_and_send, args=(schedule, myVCron, timezone))
                log.debug(f"Выполнение расписания {schedule}")
                processes.append(p)
                p.start()

            # Ожидание завершения всех процессов
            for p in processes:
                p.join()

        log.info(f"Следующая проверка через {CHECK_INTERVAL} секунд")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    CHECK_INTERVAL = CHECK_MINUTES * 60  # Конвертируем минуты в секунды
    main()
