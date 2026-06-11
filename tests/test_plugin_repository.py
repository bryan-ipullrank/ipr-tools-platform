"""Round-trip tests for the SQLAlchemy plugin repository."""

from app.plugin_status import PLUGIN_DRAFT, PLUGIN_PUBLISHED
from app.repositories import SqlAlchemyPluginRepository


def _payload(**overrides):
    data = {
        "name": "backlink-analyzer",
        "display_name": "Backlink Analyzer",
        "description": "scoring",
        "repo": "ipullrank/backlink-analyzer",
        "source_type": "github",
        "version": "1.0.0",
    }
    data.update(overrides)
    return data


def test_create_defaults_to_draft(app_ctx):
    repo = SqlAlchemyPluginRepository()
    plugin = repo.create(_payload())
    assert plugin.id is not None
    assert plugin.status == PLUGIN_DRAFT
    assert repo.get(plugin.id).name == "backlink-analyzer"


def test_get_by_name(app_ctx):
    repo = SqlAlchemyPluginRepository()
    repo.create(_payload())
    assert repo.get_by_name("backlink-analyzer").repo == "ipullrank/backlink-analyzer"
    assert repo.get_by_name("missing") is None


def test_list_filters_by_status(app_ctx):
    repo = SqlAlchemyPluginRepository()
    a = repo.create(_payload(name="alpha"))
    repo.create(_payload(name="beta"))
    repo.set_status(a.id, PLUGIN_PUBLISHED)

    assert [p.name for p in repo.list(status=PLUGIN_PUBLISHED)] == ["alpha"]
    assert len(repo.list()) == 2                       # no filter -> all
    assert [p.name for p in repo.list()] == ["alpha", "beta"]  # ordered by name


def test_set_status_and_update_and_delete(app_ctx):
    repo = SqlAlchemyPluginRepository()
    plugin = repo.create(_payload())
    assert repo.set_status(plugin.id, PLUGIN_PUBLISHED).status == PLUGIN_PUBLISHED
    assert repo.update(plugin.id, {"version": "2.0.0"}).version == "2.0.0"
    assert repo.delete(plugin.id) is True
    assert repo.get(plugin.id) is None


def test_mutations_on_missing_return_falsey(app_ctx):
    repo = SqlAlchemyPluginRepository()
    assert repo.update(999, {"version": "9.9.9"}) is None
    assert repo.set_status(999, PLUGIN_PUBLISHED) is None
    assert repo.delete(999) is False


def test_marketplace_entry_shape(app_ctx):
    repo = SqlAlchemyPluginRepository()
    plugin = repo.create(_payload())
    entry = plugin.to_marketplace_entry()
    assert entry == {
        "name": "backlink-analyzer",
        "displayName": "Backlink Analyzer",
        "description": "scoring",
        "source": {"source": "github", "repo": "ipullrank/backlink-analyzer"},
        "version": "1.0.0",
    }
