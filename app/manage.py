"""Server-rendered management UI for the tool catalog and user roles.

Reuses the same validation (``validate_tool_payload``) and repositories as the
JSON API, so the rules stay in one place. Routes orchestrate; permission checks
use ``authz``.
"""

from __future__ import annotations

import logging

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from .authz import ROLE_ADMIN, ROLES, admin_required, can_edit_plugin, can_edit_tool
from .github_publisher import sync_published_marketplace_to_github
from .plugin_status import PLUGIN_PUBLISHED, can_transition_plugin
from .plugin_validation import validate_plugin_payload
from .repositories import (
    SqlAlchemyPluginRepository,
    SqlAlchemyToolRepository,
    SqlAlchemyUserRepository,
    distinct_categories,
)
from .validation import validate_tool_payload

logger = logging.getLogger(__name__)

manage = Blueprint("manage", __name__)


def _form_to_payload(form) -> dict:
    """Map submitted form fields to a validation payload."""
    return {
        "name": form.get("name", ""),
        "url": form.get("url", ""),
        "description": form.get("description", ""),
        "category": form.get("category", ""),
        "tags": form.get("tags", ""),
        "sort_order": form.get("sort_order", "0") or "0",
        "is_active": "is_active" in form,
        "owner_id": form.get("owner_id", ""),
    }


def _tool_to_form(tool) -> dict:
    return {
        "name": tool.name,
        "url": tool.url,
        "description": tool.description or "",
        "category": tool.category or "",
        "tags": ", ".join(tool.tags or []),
        "sort_order": tool.sort_order,
        "is_active": tool.is_active,
        "owner_id": tool.owner_id or "",
    }


def _owner_choices() -> list:
    """Users for the admin-only owner dropdown (empty for non-admins)."""
    return SqlAlchemyUserRepository().list() if current_user.is_admin else []


def _render_tool_form(mode: str, tool, form: dict, errors: list):
    return render_template(
        "tool_form.html", mode=mode, tool=tool, form=form, errors=errors,
        users=_owner_choices(), categories=distinct_categories(),
    )


@manage.route("/tools/new", methods=["GET", "POST"])
@login_required
def create_tool():
    if request.method == "GET":
        return _render_tool_form("new", None, {}, [])

    payload = _form_to_payload(request.form)
    cleaned, errors = validate_tool_payload(payload)
    if errors:
        return _render_tool_form("new", None, payload, errors)

    cleaned["owner_id"] = current_user.id  # creator owns it
    tool = SqlAlchemyToolRepository().create(cleaned)
    flash(f"Created “{tool.name}”.", "success")
    return redirect(url_for("routes.dashboard"))


@manage.route("/tools/<int:tool_id>/edit", methods=["GET", "POST"])
@login_required
def edit_tool(tool_id: int):
    repo = SqlAlchemyToolRepository()
    tool = repo.get(tool_id)
    if tool is None:
        abort(404)
    if not can_edit_tool(current_user, tool):
        abort(403)

    if request.method == "GET":
        return _render_tool_form("edit", tool, _tool_to_form(tool), [])

    payload = _form_to_payload(request.form)
    cleaned, errors = validate_tool_payload(payload)
    if errors:
        return _render_tool_form("edit", tool, payload, errors)

    _apply_admin_owner_change(cleaned, request.form)
    repo.update(tool_id, cleaned)
    flash(f"Updated “{cleaned['name']}”.", "success")
    return redirect(url_for("routes.dashboard"))


def _apply_admin_owner_change(cleaned: dict, form) -> None:
    """Admins may reassign the owner; members cannot (field ignored)."""
    if not current_user.is_admin:
        return
    raw = form.get("owner_id", "")
    if raw == "":
        cleaned["owner_id"] = None  # explicit "unowned"
        return
    owner = SqlAlchemyUserRepository().get(int(raw))
    if owner is not None:
        cleaned["owner_id"] = owner.id


@manage.route("/tools/<int:tool_id>/delete", methods=["POST"])
@login_required
def delete_tool(tool_id: int):
    repo = SqlAlchemyToolRepository()
    tool = repo.get(tool_id)
    if tool is None:
        abort(404)
    if not can_edit_tool(current_user, tool):
        abort(403)
    repo.delete(tool_id)
    flash("Tool deleted.", "success")
    return redirect(url_for("routes.dashboard"))


# --- Plugin catalog management (mirrors the tool routes above) ---------------


def _plugin_form_to_payload(form) -> dict:
    """Map submitted plugin form fields to a validation payload."""
    return {
        "name": form.get("name", ""),
        "display_name": form.get("display_name", ""),
        "description": form.get("description", ""),
        "repo": form.get("repo", ""),
        "source_type": form.get("source_type", "github") or "github",
        "version": form.get("version", ""),
        "category": form.get("category", ""),
        "tags": form.get("tags", ""),
        "owner_id": form.get("owner_id", ""),
    }


