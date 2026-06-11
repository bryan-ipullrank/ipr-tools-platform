"""REST API for the plugin catalog.

Mirrors ``api.py`` (the tool catalog API): every handler is a thin orchestrator
— parse -> validate -> authorize -> repository -> serialize — with guard clauses
and explicit logging on failure paths. All endpoints sit behind the same
Flask-Login session as the rest of the app; writes are gated by
``can_edit_plugin`` and status changes by ``can_transition_plugin``.

This is the programmatic surface Phase 4 automation can use to publish plugins.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from .authz import can_edit_plugin
from .plugin_status import can_transition_plugin
from .plugin_validation import validate_plugin_payload
from .repositories import (
    PluginRepository,
    SqlAlchemyPluginRepository,
    SqlAlchemyUserRepository,
)

logger = logging.getLogger(__name__)

api_plugins = Blueprint("api_plugins", __name__, url_prefix="/api")


def _repo() -> PluginRepository:
    return SqlAlchemyPluginRepository()


def _json_error(message: str, status: int, errors: list[str] | None = None) -> tuple[Response, int]:
    payload: dict[str, Any] = {"error": message}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), status


def _name_conflict(repo: PluginRepository, name: str, exclude_id: int | None) -> bool:
    """True when another plugin already uses ``name`` (it's the unique id)."""
    existing = repo.get_by_name(name)
    return existing is not None and existing.id != exclude_id


def _resolve_owner_id(payload: dict[str, Any]) -> tuple[int | None, tuple[Response, int] | None]:
    """Resolve an admin-supplied owner reference to a user id.

    Returns ``(owner_id, error)``. ``owner_id`` is None when no owner field was
    supplied (caller leaves ownership unchanged); ``error`` is a ready response
    tuple when the supplied owner does not resolve.
    """
    if "owner_id" not in payload and "owner_email" not in payload:
        return None, None

    users = SqlAlchemyUserRepository()
    if payload.get("owner_id") is not None:
        owner = users.get(payload["owner_id"])
    else:
        owner = users.get_by_email(str(payload.get("owner_email", "")))

    if owner is None:
        return None, _json_error("Specified owner does not exist.", 400)
    return owner.id, None


@api_plugins.route("/plugins", methods=["GET"])
@login_required
def list_plugins() -> tuple[Response, int]:
    status = request.args.get("status") or None
    plugins = _repo().list(status=status)
    return jsonify([plugin.to_dict() for plugin in plugins]), 200


@api_plugins.route("/plugins/<int:plugin_id>", methods=["GET"])
@login_required
def get_plugin(plugin_id: int) -> tuple[Response, int]:
    plugin = _repo().get(plugin_id)
    if plugin is None:
        return _json_error("Plugin not found.", 404)
    return jsonify(plugin.to_dict()), 200


@api_plugins.route("/plugins", methods=["POST"])
@login_required
def create_plugin() -> tuple[Response, int]:
    repo = _repo()
    cleaned, errors = validate_plugin_payload(request.get_json(silent=True))
    if errors:
        logger.info("Rejected plugin create: %s", errors)
        return _json_error("Validation failed.", 400, errors)
    if _name_conflict(repo, cleaned["name"], exclude_id=None):
        return _json_error("A plugin with that name already exists.", 409)

    cleaned["owner_id"] = current_user.id  # creator owns it; starts as draft
    plugin = repo.create(cleaned)
    return jsonify(plugin.to_dict()), 201


@api_plugins.route("/plugins/<int:plugin_id>", methods=["PUT"])
@login_required
def update_plugin(plugin_id: int) -> tuple[Response, int]:
    repo = _repo()
    plugin = repo.get(plugin_id)
    if plugin is None:
        return _json_error("Plugin not found.", 404)
    if not can_edit_plugin(current_user, plugin):
        return _json_error("You do not have permission to edit this plugin.", 403)

    payload = request.get_json(silent=True) or {}
    cleaned, errors = validate_plugin_payload(payload)
    if errors:
        logger.info("Rejected plugin update %s: %s", plugin_id, errors)
        return _json_error("Validation failed.", 400, errors)
    if _name_conflict(repo, cleaned["name"], exclude_id=plugin_id):
        return _json_error("A plugin with that name already exists.", 409)

    # Owner reassignment is admin-only; a non-admin's owner field is ignored.
    if current_user.is_admin:
        owner_id, error = _resolve_owner_id(payload)
        if error is not None:
            return error
        if owner_id is not None:
            cleaned["owner_id"] = owner_id

    updated = repo.update(plugin_id, cleaned)
    return jsonify(updated.to_dict()), 200


@api_plugins.route("/plugins/<int:plugin_id>", methods=["DELETE"])
@login_required
def delete_plugin(plugin_id: int) -> tuple[Any, int]:
    repo = _repo()
    plugin = repo.get(plugin_id)
    if plugin is None:
        return _json_error("Plugin not found.", 404)
    if not can_edit_plugin(current_user, plugin):
        return _json_error("You do not have permission to delete this plugin.", 403)
    repo.delete(plugin_id)
    return "", 204


@api_plugins.route("/plugins/<int:plugin_id>/transition", methods=["POST"])
@login_required
def transition_plugin(plugin_id: int) -> tuple[Response, int]:
    """Move a plugin's lifecycle status (submit/approve/reject/unpublish)."""
    repo = _repo()
    plugin = repo.get(plugin_id)
    if plugin is None:
        return _json_error("Plugin not found.", 404)

    target = str((request.get_json(silent=True) or {}).get("target") or "").strip()
    if not can_transition_plugin(current_user, plugin, target):
        return _json_error("That status change is not allowed.", 403)

    updated = repo.set_status(plugin_id, target)
    return jsonify(updated.to_dict()), 200
