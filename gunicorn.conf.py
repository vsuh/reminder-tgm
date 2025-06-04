import os
import multiprocessing
from pathlib import Path
from lib.utils import get_environment_name, load_env

if not load_env(".env"):
    environment = get_environment_name()
    load_env(environment)

# Получение значений из переменных окружения
PORT = os.getenv("TLCR_FLASK_PORT", "7878")
WORKERS = os.getenv("GUNICORN_WORKERS", 2)
TIMEOUT = os.getenv("GUNICORN_TIMEOUT", 120)
LOG_PATH = os.getenv("TLCR_LOGPATH", "log")
LOG_PATH = os.path.abspath(os.getenv("TLCR_LOGPATH", "log"))



# Отладочный вывод
print(f"Loading gunicorn config...")
print(f"Environment: {environment}")
print(f"Port: {PORT}")
print(f"Log path: {LOG_PATH}")


# Настройки Gunicorn
bind = f"127.0.0.1:{PORT}" if environment == 'dev' else f"0.0.0.0:{PORT}"
workers = int(WORKERS)
worker_class = "sync"
timeout = int(TIMEOUT)
os.makedirs(LOG_PATH, exist_ok=True)


# Настройки логирования

accesslog = os.path.join(LOG_PATH, "gunicorn-access.log")
errorlog = os.path.join(LOG_PATH, "gunicorn-error.log")
loglevel = "debug"
capture_output = True
enable_stdio_inheritance = True

# Отладочный вывод
print(f"Access log: {accesslog}")
print(f"Error log: {errorlog}")
print(f"Log level: {loglevel}") 
