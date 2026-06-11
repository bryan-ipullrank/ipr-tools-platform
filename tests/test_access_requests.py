"""Unit tests for the pure repo-access mailto builder."""

from urllib.parse import parse_qs, urlsplit

from app.access_requests import build_access_request_mailto

_ADMINS = ["admin1@ipullrank.com", "admin2@ipullrank.com"]


def _parse(mailto: str):
    """Split a mailto: URL into (recipients, query-dict)."""
    parts = urlsplit(mailto)
    assert parts.scheme == "mailto"
    recipients = parts.path.split(",") if parts.path else []
    query = {k: v[0] for k, v in parse_qs(parts.query).items()}
    return recipients, query


def test_owned_plugin_addresses_owner_and_ccs_admins():
    mailto = build_access_request_mailto(
        repo="ipullrank/backlink-analyzer",
        plugin_label="Backlink Analyzer",
        requester_email="dev@ipullrank.com",
        owner_email="owner@ipullrank.com",
        admin_emails=_ADMINS,
    )
    recipients, query = _parse(mailto)
    assert recipients == ["owner@ipullrank.com"]
    assert set(query["cc"].split(",")) == set(_ADMINS)


def test_unowned_plugin_addresses_admins_with_no_cc():
    mailto = build_access_request_mailto(
        repo="ipullrank/x",
        plugin_label="X",
        requester_email="dev@ipullrank.com",
        owner_email=None,
        admin_emails=_ADMINS,
    )
    recipients, query = _parse(mailto)
    assert set(recipients) == set(_ADMINS)
    assert "cc" not in query


def test_owner_is_not_duplicated_in_cc():
    mailto = build_access_request_mailto(
        repo="ipullrank/x",
        plugin_label="X",
        requester_email="dev@ipullrank.com",
        owner_email="admin1@ipullrank.com",      # owner is also an admin
        admin_emails=_ADMINS,
    )
    recipients, query = _parse(mailto)
    assert recipients == ["admin1@ipullrank.com"]
    assert query.get("cc", "") == "admin2@ipullrank.com"  # owner removed from cc


def test_subject_and_body_carry_repo_and_requester():
    mailto = build_access_request_mailto(
        repo="ipullrank/backlink-analyzer",
        plugin_label="Backlink Analyzer",
        requester_email="dev@ipullrank.com",
        owner_email="owner@ipullrank.com",
        admin_emails=_ADMINS,
    )
    _, query = _parse(mailto)
    assert "ipullrank/backlink-analyzer" in query["subject"]
    assert "dev@ipullrank.com" in query["body"]
    assert "Backlink Analyzer" in query["body"]
    assert "https://github.com/ipullrank/backlink-analyzer" in query["body"]


def test_spaces_are_percent_encoded_not_plus():
    mailto = build_access_request_mailto(
        repo="ipullrank/x", plugin_label="My Plugin",
        requester_email="dev@ipullrank.com", owner_email="o@ipullrank.com",
        admin_emails=[],
    )
    # quote_via=quote encodes spaces as %20; mail clients handle that reliably.
    assert "%20" in mailto
    assert "+" not in mailto.split("?", 1)[1]


def test_handles_empty_admins_gracefully():
    mailto = build_access_request_mailto(
        repo="ipullrank/x", plugin_label="X",
        requester_email="dev@ipullrank.com", owner_email=None, admin_emails=[],
    )
    recipients, _ = _parse(mailto)
    assert recipients == []  # degenerate but well-formed (no recipients)
