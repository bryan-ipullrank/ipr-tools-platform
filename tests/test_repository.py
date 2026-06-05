"""Round-trip tests for the SQLAlchemy repositories."""

from app.repositories import SqlAlchemyToolRepository, SqlAlchemyUserRepository


def _payload(**overrides):
    data = {
        "name": "Grafana",
        "url": "https://g.example",
        "description": "metrics",
        "category": None,
        "sort_order": 0,
        "is_active": True,
    }
    data.update(overrides)
    return data


def test_create_and_get(app_ctx):
    repo = SqlAlchemyToolRepository()
    tool = repo.create(_payload())
    assert tool.id is not None
    assert repo.get(tool.id).name == "Grafana"


def test_list_excludes_inactive_by_default(app_ctx):
    repo = SqlAlchemyToolRepository()
    repo.create(_payload(name="Active"))
    repo.create(_payload(name="Hidden", is_active=False))
    assert [t.name for t in repo.list()] == ["Active"]
    assert len(repo.list(include_inactive=True)) == 2


def test_list_is_ordered_by_sort_order(app_ctx):
    repo = SqlAlchemyToolRepository()
    repo.create(_payload(name="Second", sort_order=2))
    repo.create(_payload(name="First", sort_order=1))
    assert [t.name for t in repo.list()] == ["First", "Second"]


def test_update_and_delete(app_ctx):
    repo = SqlAlchemyToolRepository()
    tool = repo.create(_payload())
    updated = repo.update(tool.id, {"name": "Renamed"})
    assert updated.name == "Renamed"
    assert repo.delete(tool.id) is True
    assert repo.get(tool.id) is None


def test_update_and_delete_missing_return_falsey(app_ctx):
    repo = SqlAlchemyToolRepository()
    assert repo.update(999, {"name": "x"}) is None
    assert repo.delete(999) is False


def test_user_upsert_is_idempotent_and_normalizes_email(app_ctx):
    users = SqlAlchemyUserRepository()
    first = users.upsert_on_login("Bryan@IPullRank.com", "Bryan", seed_admin=False)
    again = users.upsert_on_login("bryan@ipullrank.com", "Bryan M", seed_admin=False)
    assert first.id == again.id            # same row, not a duplicate
    assert again.email == "bryan@ipullrank.com"
    assert again.name == "Bryan M"         # name refreshed
    assert len(users.list()) == 1


def test_seed_admin_is_promoted_on_login(app_ctx):
    users = SqlAlchemyUserRepository()
    user = users.upsert_on_login("a@ipullrank.com", "A", seed_admin=True)
    assert user.role == "admin"


def test_set_role(app_ctx):
    users = SqlAlchemyUserRepository()
    user = users.upsert_on_login("m@ipullrank.com", "M", seed_admin=False)
    assert user.role == "member"
    users.set_role(user.id, "admin")
    assert users.get(user.id).role == "admin"
    assert users.set_role(999, "admin") is None
