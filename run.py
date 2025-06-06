"""
Отправляет уведомление в Telegram, если находит подходящее в БД
"""
import os
import time
import requests
import pytz
from datetime import datetime
import multiprocessing
import json

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

def get_message_from_json(message: str) -> str:
    """
    Если сообщение имеет формат '#!/path/to/file.json',
    пытается загрузить JSON файл и найти сообщение для текущей даты.
    
    Args:
        message (str): Исходное сообщение в формате '#!/path/to/file.json'
        
    Returns:
        str: Текст сообщения для отправки
    """
    if not message.startswith('#!/'):
        return message
        
    try:
        # Получаем путь к файлу после #!
        json_path = message[2:].strip()
        if not os.path.isfile(json_path):
            log.error(f"Файл {json_path} не найден")
            return message
            
        with open(json_path, 'r', encoding='utf-8') as f:
            messages = json.load(f)
            
        if not isinstance(messages, list):
            log.error(f"Содержимое файла {json_path} должно быть массивом")
            return message
            
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Ищем сообщение для сегодняшней даты
        for item in messages:
            if not isinstance(item, dict) or 'date' not in item or 'text' not in item:
                continue
                
            if item['date'] == today:
                log.debug(f"Найдено сообщение для даты {today} в файле {json_path}")
                return item['text']
                
        log.warning(f"В файле {json_path} не найдено сообщение для даты {today}")
        return message
            
    except json.JSONDecodeError as e:
        log.error(f"Ошибка при разборе JSON файла {json_path}: {e}")
        return message
    except Exception as e:
        log.error(f"Непредвиденная ошибка при обработке файла {json_path}: {e}")
        return message

def send_telegram_message(message, chat_id):
    """
    Отправляет сообщение в Telegram.

    Args:
        message (str): Текст сообщения.
        chat_id (int): ID чата Telegram.
    """
    # Обрабатываем сообщение, если оно начинается с #!
    actual_message = get_message_from_json(message)
    # Добавляем текущую дату перед сообщением
    today = datetime.now().strftime('%d-%m-%Y')
    formatted_message = f"{today}\n{actual_message}"
     
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": formatted_message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        log.debug(f"Сообщение успешно отправлено chat_id={chat_id}: {formatted_message}")
    except requests.exceptions.RequestException as e:
        log.error("Ошибка при отправке сообщения: %s, ошибка: %s", formatted_message, e)

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
    now = datetime.now(timezone)

    log.info(f"Запуск скрипта напоминаний ({environment}) {now.strftime('%d-%m-%Y %H:%M:%S')}")

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

    log.info(f"Завершение работы скрипта {datetime.now(timezone).strftime('%d-%m-%Y %H:%M:%S')}")

if __name__ == "__main__":
    main()
