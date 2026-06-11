"""Pure validation for plugin payloads — no Flask deps, directly unit-testable.

Separated from processing (the API routes / repository) so the rules can be
tested in isolation and reused by any writer (UI form, API, future importer).
Mirrors ``validation.validate_tool_payload`` and its ``(cleaned, errors)``
guard-clause contract.

``status`` is intentionally NOT validated here: new plugins always start as
``draft`` and only move through ``plugin_status`` transitions, never via a
payload field.
"""

from __future__ import annotations

import re
from typing import Any

# kebab-case: lowercase alphanumerics joined by single hyphens. This is the
# plugin's install identifier (`<name>@<marketplace>`), so it must be unique and
# URL/CLI-safe.
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# "owner/repo" — a single slash, each side GitHub-name-safe.
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
# semver-ish: MAJOR.MINOR.PATCH with an optional pre-release/build suffix.
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+([-.+].*)?$")

_ALLOWED_SOURCE_TYPES = {"github"}
_DEFAULT_SOURCE_TYPE = "github"


def validate_plugin_payload(data: Any) -> tuple[dict[str, Any], list[str]]:
    """Validate and normalize a plugin payload.

    Returns ``(cleaned, errors)``. When ``errors`` is non-empty, ``cleaned`` is
    empty and callers must not proceed (guard-clause contract).
    """
    if not isinstance(data, dict):
        return {}, ["Request body must be a JSON object."]

    errors: list[str] = []

    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("name is required.")
    elif not _NAME_RE.match(name):
        errors.append("name must be kebab-case (e.g. backlink-analyzer).")

    repo = str(data.get("repo") or "").strip()
    if not repo:
        errors.append("repo is required.")
    elif not _REPO_RE.match(repo):
        errors.append("repo must be in 'owner/repo' format.")

    version = str(data.get("version") or "").strip()
    if not version:
        errors.append("version is required.")
    elif not _VERSION_RE.match(version):
        errors.append("version must be semver-like (e.g. 1.0.0).")

    source_type = str(data.get("source_type") or _DEFAULT_SOURCE_TYPE).strip().lower()
    if source_type not in _ALLOWED_SOURCE_TYPES:
        errors.append(f"source_type must be one of: {', '.join(sorted(_ALLOWED_SOURCE_TYPES))}.")

    if errors:
        return {}, errors

    display_name = str(data.get("display_name") or "").strip() or name
    cleaned = {
        "name": name,
        "display_name": display_name,
        "description": str(data.get("description") or "").strip(),
        "repo": repo,
        "source_type": source_type,
        "version": version,
    }
    return cleaned, []
