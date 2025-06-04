import os
import multiprocessing

# Загрузка переменных окружения
from lib.utils import get_environment_name, load_env

if not load_env(".env"):
    environment = get_environment_name()
    load_env(environment)

# Получение значений из переменных окружения
PORT = os.getenv("TLCR_FLASK_PORT", "7878")
WORKERS = os.getenv("GUNICORN_WORKERS", 2)
TIMEOUT = os.getenv("GUNICORN_TIMEOUT", 120)
LOG_PATH = os.getenv("TLCR_LOGPATH", "log")

# Настройки Gunicorn
bind = f"127.0.0.1:{PORT}" if environment == 'dev' else f"0.0.0.0:{PORT}"
workers = int(WORKERS)
worker_class = "sync"
timeout = int(TIMEOUT)

# Настройки логирования
accesslog = f"{LOG_PATH}/gunicorn-access.log"
errorlog = f"{LOG_PATH}/gunicorn-error.log"
loglevel = "debug"
capture_output = True
enable_stdio_inheritance = True
