"""Registry of internal tools shown on the dashboard.

Phase 1 is a static directory: edit this list to add, remove, or relabel a
tool tile. Each entry needs ``name``, ``url``, and ``description``.

These are placeholders — replace the URLs with the real internal endpoints.
"""

from __future__ import annotations

TOOLS: list[dict[str, str]] = [
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
