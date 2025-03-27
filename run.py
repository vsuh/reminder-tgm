"""
Отправляет уведомление в Telegram, если находит подходящее в БД
"""
# import json
import os
from datetime import datetime

import requests
import pytz
# from croniter import croniter

from lib.cron_utils import VCron
from lib.db_utils import update_last_fired
from lib.utils import get_environment_name, init_log, load_env

# Load environment variables
environment = get_environment_name()
load_env(environment)

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TIMEZONE = os.getenv("reminderTZ", "UTC")
SCHEDULES_URL = "http://localhost:7878/schedules"
LOGPATH = os.getenv("LOGPATH", ".")
LOGLEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Initialize logger
log = init_log('rmndr', LOGPATH, LOGLEVEL)

# Initialize VCron
myVCron = VCron(TIMEZONE)

def send_telegram_message(message):
    """
    Отправляет сообщение в Telegram.

    Args:
        message (str): Текст сообщения.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        log.debug("Сообщение успешно отправлено: %s", message)
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
            send_telegram_message(message)
            update_last_fired(record_key)
            print(f"{now} уведомление по расписанию № {record_key}")
        else:
            log.debug(f"Сообщение не отправлено: {message} (не соответствует условиям CRON:{cron_expr}({modifier})")

log.info(f"Завершение работы скрипта  {datetime.now(timezone).strftime('%d-%m-%Y %H:%M:%S')}")
