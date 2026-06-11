"""Tests for the GitHub marketplace mirror (publisher + sync service + route)."""

import base64
import json
from types import SimpleNamespace

import pytest

from app import github_publisher
from app.github_publisher import (
    GitHubMarketplacePublisher,
    PublishResult,
    sync_published_marketplace_to_github,
)
from app.marketplace import build_marketplace_document
from app.plugin_status import PLUGIN_PUBLISHED


_CONFIG = {
    "MARKETPLACE_NAME": "ipr-tools",
    "MARKETPLACE_OWNER_NAME": "iPullRank Engineering",
    "MARKETPLACE_DESCRIPTION": "Internal SEO & engineering plugins",
}


class _FakePlugin:
    def __init__(self, name):
        self._name = name

    def to_marketplace_entry(self):
        return {"name": self._name, "source": {"source": "github", "repo": f"o/{self._name}"}}


class _FakePublisher:
    """Records the last document it was asked to publish."""

    def __init__(self):
        self.document = None
        self.message = None

    def publish(self, document, message):
        self.document = document
        self.message = message
        return PublishResult(True, "ok", "https://github.com/o/r/commit/abc")


# --- document builder --------------------------------------------------------


def test_build_marketplace_document_shape():
    doc = build_marketplace_document(_CONFIG, [_FakePlugin("a"), _FakePlugin("b")])
    assert doc["name"] == "ipr-tools"
    assert doc["owner"] == {"name": "iPullRank Engineering"}
    assert [p["name"] for p in doc["plugins"]] == ["a", "b"]


# --- sync service ------------------------------------------------------------


def test_sync_not_configured_returns_failure(app_ctx):
    # No GITHUB_MARKETPLACE_TOKEN / MARKETPLACE_REPO on the test app.
    result = sync_published_marketplace_to_github()
    assert result.ok is False
    assert "not configured" in result.message


def test_sync_uses_injected_publisher_with_published_plugins(app_ctx):
    from app.repositories import SqlAlchemyPluginRepository

    repo = SqlAlchemyPluginRepository()
    pub = repo.create({
        "name": "alpha", "display_name": "Alpha", "description": "",
        "repo": "bryan-ipullrank/alpha", "source_type": "github", "version": "1.0.0",
    })
    repo.set_status(pub.id, PLUGIN_PUBLISHED)
    repo.create({  # draft — must NOT be mirrored
        "name": "beta", "display_name": "Beta", "description": "",
        "repo": "bryan-ipullrank/beta", "source_type": "github", "version": "1.0.0",
    })

    fake = _FakePublisher()
    result = sync_published_marketplace_to_github(publisher=fake)
    assert result.ok is True
    names = [p["name"] for p in fake.document["plugins"]]
    assert names == ["alpha"]  # only the published one


# --- GitHubMarketplacePublisher (HTTP monkeypatched) -------------------------


def _resp(status, payload):
    return SimpleNamespace(
        status_code=status,
        json=lambda: payload,
        raise_for_status=lambda: None,
    )


def test_publisher_updates_existing_file_with_sha(monkeypatch):
    calls = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        return _resp(200, {"sha": "existing-sha"})

    def fake_put(url, json=None, headers=None, timeout=None):
        calls["body"] = json
        return _resp(200, {"commit": {"html_url": "https://github.com/o/r/commit/xyz"}})

    monkeypatch.setattr(github_publisher.requests, "get", fake_get)
    monkeypatch.setattr(github_publisher.requests, "put", fake_put)

    pub = GitHubMarketplacePublisher(token="t", repo="o/r")
    result = pub.publish({"name": "ipr-tools", "plugins": [{"name": "a"}]}, "msg")

    assert result.ok is True
    assert result.commit_url.endswith("/xyz")
    body = calls["body"]
    assert body["sha"] == "existing-sha"               # update path
    decoded = base64.b64decode(body["content"]).decode()
    assert json.loads(decoded)["name"] == "ipr-tools"  # content is the doc


def test_publisher_creates_new_file_without_sha(monkeypatch):
    captured = {}
    monkeypatch.setattr(github_publisher.requests, "get",
                        lambda *a, **k: _resp(404, {}))
    monkeypatch.setattr(github_publisher.requests, "put",
                        lambda url, json=None, **k: captured.update(body=json) or _resp(201, {"commit": {}}))

    pub = GitHubMarketplacePublisher(token="t", repo="o/r")
    result = pub.publish({"name": "x", "plugins": []}, "msg")
    assert result.ok is True
    assert "sha" not in captured["body"]  # create path, no SHA


def test_publisher_reports_network_failure(monkeypatch):
    def boom(*a, **k):
        raise github_publisher.requests.RequestException("network down")

    monkeypatch.setattr(github_publisher.requests, "get", boom)
    pub = GitHubMarketplacePublisher(token="t", repo="o/r")
    result = pub.publish({"name": "x", "plugins": []}, "msg")
    assert result.ok is False
    assert "failed" in result.message.lower()


# --- admin route -------------------------------------------------------------


def test_sync_route_requires_admin(make_user, client_as):
    member = make_user("m@ipullrank.com")
    assert client_as(member).post("/plugins/sync-github").status_code == 403


def test_admin_sync_route_invokes_publisher(make_user, client_as, monkeypatch):
    admin = make_user("a@ipullrank.com", role="admin")
    monkeypatch.setattr(
        github_publisher, "_build_publisher_from_config", lambda: _FakePublisher()
    )
    resp = client_as(admin).post("/plugins/sync-github")
    assert resp.status_code == 302  # redirect back to /plugins with a flash
