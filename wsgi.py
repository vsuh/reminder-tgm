from web.app import WebApp

def create_app():
    return WebApp().app

# Для gunicorn/uWSGI и пр. нужен объект app
app = create_app()

if __name__ == "__main__":
    # Локальный/standalone запуск использует настройки из .env (TLCR_FLASK_HOST/PORT, DEBUG)
    web = WebApp()
    web.run()
