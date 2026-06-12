"""User-facing routes: login landing, protected dashboard, logout."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for
from flask_dance.contrib.google import google
from flask_login import current_user, login_required, logout_user

from .access_requests import build_access_request_mailto
from .authz import ROLE_ADMIN
from .catalog_display import group_by_category
from .repositories import (
    SqlAlchemyPluginRepository,
    SqlAlchemyToolRepository,
    SqlAlchemyUserRepository,
    distinct_categories,
)

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
    """The internal tool directory, grouped by category. Requires a signed-in user."""
    tools = SqlAlchemyToolRepository().list()
    return render_template(
        "dashboard.html",
        groups=group_by_category(tools),
        categories=distinct_categories(),
    )


@routes.route("/plugins")
@login_required
def plugins():
    """The internal Claude Code plugin catalog with lifecycle + access controls."""
    all_plugins = SqlAlchemyPluginRepository().list()
    admin_emails = [
        u.email for u in SqlAlchemyUserRepository().list() if u.role == ROLE_ADMIN
    ]
    access_links = {
        plugin.id: build_access_request_mailto(
            repo=plugin.repo,
            plugin_label=plugin.display_name or plugin.name,
            requester_email=current_user.email,
            owner_email=plugin.owner.email if plugin.owner else None,
            admin_emails=admin_emails,
        )
        for plugin in all_plugins
    }
    return render_template(
        "plugins.html",
        groups=group_by_category(all_plugins),
        access_links=access_links,
        categories=distinct_categories(),
    )


@routes.route("/logout")
def logout():
    """Clear the Flask-Login session and the cached Google OAuth token."""
    logout_user()
    token = google.blueprint.token
    if token:
        del google.blueprint.token
    return redirect(url_for("routes.login"))
