"""Unit tests for the pure catalog display/normalization helpers."""

from types import SimpleNamespace

from app.catalog_display import (
    UNCATEGORIZED,
    display_tags,
    group_by_category,
    parse_tags,
    wip_stamp,
)


def test_parse_tags_from_string_trims_dedupes():
    assert parse_tags("  a, b ,a , ,B") == ["a", "b"]  # case-insensitive dedupe, blanks dropped


def test_parse_tags_from_list():
    assert parse_tags(["x", " y ", "x"]) == ["x", "y"]


def test_parse_tags_handles_non_iterable():
    assert parse_tags(None) == []
    assert parse_tags(5) == []


def test_display_tags_hides_reserved_wip():
    assert display_tags(["WIP", "json-ld", "wip"]) == ["json-ld"]


def test_wip_stamp_from_tag_case_insensitive():
    assert wip_stamp(["WIP"]) is True
    assert wip_stamp(["wip"]) is True
    assert wip_stamp(["other"]) is False
    assert wip_stamp([]) is False


def test_wip_stamp_unpublished_is_always_wip():
    assert wip_stamp([], published=False) is True
    assert wip_stamp(["x"], published=True) is False


def test_group_by_category_orders_uncategorized_last():
    items = [
        SimpleNamespace(name="b", category="SEO"),
        SimpleNamespace(name="a", category=None),       # -> Uncategorized
        SimpleNamespace(name="c", category="Content"),
        SimpleNamespace(name="d", category="SEO"),
    ]
    groups = group_by_category(items)
    assert [c for c, _ in groups] == ["Content", "SEO", UNCATEGORIZED]
    # order within a group is preserved
    seo = dict(groups)["SEO"]
    assert [i.name for i in seo] == ["b", "d"]
