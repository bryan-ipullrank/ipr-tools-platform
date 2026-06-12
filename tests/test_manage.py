"""Tests for the server-rendered management UI (forms + permissions).

These go through HTTP only (no direct DB access) so each request gets its own
app context — see conftest for why that matters.
"""


def _api_create(client, name="X", url="https://x.example"):
    """Create a tool via the API and return its id."""
    return client.post(
        "/api/tools", json={"name": name, "url": url, "category": "SEO"}
    ).get_json()["id"]


def test_create_tool_via_form_sets_owner(make_user, client_as):
    member = make_user("m@ipullrank.com")
    c = client_as(member)
    resp = c.post(
        "/tools/new",
        data={"name": "Grafana", "url": "https://g.example", "category": "SEO", "is_active": "on"},
    )
    assert resp.status_code == 302  # redirect to dashboard on success
    tools = c.get("/api/tools").get_json()
    assert len(tools) == 1
    assert tools[0]["owner_id"] == member.id


def test_create_tool_invalid_rerenders_form(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.post("/tools/new", data={"name": "", "url": "nope"})
    assert resp.status_code == 200          # form re-rendered, not redirected
    assert b"url must be a valid" in resp.data


def test_missing_category_rerenders_form(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.post("/tools/new", data={"name": "X", "url": "https://x.example"})
    assert resp.status_code == 200
    assert b"category is required" in resp.data


def test_dashboard_groups_by_category_and_shows_wip(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    c.post("/tools/new", data={"name": "Grafana", "url": "https://g.example",
                               "category": "Monitoring", "is_active": "on"})
    c.post("/tools/new", data={"name": "Draft Tool", "url": "https://d.example",
                               "category": "Reporting", "tags": "WIP", "is_active": "on"})
    resp = c.get("/dashboard")
    body = resp.data.decode()
    assert "<h2" in body and "Monitoring" in body and "Reporting" in body  # category headers
    assert "wip-stamp" in body                                             # WIP stamp rendered
    assert 'onclick="toggleCategory' in body                               # filter present


def test_member_cannot_open_others_edit_page(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    other = make_user("other@ipullrank.com")
    tool_id = _api_create(client_as(owner))
    assert client_as(other).get(f"/tools/{tool_id}/edit").status_code == 403


def test_owner_can_open_edit_page(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    tool_id = _api_create(c)
    assert c.get(f"/tools/{tool_id}/edit").status_code == 200


def test_admin_reassigns_owner_via_form(make_user, client_as):
    member = make_user("m@ipullrank.com")
    admin = make_user("a@ipullrank.com", role="admin")
    new_owner = make_user("new@ipullrank.com")
    tool_id = _api_create(client_as(member))

    admin_c = client_as(admin)
    resp = admin_c.post(
        f"/tools/{tool_id}/edit",
        data={"name": "X", "url": "https://x.example", "category": "SEO",
              "owner_id": str(new_owner.id), "is_active": "on"},
    )
    assert resp.status_code == 302
    assert admin_c.get(f"/api/tools/{tool_id}").get_json()["owner_id"] == new_owner.id


def test_admin_users_page_requires_admin(make_user, client_as):
    member = make_user("m@ipullrank.com")
    assert client_as(member).get("/admin/users").status_code == 403

    admin = make_user("a@ipullrank.com", role="admin")
    assert client_as(admin).get("/admin/users").status_code == 200


def test_admin_can_promote_member(make_user, client_as):
    admin = make_user("a@ipullrank.com", role="admin")
    member = make_user("m@ipullrank.com")

    resp = client_as(admin).post(
        f"/admin/users/{member.id}/role", data={"role": "admin"}
    )
    assert resp.status_code == 302
    # Behavioral proof: the promoted member can now reach the admin page.
    assert client_as(member).get("/admin/users").status_code == 200


def test_admin_cannot_self_demote(make_user, client_as):
    admin = make_user("a@ipullrank.com", role="admin")
    admin_c = client_as(admin)
    admin_c.post(f"/admin/users/{admin.id}/role", data={"role": "member"})
    # Still an admin: admin page still reachable.
    assert admin_c.get("/admin/users").status_code == 200
