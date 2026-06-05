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
# load_dotenv does NOT raise when the file is absent — it returns False — so we
# remember the outcome and surface it in the error message below.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_DOTENV_LOADED = load_dotenv(_ENV_PATH)

_REQUIRED_ENV = (
    "FLASK_SECRET_KEY",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
)


def _env_diagnosis() -> str:
    """Explain WHERE we looked for config, so a missing var is self-debugging."""
    if not _ENV_PATH.exists():
        return (
            f"No .env file was found at {_ENV_PATH}. On PythonAnywhere, .env is "
            "gitignored and not uploaded with the repo — create it on the server "
            "(copy .env.example to .env there and fill in real values), then reload "
            "the web app. Alternatively, set the variables in your WSGI config file."
        )
    if not _DOTENV_LOADED:
        return f".env exists at {_ENV_PATH} but python-dotenv could not parse it."
    return (
        f".env at {_ENV_PATH} was loaded, but this key is empty or absent in it. "
        "Check for a blank value (e.g. 'FLASK_SECRET_KEY=' with nothing after '=')."
    )


def _require_env() -> dict[str, str]:
    """Read required secrets, failing loudly on the first one missing."""
    values: dict[str, str] = {}
    for key in _REQUIRED_ENV:
        value = os.environ.get(key)
        if not value:
            raise RuntimeError(
                f"Missing required environment variable: {key}. {_env_diagnosis()}"
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
        # Bootstrap admins: comma-separated emails promoted to admin on login.
        IDP_ADMINS={
            e.strip().lower()
            for e in os.environ.get("IDP_ADMINS", "").split(",")
            if e.strip()
        },
        PREFERRED_URL_SCHEME="https",
        # Engine-agnostic: default to a SQLite file in the project root; override
        # with DATABASE_URL to point at MySQL/Postgres later (no code change).
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", f"sqlite:///{_PROJECT_ROOT / 'idp.db'}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    # PythonAnywhere terminates TLS at its proxy and forwards to us over HTTP.
    # Trust the X-Forwarded-Proto/Host headers so Flask-Dance builds an
    # https:// redirect URI and Google does not reject it as a mismatch.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # type: ignore[method-assign]

    # Import here to avoid circular imports at module load time.
    from . import models  # noqa: F401  (registers models with SQLAlchemy)
    from .api import api
    from .auth import register_auth
    from .authz import can_edit_tool
    from .cli import register_cli
    from .extensions import db, migrate
    from .manage import manage
    from .routes import routes

    db.init_app(app)
    # render_as_batch lets SQLite ALTER TABLE (e.g. add tools.owner_id) by
    # rebuilding the table — SQLite can't add FKs/constraints in place.
    migrate.init_app(app, db, render_as_batch=True)
    register_auth(app)
    app.register_blueprint(routes)
    app.register_blueprint(api)
    app.register_blueprint(manage)
    register_cli(app)

    @app.context_processor
    def _inject_permissions() -> dict:
        """Expose permission helpers to all templates."""
        from flask_login import current_user

        return {
            "can_edit_tool": lambda tool: can_edit_tool(current_user, tool),
            "is_admin": getattr(current_user, "is_admin", False),
        }

    return app
