import json
import os
import datetime
import pytz
import requests
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from croniter import croniter
import pathlib
from pathlib import Path as pt


class MyError(Exception):
    pass

# Загрузка переменных окружения
ENVIRONMENT = 'prod' if os.name == 'posix' else 'dev'
dotenv = f'.env.{ENVIRONMENT}'
if not pt(dotenv).exists():
    raise MyError(f"file {dotenv} not found")

load_dotenv(dotenv)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TIMEZONE = os.getenv("reminderTZ", "UTC")
SCHEDULES_URL = "http://localhost:7878/schedules"
LOGPATH = os.getenv("LOGPATH", ".")

def init_log(name: str):
    # Настройка логирования

    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    
    handler2file = RotatingFileHandler(pt(LOGPATH).joinpath(f'{name}.log'),encoding="utf-8", maxBytes=50000, backupCount=2)
    handler2file.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler2file.setFormatter(formatter)
    handler2con = logging.StreamHandler()
    handler2con.setLevel(logging.INFO)

    log.addHandler(handler2file)
    log.addHandler(handler2con)
    return log

log = init_log('rmndr')

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    response = requests.post(url, data=data)
    if response.status_code == 200:
        log.debug("Сообщение успешно отправлено: %s", message)
    else:
        log.error("Ошибка при отправке сообщения: %s, код ответа: %d", message, response.status_code)

def check_modifier(modifier, now):
    if not modifier:
        return True  # Если модификатор не задан, всегда срабатывает

    parts = modifier.split('>')
    if len(parts) == 2:
        start_date_str, rule = parts
    else:
        start_date_str, rule = '00010101', parts[0]  # По умолчанию 01.01.0001

    start_date = datetime.datetime.strptime(start_date_str, "%Y%m%d").date()
    
    if rule.startswith('w/'):
        interval = int(rule[2:])
        week_number = (now - start_date).days // 7
        return week_number % interval == 0
    
    if rule.startswith('d/'):
        interval = int(rule[2:])
        days_since_start = (now - start_date).days
        return days_since_start % interval == 0
    
    return False

def get_schedules():
    try:
        response = requests.get(SCHEDULES_URL)
        if response.status_code == 200:
            log.debug("Получены расписания от сервера")
            return response.json()
        else:
            log.error("Ошибка при получении расписания, код ответа: %d", response.status_code)
            return []
    except Exception as e:
        log.exception("Ошибка при запросе к серверу расписаний: %s", str(e))
        return []

# Основная логика выполнения задач
timezone = pytz.timezone(TIMEZONE)
now = datetime.datetime.now(timezone).date()
strtime = datetime.datetime.now(timezone).strftime('%d-%m-%Y %H:%M:%S')
log.info(f"Запуск скрипта напоминаний ({ENVIRONMENT}) {strtime}")

schedules = get_schedules()
for schedule in schedules:
    cron_expr = schedule["cron"]
    message = schedule["message"]
    modifier = schedule.get("modifier", "")
    id = schedule["id"]
    
    if croniter.match(cron_expr, datetime.datetime.now(timezone)) and check_modifier(modifier, now):
        log.info("Телеграфирую: %s", message)
        send_telegram_message(message)
        print(f"{now} sent № {id}")
    else:
        log.debug(f"Сообщение не отправлено: {message} (не соответствует условиям CRON:{cron_expr}({modifier})")

strtime = datetime.datetime.now(timezone).strftime('%d-%m-%Y %H:%M:%S')
log.info(f"Завершение работы скрипта  {strtime}")
