"""Tests for the token-gated Claude Code marketplace endpoint.

Covers the fail-closed gate (503 unconfigured, 401 missing/wrong) and that the
generated document is spec-valid and contains only published plugins.
"""

import base64

from app.plugin_status import PLUGIN_PUBLISHED
from app.repositories import SqlAlchemyPluginRepository

_TOKEN = "s3cret-marketplace-token"


def _auth(password, user="dev"):
    raw = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


def _make_plugin(app, name, status):
    with app.app_context():
        repo = SqlAlchemyPluginRepository()
        plugin = repo.create({
            "name": name, "display_name": name.title(), "description": "desc",
            "repo": f"ipullrank/{name}", "source_type": "github", "version": "1.0.0",
        })
        if status != "draft":
            repo.set_status(plugin.id, status)


def test_503_when_token_unconfigured(app, client):
    app.config["MARKETPLACE_TOKEN"] = None
    resp = client.get("/marketplace.json", headers=_auth("anything"))
    assert resp.status_code == 503


def test_401_without_credentials(app, client):
    app.config["MARKETPLACE_TOKEN"] = _TOKEN
    resp = client.get("/marketplace.json")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


def test_401_with_wrong_token(app, client):
    app.config["MARKETPLACE_TOKEN"] = _TOKEN
    resp = client.get("/marketplace.json", headers=_auth("wrong"))
    assert resp.status_code == 401


def test_200_with_correct_token_and_spec_valid_shape(app, client):
    app.config["MARKETPLACE_TOKEN"] = _TOKEN
    app.config["MARKETPLACE_NAME"] = "ipr-tools"
    _make_plugin(app, "backlink-analyzer", PLUGIN_PUBLISHED)

    resp = client.get("/marketplace.json", headers=_auth(_TOKEN))
    assert resp.status_code == 200
    doc = resp.get_json()

    # Spec-required top-level shape.
    assert doc["name"] == "ipr-tools"
    assert isinstance(doc["owner"], dict) and doc["owner"]["name"]
    assert isinstance(doc["plugins"], list) and len(doc["plugins"]) == 1

    entry = doc["plugins"][0]
    assert entry["name"] == "backlink-analyzer"
    assert entry["source"] == {"source": "github", "repo": "ipullrank/backlink-analyzer"}
    assert entry["version"] == "1.0.0"
    assert "displayName" in entry


def test_only_published_plugins_are_listed(app, client):
    app.config["MARKETPLACE_TOKEN"] = _TOKEN
    _make_plugin(app, "published-one", PLUGIN_PUBLISHED)
    _make_plugin(app, "draft-one", "draft")
    _make_plugin(app, "pending-one", "pending")

    resp = client.get("/marketplace.json", headers=_auth(_TOKEN))
    names = [p["name"] for p in resp.get_json()["plugins"]]
    assert names == ["published-one"]
