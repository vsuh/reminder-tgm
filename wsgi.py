from web.app import WebApp

# Храним экземпляр WebApp, чтобы не создавать его многократно
_web_instance: WebApp | None = None

def create_app():
    global _web_instance
    if _web_instance is None:
        _web_instance = WebApp()
    return _web_instance.app

# Для gunicorn/uWSGI и пр. нужен объект app
app = create_app()

if __name__ == "__main__":
    # Локальный/standalone запуск использует те же настройки и тот же экземпляр
    web = _web_instance or WebApp()
    web.run()
