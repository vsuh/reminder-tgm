import os
import multiprocessing

# Загрузка переменных окружения
from lib.utils import get_environment_name, load_env
environment = get_environment_name()
load_env(environment)

# Получение значений из переменных окружения
PORT = os.getenv("PORT", "7878")
WORKERS = os.getenv("GUNICORN_WORKERS", 2)
TIMEOUT = os.getenv("GUNICORN_TIMEOUT", 120)

# Настройки Gunicorn
bind = f"0.0.0.0:{PORT}" if environment == 'prod' else f"127.0.0.1:{PORT}"
workers = int(WORKERS)
worker_class = "sync"
timeout = int(TIMEOUT)