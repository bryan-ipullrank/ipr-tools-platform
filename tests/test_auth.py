"""Unit tests for the domain-restriction logic — the one critical guard."""

import pytest

from app.auth import is_allowed_email

DOMAIN = "ipullrank.com"


@pytest.mark.parametrize(
    "email",
    [
        "bryan@ipullrank.com",
        "Bryan@IPullRank.com",   # case-insensitive
        "  ada@ipullrank.com  ",  # surrounding whitespace tolerated
    ],
)
def test_allows_company_domain(email):
    assert is_allowed_email(email, DOMAIN) is True


@pytest.mark.parametrize(
    "email",
    [
        "user@gmail.com",
        "user@notipullrank.com",
        "user@sub.ipullrank.com",  # subdomain is a different domain
        "@ipullrank.com",          # missing local part
        "ipullrank.com",           # no @
        "",
        None,
    ],
)
def test_rejects_everything_else(email):
    assert is_allowed_email(email, DOMAIN) is False


def test_rejects_when_domain_missing():
    assert is_allowed_email("bryan@ipullrank.com", "") is False
