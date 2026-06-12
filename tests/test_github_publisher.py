"""Tests for the monorepo marketplace publisher (Git Data API full rebuild)."""

import json
from types import SimpleNamespace

from app import github_publisher
from app.github_publisher import (
    build_monorepo_document,
    sync_published_marketplace_to_github,
)
from app.plugin_status import PLUGIN_PUBLISHED

_MONO = "bryan-ipullrank/ipr-marketplace"

_CONFIG = {
    "MARKETPLACE_NAME": "ipr-tools",
    "MARKETPLACE_OWNER_NAME": "iPullRank Engineering",
    "MARKETPLACE_DESCRIPTION": "Internal SEO & engineering plugins",
}


def _plugin(name, repo, category="SEO", tags=None):
    return SimpleNamespace(name=name, display_name=name.title(), description="d",
                           repo=repo, version="1.0.0", category=category, tags=tags or [])


# --- monorepo document -------------------------------------------------------


def test_monorepo_document_uses_relative_strict_false_entries():
    doc = build_monorepo_document(_CONFIG, [_plugin("schema-markup", "o/schema-markup",
                                                    tags=["json-ld"])])
    entry = doc["plugins"][0]
    assert entry["source"] == "./plugins/schema-markup"
    assert entry["strict"] is False
    assert entry["skills"] == ["./"]
    assert entry["category"] == "SEO"
    assert entry["tags"] == ["json-ld"]


# --- full-rebuild sync via a fake Git Data writer ----------------------------


class _FakeRepoWriter:
    """In-memory Git Data API: serves source trees, records the rebuilt tree."""

    def __init__(self, source_trees, mono_existing):
        self._source_trees = source_trees          # {repo: [{path, mode, sha}]}
        self._mono_existing = mono_existing          # [{path, mode, sha}]
        self.written = {}                            # sha -> content
        self.tree_entries = None
        self.moved_to = None
        self._n = 0

    def default_branch(self, repo):
        return "main"

    def list_blobs(self, repo, ref):
        if repo == _MONO:
            return [{**b, "type": "blob"} for b in self._mono_existing]
        return [{**b, "type": "blob"} for b in self._source_trees.get(repo, [])]

    def read_blob(self, repo, sha):
        return f"b64-{repo}-{sha}"

    def write_blob(self, repo, content, encoding):
        self._n += 1
        sha = f"new{self._n}"
        self.written[sha] = content
        return sha

    def head(self, repo, branch):
        return "commit0"

    def make_tree(self, repo, entries):
        self.tree_entries = entries
        return "tree1"

    def make_commit(self, repo, message, tree, parent):
        return "commitNEW"

    def move_ref(self, repo, branch, commit):
        self.moved_to = (branch, commit)


def _configure(app_ctx):
    from flask import current_app
    current_app.config["MARKETPLACE_REPO"] = _MONO
    current_app.config.update(_CONFIG)


def test_sync_not_configured_is_failclosed(app_ctx):
    # No writer + no GITHUB_MARKETPLACE_TOKEN/MARKETPLACE_REPO on the test app.
    result = sync_published_marketplace_to_github()
    assert result.ok is False
    assert "not configured" in result.message


def test_full_rebuild_vendors_published_and_writes_marketplace(app_ctx):
    from app.repositories import SqlAlchemyPluginRepository

    _configure(app_ctx)
    repo = SqlAlchemyPluginRepository()
    pub = repo.create({"name": "schema-markup", "display_name": "Schema Markup",
                       "description": "d", "repo": "bryan-ipullrank/schema-markup",
                       "source_type": "github", "version": "1.0.0", "category": "Technical SEO"})
    repo.set_status(pub.id, PLUGIN_PUBLISHED)
    repo.create({"name": "draft-one", "display_name": "Draft", "description": "d",
                 "repo": "bryan-ipullrank/draft-one", "source_type": "github",
                 "version": "1.0.0", "category": "SEO"})  # draft -> excluded

    fake = _FakeRepoWriter(
        source_trees={"bryan-ipullrank/schema-markup": [
            {"path": "SKILL.md", "mode": "100644", "sha": "s1"},
            {"path": "references/guide.md", "mode": "100644", "sha": "s2"},
        ]},
        mono_existing=[
            {"path": "README.md", "mode": "100644", "sha": "r1"},          # must be preserved
            {"path": "plugins/old/SKILL.md", "mode": "100644", "sha": "o1"},  # must be removed
        ],
    )

    result = sync_published_marketplace_to_github(writer=fake)
    assert result.ok is True
    assert fake.moved_to == ("main", "commitNEW")

    paths = {e["path"]: e for e in fake.tree_entries}
    # complete tree: README carried forward by its existing sha, stale plugin dropped
    assert paths["README.md"]["sha"] == "r1"
    assert "plugins/old/SKILL.md" not in paths
    # published plugin vendored under plugins/<name>/
    assert "plugins/schema-markup/SKILL.md" in paths
    assert "plugins/schema-markup/references/guide.md" in paths
    # marketplace.json regenerated with only the published plugin, relative source
    doc_entry = paths[".claude-plugin/marketplace.json"]
    doc = json.loads(fake.written[doc_entry["sha"]])
    names = [p["name"] for p in doc["plugins"]]
    assert names == ["schema-markup"]
    assert doc["plugins"][0]["source"] == "./plugins/schema-markup"
    assert doc["plugins"][0]["strict"] is False


# --- admin route -------------------------------------------------------------


def test_sync_route_requires_admin(make_user, client_as):
    member = make_user("m@ipullrank.com")
    assert client_as(member).post("/plugins/sync-github").status_code == 403


def test_admin_sync_route_redirects(make_user, client_as):
    admin = make_user("a@ipullrank.com", role="admin")
    # GitHub isn't configured on the test app -> fail-closed, but still a clean redirect.
    assert client_as(admin).post("/plugins/sync-github").status_code == 302
