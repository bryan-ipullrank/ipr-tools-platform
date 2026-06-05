"""Shared Flask extension singletons.

Kept in their own module so ``app/__init__.py``, ``app/auth.py``, and route
modules can all import the same instances without circular imports.
"""

from __future__ import annotations

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

login_manager = LoginManager()
login_manager.login_view = "routes.login"
login_manager.login_message = "Please sign in to access the developer portal."

# Deterministic constraint names so SQLite batch migrations (table rebuilds)
# can drop/recreate constraints by name.
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base enabling SQLAlchemy 2.0 typed (``Mapped``) models."""

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
