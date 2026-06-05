"""Unit tests for the pure authorization helpers."""

from types import SimpleNamespace

from app.authz import ROLE_ADMIN, ROLE_MEMBER, can_edit_tool, is_seed_admin


def _user(uid, role=ROLE_MEMBER):
    return SimpleNamespace(id=uid, role=role, is_authenticated=True,
                           is_admin=(role == ROLE_ADMIN))


def _tool(owner_id):
    return SimpleNamespace(owner_id=owner_id)


def test_is_seed_admin_matches_case_insensitively():
    admins = {"bryan@ipullrank.com"}
    assert is_seed_admin("Bryan@IPullRank.com", admins) is True
    assert is_seed_admin("someone@ipullrank.com", admins) is False
    assert is_seed_admin(None, admins) is False
    assert is_seed_admin("bryan@ipullrank.com", set()) is False


def test_admin_can_edit_any_tool():
    assert can_edit_tool(_user(1, ROLE_ADMIN), _tool(owner_id=2)) is True
    assert can_edit_tool(_user(1, ROLE_ADMIN), _tool(owner_id=None)) is True


def test_member_can_edit_only_own():
    assert can_edit_tool(_user(5), _tool(owner_id=5)) is True
    assert can_edit_tool(_user(5), _tool(owner_id=6)) is False


def test_member_cannot_edit_unowned_tool():
    assert can_edit_tool(_user(5), _tool(owner_id=None)) is False


def test_anonymous_cannot_edit():
    anon = SimpleNamespace(is_authenticated=False)
    assert can_edit_tool(anon, _tool(owner_id=None)) is False
    assert can_edit_tool(None, _tool(owner_id=1)) is False
