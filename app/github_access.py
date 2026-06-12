"""GitHub repo-access checks + auto-accepting collaborator invitations.

A plugin's source repo is private and may be owned by a teammate. To publish it,
the IDP's GitHub account (the owner of MARKETPLACE_REPO / GITHUB_MARKETPLACE_TOKEN)
needs read access. The teammate grants it by adding that account as a collaborator
on GitHub, which sends a *repository invitation*; the IDP then **auto-accepts** it —
so nobody has to click "accept" on GitHub.

Security: ``ensure_repo_access`` only ever accepts the invitation **for the exact
repo it was asked about** (always a catalog plugin's repo), so the account never
auto-joins arbitrary repos it's invited to. The token is read from config and never
logged. When GitHub isn't configured the gate is a no-op (returns True) — it's a
publish-readiness convenience, not a security boundary (vendoring still enforces
real access at publish time).
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

import requests
from flask import current_app

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 10


class GitHubAccess(Protocol):
    """Minimal GitHub access surface — fakeable in tests."""

    def can_read(self, repo: str) -> bool: ...
    def pending_invitations(self) -> list[dict[str, Any]]: ...  # [{id, repo}]
    def accept_invitation(self, invitation_id: int) -> None: ...


class GitHubAccessClient:
    """``GitHubAccess`` over the GitHub REST API using the marketplace token."""

    def __init__(self, token: str) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def can_read(self, repo: str) -> bool:
        resp = requests.get(f"{_GITHUB_API}/repos/{repo}", headers=self._headers(), timeout=_TIMEOUT)
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False  # private + no access reads as 404
        resp.raise_for_status()
        return False

    def pending_invitations(self) -> list[dict[str, Any]]:
        resp = requests.get(
            f"{_GITHUB_API}/user/repository_invitations", headers=self._headers(), timeout=_TIMEOUT
        )
        resp.raise_for_status()
        return [
            {"id": inv["id"], "repo": inv.get("repository", {}).get("full_name", "")}
            for inv in resp.json()
        ]

    def accept_invitation(self, invitation_id: int) -> None:
        resp = requests.patch(
            f"{_GITHUB_API}/user/repository_invitations/{invitation_id}",
            headers=self._headers(), timeout=_TIMEOUT,
        )
        resp.raise_for_status()


def _build_access_from_config() -> Optional[GitHubAccessClient]:
    token = current_app.config.get("GITHUB_MARKETPLACE_TOKEN")
    if not token:
        return None
    return GitHubAccessClient(token)


def ensure_repo_access(repo: str, access: Optional[GitHubAccess] = None) -> bool:
    """True if the IDP can read ``repo`` (accepting its pending invite if needed).

    Only the invitation whose repo matches ``repo`` is accepted — the IDP never
    auto-joins repos outside what it was asked about. Fail-open (True) when GitHub
    isn't configured or on a transient error, so submission isn't blocked by an
    unconfigured/flaky integration; real enforcement happens at publish (vendor) time.
    """
    if access is None:
        access = _build_access_from_config()
    if access is None:
        return True  # GitHub not configured — don't gate submission

    try:
        if access.can_read(repo):
            return True
        for invitation in access.pending_invitations():
            if invitation["repo"].lower() == repo.lower():
                logger.info("Accepting repo invitation for %s", repo)
                access.accept_invitation(invitation["id"])
                return access.can_read(repo)
        return False
    except requests.RequestException as exc:
        logger.warning("Repo access check for %s failed, allowing submission: %s", repo, exc)
        return True
