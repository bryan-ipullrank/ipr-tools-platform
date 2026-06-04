"""Transient user model for the IDP.

Phase 1 has no database. A ``User`` is built from the Google profile on each
login and rebuilt from the email stored in the signed session cookie on every
subsequent request via the Flask-Login ``user_loader``.
"""

from __future__ import annotations

from flask_login import UserMixin


class User(UserMixin):
    """A logged-in developer. ``id`` is the email address."""

    def __init__(self, email: str, name: str | None = None) -> None:
        self.id = email
        self.email = email
        self.name = name or email
