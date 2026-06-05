"""Pure validation for tool payloads — no Flask deps, directly unit-testable.

Separated from processing (the API routes / repository) so the rules can be
tested in isolation and reused by any future writer (UI form, importer, etc.).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


def _is_valid_url(value: str) -> bool:
    """True for a well-formed http(s) URL with a network location."""
    try:
        parsed = urlparse(value)
    except (ValueError, AttributeError):
        return False
    return parsed.scheme in _ALLOWED_SCHEMES and bool(parsed.netloc)


def validate_tool_payload(data: Any) -> tuple[dict[str, Any], list[str]]:
    """Validate and normalize a tool payload.

    Returns ``(cleaned, errors)``. When ``errors`` is non-empty, ``cleaned`` is
    empty and callers must not proceed (guard-clause contract).
    """
    if not isinstance(data, dict):
        return {}, ["Request body must be a JSON object."]

    errors: list[str] = []

    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("name is required.")

    url = str(data.get("url") or "").strip()
    if not url:
        errors.append("url is required.")
    elif not _is_valid_url(url):
        errors.append("url must be a valid http(s) URL.")

    sort_order_raw = data.get("sort_order", 0)
    sort_order = 0
    try:
        sort_order = int(sort_order_raw)
    except (TypeError, ValueError):
        errors.append("sort_order must be an integer.")

    if errors:
        return {}, errors

    category = data.get("category")
    cleaned = {
        "name": name,
        "url": url,
        "description": str(data.get("description") or "").strip(),
        "category": category.strip() if isinstance(category, str) and category.strip() else None,
        "sort_order": sort_order,
        "is_active": bool(data.get("is_active", True)),
    }
    return cleaned, []
