import json
import requests
from datetime import datetime
import logging
import pytz
from crontab import CronTab
from dotenv import load_dotenv
import os

# Загрузка переменных окружения из файла .env
load_dotenv()
with open('settings.json', 'r', encoding='utf-8') as f:
    settings = json.load(f)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Получение токена и chat ID из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Функция для отправки сообщения в Telegram
def send_message(token, chat_id, message):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    response = requests.post(url, json=payload)
    logging.debug(f"Отправлено сообщение: {message}, статус: {response.status_code}")

# Основная функция
def main():

    TZ = pytz.timezone(settings['globals']['timezone'])
    current_time = datetime.now(TZ)
    logging.debug("Текущее время в Москве: %s", current_time)

    currUTC = current_time.replace(minute=0, second=0, microsecond=0)
    for schedule in settings['schedules']:
        cron_expression = schedule['cron']
        message = schedule['message']

        logging.debug("Проверка cron-выражения: %s", cron_expression)

        # Создаем объект CronTab для проверки cron-выражения
        cron = CronTab(cron_expression)

        # Проверяем, соответствует ли текущее время cron-выражению
        if cron.test(currUTC):
            logging.info("Соответствие найдено! Отправка сообщения: %s", message)
            send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, message)
        else:
            logging.debug("Текущее время не соответствует cron-выражению.")            

if __name__ == '__main__':
    main()