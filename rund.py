"""
Демон напоминаний: периодически проверяет расписания,
отправляет уведомления в Telegram и (опционально) в ntfy.
"""
import os
import time
import requests
import pytz
from datetime import datetime
import multiprocessing
import json
import signal
import sys

from lib.cron_utils import VCron
from lib.db_utils import (
    update_last_fired, get_chats, get_schedules as db_get_schedules,
    get_ntfy_channel, backup_database,
    DB_PATH, LOGPATH, LOGLEVEL
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
BACKUP_DIR = os.getenv("TLCR_BACKUP_PATH", "static/db.bak")

# Настройки scp-репликации бэкапов
BACKUP_SCP_ODD = os.getenv("TLCR_BACKUP_SCP_ODD", "").strip()
BACKUP_SCP_EVEN = os.getenv("TLCR_BACKUP_SCP_EVEN", "").strip()
BACKUP_SSH_KEY_PATH = os.getenv("TLCR_BACKUP_SSH_KEY_PATH", "").strip()
# ntfy-топик для аварийных уведомлений о сбое scp
BACKUP_SCP_ERROR_NTFY_URL = "https://ntfy.sh/HELOR_tg_cron_notify_1956GH7y"

# Initialize logger
log = init_log('rmndr', LOGPATH, LOGLEVEL)

# Initialize VCron
myVCron = VCron(TIMEZONE)

# Глобальная переменная для отслеживания состояния работы
running = True
# Список активных процессов
active_processes: list[multiprocessing.Process] = []


def signal_handler(signum, frame):
    """
    Обработчик сигналов для корректного завершения работы.
    """
    global running
    if signum == signal.SIGINT:
        log.info("Получен сигнал прерывания (Ctrl-C). Завершаем работу...")
        running = False
        for p in active_processes:
            if p.is_alive():
                log.debug(f"Завершаем процесс {p.pid}")
                p.terminate()
                p.join(timeout=5)
                if p.is_alive():
                    log.warning(f"Процесс {p.pid} не завершился корректно, убиваем принудительно")
                    p.kill()
        sys.exit(0)


def get_message_from_json(message: str) -> str:
    """
    Если сообщение имеет формат '#!/path/to/file.json',
    пытается загрузить JSON файл и найти сообщение для текущей даты.
    """
    if not message.startswith('#!/'):
        return message

    try:
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


def send_telegram_message(message: str, chat_id: int):
    """
    Отправляет сообщение в Telegram.
    Принимает уже обработанный текст (без shebang).
    """
    today = datetime.now().strftime('%d-%m-%Y')
    formatted_message = f"{today}\n{message}"

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": formatted_message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        log.debug(f"Сообщение успешно отправлено chat_id={chat_id}: {formatted_message}")
    except requests.exceptions.RequestException as e:
        log.error("Ошибка при отправке сообщения: %s, ошибка: %s", formatted_message, e)


def send_ntfy_message(url: str, message: str, title: str | None = None):
    """
    Отправляет уведомление в ntfy.sh топик.

    ВАЖНО: HTTP-заголовки должны быть совместимы с latin-1.
    Если title содержит не-ASCII символы, заголовок Title не отправляется.
    """
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    if title:
        try:
            title.encode("latin-1")
            headers["Title"] = title
        except UnicodeEncodeError:
            log.warning(
                "Заголовок ntfy Title содержит не-ASCII символы и будет опущен: %r",
                title,
            )

    try:
        response = requests.post(url, data=message.encode("utf-8"), headers=headers)
        response.raise_for_status()
        log.debug(f"ntfy уведомление отправлено на {url}")
    except requests.exceptions.RequestException as e:
        log.error("Ошибка при отправке ntfy на %s: %s", url, e)


def replicate_backup_via_scp(backup_file_path: str):
    """
    Копирует файл бэкапа по scp на один из двух удалённых хостов
    в зависимости от чётности номера дня года.

    Требуется настроенная беспарольная авторизация ssh (ключ монтируется в контейнер
    и путь задаётся через TLCR_BACKUP_SSH_KEY_PATH).

    TLCR_BACKUP_SCP_ODD  - scp-цель для нечётных дней (например, user@host:/path)
    TLCR_BACKUP_SCP_EVEN - scp-цель для чётных дней

    При неудаче отправляет уведомление в резервный ntfy-топик BACKUP_SCP_ERROR_NTFY_URL.
    """
    if not BACKUP_SCP_ODD and not BACKUP_SCP_EVEN:
        # Ничего не настроено — выходим
        return

    day_of_year = int(datetime.now().strftime("%j"))
    is_odd = (day_of_year % 2 == 1)
    target = BACKUP_SCP_ODD if is_odd else BACKUP_SCP_EVEN

    if not target:
        log.warning(
            "TLCR_BACKUP_SCP_%s не задан, пропускаем scp для бэкапа %s",
            "ODD" if is_odd else "EVEN",
            backup_file_path,
        )
        return

    ssh_opts = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    key_part = f"-i {BACKUP_SSH_KEY_PATH}" if BACKUP_SSH_KEY_PATH else ""
    cmd = f"scp {ssh_opts} {key_part} {backup_file_path} {target}"

    log.info(
        "Отправка бэкапа по scp (day_of_year=%d, %s день): %s",
        day_of_year,
        "нечётный" if is_odd else "чётный",
        cmd,
    )

    try:
        exit_code = os.system(cmd)
        if exit_code == 0:
            log.info("Бэкап %s успешно скопирован на %s", backup_file_path, target)
        else:
            msg = (
                f"Ошибка scp бэкапа\n"
                f"Файл: {backup_file_path}\n"
                f"Цель: {target}\n"
                f"Код выхода: {exit_code}"
            )
            log.error(msg)
            send_ntfy_message(BACKUP_SCP_ERROR_NTFY_URL, msg, title="Backup SCP ERROR")
    except Exception as e:
        msg = (
            f"Исключение при scp бэкапа\n"
            f"Файл: {backup_file_path}\n"
            f"Цель: {target}\n"
            f"Ошибка: {e}"
        )
        log.error("Ошибка при отправке бэкапа по scp: %s", e)
        send_ntfy_message(BACKUP_SCP_ERROR_NTFY_URL, msg, title="Backup SCP ERROR")


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


def calculate_age(birth_date: datetime, today: datetime) -> int:
    """
    Возвращает возраст в годах, учитывая дату рождения и текущую дату.
    """
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def check_and_send(schedule, myVCron: VCron, timezone):
    """
    Проверяет расписание и отправляет уведомление, если необходимо.
    Эта функция предназначена для запуска в отдельном процессе.
    """
    now = datetime.now(timezone)
    cron_expr = schedule["cron"]
    message = schedule["message"]
    modifier = schedule.get("modifier", "")
    record_key = schedule["id"]

    # Если сообщение про ДР и в modifier лежит дата, добавляем возраст
    if isinstance(message, str) and message.startswith("ДР") and modifier:
        try:
            birth_date = datetime.strptime(modifier.strip(), "%Y%m%d").date()
            today_date = now.date()
            age = calculate_age(
                datetime(birth_date.year, birth_date.month, birth_date.day),
                datetime(today_date.year, today_date.month, today_date.day),
            )
            message = f"{message} ({age} лет)"
        except ValueError:
            log.warning(
                "Не удалось распарсить дату из modifier='%s' для сообщения '%s'",
                modifier,
                message,
            )

    if myVCron.check_cron(cron_expr, now) and myVCron.check_modifier(modifier, now):
        log.info("Телеграфирую: %s", message)

        chat_id = get_chat_id(schedule["chat_id"])
        if chat_id is None:
            log.error(f"Не найден chat_id для schedule_id={record_key}")
            return

        # Один раз формируем итоговый текст (учитывая shebang)
        actual_message = get_message_from_json(message)

        send_telegram_message(actual_message, chat_id)
        update_last_fired(record_key, DB_PATH)
        print(f"{now} уведомление по расписанию № {record_key}")

        # Дублируем в ntfy, если канал назначен
        ntfy_id = schedule.get("ntfy_id")
        if ntfy_id:
            ntfy = get_ntfy_channel(ntfy_id, DB_PATH)
            if ntfy:
                send_ntfy_message(ntfy["url"], actual_message, ntfy.get("title"))
            else:
                log.warning(f"ntfy канал id={ntfy_id} не найден для schedule_id={record_key}")
    else:
        log.debug(
            f"Сообщение не отправлено: {message} "
            f"(не соответствует условиям CRON:{cron_expr}({modifier})"
        )


def main():
    """Основная функция демона напоминаний."""
    global running, active_processes

    # Устанавливаем обработчик Ctrl-C
    signal.signal(signal.SIGINT, signal_handler)

    timezone = pytz.timezone(TIMEZONE)
    myVCron_local = VCron(TIMEZONE)
    last_backup_time = time.time()

    log.info("Демон напоминаний запущен. Для завершения нажмите Ctrl-C")

    while running:
        try:
            now = datetime.now(timezone)
            log.info(f"Проверка расписаний ({now.strftime('%d-%m-%Y %H:%M:%S')})")

            # Проверяем необходимость создания резервной копии
            current_time = time.time()
            work_time = int(current_time - last_backup_time)
            if work_time >= BACKUP_HOURS * 3600 or work_time == 0:
                try:
                    backup_file = backup_database(backup_dir=BACKUP_DIR, db_path=DB_PATH)
                    last_backup_time = current_time
                    if backup_file:
                        replicate_backup_via_scp(str(backup_file))
                except Exception as e:
                    log.error(f"Ошибка при создании резервной копии: {e}")

            # Чистим список активных процессов от завершённых
            active_processes = [p for p in active_processes if p.is_alive()]

            if schedules := db_get_schedules(DB_PATH):
                for schedule in schedules:
                    if not running:
                        break
                    p = multiprocessing.Process(
                        target=check_and_send,
                        args=(schedule, myVCron_local, timezone),
                    )
                    log.debug(f"Выполнение расписания {schedule}")
                    active_processes.append(p)
                    p.start()

                # Ждём завершения с таймаутом, чтобы не зависнуть
                for p in active_processes:
                    p.join(timeout=10)
                    if p.is_alive():
                        log.warning(f"Процесс {p.pid} не завершился вовремя")

            if running:
                CHECK_INTERVAL = CHECK_MINUTES * 60
                log.info(f"Следующая проверка через {CHECK_INTERVAL} секунд")
                for _ in range(CHECK_INTERVAL):
                    if not running:
                        break
                    time.sleep(1)

        except Exception as e:
            log.error(f"Неожиданная ошибка в главном цикле: {e}")
            if running:
                time.sleep(60)

    log.info("Демон напоминаний завершил работу")


if __name__ == "__main__":
    main()
