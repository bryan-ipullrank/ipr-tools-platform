"""Unit tests for the pure tool-payload validator."""

from app.validation import validate_tool_payload


def test_valid_payload_is_normalized():
    cleaned, errors = validate_tool_payload(
        {"name": "  Grafana ", "url": "https://g.example", "category": "SEO",
         "tags": "a, b", "sort_order": "5"}
    )
    assert errors == []
    assert cleaned["name"] == "Grafana"
    assert cleaned["url"] == "https://g.example"
    assert cleaned["sort_order"] == 5          # coerced from string
    assert cleaned["is_active"] is True        # defaulted
    assert cleaned["category"] == "SEO"
    assert cleaned["tags"] == ["a", "b"]       # parsed from comma string


def test_missing_name_is_rejected():
    cleaned, errors = validate_tool_payload({"url": "https://x.example"})
    assert cleaned == {}
    assert any("name" in e for e in errors)


def test_malformed_url_is_rejected():
    cleaned, errors = validate_tool_payload({"name": "X", "url": "not-a-url"})
    assert cleaned == {}
    assert any("url" in e for e in errors)


def test_non_dict_is_rejected():
    cleaned, errors = validate_tool_payload("nope")
    assert cleaned == {}
    assert errors


def test_bad_sort_order_is_rejected():
    cleaned, errors = validate_tool_payload(
        {"name": "X", "url": "https://x.example", "sort_order": "abc"}
    )
    assert cleaned == {}
    assert any("sort_order" in e for e in errors)


def test_blank_category_is_rejected():
    cleaned, errors = validate_tool_payload(
        {"name": "X", "url": "https://x.example", "category": "   "}
    )
    assert cleaned == {}
    assert any("category" in e for e in errors)
