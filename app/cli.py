"""Custom Flask CLI commands."""

from __future__ import annotations

import click
from flask import Flask

from .authz import ROLES
from .plugins_seed import SEED_PLUGINS
from .repositories import (
    SqlAlchemyPluginRepository,
    SqlAlchemyToolRepository,
    SqlAlchemyUserRepository,
)
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

    @app.cli.command("seed-plugins")
    def seed_plugins() -> None:
        """Insert seed plugins as drafts, skipping any that already exist.

        Idempotent per-name (not all-or-nothing like seed-tools) so adding a new
        entry to SEED_PLUGINS and re-running only inserts the missing ones. Seeds
        land as ``draft`` — an admin reviews and publishes them.
        """
        repo = SqlAlchemyPluginRepository()
        created = 0
        for entry in SEED_PLUGINS:
            if repo.get_by_name(entry["name"]) is not None:
                continue
            repo.create(
                {
                    "name": entry["name"],
                    "display_name": entry.get("display_name", entry["name"]),
                    "description": entry.get("description", ""),
                    "repo": entry["repo"],
                    "source_type": entry.get("source_type", "github"),
                    "version": entry.get("version", "0.1.0"),
                }
            )
            created += 1
        skipped = len(SEED_PLUGINS) - created
        click.echo(f"Seeded {created} new plugin(s) as drafts; {skipped} already present.")

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
