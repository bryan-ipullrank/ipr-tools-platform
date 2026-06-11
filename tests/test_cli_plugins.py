"""Tests for the seed-plugins CLI command (drafts + idempotency)."""

from app.plugins_seed import SEED_PLUGINS


def test_every_seed_entry_is_valid():
    """A malformed seed would silently fail to insert — catch it here."""
    from app.plugin_validation import validate_plugin_payload

    for entry in SEED_PLUGINS:
        cleaned, errors = validate_plugin_payload(entry)
        assert errors == [], f"{entry['name']}: {errors}"


def test_seed_plugins_inserts_drafts(app):
    from app.repositories import SqlAlchemyPluginRepository

    result = app.test_cli_runner().invoke(args=["seed-plugins"])
    assert result.exit_code == 0
    assert f"Seeded {len(SEED_PLUGINS)} new" in result.output

    with app.app_context():
        plugins = SqlAlchemyPluginRepository().list()
    assert len(plugins) == len(SEED_PLUGINS)
    assert all(p.status == "draft" for p in plugins)          # never auto-published
    assert {p.name for p in plugins} == {e["name"] for e in SEED_PLUGINS}


def test_seed_plugins_is_idempotent(app):
    from app.repositories import SqlAlchemyPluginRepository

    app.test_cli_runner().invoke(args=["seed-plugins"])
    second = app.test_cli_runner().invoke(args=["seed-plugins"])
    assert "Seeded 0 new" in second.output

    with app.app_context():
        assert len(SqlAlchemyPluginRepository().list()) == len(SEED_PLUGINS)


def test_seed_plugins_only_adds_missing(app):
    """Pre-creating one seed leaves seed-plugins to insert just the rest."""
    from app.plugin_validation import validate_plugin_payload
    from app.repositories import SqlAlchemyPluginRepository

    first = SEED_PLUGINS[0]
    with app.app_context():
        cleaned, errors = validate_plugin_payload(first)
        assert errors == []
        SqlAlchemyPluginRepository().create(cleaned)

    result = app.test_cli_runner().invoke(args=["seed-plugins"])
    expected_new = len(SEED_PLUGINS) - 1
    assert f"Seeded {expected_new} new" in result.output
    with app.app_context():
        assert len(SqlAlchemyPluginRepository().list()) == len(SEED_PLUGINS)
