"""Publish the plugin catalog to the private GitHub monorepo (Cowork/Desktop channel).

Org plugin marketplaces only sync *private* content that lives inside the connected
repo (relative paths) — cross-repo private sources aren't allowed. So this module
mirrors the catalog into ``MARKETPLACE_REPO`` as a monorepo: each published plugin's
source repo is **vendored** into ``plugins/<name>/`` and ``.claude-plugin/marketplace.json``
is regenerated with relative, ``strict:false`` entries.

The sync is a full rebuild done as **one atomic commit** via the Git Data API: it
deletes the existing ``plugins/`` tree, re-vendors every currently-published plugin,
and writes the fresh marketplace document — so it's idempotent and self-healing.
Both the publish/unpublish transition and the admin "Sync to GitHub" button call it.

Security: the token is read from config and never logged. The sync fails closed
(``PublishResult(ok=False, …)``) when GitHub isn't configured.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import requests
from flask import current_app

from .plugin_status import PLUGIN_PUBLISHED
from .repositories import SqlAlchemyPluginRepository

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 15
_DEFAULT_MESSAGE = "Sync marketplace from iPullRank IDP"


@dataclass
class PublishResult:
    ok: bool
    message: str
    commit_url: Optional[str] = None


def build_monorepo_document(config: Any, plugins: list) -> dict[str, Any]:
    """The monorepo marketplace.json: relative sources + inline (strict:false) manifests.

    Each plugin's folder (``plugins/<name>``) is a single-skill plugin, declared
    inline because the org marketplace won't auto-load a bare ``SKILL.md``.
    """
    entries = []
    for p in plugins:
        entry: dict[str, Any] = {
            "name": p.name,
            "displayName": p.display_name or p.name,
            "description": p.description,
            "source": f"./plugins/{p.name}",
            "strict": False,
            "skills": ["./"],
            "version": p.version,
            "category": p.category,
        }
        if p.tags:
            entry["tags"] = p.tags
        entries.append(entry)
    return {
        "name": config["MARKETPLACE_NAME"],
        "owner": {"name": config["MARKETPLACE_OWNER_NAME"]},
        "description": config["MARKETPLACE_DESCRIPTION"],
        "plugins": entries,
    }


class RepoWriter(Protocol):
    """Minimal Git Data API surface — fakeable in tests."""

    def default_branch(self, repo: str) -> str: ...
    def list_blobs(self, repo: str, ref: str) -> list[dict[str, Any]]: ...
    def read_blob(self, repo: str, sha: str) -> str: ...           # base64
    def write_blob(self, repo: str, content: str, encoding: str) -> str: ...  # -> sha
    def head(self, repo: str, branch: str) -> tuple[str, str]: ...  # (commit_sha, tree_sha)
    def make_tree(self, repo: str, base_tree: str, entries: list[dict[str, Any]]) -> str: ...
    def make_commit(self, repo: str, message: str, tree: str, parent: str) -> str: ...
    def move_ref(self, repo: str, branch: str, commit: str) -> None: ...


class GitHubRepoWriter:
    """``RepoWriter`` over the GitHub REST Git Data API."""

    def __init__(self, token: str) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        resp = requests.get(f"{_GITHUB_API}{path}", params=params or None,
                            headers=self._headers(), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        resp = requests.post(f"{_GITHUB_API}{path}", json=body,
                             headers=self._headers(), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def default_branch(self, repo: str) -> str:
        return self._get(f"/repos/{repo}").get("default_branch", "main")

    def list_blobs(self, repo: str, ref: str) -> list[dict[str, Any]]:
        tree = self._get(f"/repos/{repo}/git/trees/{ref}", recursive=1)
        return [e for e in tree.get("tree", []) if e.get("type") == "blob"]

    def read_blob(self, repo: str, sha: str) -> str:
        return self._get(f"/repos/{repo}/git/blobs/{sha}")["content"]  # base64

    def write_blob(self, repo: str, content: str, encoding: str) -> str:
        return self._post(f"/repos/{repo}/git/blobs",
                         {"content": content, "encoding": encoding})["sha"]

    def head(self, repo: str, branch: str) -> tuple[str, str]:
        ref = self._get(f"/repos/{repo}/git/ref/heads/{branch}")
        commit_sha = ref["object"]["sha"]
        commit = self._get(f"/repos/{repo}/git/commits/{commit_sha}")
        return commit_sha, commit["tree"]["sha"]

    def make_tree(self, repo: str, base_tree: str, entries: list[dict[str, Any]]) -> str:
        return self._post(f"/repos/{repo}/git/trees",
                         {"base_tree": base_tree, "tree": entries})["sha"]

    def make_commit(self, repo: str, message: str, tree: str, parent: str) -> str:
        return self._post(f"/repos/{repo}/git/commits",
                         {"message": message, "tree": tree, "parents": [parent]})["sha"]

    def move_ref(self, repo: str, branch: str, commit: str) -> None:
        resp = requests.patch(
            f"{_GITHUB_API}/repos/{repo}/git/refs/heads/{branch}",
            json={"sha": commit}, headers=self._headers(), timeout=_TIMEOUT,
        )
        resp.raise_for_status()


def _build_writer_from_config() -> Optional[GitHubRepoWriter]:
    token = current_app.config.get("GITHUB_MARKETPLACE_TOKEN")
    repo = current_app.config.get("MARKETPLACE_REPO")
    if not token or not repo:
        return None
    return GitHubRepoWriter(token)


def _rebuild_tree_entries(writer: RepoWriter, mono_repo: str, branch: str,
                          json_path: str, document: dict[str, Any],
                          published: list) -> list[dict[str, Any]]:
    """Tree ops for a full rebuild: drop existing plugins/, re-vendor, write marketplace.json."""
    entries: list[dict[str, Any]] = []

    # 1. Delete every existing vendored plugin file (path + null sha removes it under base_tree).
    for blob in writer.list_blobs(mono_repo, branch):
        if blob["path"].startswith("plugins/"):
            entries.append({"path": blob["path"], "sha": None})

    # 2. Re-vendor each published plugin's source repo under plugins/<name>/.
    for plugin in published:
        src = plugin.repo
        src_branch = writer.default_branch(src)
        for blob in writer.list_blobs(src, src_branch):
            content = writer.read_blob(src, blob["sha"])
            new_sha = writer.write_blob(mono_repo, content, "base64")
            entries.append({"path": f"plugins/{plugin.name}/{blob['path']}",
                           "mode": blob["mode"], "type": "blob", "sha": new_sha})

    # 3. Write the regenerated marketplace.json.
    doc_sha = writer.write_blob(
        mono_repo, json.dumps(document, indent=2) + "\n", "utf-8"
    )
    entries.append({"path": json_path, "mode": "100644", "type": "blob", "sha": doc_sha})
    return entries


def sync_published_marketplace_to_github(
    writer: Optional[RepoWriter] = None, message: str = _DEFAULT_MESSAGE,
) -> PublishResult:
    """Full-rebuild the monorepo from the currently-published plugins, in one commit.

    Idempotent and self-healing: vendors every published plugin's files and rewrites
    marketplace.json. Fail-closed with a clear message when GitHub isn't configured.
    """
    if writer is None:
        writer = _build_writer_from_config()
    if writer is None:
        return PublishResult(
            False,
            "GitHub marketplace is not configured "
            "(set GITHUB_MARKETPLACE_TOKEN and MARKETPLACE_REPO).",
        )

    config = current_app.config
    mono_repo = config["MARKETPLACE_REPO"]
    branch = config["MARKETPLACE_REPO_BRANCH"]
    json_path = config["MARKETPLACE_JSON_PATH"]

    published = SqlAlchemyPluginRepository().list(status=PLUGIN_PUBLISHED)
    document = build_monorepo_document(config, published)

    try:
        entries = _rebuild_tree_entries(writer, mono_repo, branch, json_path, document, published)
        commit_sha, base_tree = writer.head(mono_repo, branch)
        tree = writer.make_tree(mono_repo, base_tree, entries)
        new_commit = writer.make_commit(mono_repo, message, tree, commit_sha)
        writer.move_ref(mono_repo, branch, new_commit)
    except requests.RequestException as exc:
        logger.error("GitHub marketplace sync failed: %s", exc)
        return PublishResult(False, f"GitHub sync failed: {exc}")

    commit_url = f"https://github.com/{mono_repo}/commit/{new_commit}"
    return PublishResult(
        True, f"Synced {len(published)} published plugin(s) to {mono_repo}.", commit_url
    )
