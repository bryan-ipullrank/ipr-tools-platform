"""Data models for the IDP.

``User`` is persisted (one row per developer, upserted on login) and carries a
role used for authorization. ``Tool`` is the catalog entry, optionally owned by
a user.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from flask_login import UserMixin
from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .authz import ROLE_ADMIN, ROLE_MEMBER
from .extensions import db
from .plugin_status import PLUGIN_DRAFT


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
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
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
            "tags": self.tags or [],
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "owner_id": self.owner_id,
            "owner_email": self.owner.email if self.owner else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Plugin(db.Model):
    """A Claude Code plugin entry, published to the org marketplace catalog.

    Structurally a sibling of ``Tool``: optionally owned by a user, with a
    lifecycle ``status`` (see ``plugin_status``) gating whether it appears in
    ``marketplace.json``. ``name`` is the install identifier (``name@market``)
    so it is unique. The payload lives in a GitHub ``repo``; Flask only hosts
    this metadata.
    """

    __tablename__ = "plugins"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
    repo: Mapped[str] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(default="github", server_default="github")
    version: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(
        default="Uncategorized", server_default="Uncategorized"
    )
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    status: Mapped[str] = mapped_column(
        default=PLUGIN_DRAFT, server_default=PLUGIN_DRAFT
    )
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
            "display_name": self.display_name,
            "description": self.description,
            "repo": self.repo,
            "source_type": self.source_type,
            "version": self.version,
            "category": self.category,
            "tags": self.tags or [],
            "status": self.status,
            "owner_id": self.owner_id,
            "owner_email": self.owner.email if self.owner else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_marketplace_entry(self) -> dict[str, Any]:
        """Serialize to a Claude Code marketplace.json plugin entry.

        ``category``/``tags`` are spec-supported, marketplace-specific fields; tags
        are omitted when empty to keep the document tidy.
        """
        entry: dict[str, Any] = {
            "name": self.name,
            "displayName": self.display_name or self.name,
            "description": self.description,
            "source": {"source": self.source_type, "repo": self.repo},
            "version": self.version,
            "category": self.category,
        }
        if self.tags:
            entry["tags"] = self.tags
        return entry
