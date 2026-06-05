# iPullRank Internal Developer Portal (IDP)

A Flask app, secured by Google OAuth 2.0, that serves as a single landing page
and tool directory for internal developers.

> **Status:** Phase 1 is **live on PythonAnywhere** (paid account) with working
> Google OAuth. PythonAnywhere is the current production host.
>
> **Roadmap resequenced:** Phase 2 (edge SSO via NGINX + oauth2-proxy) requires a
> Docker-capable host, which PythonAnywhere is not — so it is **deferred** until a
> VM is provisioned. Phases 3 and 4 run fine on PythonAnywhere and are the active
> track. See [`Phase 2 Game Plan_ Containerized IAP.md`](./Phase%202%20Game%20Plan_%20Containerized%20IAP.md)
> for the why and the eventual migration plan.

**Roadmap** (full detail in `Long-Term IDP Vision.md`):

| Phase | Goal | State |
|-------|------|-------|
| 1 | Flask hub + Flask-Dance Google OAuth on PythonAnywhere | ✅ Done |
| 3 | Serve a Claude Code plugin `marketplace.json` from Flask | ⏭️ Next (PA-friendly) |
| 4 | GitHub scaffolding via PyGithub | Next (PA-friendly) |
| 2 | Containerize; NGINX + oauth2-proxy edge auth; strip OAuth from Flask | ⏸️ Deferred — needs a Docker VM, not PythonAnywhere |

## How it works

- **Flask-Dance** runs the Google OAuth dance.
- The `oauth_authorized` handler in `app/auth.py` fetches the user's Google
  profile and only logs them in if their email is on `ALLOWED_EMAIL_DOMAIN`
  (default `ipullrank.com`). The check lives in the pure, unit-tested
  `is_allowed_email()`.
- **Flask-Login** persists the session in a signed HTTP-only cookie. Users are
  **persisted** (a `users` row, upserted on login) and carry a `role`
  (`admin`/`member`). Admins are bootstrapped from the `IDP_ADMINS` env list and
  can promote/demote others at `/admin/users`.
