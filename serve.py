"""Compatibility WSGI entrypoint for the V4 gunicorn service."""

from cardioclaw.config import get_settings
from cardioclaw.server import create_app

app = create_app(get_settings())

if __name__ == "__main__":
    settings = get_settings()
    app.run(host=settings.server_host, port=settings.server_port)
