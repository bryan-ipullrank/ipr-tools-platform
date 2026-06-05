"""Data models for the IDP.

``User`` is persisted (one row per developer, upserted on login) and carries a
role used for authorization. ``Tool`` is the catalog entry, optionally owned by
a user.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from flask_login import UserMixin
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .authz import ROLE_ADMIN, ROLE_MEMBER
from .extensions import db


class User(UserMixin, db.Model):
    """A developer who has signed in. The integer ``id`` is the login id."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(default="")
    role: Mapped[str] = mapped_column(default=ROLE_MEMBER, server_default=ROLE_MEMBER)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
        }


class Tool(db.Model):
    """An internal tool listed in the developer portal catalog."""

    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    url: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(default="")
    category: Mapped[Optional[str]] = mapped_column(default=None)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[Optional[User]] = relationship("User", lazy="joined")

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "category": self.category,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "owner_id": self.owner_id,
            "owner_email": self.owner.email if self.owner else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
