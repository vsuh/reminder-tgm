import os

from lib.utils import get_environment_name, load_env, init_log
from app import app, init_db

def create_app(environment_name: str = None):
    """
    Создает экземпляр Flask приложения.

    Args:
        environment_name (str, optional): Имя окружения. По умолчанию None.

    Returns:
        Flask: Экземпляр Flask приложения.
    """
    # Load environment variables
    if environment_name is None:
        environment = get_environment_name()
    else:
        environment = environment_name
    load_env(environment)

    # Read environment variables
    TIMEZONE = os.getenv("reminderTZ", "UTC")
    DB_PATH = os.getenv("DB_PATH", "settings.db")
    LOGPATH = os.getenv("LOGPATH", ".")
    LOGLEVEL = os.getenv("LOG_LEVEL", 'INFO').upper()
    APIPORT = os.getenv("PORT", "7878")
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = os.getenv("DEBUG", False).lower() in ('true', 'yes', '1')

    # Initialize Flask
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['DEBUG'] = DEBUG

    # Initialize database
    init_db(DB_PATH, False)

    # Initialize logger
    log = init_log('svrm', LOGPATH, LOGLEVEL)

    return app

app = create_app()