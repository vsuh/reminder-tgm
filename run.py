"""
Отправляет уведомление в Telegram, если находит подходящее в БД
"""
import os
from datetime import datetime

import requests
import pytz

from lib.cron_utils import VCron
from lib.db_utils import update_last_fired, get_chats
from lib.utils import get_environment_name, init_log, load_env

# Load environment variables
environment = get_environment_name()
load_env(environment)

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TLCR_TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TLCR_TELEGRAM_CHAT_ID")
TIMEZONE = os.getenv("TLCR_TZ", "UTC")
PORT = os.getenv("TLCR_FLASK_PORT", "7999")
SCHEDULES_URL = f"http://localhost:{PORT}/schedules"
LOGPATH = os.getenv("TLCR_LOGPATH", ".")
LOGLEVEL = os.getenv("TLCR_LOG_LEVEL", "INFO").upper()
DB_PATH = os.getenv("TLCR_DB_PATH", "settings.db")

# Initialize logger
log = init_log('rmndr', LOGPATH, LOGLEVEL)

# Initialize VCron
myVCron = VCron(TIMEZONE)

def send_telegram_message(message, chat_id):
    """
    Отправляет сообщение в Telegram.

    Args:
        message (str): Текст сообщения.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        log.debug(f"Сообщение успешно отправлено chat_id={chat_id}: {message}")
    except requests.exceptions.RequestException as e:
        log.error("Ошибка при отправке сообщения: %s, ошибка: %s", message, e)

def get_schedules() -> list:
    """
    Получает список расписаний с сервера.

    Returns:
        list: Список расписаний.
    """
    try:
        response = requests.get(SCHEDULES_URL)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        schedules = response.json()
        log.debug(f"Получены расписания от сервера ({len(schedules)})")
        return schedules
    except requests.exceptions.RequestException as e:
        log.error(f"Ошибка при запросе к серверу расписаний: {e}")
        return []

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

# Main script logic
timezone = pytz.timezone(TIMEZONE)
now = datetime.now(timezone)

log.info(f"Запуск скрипта напоминаний ({environment}) {now.strftime('%d-%m-%Y %H:%M:%S')}")

if schedules := get_schedules():
    for schedule in schedules:
        cron_expr = schedule["cron"]
        message = schedule["message"]
        modifier = schedule.get("modifier", "")
        record_key = schedule["id"]

        if myVCron.check_cron(cron_expr, now) and myVCron.check_modifier(modifier, now):
            log.info("Телеграфирую: %s", message)
            chat_id = get_chat_id(schedule["chat_id"])
            if chat_id is None:
                log.error(f"Не найден chat_id для schedule_id={record_key}")
                continue # Skip to the next schedule

            send_telegram_message(message, chat_id)
            update_last_fired(record_key, DB_PATH)
            print(f"{now} уведомление по расписанию № {record_key}")
        else:
            log.debug(f"Сообщение не отправлено: {message} (не соответствует условиям CRON:{cron_expr}({modifier})")

log.info(f"Завершение работы скрипта  {datetime.now(timezone).strftime('%d-%m-%Y %H:%M:%S')}")
