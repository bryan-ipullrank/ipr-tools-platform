"""Seed data for the plugin catalog.

Inserted (as unpublished drafts) by the ``seed-plugins`` CLI command so the
catalog isn't empty on first deploy. An admin reviews each entry and publishes it.

Each entry below is a **single-skill plugin repo**: a private GitHub repo with a
``SKILL.md`` at its root (plus references/scripts), which Claude Code auto-loads
as a one-skill plugin — no ``.claude-plugin/plugin.json`` required (v2.1.142+).
Because the repos are private, an installing developer needs GitHub access; the
"Request access" link on each plugin emails the owner/admins to arrange it.

``name`` mirrors the repo's ``SKILL.md`` frontmatter ``name`` so the install id
(``name@ipr-tools``) and the skill's invocation name line up.
"""

from __future__ import annotations

from typing import Any

_OWNER = "bryan-ipullrank"


def _entry(
    name: str, display_name: str, description: str, category: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """One single-skill repo seed (repo == owner/name, github, v1.0.0)."""
    return {
        "name": name,
        "display_name": display_name,
        "description": description,
        "repo": f"{_OWNER}/{name}",
        "source_type": "github",
        "version": "1.0.0",
        "category": category,
        "tags": tags or [],
    }


SEED_PLUGINS: list[dict[str, Any]] = [
    _entry(
        "wikipedia-entity-builder",
        "Wikipedia Entity Builder",
        "Builds a Wikipedia readiness package — Wikidata presence check, notability "
        "triage, a Wikidata property template, and an AfC-ready wikitext draft.",
        category="Knowledge Graph",
        tags=["wikipedia", "wikidata", "entities"],
    ),
    _entry(
        "wikidata-querier",
        "Wikidata Querier",
        "Queries Wikidata for entity research: QIDs, SPARQL, and SEO knowledge-graph "
        "signals (Wikipedia coverage, knowledge-panel fields, co-occurring entities).",
        category="Knowledge Graph",
        tags=["wikidata", "sparql", "entities"],
    ),
    _entry(
        "screaming-frog-crawl",
        "Screaming Frog Crawl",
        "Runs a headless Screaming Frog SEO Spider crawl via CLI and exports the CSV "
        "files that downstream SEO audit skills consume.",
        category="Technical SEO",
        tags=["crawling", "screaming-frog"],
    ),
    _entry(
        "schema-markup",
        "Schema Markup",
        "Audits JSON-LD structured data for AI-search visibility, scores gaps against "
        "required/recommended types, and generates ready-to-implement schema templates.",
        category="Technical SEO",
        tags=["json-ld", "structured-data", "ai-search"],
    ),
    _entry(
        "backlink-404-redirect-map",
        "Backlink 404 Redirect Map",
        "Finds live backlinks (SEMrush + Ahrefs) pointing at 404 pages and builds a "
        "prioritized 301 redirect map to recover lost link equity.",
        category="Link Building",
        tags=["backlinks", "redirects"],
    ),
]