- The tool catalog lives in a **SQLite database** (via SQLAlchemy). The dashboard,
  the management UI, and the JSON API all read it through a repository; see
  [Data & API](#data--api) and [Roles & ownership](#roles--ownership).

## Project layout

```
app/
  __init__.py     # app factory: .env load, ProxyFix, DB init, blueprint + CLI registration
  extensions.py   # shared singletons: login_manager, db (SQLAlchemy), migrate
  auth.py         # Google blueprint, domain check, login handler
  models.py       # transient User(UserMixin) + persisted Tool(db.Model)
  authz.py        # roles + pure can_edit_tool()/is_seed_admin() + admin_required
  validation.py   # pure validate_tool_payload() — separated, unit-tested
  repositories.py # Tool/User repositories (Protocol + SQLAlchemy impls)
  api.py          # REST blueprint (/api/tools CRUD), session + ownership gated
  manage.py       # server-rendered UI: tool forms, delete, /admin/users
  routes.py       # / (login), /dashboard, /logout
  tools.py        # SEED_TOOLS — one-time seed data for an empty catalog
  cli.py          # `flask seed-tools`, `flask set-role` commands
  templates/      # base / login / dashboard / tool_form / admin_users (Tailwind CDN)
migrations/       # Flask-Migrate (Alembic) schema migrations
wsgi.py           # production entry (PythonAnywhere)
run.py            # local dev server
tests/            # pytest (auth, validation, repository, api)
```

## Data & API

The tool catalog is the `Tool` model (`app/models.py`), persisted in SQLite by
default (`idp.db` in the project root). Set `DATABASE_URL` to point at
MySQL/Postgres instead — no code change, just `pip install` the driver and run
`flask db upgrade`.

**REST API** (`app/api.py`, prefix `/api`, all endpoints behind the Google login
session):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/tools` | List active tools (`?include_inactive=1` for all) |
| GET | `/api/tools/<id>` | Fetch one (404 if missing) |
| POST | `/api/tools` | Create (201, or 400 `{errors:[...]}`); creator becomes owner |
| PUT | `/api/tools/<id>` | Update (200 / 403 / 404); admins may pass `owner_id`/`owner_email` to reassign |
| DELETE | `/api/tools/<id>` | Delete (204 / 403 / 404) |

**Schema & seed commands** (need `FLASK_APP=app`):

```bash
FLASK_APP=app flask db upgrade     # create/upgrade the schema
FLASK_APP=app flask seed-tools     # load placeholder tiles if the table is empty
FLASK_APP=app flask set-role someone@ipullrank.com admin   # change a role (after they've logged in once)
```

## Roles & ownership

Two roles, enforced by the pure `can_edit_tool()` / `admin_required` helpers in
`app/authz.py`:

- **member** (default) — can add tools and edit/delete the ones they **own**.
- **admin** — can edit/delete **any** tool, **reassign ownership**, and manage
  roles. Seeded/legacy tools (no owner) are admin-only.

Admins are bootstrapped from the `IDP_ADMINS` env var (comma-separated emails),
applied on login. After that, an admin can promote/demote anyone at
**`/admin/users`** (a user must have logged in once to appear there).

**Management UI** (`app/manage.py`, server-rendered Tailwind, behind login):
`GET/POST /tools/new`, `GET/POST /tools/<id>/edit` (owner/admin; admins get an
Owner dropdown), `POST /tools/<id>/delete`, and `/admin/users` (admin only). The
dashboard shows each tool's owner and per-tile Edit/Delete controls only when you
may edit it.

## Google Cloud setup

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. OAuth consent screen → **Internal** (restricts to the Workspace org).
3. Create OAuth 2.0 **Client credentials** (Web application).
4. Add **Authorized redirect URIs**:
   - `http://localhost:5000/login/google/authorized` (local dev)
   - `https://<username>.pythonanywhere.com/login/google/authorized` (prod)

## Local development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env       # then fill in the values
python -c "import secrets; print(secrets.token_hex(32))"  # -> FLASK_SECRET_KEY

FLASK_APP=app flask db upgrade     # create the SQLite schema
FLASK_APP=app flask seed-tools     # load placeholder tools

python run.py              # http://localhost:5000
```

`OAUTHLIB_INSECURE_TRANSPORT=1` must be set in `.env` for local http. Sign in
with an `@ipullrank.com` account; a non-domain account is rejected with a flash
message.

Run the tests:

```bash
pytest -q
```

## Deploying to PythonAnywhere

1. Upload the project (e.g. to `/home/<username>/ipr-tools-platform`) and create
   a `.env` there with real secrets. **Do not** set `OAUTHLIB_INSECURE_TRANSPORT`
   — PythonAnywhere serves real HTTPS.

   > ⚠️ **`.env` is gitignored**, so it is *not* uploaded with the repo. You must
   > create it directly on the server (`cp .env.example .env` in a Bash console,
   > then fill it in). If it is missing or a key is blank, the app fails on reload
   > with a self-diagnosing `RuntimeError` that names the exact path it checked.
   > Verify with `cat ~/ipr-tools-platform/.env` before reloading.
2. **Web** tab → **Add a new web app** → **Manual configuration** (matching the
   Python version).
3. Create/point a virtualenv and `pip install -r requirements.txt`.
4. Edit the WSGI config file
   (`/var/www/<username>_pythonanywhere_com_wsgi.py`) to:

   ```python
   import sys
   path = "/home/<username>/ipr-tools-platform"
   if path not in sys.path:
       sys.path.insert(0, path)

   from wsgi import application  # noqa: E402,F401
   ```

5. Initialize the database (once, in a Bash console with the virtualenv active):

   ```bash
   cd ~/ipr-tools-platform
   FLASK_APP=app flask db upgrade     # create the SQLite schema
   FLASK_APP=app flask seed-tools     # load placeholder tools (idempotent)
   ```

   The `idp.db` file lives in the project dir — writable and persistent on PA.
   Back it up by copying the file. (After future model changes: `git pull`, then
   `flask db upgrade` again.)
6. Set `IDP_ADMINS` in the server `.env` (e.g. `IDP_ADMINS=bryan@ipullrank.com`)
   so you're promoted to admin on your next login.
7. **Reload** the web app and visit `https://<username>.pythonanywhere.com`.

> **Heads-up after deploying the roles change:** the login identity moved from
> the email string to the integer user id, so existing session cookies are
> invalid — everyone signs in once more (harmless). On that first login each
> user is created in the `users` table.

The `ProxyFix` middleware in the app factory makes Flask honor PythonAnywhere's
`X-Forwarded-Proto` header so the OAuth redirect URI is built as `https://`,
avoiding Google's `redirect_uri_mismatch` error.

## What's next

We're building **Phase 3 and/or Phase 4 on PythonAnywhere** (both are supported
by the paid account). Phase 1's `app/auth.py` Google OAuth stays in place — new
phases add endpoints to the same Flask app behind the existing login.

**Phase 2 is deferred.** It moves the app into containers with **NGINX +
oauth2-proxy** doing edge auth (true cross-tool SSO; Flask-Dance removed in favor
of a trusted `X-Forwarded-Email` header). That stack cannot run on PythonAnywhere
— no Docker, no control over the ingress NGINX, and arbitrary ports aren't routed
— so it waits until a Docker-capable VM is provisioned. Full rationale and the
migration steps are in
[`Phase 2 Game Plan_ Containerized IAP.md`](./Phase%202%20Game%20Plan_%20Containerized%20IAP.md).
