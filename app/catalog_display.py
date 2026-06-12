"""Pure display/normalization helpers for the tool & plugin catalogs.

No Flask or DB deps, so the rules (tag parsing, category grouping, the WIP stamp)
are unit-testable in isolation and reused by validators, routes, and templates.
"""

from __future__ import annotations

from typing import Any, Iterable

UNCATEGORIZED = "Uncategorized"
_WIP_TAG = "wip"  # reserved tag, matched case-insensitively; shown as a stamp


def parse_tags(raw: Any) -> list[str]:
    """Normalize tags from a comma-separated string or a list into a clean list.

    Trims whitespace, drops blanks, and de-duplicates case-insensitively while
    preserving first-seen casing and order.
    """
    if isinstance(raw, str):
        items = raw.split(",")
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        tag = str(item).strip()
        key = tag.lower()
        if tag and key not in seen:
            seen.add(key)
            cleaned.append(tag)
    return cleaned


def display_tags(tags: Iterable[str] | None) -> list[str]:
    """Tags shown to users — the reserved ``WIP`` tag is rendered as a stamp instead."""
    return [t for t in (tags or []) if t.strip().lower() != _WIP_TAG]


def wip_stamp(tags: Iterable[str] | None, published: bool = True) -> bool:
    """True when a card should show the red WIP stamp.

    A manual ``WIP`` tag flags work-in-progress on any entry; additionally, an
    unpublished plugin (``published=False``) is always WIP. Tools call this with
    the default ``published=True``, so only the tag matters for them.
    """
    if not published:
        return True
    return any(str(t).strip().lower() == _WIP_TAG for t in (tags or []))


def group_by_category(items: Iterable[Any]) -> list[tuple[str, list[Any]]]:
    """Group catalog entries by ``category`` into ``[(category, [items]), …]``.

    Categories are sorted alphabetically with ``Uncategorized`` last; item order
    within a group is preserved (callers pre-order by sort_order/name).
    """
    groups: dict[str, list[Any]] = {}
    for item in items:
        category = (getattr(item, "category", None) or UNCATEGORIZED).strip() or UNCATEGORIZED
        groups.setdefault(category, []).append(item)

    def _key(name: str) -> tuple[int, str]:
        return (1 if name == UNCATEGORIZED else 0, name.lower())

    return [(name, groups[name]) for name in sorted(groups, key=_key)]
