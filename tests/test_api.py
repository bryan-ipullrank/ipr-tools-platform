"""Endpoint tests for the tools REST API, including ownership rules."""


def _create(client, name="X", url="https://x.example"):
    return client.post("/api/tools", json={"name": name, "url": url, "category": "SEO"})


def test_list_requires_auth(client):
    resp = client.get("/api/tools")
    assert resp.status_code in (302, 401)


def test_list_empty(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.get("/api/tools")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_sets_owner_to_creator(make_user, client_as):
    member = make_user("m@ipullrank.com")
    resp = _create(client_as(member))
    assert resp.status_code == 201
    assert resp.get_json()["owner_id"] == member.id


def test_create_invalid_returns_400(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.post("/api/tools", json={"name": "", "url": "nope"})
    assert resp.status_code == 400
    assert resp.get_json()["errors"]


def test_member_cannot_edit_others_tool(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    other = make_user("other@ipullrank.com")
    tool_id = _create(client_as(owner)).get_json()["id"]

    resp = client_as(other).put(
        f"/api/tools/{tool_id}", json={"name": "Hacked", "url": "https://h.example"}
    )
    assert resp.status_code == 403


def test_owner_can_edit_own_tool(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    tool_id = _create(c).get_json()["id"]
    resp = c.put(f"/api/tools/{tool_id}", json={"name": "Renamed", "url": "https://r.example", "category": "SEO"})
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Renamed"


def test_admin_can_edit_any_tool(make_user, client_as):
    member = make_user("m@ipullrank.com")
    admin = make_user("a@ipullrank.com", role="admin")
    tool_id = _create(client_as(member)).get_json()["id"]

    resp = client_as(admin).put(
        f"/api/tools/{tool_id}", json={"name": "AdminEdit", "url": "https://a.example", "category": "SEO"}
    )
    assert resp.status_code == 200


def test_admin_reassigns_owner(make_user, client_as):
    member = make_user("m@ipullrank.com")
    admin = make_user("a@ipullrank.com", role="admin")
    new_owner = make_user("new@ipullrank.com")
    tool_id = _create(client_as(member)).get_json()["id"]

    resp = client_as(admin).put(
        f"/api/tools/{tool_id}",
        json={"name": "X", "url": "https://x.example", "category": "SEO", "owner_email": "new@ipullrank.com"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["owner_id"] == new_owner.id


def test_member_cannot_reassign_owner(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    other = make_user("other@ipullrank.com")
    c = client_as(owner)
    tool_id = _create(c).get_json()["id"]

    # Owner edits own tool but tries to hand it to someone else -> field ignored.
    resp = c.put(
        f"/api/tools/{tool_id}",
        json={"name": "X", "url": "https://x.example", "category": "SEO", "owner_id": other.id},
    )
    assert resp.status_code == 200
    assert resp.get_json()["owner_id"] == owner.id


def test_admin_reassign_to_missing_user_400(make_user, client_as):
    admin = make_user("a@ipullrank.com", role="admin")
    tool_id = _create(client_as(admin)).get_json()["id"]
    resp = client_as(admin).put(
        f"/api/tools/{tool_id}",
        json={"name": "X", "url": "https://x.example", "category": "SEO", "owner_id": 9999},
    )
    assert resp.status_code == 400


def test_delete_permissions(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    other = make_user("other@ipullrank.com")
    tool_id = _create(client_as(owner)).get_json()["id"]

    assert client_as(other).delete(f"/api/tools/{tool_id}").status_code == 403
    assert client_as(owner).delete(f"/api/tools/{tool_id}").status_code == 204
    assert client_as(owner).get(f"/api/tools/{tool_id}").status_code == 404
