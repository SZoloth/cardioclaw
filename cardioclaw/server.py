from __future__ import annotations

import hmac
from pathlib import Path

from flask import Flask, Response, abort, send_file
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from cardioclaw.config import Settings, get_settings
from cardioclaw.publisher import ReleasePublisher


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or get_settings()
    publisher = ReleasePublisher(settings)
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    def authorize(token: str) -> None:
        if not hmac.compare_digest(token, settings.feed_token_value):
            abort(404)

    def release_file(release_id: str, subdirectory: str, filename: str) -> Path:
        safe_release = secure_filename(release_id)
        safe_filename = secure_filename(filename)
        if safe_release != release_id or safe_filename != filename:
            abort(404)
        base = publisher.release_dir(safe_release).resolve()
        path = (base / subdirectory / safe_filename).resolve()
        if base not in path.parents or not path.is_file():
            abort(404)
        return path

    @app.after_request
    def security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/")
    def index() -> dict[str, str | bool]:
        return {
            "service": "Cardiology Claw",
            "status": "ok",
            "release_available": publisher.current_release_id() is not None,
        }

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.route("/feed/<token>.xml", methods=["GET", "HEAD"])
    def feed(token: str):
        authorize(token)
        current = publisher.current_release_dir()
        if not current:
            abort(404)
        response = send_file(
            current / "feed.xml",
            mimetype="application/rss+xml",
            conditional=True,
            max_age=0,
        )
        response.headers["Cache-Control"] = "no-cache, max-age=0"
        return response

    @app.route("/media/<token>/<release_id>/<filename>", methods=["GET", "HEAD"])
    def media(token: str, release_id: str, filename: str):
        authorize(token)
        response = send_file(
            release_file(release_id, "audio", filename),
            mimetype="audio/mpeg",
            conditional=True,
            max_age=31_536_000,
        )
        response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        response.headers["Accept-Ranges"] = "bytes"
        return response

    @app.route("/transcripts/<token>/<release_id>/<filename>", methods=["GET", "HEAD"])
    def transcript(token: str, release_id: str, filename: str):
        authorize(token)
        return send_file(
            release_file(release_id, "transcripts", filename),
            mimetype="text/html",
            conditional=True,
            max_age=31_536_000,
        )

    @app.route("/assets/<token>/<filename>", methods=["GET", "HEAD"])
    def asset(token: str, filename: str):
        authorize(token)
        if secure_filename(filename) != settings.cover_filename:
            abort(404)
        cover = settings.resolved_cover_path
        if not cover.is_file():
            abort(404)
        return send_file(cover, mimetype="image/png", conditional=True, max_age=86_400)

    return app
