"""Unit tests for the pure plugin status state machine."""

from types import SimpleNamespace

from app.authz import ROLE_ADMIN, ROLE_MEMBER
from app.plugin_status import (
    PLUGIN_DRAFT,
    PLUGIN_PENDING,
    PLUGIN_PUBLISHED,
    PLUGIN_REJECTED,
    allowed_targets,
    can_transition_plugin,
    transition_label,
)


def _user(uid, role=ROLE_MEMBER):
    return SimpleNamespace(id=uid, role=role, is_authenticated=True,
                           is_admin=(role == ROLE_ADMIN))


def _plugin(status, owner_id):
    return SimpleNamespace(status=status, owner_id=owner_id)


def test_owner_can_submit_draft_for_approval():
    owner = _user(1)
    assert can_transition_plugin(owner, _plugin(PLUGIN_DRAFT, 1), PLUGIN_PENDING) is True


def test_non_owner_member_cannot_submit():
    other = _user(2)
    assert can_transition_plugin(other, _plugin(PLUGIN_DRAFT, 1), PLUGIN_PENDING) is False


def test_only_admin_can_approve():
    admin = _user(9, ROLE_ADMIN)
    owner = _user(1)
    pending = _plugin(PLUGIN_PENDING, 1)
    assert can_transition_plugin(admin, pending, PLUGIN_PUBLISHED) is True
    assert can_transition_plugin(owner, pending, PLUGIN_PUBLISHED) is False


def test_only_admin_can_reject_and_unpublish():
    admin = _user(9, ROLE_ADMIN)
    owner = _user(1)
    assert can_transition_plugin(admin, _plugin(PLUGIN_PENDING, 1), PLUGIN_REJECTED) is True
    assert can_transition_plugin(owner, _plugin(PLUGIN_PENDING, 1), PLUGIN_REJECTED) is False
    assert can_transition_plugin(admin, _plugin(PLUGIN_PUBLISHED, 1), PLUGIN_DRAFT) is True
    assert can_transition_plugin(owner, _plugin(PLUGIN_PUBLISHED, 1), PLUGIN_DRAFT) is False


def test_owner_can_withdraw_and_resubmit():
    owner = _user(1)
    assert can_transition_plugin(owner, _plugin(PLUGIN_PENDING, 1), PLUGIN_DRAFT) is True
    assert can_transition_plugin(owner, _plugin(PLUGIN_REJECTED, 1), PLUGIN_PENDING) is True


def test_illegal_transitions_are_blocked():
    admin = _user(9, ROLE_ADMIN)
    # draft -> published directly is not in the table
    assert can_transition_plugin(admin, _plugin(PLUGIN_DRAFT, 1), PLUGIN_PUBLISHED) is False
    # published -> pending is not allowed
    assert can_transition_plugin(admin, _plugin(PLUGIN_PUBLISHED, 1), PLUGIN_PENDING) is False


def test_unknown_target_is_blocked():
    admin = _user(9, ROLE_ADMIN)
    assert can_transition_plugin(admin, _plugin(PLUGIN_DRAFT, 1), "bogus") is False


def test_anonymous_cannot_transition():
    anon = SimpleNamespace(is_authenticated=False)
    assert can_transition_plugin(anon, _plugin(PLUGIN_DRAFT, 1), PLUGIN_PENDING) is False
    assert can_transition_plugin(None, _plugin(PLUGIN_DRAFT, 1), PLUGIN_PENDING) is False


def test_allowed_targets_for_admin_on_pending():
    admin = _user(9, ROLE_ADMIN)
    targets = set(allowed_targets(admin, _plugin(PLUGIN_PENDING, 1)))
    assert targets == {PLUGIN_DRAFT, PLUGIN_PUBLISHED, PLUGIN_REJECTED}


def test_allowed_targets_for_owner_on_draft():
    owner = _user(1)
    assert allowed_targets(owner, _plugin(PLUGIN_DRAFT, 1)) == [PLUGIN_PENDING]


def test_transition_label_is_human_readable():
    assert transition_label(PLUGIN_PENDING, PLUGIN_PUBLISHED) == "Approve"
    assert transition_label(PLUGIN_DRAFT, PLUGIN_PENDING) == "Submit for approval"
    assert transition_label(PLUGIN_PUBLISHED, PLUGIN_DRAFT) == "Unpublish"