def _plugin_to_form(plugin) -> dict:
    return {
        "name": plugin.name,
        "display_name": plugin.display_name or "",
        "description": plugin.description or "",
        "repo": plugin.repo,
        "source_type": plugin.source_type,
        "version": plugin.version,
        "category": plugin.category or "",
        "tags": ", ".join(plugin.tags or []),
        "owner_id": plugin.owner_id or "",
    }


def _render_plugin_form(mode: str, plugin, form: dict, errors: list):
    return render_template(
        "plugin_form.html", mode=mode, plugin=plugin, form=form, errors=errors,
        users=_owner_choices(), categories=distinct_categories(),
    )


@manage.route("/plugins/new", methods=["GET", "POST"])
@login_required
def create_plugin():
    if request.method == "GET":
        return _render_plugin_form("new", None, {}, [])

    repo = SqlAlchemyPluginRepository()
    payload = _plugin_form_to_payload(request.form)
    cleaned, errors = validate_plugin_payload(payload)
    if not errors and repo.get_by_name(cleaned["name"]) is not None:
        errors = ["A plugin with that name already exists."]
    if errors:
        return _render_plugin_form("new", None, payload, errors)

    cleaned["owner_id"] = current_user.id  # creator owns it; starts as draft
    plugin = repo.create(cleaned)
    flash(f"Created “{plugin.name}”.", "success")
    return redirect(url_for("routes.plugins"))


@manage.route("/plugins/<int:plugin_id>/edit", methods=["GET", "POST"])
@login_required
def edit_plugin(plugin_id: int):
    repo = SqlAlchemyPluginRepository()
    plugin = repo.get(plugin_id)
    if plugin is None:
        abort(404)
    if not can_edit_plugin(current_user, plugin):
        abort(403)

    if request.method == "GET":
        return _render_plugin_form("edit", plugin, _plugin_to_form(plugin), [])

    payload = _plugin_form_to_payload(request.form)
    cleaned, errors = validate_plugin_payload(payload)
    if not errors:
        conflict = repo.get_by_name(cleaned["name"])
        if conflict is not None and conflict.id != plugin_id:
            errors = ["A plugin with that name already exists."]
    if errors:
        return _render_plugin_form("edit", plugin, payload, errors)

    _apply_admin_owner_change(cleaned, request.form)
    repo.update(plugin_id, cleaned)
    flash(f"Updated “{cleaned['name']}”.", "success")
    return redirect(url_for("routes.plugins"))


@manage.route("/plugins/<int:plugin_id>/delete", methods=["POST"])
@login_required
def delete_plugin(plugin_id: int):
    repo = SqlAlchemyPluginRepository()
    plugin = repo.get(plugin_id)
    if plugin is None:
        abort(404)
    if not can_edit_plugin(current_user, plugin):
        abort(403)
    repo.delete(plugin_id)
    flash("Plugin deleted.", "success")
    return redirect(url_for("routes.plugins"))


@manage.route("/plugins/<int:plugin_id>/transition", methods=["POST"])
@login_required
def transition_plugin(plugin_id: int):
    """One route covers submit/withdraw/approve/reject/unpublish via ``target``."""
    repo = SqlAlchemyPluginRepository()
    plugin = repo.get(plugin_id)
    if plugin is None:
        abort(404)
    target = request.form.get("target", "").strip()
    if not can_transition_plugin(current_user, plugin, target):
        abort(403)

    was_published = plugin.status == PLUGIN_PUBLISHED
    repo.set_status(plugin_id, target)
    flash(f"“{plugin.name}” is now {target}.", "success")

    # The published set only changes when entering or leaving "published".
    if target == PLUGIN_PUBLISHED or was_published:
        _autosync_marketplace()
    return redirect(url_for("routes.plugins"))


def _autosync_marketplace() -> None:
    """Best-effort GitHub mirror after a publish/unpublish; never blocks the UI.

    Stays silent when the mirror simply isn't configured, so non-GitHub setups
    don't see noise; surfaces real failures so an admin can retry via the button.
    """
    result = sync_published_marketplace_to_github()
    if result.ok:
        flash(result.message, "success")
    elif "not configured" not in result.message:
        flash(result.message, "error")


@manage.route("/plugins/sync-github", methods=["POST"])
@login_required
@admin_required
def sync_marketplace_github():
    """Force a resync of the published catalog to the GitHub marketplace repo."""
    result = sync_published_marketplace_to_github()
    flash(result.message, "success" if result.ok else "error")
    return redirect(url_for("routes.plugins"))


@manage.route("/admin/users")
@login_required
@admin_required
def admin_users():
    return render_template("admin_users.html", users=SqlAlchemyUserRepository().list())


@manage.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def set_user_role(user_id: int):
    role = request.form.get("role", "")
    if role not in ROLES:
        flash("Invalid role.", "error")
        return redirect(url_for("manage.admin_users"))
    if user_id == current_user.id and role != ROLE_ADMIN:
        flash("You can't remove your own admin role.", "error")
        return redirect(url_for("manage.admin_users"))

    user = SqlAlchemyUserRepository().set_role(user_id, role)
    if user is None:
        abort(404)
    flash(f"{user.email} is now {role}.", "success")
    return redirect(url_for("manage.admin_users"))
