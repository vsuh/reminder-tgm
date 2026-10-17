import re
import logging
import os
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from pathlib import Path as pt

class MyError(Exception):
    """Класс для пользовательских исключений"""
    pass

def init_log(name: str = None, log_path: str = ".", log_level: str = "INFO") -> logging.Logger:
    """

    Инициализирует логгер с обработчиками для файла и консоли.

    Args:
        name (str): Имя логгера.
        log_path (str, optional): Путь к файлу лога. По умолчанию ".".
        log_level (str, optional): Уровень логирования. По умолчанию "INFO".

    Returns:
        logging.Logger: Инициализированный логгер.
    """
    log = logging.getLogger(__name__) if name is None else logging.getLogger(name)
    if log.handlers:  # Check if handlers are already added
        return log # Logger already initialized, return it

    try:
        level = getattr(logging, log_level.upper())
    except AttributeError:
        level = logging.INFO

    # Устанавливаем уровень для самого логгера
    log.setLevel(level)
    log.setLevel(level)
    environment = get_environment_name()

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s@(%(module)s:%(lineno)d)- %(levelname)s - %(message)s'
    )

    if environment == "prod":
        handler2file = RotatingFileHandler(
            pt(log_path).joinpath(f'{name}.log'),
            encoding="utf-8",
            maxBytes=50000,
            backupCount=3,
        )
    else:
        handler2file = logging.FileHandler(
            pt(log_path).joinpath(f'{name}.log'),
            encoding="utf-8",
        )

    handler2file.setLevel(level)
    handler2file.setFormatter(formatter)
    log.addHandler(handler2file)

    handler2con = logging.StreamHandler()
    handler2con.setLevel(level)
    handler2con.setFormatter(formatter)
    log.addHandler(handler2con)

    log.info(
        f'Протоколирование уровня "{log_level}" с именем "{name}" установлено. '
        f'Логфайлы в каталоге "{log_path}"'
    )
    return log

def load_env(environment: str = "dev"):
    """
    Загружает переменные окружения из файла .env

    Args:
        environment (str, optional): Имя окружения (например, "dev", "prod"). По умолчанию "dev".
    """
    if not load_dotenv(dotenv_path=".env"):
        dotenv_path = f'env/.env.{environment}'
        if not pt(dotenv_path).exists():
            raise MyError(f"Файл {dotenv_path} не найден")
        load_dotenv(dotenv_path)

def get_environment_name() -> str:
    """
    Возвращает имя текущего окружения.

    Returns:
        str: Имя окружения ("prod" для Linux/macOS, "dev" для других ОС).
    """
    return 'prod' if os.name == 'posix' else 'dev'



def parse_thread_id(text) -> int | None:
    """
    ID топика Telegram-группы из числа или ссылки на топик.
    '5', 't.me/c/1234567890/5', 'https://t.me/c/1234567890/5/17', 't.me/mygroup/5' -> 5
    Пустой ввод -> None. Неверный формат -> ValueError.
    """
    text = (text or "").strip()
    if not text:
        return None
    if text.isdigit():
        value = int(text)
    else:
        m = re.search(r"t\.me/(?:c/\d+|(?!c/)[A-Za-z0-9_]+)/(\d+)", text)
        if not m:
            raise ValueError(
                f'Не удалось определить ID топика из "{text}". '
                'Укажите число или ссылку вида https://t.me/c/<чат>/<топик>'
            )
        value = int(m.group(1))
    if value <= 0:
        raise ValueError("ID топика должен быть положительным числом")
    return value
