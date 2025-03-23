import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path as pt

class MyError(Exception):
    pass

def init_log(name: str, log_path: str = ".", log_level: str = "INFO"):
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
    dotenv_path = f'env/.env.{environment}'
    if not pt(dotenv_path).exists():
        raise MyError(f"Файл {dotenv_path} не найден")
    from dotenv import load_dotenv
    load_dotenv(dotenv_path)

def get_environment():
    return 'prod' if os.name == 'posix' else 'dev'

