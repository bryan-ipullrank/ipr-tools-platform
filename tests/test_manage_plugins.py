"""Tests for the server-rendered plugin management UI (forms + transitions).

HTTP only (no direct DB access) so each request gets its own app context — see
conftest for why that matters.
"""


def _api_create(client, name="backlink-analyzer"):
    """Create a plugin via the API and return its id."""
    return client.post(
        "/api/plugins",
        json={"name": name, "repo": "ipullrank/backlink-analyzer", "version": "1.0.0"},
    ).get_json()["id"]


def _form(**overrides):
    data = {"name": "backlink-analyzer", "repo": "ipullrank/backlink-analyzer",
            "version": "1.0.0", "source_type": "github"}
    data.update(overrides)
    return data


def test_create_plugin_via_form_sets_owner(make_user, client_as):
    member = make_user("m@ipullrank.com")
    c = client_as(member)
    resp = c.post("/plugins/new", data=_form())
    assert resp.status_code == 302  # redirect to /plugins on success
    plugins = c.get("/api/plugins").get_json()
    assert len(plugins) == 1
    assert plugins[0]["owner_id"] == member.id
    assert plugins[0]["status"] == "draft"


def test_create_plugin_invalid_rerenders_form(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.post("/plugins/new", data=_form(name="Bad Name"))
    assert resp.status_code == 200          # form re-rendered, not redirected
    assert b"kebab-case" in resp.data


def test_duplicate_name_rerenders_form(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    c.post("/plugins/new", data=_form())
    resp = c.post("/plugins/new", data=_form())
    assert resp.status_code == 200
    assert b"already exists" in resp.data


def test_member_cannot_open_others_edit_page(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    other = make_user("other@ipullrank.com")
    pid = _api_create(client_as(owner))
    assert client_as(other).get(f"/plugins/{pid}/edit").status_code == 403


def test_owner_can_open_edit_page(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    pid = _api_create(c)
    assert c.get(f"/plugins/{pid}/edit").status_code == 200


def test_plugins_listing_page_renders(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    _api_create(c)
    resp = c.get("/plugins")
    assert resp.status_code == 200
    assert b"backlink-analyzer" in resp.data


def test_listing_renders_request_access_link(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    _api_create(c)
    resp = c.get("/plugins")
    assert resp.status_code == 200
    assert b"Request access" in resp.data
    # The mailto targets the owner and references the repo.
    assert b"mailto:owner@ipullrank.com" in resp.data
    assert b"ipullrank%2Fbacklink-analyzer" in resp.data  # repo url-encoded in body


def test_repo_structure_help_renders_on_listing(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.get("/plugins")
    assert resp.status_code == 200
    assert b'id="repo-help"' in resp.data                  # the modal
    assert b"How must a repo be structured?" in resp.data  # the trigger
    assert b".claude-plugin/plugin.json" in resp.data       # the guidance


def test_repo_structure_help_renders_on_form(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.get("/plugins/new")
    assert resp.status_code == 200
    assert b'id="repo-help"' in resp.data
    assert b"See required structure" in resp.data
    assert b".claude-plugin/plugin.json" in resp.data


def test_full_approval_flow_via_forms(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    admin = make_user("a@ipullrank.com", role="admin")
    pid = _api_create(client_as(owner))

    submit = client_as(owner).post(f"/plugins/{pid}/transition", data={"target": "pending"})
    assert submit.status_code == 302

    approve = client_as(admin).post(f"/plugins/{pid}/transition", data={"target": "published"})
    assert approve.status_code == 302
    assert client_as(owner).get(f"/api/plugins/{pid}").get_json()["status"] == "published"


def test_member_cannot_approve_via_form(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    pid = _api_create(c)
    c.post(f"/plugins/{pid}/transition", data={"target": "pending"})
    assert c.post(f"/plugins/{pid}/transition", data={"target": "published"}).status_code == 403


def test_delete_permissions_via_form(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    other = make_user("other@ipullrank.com")
    pid = _api_create(client_as(owner))
    assert client_as(other).post(f"/plugins/{pid}/delete").status_code == 403
    assert client_as(owner).post(f"/plugins/{pid}/delete").status_code == 302
