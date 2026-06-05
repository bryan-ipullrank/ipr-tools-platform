"""Seed data for the tool catalog.

The catalog now lives in the database (see ``app/models.py`` ``Tool`` and the
``seed-tools`` CLI command). This list is the one-time seed used to populate an
empty table — it is no longer read directly by the dashboard.

These are placeholders — replace the URLs with the real internal endpoints.
"""

from __future__ import annotations

SEED_TOOLS: list[dict[str, str]] = [
    {
        "name": "GitHub Organization",
        "url": "https://github.com/ipullrank",
        "description": "Source repositories, pull requests, and CI workflows.",
    },
    {
        "name": "Grafana",
        "url": "https://grafana.example.internal",
        "description": "Dashboards and metrics for internal services.",
    },
    {
        "name": "CI / CD Pipelines",
        "url": "https://ci.example.internal",
        "description": "Build, test, and deployment pipeline status.",
    },
]
