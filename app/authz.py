"""Authorization: roles and permission checks.

Pure functions (no DB access) so the rules are unit-testable in isolation and
reusable by routes, the API, and templates. The role constants live here to
avoid a circular import with ``models``.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Iterable

from flask import abort
from flask_login import current_user

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .models import Tool, User

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLES = (ROLE_ADMIN, ROLE_MEMBER)


def is_seed_admin(email: str | None, admin_emails: Iterable[str]) -> bool:
    """True when ``email`` is in the configured bootstrap-admin list."""
    if not email:
        return False
    normalized = {e.strip().lower() for e in admin_emails if e}
    return email.strip().lower() in normalized


def can_edit_tool(user: "User | Any", tool: "Tool | Any") -> bool:
    """Admins may edit any tool; members only the tools they own.

    Tools with no owner (seeded/legacy) are admin-only.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_admin", False):
        return True
    return tool.owner_id is not None and tool.owner_id == user.id


def admin_required(view: Callable) -> Callable:
    """Abort with 403 unless the current user is an admin."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return view(*args, **kwargs)

    return wrapped
