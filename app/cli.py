"""Custom Flask CLI commands."""

from __future__ import annotations

import click
from flask import Flask

from .authz import ROLES
from .repositories import SqlAlchemyToolRepository, SqlAlchemyUserRepository
from .tools import SEED_TOOLS


def register_cli(app: Flask) -> None:
    """Attach IDP management commands to the Flask CLI."""

    @app.cli.command("seed-tools")
    def seed_tools() -> None:
        """Insert the placeholder tools if the catalog is empty (idempotent)."""
        repo = SqlAlchemyToolRepository()
        if repo.list(include_inactive=True):
            click.echo("Tools already present; skipping seed.")
            return
        for order, entry in enumerate(SEED_TOOLS):
            repo.create(
                {
                    "name": entry["name"],
                    "url": entry["url"],
                    "description": entry.get("description", ""),
                    "category": entry.get("category"),
                    "sort_order": order,
                    "is_active": True,
                }
            )
        click.echo(f"Seeded {len(SEED_TOOLS)} tools.")

    @app.cli.command("set-role")
    @click.argument("email")
    @click.argument("role")
    def set_role(email: str, role: str) -> None:
        """Set a user's role: `flask set-role someone@ipullrank.com admin`.

        The user must have logged in at least once (so a row exists).
        """
        if role not in ROLES:
            click.echo(f"Invalid role {role!r}; expected one of {ROLES}.")
            return
        users = SqlAlchemyUserRepository()
        user = users.get_by_email(email)
        if user is None:
            click.echo(f"No user with email {email!r}. They must sign in once first.")
            return
        users.set_role(user.id, role)
        click.echo(f"{user.email} is now {role}.")
