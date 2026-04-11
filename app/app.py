from application import create_app
from config import APP_SETTINGS_KEY

app = create_app()


if __name__ == "__main__":
    settings = app.config[APP_SETTINGS_KEY]
    app.run(host="0.0.0.0", port=settings.flask_port)
