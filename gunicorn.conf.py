import os
#import multiprocessing
from pathlib import Path
from lib.utils import get_environment_name, load_env


environment = get_environment_name()
if Path(".env").exists():
    load_env(".env")
else:
    load_env(environment)

# Получение значений из переменных окружения
PORT = os.getenv("TLCR_FLASK_PORT", "7999")
WORKERS = os.getenv("GUNICORN_WORKERS", 2)
TIMEOUT = os.getenv("GUNICORN_TIMEOUT", 120)
LOG_PATH = os.path.abspath(os.getenv("TLCR_LOGPATH", "log"))
LOG_LEVEL = os.getenv("TLCR_LOG_LEVEL", "DEBUG")

# Отладочный вывод
print(f"""
  >>>> Loading gunicorn config...
  !>>> Envment: 	{environment}
  !>>> Port: 		{PORT}
  !>>> Logs dir: 	{LOG_PATH}
""")

# Настройки Gunicorn
bind = f"127.0.0.1:{PORT}" if environment == 'dev' else f"0.0.0.0:{PORT}"
workers = int(WORKERS)
worker_class = "sync"
timeout = int(TIMEOUT)

# Создаем директорию для логов, если её нет
os.makedirs(LOG_PATH, exist_ok=True)

# Настройки логирования
accesslog = os.path.join(LOG_PATH, "gunicorn-access.log")
errorlog = os.path.join(LOG_PATH, "gunicorn-error.log")
loglevel = LOG_LEVEL.lower()
capture_output = True
enable_stdio_inheritance = True

# Отладочный вывод
print(f"""
  )))) Access log: 	{accesslog}
  )))) Error log: 	{errorlog}
  )))) Log level: 	{loglevel}
""")
