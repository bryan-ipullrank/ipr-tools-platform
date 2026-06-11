"""Mirror the marketplace catalog into a private GitHub repo.

Claude Desktop / Cowork org marketplaces sync from a private GitHub repo's
``.claude-plugin/marketplace.json`` (not an HTTP endpoint), so alongside the Flask
``/marketplace.json`` (Claude Code channel) we commit the same generated document
into a GitHub repo. The IDP stays the source of truth; this just commits the file
via the GitHub Contents REST API.

Security: the token is read from config and **never logged**. The publisher fails
closed — when the token or repo is unconfigured, callers get a clear
``PublishResult(ok=False, …)`` rather than a silent no-op or a crash.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import requests
from flask import current_app

from .marketplace import build_marketplace_document
from .plugin_status import PLUGIN_PUBLISHED
from .repositories import SqlAlchemyPluginRepository

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 10
_DEFAULT_MESSAGE = "Update marketplace.json from iPullRank IDP"


@dataclass
class PublishResult:
    """Outcome of a publish attempt — flashed in the UI / returned by the API."""

    ok: bool
    message: str
    commit_url: Optional[str] = None


class MarketplacePublisher(Protocol):
    """Contract for committing the marketplace document somewhere durable."""

    def publish(self, document: dict[str, Any], message: str) -> PublishResult: ...


class GitHubMarketplacePublisher:
    """Commits ``marketplace.json`` to a GitHub repo via the Contents REST API."""

    def __init__(
        self,
        token: str,
        repo: str,
        path: str = ".claude-plugin/marketplace.json",
        branch: str = "main",
    ) -> None:
        self._token = token
        self._repo = repo
        self._path = path
        self._branch = branch

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _contents_url(self) -> str:
        return f"{_GITHUB_API}/repos/{self._repo}/contents/{self._path}"

    def _current_sha(self) -> Optional[str]:
        """The blob SHA of the existing file, or None when it doesn't exist yet."""
        resp = requests.get(
            self._contents_url(),
            params={"ref": self._branch},
            headers=self._headers(),
            timeout=_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("sha")

    def publish(self, document: dict[str, Any], message: str) -> PublishResult:
        content = json.dumps(document, indent=2) + "\n"
        body: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": self._branch,
        }
        try:
            sha = self._current_sha()
            if sha is not None:
                body["sha"] = sha  # required to update an existing file
            resp = requests.put(
                self._contents_url(), json=body, headers=self._headers(), timeout=_TIMEOUT
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("GitHub marketplace publish failed: %s", exc)
            return PublishResult(False, f"GitHub publish failed: {exc}")

        commit_url = resp.json().get("commit", {}).get("html_url")
        count = len(document.get("plugins", []))
        return PublishResult(True, f"Synced {count} plugin(s) to {self._repo}.", commit_url)


def _build_publisher_from_config() -> Optional[GitHubMarketplacePublisher]:
    """Build the publisher from app config, or None when it isn't configured."""
    token = current_app.config.get("GITHUB_MARKETPLACE_TOKEN")
    repo = current_app.config.get("MARKETPLACE_REPO")
    if not token or not repo:
        return None
    return GitHubMarketplacePublisher(
        token=token,
        repo=repo,
        path=current_app.config["MARKETPLACE_JSON_PATH"],
        branch=current_app.config["MARKETPLACE_REPO_BRANCH"],
    )


def sync_published_marketplace_to_github(
    publisher: Optional[MarketplacePublisher] = None,
    message: str = _DEFAULT_MESSAGE,
) -> PublishResult:
    """Build the published-plugins document and commit it to GitHub.

    ``publisher`` defaults to one built from config; tests inject a fake. Returns a
    ``PublishResult`` — fail-closed with a clear message when GitHub isn't set up.
    """
    if publisher is None:
        publisher = _build_publisher_from_config()
    if publisher is None:
        return PublishResult(
            False,
            "GitHub marketplace is not configured "
            "(set GITHUB_MARKETPLACE_TOKEN and MARKETPLACE_REPO).",
        )

    plugins = SqlAlchemyPluginRepository().list(status=PLUGIN_PUBLISHED)
    document = build_marketplace_document(current_app.config, plugins)
    return publisher.publish(document, message)
