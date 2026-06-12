"""Unit tests for the pure plugin-payload validator."""

from app.plugin_validation import validate_plugin_payload


def _valid(**overrides):
    data = {"name": "backlink-analyzer", "repo": "ipullrank/backlink-analyzer",
            "version": "1.0.0", "category": "SEO"}
    data.update(overrides)
    return data


def test_valid_payload_is_normalized():
    cleaned, errors = validate_plugin_payload(_valid(name="  backlink-analyzer "))
    assert errors == []
    assert cleaned["name"] == "backlink-analyzer"
    assert cleaned["repo"] == "ipullrank/backlink-analyzer"
    assert cleaned["version"] == "1.0.0"
    assert cleaned["source_type"] == "github"   # defaulted
    assert cleaned["display_name"] == "backlink-analyzer"  # defaults to name


def test_display_name_defaults_to_name_when_blank():
    cleaned, _ = validate_plugin_payload(_valid(display_name="   "))
    assert cleaned["display_name"] == "backlink-analyzer"


def test_display_name_preserved_when_given():
    cleaned, _ = validate_plugin_payload(_valid(display_name="Backlink Analyzer"))
    assert cleaned["display_name"] == "Backlink Analyzer"


def test_non_kebab_name_is_rejected():
    for bad in ("Backlink_Analyzer", "Backlink Analyzer", "-leading", "trailing-",
                "UPPER", "double--hyphen"):
        cleaned, errors = validate_plugin_payload(_valid(name=bad))
        assert cleaned == {}, bad
        assert any("kebab" in e for e in errors), bad


def test_missing_name_is_rejected():
    cleaned, errors = validate_plugin_payload(_valid(name=""))
    assert cleaned == {}
    assert any("name" in e for e in errors)


def test_bad_repo_format_is_rejected():
    for bad in ("noslash", "too/many/slashes", "/missingowner", "owner/"):
        cleaned, errors = validate_plugin_payload(_valid(repo=bad))
        assert cleaned == {}, bad
        assert any("repo" in e for e in errors), bad


def test_bad_version_is_rejected():
    for bad in ("1.0", "v1.0.0", "abc", "1"):
        cleaned, errors = validate_plugin_payload(_valid(version=bad))
        assert cleaned == {}, bad
        assert any("version" in e for e in errors), bad


def test_prerelease_version_is_allowed():
    cleaned, errors = validate_plugin_payload(_valid(version="1.2.3-beta.1"))
    assert errors == []
    assert cleaned["version"] == "1.2.3-beta.1"


def test_unknown_source_type_is_rejected():
    cleaned, errors = validate_plugin_payload(_valid(source_type="gitlab"))
    assert cleaned == {}
    assert any("source_type" in e for e in errors)


def test_missing_category_is_rejected():
    cleaned, errors = validate_plugin_payload(_valid(category=""))
    assert cleaned == {}
    assert any("category" in e for e in errors)


def test_tags_are_parsed():
    cleaned, _ = validate_plugin_payload(_valid(tags="a, b ,a"))
    assert cleaned["tags"] == ["a", "b"]


def test_non_dict_is_rejected():
    cleaned, errors = validate_plugin_payload("nope")
    assert cleaned == {}
    assert errors
