"""User-facing routes: login landing, protected dashboard, logout."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for
from flask_dance.contrib.google import google
from flask_login import current_user, login_required, logout_user

from .tools import TOOLS

routes = Blueprint("routes", __name__)


@routes.route("/")
def login():
    """Public landing page. Authenticated users skip straight to the hub."""
    if current_user.is_authenticated:
        return redirect(url_for("routes.dashboard"))
    return render_template("login.html")


@routes.route("/dashboard")
@login_required
def dashboard():
    """The internal tool directory. Requires a signed-in, allowed user."""
    return render_template("dashboard.html", tools=TOOLS)


@routes.route("/logout")
def logout():
    """Clear the Flask-Login session and the cached Google OAuth token."""
    logout_user()
    token = google.blueprint.token
    if token:
        del google.blueprint.token
    return redirect(url_for("routes.login"))
