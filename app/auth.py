"""Google OAuth dance and domain-restricted authorization.

Validation (``is_allowed_email``) is deliberately kept pure and Flask-free so
it can be unit-tested in isolation. The signal handler orchestrates: fetch
profile -> validate -> log in, with guard clauses that fail fast.
"""

from __future__ import annotations

import logging

from flask import current_app, flash, redirect, url_for
from flask_dance.consumer import oauth_authorized
from flask_dance.contrib.google import make_google_blueprint
from flask_login import login_user

from .extensions import login_manager
from .models import User

logger = logging.getLogger(__name__)

# Flask-Dance reads GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET from
# app.config automatically when client_id/secret are not passed explicitly.
google_bp = make_google_blueprint(
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email",
           "https://www.googleapis.com/auth/userinfo.profile"],
    redirect_to="routes.dashboard",
)

USERINFO_ENDPOINT = "/oauth2/v2/userinfo"


def is_allowed_email(email: str | None, domain: str) -> bool:
    """Return True only for a well-formed address on the allowed domain."""
    if not email or not domain:
        return False
    parts = email.strip().lower().rsplit("@", 1)
    if len(parts) != 2 or not parts[0]:
        return False
    return parts[1] == domain.strip().lower()


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Rebuild the transient user from the email stored in the session."""
    if not user_id:
        return None
    return User(email=user_id)


@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    """Handle Google's OAuth callback: validate the user, then log them in."""
    if not token:
        flash("Google sign-in failed: no token was returned.", "error")
        logger.warning("OAuth authorized signal fired without a token.")
        return False

    resp = blueprint.session.get(USERINFO_ENDPOINT)
    if not resp.ok:
        flash("Could not fetch your Google profile. Please try again.", "error")
        logger.error("userinfo request failed: %s %s", resp.status_code, resp.text)
        return False

    info = resp.json()
    email = info.get("email")
    domain = current_app.config["ALLOWED_EMAIL_DOMAIN"]

    if not is_allowed_email(email, domain):
        flash(f"Access is restricted to @{domain} accounts.", "error")
        logger.warning("Rejected sign-in for non-allowed email: %r", email)
        return False

    login_user(User(email=email, name=info.get("name")))
    flash(f"Signed in as {email}.", "success")

    # Return False so Flask-Dance does not also persist the OAuth token —
    # Flask-Login owns the session from here.
    return False


def register_auth(app) -> None:
    """Attach the auth extensions and blueprint to the app."""
    login_manager.init_app(app)
    app.register_blueprint(google_bp, url_prefix="/login")
