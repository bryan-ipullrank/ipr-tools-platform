"""Endpoint tests for the plugins REST API: CRUD, ownership, transitions."""


def _create(client, name="backlink-analyzer", repo="ipullrank/backlink-analyzer",
            version="1.0.0"):
    return client.post(
        "/api/plugins",
        json={"name": name, "repo": repo, "version": version, "category": "SEO"},
    )


def test_list_requires_auth(client):
    resp = client.get("/api/plugins")
    assert resp.status_code in (302, 401)


def test_list_empty(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.get("/api/plugins")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_sets_owner_and_draft(make_user, client_as):
    member = make_user("m@ipullrank.com")
    resp = _create(client_as(member))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["owner_id"] == member.id
    assert body["status"] == "draft"


def test_create_invalid_returns_400(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    resp = c.post("/api/plugins", json={"name": "Bad Name", "repo": "x", "version": "1"})
    assert resp.status_code == 400
    assert resp.get_json()["errors"]


def test_duplicate_name_returns_409(make_user, client_as):
    c = client_as(make_user("m@ipullrank.com"))
    assert _create(c).status_code == 201
    assert _create(c).status_code == 409


def test_member_cannot_edit_others_plugin(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    other = make_user("other@ipullrank.com")
    pid = _create(client_as(owner)).get_json()["id"]
    resp = client_as(other).put(
        f"/api/plugins/{pid}",
        json={"name": "backlink-analyzer", "repo": "ipullrank/x", "version": "2.0.0"},
    )
    assert resp.status_code == 403


def test_owner_can_edit_own_plugin(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    pid = _create(c).get_json()["id"]
    resp = c.put(
        f"/api/plugins/{pid}",
        json={"name": "backlink-analyzer", "repo": "ipullrank/renamed", "version": "2.0.0", "category": "SEO"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["repo"] == "ipullrank/renamed"


def test_admin_reassigns_owner(make_user, client_as):
    member = make_user("m@ipullrank.com")
    admin = make_user("a@ipullrank.com", role="admin")
    new_owner = make_user("new@ipullrank.com")
    pid = _create(client_as(member)).get_json()["id"]
    resp = client_as(admin).put(
        f"/api/plugins/{pid}",
        json={"name": "backlink-analyzer", "repo": "ipullrank/backlink-analyzer",
              "version": "1.0.0", "category": "SEO", "owner_email": "new@ipullrank.com"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["owner_id"] == new_owner.id


# --- transition / approval workflow -----------------------------------------


def test_owner_submits_then_admin_approves(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    admin = make_user("a@ipullrank.com", role="admin")
    pid = _create(client_as(owner)).get_json()["id"]

    submit = client_as(owner).post(f"/api/plugins/{pid}/transition", json={"target": "pending"})
    assert submit.status_code == 200
    assert submit.get_json()["status"] == "pending"

    approve = client_as(admin).post(f"/api/plugins/{pid}/transition", json={"target": "published"})
    assert approve.status_code == 200
    assert approve.get_json()["status"] == "published"


def test_member_cannot_approve_own_plugin(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    pid = _create(c).get_json()["id"]
    c.post(f"/api/plugins/{pid}/transition", json={"target": "pending"})
    resp = c.post(f"/api/plugins/{pid}/transition", json={"target": "published"})
    assert resp.status_code == 403


def test_illegal_transition_is_rejected(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    c = client_as(owner)
    pid = _create(c).get_json()["id"]
    # draft -> published directly is not a legal step
    resp = c.post(f"/api/plugins/{pid}/transition", json={"target": "published"})
    assert resp.status_code == 403


def test_delete_permissions(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    other = make_user("other@ipullrank.com")
    pid = _create(client_as(owner)).get_json()["id"]
    assert client_as(other).delete(f"/api/plugins/{pid}").status_code == 403
    assert client_as(owner).delete(f"/api/plugins/{pid}").status_code == 204
    assert client_as(owner).get(f"/api/plugins/{pid}").status_code == 404


def test_list_filters_by_status(make_user, client_as):
    owner = make_user("owner@ipullrank.com")
    admin = make_user("a@ipullrank.com", role="admin")
    pid = _create(client_as(owner)).get_json()["id"]
    client_as(owner).post(f"/api/plugins/{pid}/transition", json={"target": "pending"})
    client_as(admin).post(f"/api/plugins/{pid}/transition", json={"target": "published"})

    published = client_as(owner).get("/api/plugins?status=published").get_json()
    assert [p["name"] for p in published] == ["backlink-analyzer"]
    drafts = client_as(owner).get("/api/plugins?status=draft").get_json()
    assert drafts == []
