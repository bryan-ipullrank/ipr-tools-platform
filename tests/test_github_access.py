"""Tests for repo-access checks + catalog-scoped invitation auto-accept."""

from app.github_access import ensure_repo_access


class _FakeAccess:
    """Fake GitHubAccess: configurable readable repos + pending invitations."""

    def __init__(self, readable=None, invitations=None):
        self.readable = set(readable or [])
        self.invitations = list(invitations or [])   # [{id, repo}]
        self.accepted = []

    def can_read(self, repo):
        return repo in self.readable

    def pending_invitations(self):
        return self.invitations

    def accept_invitation(self, invitation_id):
        self.accepted.append(invitation_id)
        # Accepting grants read access to that invite's repo.
        for inv in self.invitations:
            if inv["id"] == invitation_id:
                self.readable.add(inv["repo"])


def test_already_readable_needs_no_invite():
    fake = _FakeAccess(readable={"o/repo"})
    assert ensure_repo_access("o/repo", access=fake) is True
    assert fake.accepted == []          # no invitation touched


def test_accepts_only_the_matching_invitation():
    fake = _FakeAccess(
        readable=set(),
        invitations=[{"id": 1, "repo": "o/other"}, {"id": 2, "repo": "o/repo"}],
    )
    assert ensure_repo_access("o/repo", access=fake) is True
    assert fake.accepted == [2]          # only the invite for the asked repo


def test_no_matching_invitation_returns_false():
    fake = _FakeAccess(readable=set(), invitations=[{"id": 1, "repo": "o/other"}])
    assert ensure_repo_access("o/repo", access=fake) is False
    assert fake.accepted == []           # never auto-joins an unrelated repo


def test_unconfigured_gate_is_open(app_ctx):
    # No GITHUB_MARKETPLACE_TOKEN on the test app -> don't block submission.
    assert ensure_repo_access("o/repo") is True
