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

from .authz import ROLE_ADMIN, ROLES, admin_required, can_edit_tool
from .repositories import SqlAlchemyToolRepository, SqlAlchemyUserRepository
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
        "sort_order": tool.sort_order,
        "is_active": tool.is_active,
        "owner_id": tool.owner_id or "",
    }


def _owner_choices() -> list:
    """Users for the admin-only owner dropdown (empty for non-admins)."""
    return SqlAlchemyUserRepository().list() if current_user.is_admin else []


@manage.route("/tools/new", methods=["GET", "POST"])
@login_required
def create_tool():
    if request.method == "GET":
        return render_template(
            "tool_form.html", mode="new", tool=None, form={}, errors=[],
            users=_owner_choices(),
        )

    payload = _form_to_payload(request.form)
    cleaned, errors = validate_tool_payload(payload)
    if errors:
        return render_template(
            "tool_form.html", mode="new", tool=None, form=payload, errors=errors,
            users=_owner_choices(),
        )

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
        return render_template(
            "tool_form.html", mode="edit", tool=tool, form=_tool_to_form(tool),
            errors=[], users=_owner_choices(),
        )

    payload = _form_to_payload(request.form)
    cleaned, errors = validate_tool_payload(payload)
    if errors:
        return render_template(
            "tool_form.html", mode="edit", tool=tool, form=payload, errors=errors,
            users=_owner_choices(),
        )

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
