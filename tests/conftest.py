"""Shared pytest fixtures.

Important: the ``app`` fixture does NOT hold an application context open while
tests run. Flask-Login caches the current user on ``g`` (which is app-context
scoped), so if one context wrapped multiple test-client requests, every request
would reuse the first user. Setup/assertion helpers open their own short-lived
contexts; client requests run with none active and each gets a fresh context.
"""

import os

import pytest


class _Rec:
    """A detached snapshot of a DB row (plain attributes, no ORM session)."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.fixture
def app(tmp_path):
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")
    os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test-id")
    os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.db'}"

    from app import create_app
    from app.extensions import db

    flask_app = create_app()
    with flask_app.app_context():
        db.create_all()
    yield flask_app
    with flask_app.app_context():
        db.drop_all()


@pytest.fixture
def app_ctx(app):
    """For tests that touch the DB directly (no HTTP request)."""
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    """Factory creating persisted users; returns a detached snapshot."""
    from app.extensions import db
    from app.models import User

    def _make(email, role="member", name=""):
        with app.app_context():
            user = User(email=email, role=role, name=name or email)
            db.session.add(user)
            db.session.commit()
            return _Rec(id=user.id, email=user.email, role=user.role, name=user.name)

    return _make


@pytest.fixture
def client_as(app):
    """Return a test client with a logged-in session for the given user."""

    def _login(user):
        test_client = app.test_client()
        with test_client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return test_client

    return _login
