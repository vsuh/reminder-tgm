from web.app import WebApp

def create_app():
    return WebApp().app

app = create_app()

if __name__ == "__main__":
    app.run()
