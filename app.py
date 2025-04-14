from flask import Flask
from datetime import datetime

from lib.utils import MyError, get_environment_name, load_env
from wsgi import create_app
from wsgi import application

if __name__ == "__main__":
    from waitress import serve
    from lib.utils import get_environment_name, load_env
    import os

    environment = get_environment_name()
    load_env(environment)
    APIPORT = os.getenv("PORT", "7878")

    if environment == 'dev':
        app = create_app()
        app.logger.info(f"Запуск Flask-сервера: http://{app.config['SERVER_NAME']}")
        app.run(host="0.0.0.0", port=int(APIPORT))
    else:
        serve(application, host='0.0.0.0', port=int(APIPORT))

