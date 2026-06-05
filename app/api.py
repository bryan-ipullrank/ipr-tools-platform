"""REST API for the tool catalog.

Every handler is a thin orchestrator: parse -> validate -> authorize ->
repository -> serialize, with guard clauses and explicit logging on failure
paths. All endpoints sit behind the same Flask-Login session as the rest of the
app; writes are additionally gated by ``can_edit_tool``.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from .authz import can_edit_tool
from .repositories import (
    SqlAlchemyToolRepository,
    SqlAlchemyUserRepository,
    ToolRepository,
)
from .validation import validate_tool_payload

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__, url_prefix="/api")

_TRUTHY = {"1", "true", "yes", "on"}


def _repo() -> ToolRepository:
    return SqlAlchemyToolRepository()


def _json_error(message: str, status: int, errors: list[str] | None = None) -> tuple[Response, int]:
    payload: dict[str, Any] = {"error": message}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), status


def _resolve_owner_id(payload: dict[str, Any]) -> tuple[int | None, tuple[Response, int] | None]:
    """Resolve an admin-supplied owner reference to a user id.

    Returns ``(owner_id, error)``. ``owner_id`` is None when no owner field was
    supplied (caller leaves ownership unchanged). ``error`` is a ready response
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


@api.route("/tools", methods=["GET"])
@login_required
def list_tools() -> tuple[Response, int]:
    include_inactive = request.args.get("include_inactive", "").lower() in _TRUTHY
    tools = _repo().list(include_inactive=include_inactive)
    return jsonify([tool.to_dict() for tool in tools]), 200


@api.route("/tools/<int:tool_id>", methods=["GET"])
@login_required
def get_tool(tool_id: int) -> tuple[Response, int]:
    tool = _repo().get(tool_id)
    if tool is None:
        return _json_error("Tool not found.", 404)
    return jsonify(tool.to_dict()), 200


@api.route("/tools", methods=["POST"])
@login_required
def create_tool() -> tuple[Response, int]:
    cleaned, errors = validate_tool_payload(request.get_json(silent=True))
    if errors:
        logger.info("Rejected tool create: %s", errors)
        return _json_error("Validation failed.", 400, errors)
    cleaned["owner_id"] = current_user.id  # creator owns it
    tool = _repo().create(cleaned)
    return jsonify(tool.to_dict()), 201


@api.route("/tools/<int:tool_id>", methods=["PUT"])
@login_required
def update_tool(tool_id: int) -> tuple[Response, int]:
    repo = _repo()
    tool = repo.get(tool_id)
    if tool is None:
        return _json_error("Tool not found.", 404)
    if not can_edit_tool(current_user, tool):
        return _json_error("You do not have permission to edit this tool.", 403)

    payload = request.get_json(silent=True) or {}
    cleaned, errors = validate_tool_payload(payload)
    if errors:
        logger.info("Rejected tool update %s: %s", tool_id, errors)
        return _json_error("Validation failed.", 400, errors)

    # Owner reassignment is admin-only; a non-admin's owner field is ignored.
    if current_user.is_admin:
        owner_id, error = _resolve_owner_id(payload)
        if error is not None:
            return error
        if owner_id is not None:
            cleaned["owner_id"] = owner_id

    updated = repo.update(tool_id, cleaned)
    return jsonify(updated.to_dict()), 200


@api.route("/tools/<int:tool_id>", methods=["DELETE"])
@login_required
def delete_tool(tool_id: int) -> tuple[Any, int]:
    repo = _repo()
    tool = repo.get(tool_id)
    if tool is None:
        return _json_error("Tool not found.", 404)
    if not can_edit_tool(current_user, tool):
        return _json_error("You do not have permission to delete this tool.", 403)
    repo.delete(tool_id)
    return "", 204
