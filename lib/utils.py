import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path as pt

class MyError(Exception):
    """Класс для пользовательских исключений"""
    pass

def init_log(name: str, log_path: str = ".", log_level: str = "INFO") -> logging.Logger:
    """
    Инициализирует логгер с обработчиками для файла и консоли.

    Args:
        name (str): Имя логгера.
        log_path (str, optional): Путь к файлу лога. По умолчанию ".".
        log_level (str, optional): Уровень логирования. По умолчанию "INFO".

    Returns:
        logging.Logger: Инициализированный логгер.
    """
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

    try:
        level = getattr(logging, log_level.upper())
    except AttributeError:
        level = logging.INFO

    handler2file = RotatingFileHandler(pt(log_path).joinpath(f'{name}.log'), encoding="utf-8", maxBytes=50000, backupCount=5)
    handler2file.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler2file.setFormatter(formatter)

    handler2con = logging.StreamHandler()
    handler2con.setLevel(level)

    log.addHandler(handler2file)
    log.addHandler(handler2con)
    return log

def load_env(environment: str = "dev"):
    """
    Загружает переменные окружения из файла .env.

    Args:
        environment (str, optional): Имя окружения (например, "dev", "prod"). По умолчанию "dev".
    """
    dotenv_path = f'env/.env.{environment}'
    if not pt(dotenv_path).exists():
        raise MyError(f"Файл {dotenv_path} не найден")
    from dotenv import load_dotenv
    load_dotenv(dotenv_path)

def get_environment_name() -> str:
    """
    Возвращает имя текущего окружения.

    Returns:
        str: Имя окружения ("prod" для Linux/macOS, "dev" для других ОС).
    """
    return 'prod' if os.name == 'posix' else 'dev'

