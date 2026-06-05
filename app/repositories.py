"""Data-access layer for the tool catalog.

A ``Protocol`` defines the contract so callers (routes, CLI) depend on the
abstraction, not the SQLAlchemy implementation — making the behavior swappable
and easy to fake in tests (composition over inheritance).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy import select

from .authz import ROLE_ADMIN, ROLE_MEMBER
from .extensions import db
from .models import Tool, User


class ToolRepository(Protocol):
    """Contract for tool persistence."""

    def list(self, include_inactive: bool = False) -> list[Tool]: ...

    def get(self, tool_id: int) -> Tool | None: ...

    def create(self, data: dict[str, Any]) -> Tool: ...

    def update(self, tool_id: int, data: dict[str, Any]) -> Tool | None: ...

    def delete(self, tool_id: int) -> bool: ...


class SqlAlchemyToolRepository:
    """SQLAlchemy-backed ``ToolRepository``."""

    def list(self, include_inactive: bool = False) -> list[Tool]:
        stmt = select(Tool)
        if not include_inactive:
            stmt = stmt.where(Tool.is_active.is_(True))
        stmt = stmt.order_by(Tool.sort_order, Tool.name)
        return list(db.session.scalars(stmt))

    def get(self, tool_id: int) -> Tool | None:
        return db.session.get(Tool, tool_id)

    def create(self, data: dict[str, Any]) -> Tool:
        tool = Tool(**data)
        db.session.add(tool)
        db.session.commit()
        return tool

    def update(self, tool_id: int, data: dict[str, Any]) -> Tool | None:
        tool = self.get(tool_id)
        if tool is None:
            return None
        for key, value in data.items():
            setattr(tool, key, value)
        db.session.commit()
        return tool

    def delete(self, tool_id: int) -> bool:
        tool = self.get(tool_id)
        if tool is None:
            return False
        db.session.delete(tool)
        db.session.commit()
        return True


class UserRepository(Protocol):
    """Contract for user persistence."""

    def get(self, user_id: int) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def list(self) -> list[User]: ...

    def upsert_on_login(self, email: str, name: str | None, seed_admin: bool) -> User: ...

    def set_role(self, user_id: int, role: str) -> User | None: ...


class SqlAlchemyUserRepository:
    """SQLAlchemy-backed ``UserRepository``."""

    def get(self, user_id: int) -> User | None:
        return db.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        return db.session.scalar(select(User).where(User.email == normalized))

    def list(self) -> list[User]:
        return list(db.session.scalars(select(User).order_by(User.email)))

    def upsert_on_login(self, email: str, name: str | None, seed_admin: bool) -> User:
        """Create the user on first login, or refresh name/last_login otherwise.

        A seed admin (email in IDP_ADMINS) is always (re)promoted to admin so the
        bootstrap list stays authoritative; it never demotes.
        """
        normalized = email.strip().lower()
        user = self.get_by_email(normalized)
        if user is None:
            user = User(
                email=normalized,
                name=name or "",
                role=ROLE_ADMIN if seed_admin else ROLE_MEMBER,
            )
            db.session.add(user)
        else:
            if name:
                user.name = name
            if seed_admin and user.role != ROLE_ADMIN:
                user.role = ROLE_ADMIN
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
        return user

    def set_role(self, user_id: int, role: str) -> User | None:
        user = self.get(user_id)
        if user is None:
            return None
        user.role = role
        db.session.commit()
        return user
