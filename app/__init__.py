"""Application factory for the iPullRank Internal Developer Portal.

create_app() orchestrates configuration, the HTTPS proxy fix, and blueprint
registration — it does not implement business logic itself.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

# Project root holds .env. Load it with an explicit path so this works inside
# PythonAnywhere's WSGI process, whose working directory is not guaranteed.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

_REQUIRED_ENV = (
    "FLASK_SECRET_KEY",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
)


def _require_env() -> dict[str, str]:
    """Read required secrets, failing loudly on the first one missing."""
    values: dict[str, str] = {}
    for key in _REQUIRED_ENV:
        value = os.environ.get(key)
        if not value:
            raise RuntimeError(
                f"Missing required environment variable: {key}. "
                "Copy .env.example to .env and fill it in."
            )
        values[key] = value
    return values


def create_app() -> Flask:
    env = _require_env()

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=env["FLASK_SECRET_KEY"],
        GOOGLE_OAUTH_CLIENT_ID=env["GOOGLE_OAUTH_CLIENT_ID"],
        GOOGLE_OAUTH_CLIENT_SECRET=env["GOOGLE_OAUTH_CLIENT_SECRET"],
        ALLOWED_EMAIL_DOMAIN=os.environ.get("ALLOWED_EMAIL_DOMAIN", "ipullrank.com"),
        PREFERRED_URL_SCHEME="https",
    )

    # PythonAnywhere terminates TLS at its proxy and forwards to us over HTTP.
    # Trust the X-Forwarded-Proto/Host headers so Flask-Dance builds an
    # https:// redirect URI and Google does not reject it as a mismatch.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Import here to avoid circular imports at module load time.
    from .auth import register_auth
    from .routes import routes

    register_auth(app)
    app.register_blueprint(routes)

    return app
