"""Plugin lifecycle status and transition rules.

A small, data-driven state machine kept pure (no DB, no Flask) so the rules are
unit-testable in isolation and reusable by the management UI, the JSON API, and
templates. Only ``published`` plugins are exposed in ``marketplace.json``.

The lifecycle is ``draft -> pending -> published`` with a ``rejected`` side
state for an admin to bounce a submission back. ``_PLUGIN_TRANSITIONS`` maps a
``(from, to)`` pair to the capability required, where ``"owner"`` means
owner-or-admin and ``"admin"`` means admin only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .authz import can_edit_plugin

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .models import Plugin, User

PLUGIN_DRAFT = "draft"
PLUGIN_PENDING = "pending"
PLUGIN_PUBLISHED = "published"
PLUGIN_REJECTED = "rejected"
PLUGIN_STATUSES = (PLUGIN_DRAFT, PLUGIN_PENDING, PLUGIN_PUBLISHED, PLUGIN_REJECTED)

# Capability required for each allowed (from, to) transition.
#   "owner" -> owner-or-admin (via can_edit_plugin)
#   "admin" -> admin only
_CAP_OWNER = "owner"
_CAP_ADMIN = "admin"

_PLUGIN_TRANSITIONS: dict[tuple[str, str], str] = {
    (PLUGIN_DRAFT, PLUGIN_PENDING): _CAP_OWNER,        # submit for approval
    (PLUGIN_PENDING, PLUGIN_DRAFT): _CAP_OWNER,        # withdraw
    (PLUGIN_PENDING, PLUGIN_PUBLISHED): _CAP_ADMIN,    # approve
    (PLUGIN_PENDING, PLUGIN_REJECTED): _CAP_ADMIN,     # reject
    (PLUGIN_REJECTED, PLUGIN_PENDING): _CAP_OWNER,     # resubmit
    (PLUGIN_PUBLISHED, PLUGIN_DRAFT): _CAP_ADMIN,      # unpublish
}


# Human-readable label for each transition, keyed by (from, to). Kept beside the
# transition table so the UI never has to reconstruct intent from a bare target.
_TRANSITION_LABELS: dict[tuple[str, str], str] = {
    (PLUGIN_DRAFT, PLUGIN_PENDING): "Submit for approval",
    (PLUGIN_PENDING, PLUGIN_DRAFT): "Withdraw",
    (PLUGIN_PENDING, PLUGIN_PUBLISHED): "Approve",
    (PLUGIN_PENDING, PLUGIN_REJECTED): "Reject",
    (PLUGIN_REJECTED, PLUGIN_PENDING): "Resubmit",
    (PLUGIN_PUBLISHED, PLUGIN_DRAFT): "Unpublish",
}


def transition_label(from_status: str, target: str) -> str:
    """Human label for a transition, e.g. (pending, published) -> 'Approve'."""
    return _TRANSITION_LABELS.get((from_status, target), target)


def can_transition_plugin(
    user: "User | Any", plugin: "Plugin | Any", target: str
) -> bool:
    """True when ``user`` may move ``plugin`` from its status to ``target``.

    Guard clauses fail fast: an unauthenticated user, an unknown target status,
    or a ``(from, to)`` pair not in the transition table all return False.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if target not in PLUGIN_STATUSES:
        return False

    capability = _PLUGIN_TRANSITIONS.get((plugin.status, target))
    if capability is None:
        return False
    if capability == _CAP_ADMIN:
        return bool(getattr(user, "is_admin", False))
    return can_edit_plugin(user, plugin)


def allowed_targets(user: "User | Any", plugin: "Plugin | Any") -> list[str]:
    """The status values ``user`` may move ``plugin`` to right now.

    Used by templates to render exactly the action buttons that will succeed.
    """
    return [
        target
        for (source, target) in _PLUGIN_TRANSITIONS
        if source == plugin.status and can_transition_plugin(user, plugin, target)
    ]
