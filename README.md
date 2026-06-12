# iPullRank Internal Developer Portal (IDP)

A Flask app, secured by Google OAuth 2.0, that serves as a single landing page
and tool directory for internal developers.

> **Status:** **live on PythonAnywhere** (paid account). In production:
> - Google OAuth login + persisted users with **admin/member roles**.
> - A SQLite **tool catalog** (REST API, ownership, management UI).
> - A **Claude Code plugin marketplace** — a token-gated `marketplace.json`, a
>   `Plugin` catalog with an **approval workflow** (`draft → pending → published`,
>   plus `rejected` and `access_pending`), a `/api/plugins` API, and a no-secrets
>   **"Request access"** flow.
> - **Two distribution channels** from one catalog: the token-gated Flask endpoint
>   (Claude Code CLI) and a **private GitHub monorepo** the IDP vendors plugins into
>   (Claude Desktop/Cowork org marketplace).
> - **Categories (required) + tags** on every tool and plugin, with grouped/filtered
>   catalog views, a detail modal, and a WIP stamp.
> - **Collaborator-access automation**: submitting a plugin auto-accepts the GitHub
>   repo invitation (catalog-scoped) so it can be published.
>
> **Roadmap resequenced:** Phase 2 (edge SSO via NGINX + oauth2-proxy) requires a
> Docker-capable host, which PythonAnywhere is not — so it is **deferred** until a
> VM is provisioned. Phases 3 (done) and 4 run fine on PythonAnywhere. See
> [`Phase 2 Game Plan_ Containerized IAP.md`](./Phase%202%20Game%20Plan_%20Containerized%20IAP.md)
> for the why and the eventual migration plan.

**Roadmap** (full detail in `Long-Term IDP Vision.md`):

| Phase | Goal | State |
|-------|------|-------|
| 1 | Flask hub + Flask-Dance Google OAuth on PythonAnywhere | ✅ Done |
| 1.5 | DB-backed tool catalog + REST API + roles/ownership + management UI | ✅ Done |
| 3 | Claude Code plugin marketplace: token-gated `marketplace.json`, approval workflow, `/api/plugins`, request-access | ✅ Done — see `Phase 3 Game Plan_ Claude Marketplace.md` |
| 3.6 | Mirror the catalog to a private GitHub repo for the Claude Desktop/Cowork channel | ✅ Done |
| 3.7 | Categories & tags + grouped catalog UI; monorepo auto-publish (vendoring) + collaborator-access automation | ✅ Done |
| 4 | GitHub scaffolding via PyGithub | ⏭️ Next (PA-friendly) |
| 2 | Containerize; NGINX + oauth2-proxy edge auth; strip OAuth from Flask | ⏸️ Deferred — needs a Docker VM, not PythonAnywhere |

## Quickstart: fresh setup (no database yet)

Starting from a clean checkout with no `idp.db`. On PythonAnywhere, run these in a
Bash console with the virtualenv active; locally, the same minus the reload.

```bash
git pull
pip install -r requirements.txt          # Flask-SQLAlchemy / Flask-Migrate are required

# .env is gitignored — create it on the machine if absent, then fill it in.
cp .env.example .env                      # skip if you already have one
#   required: FLASK_SECRET_KEY, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
#   set:      IDP_ADMINS=bryan@ipullrank.com   (makes you admin on login)
#   marketplace: MARKETPLACE_TOKEN (gates /marketplace.json for Claude Code)
#   cowork sync: MARKETPLACE_REPO + GITHUB_MARKETPLACE_TOKEN (mirror to GitHub)
#   local only: OAUTHLIB_INSECURE_TRANSPORT=1  (never on PythonAnywhere)

FLASK_APP=app flask db upgrade            # builds the schema (users + tools + plugins) from migrations
FLASK_APP=app flask seed-tools            # loads placeholder tools (idempotent)
FLASK_APP=app flask seed-plugins          # loads the plugin catalog as drafts (idempotent)
```

Then **reload** the PythonAnywhere web app (or `python run.py` locally) and sign
in. Because your email is in `IDP_ADMINS`, your first login makes you an admin.

> `flask db upgrade` *applies* the committed migration — you do **not** run
> `flask db init` / `flask db migrate` for setup (those author new migrations).
> Since there was no DB before, this builds it from scratch in one shot.

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
  __init__.py        # app factory: .env load, ProxyFix, DB init, blueprint + CLI registration
  extensions.py      # shared singletons: login_manager, db (SQLAlchemy), migrate
  auth.py            # Google blueprint, domain check, login handler
  models.py          # User + Tool + Plugin (category, tags, status); to_dict/to_marketplace_entry
  authz.py           # roles + pure can_edit_tool()/can_edit_plugin()/is_seed_admin() + admin_required
  validation.py      # pure validate_tool_payload() (category required, tags) — unit-tested
  plugin_validation.py # pure validate_plugin_payload() (kebab name, owner/repo, semver, category, tags)
  plugin_status.py   # pure lifecycle state machine: draft→pending→published (+rejected, access_pending)
  catalog_display.py # pure helpers: parse_tags / group_by_category / wip_stamp / display_tags
  repositories.py    # Tool/User/Plugin repositories (Protocol + SQLAlchemy) + distinct_categories()
  api.py             # REST blueprint (/api/tools CRUD), session + ownership gated
  api_plugins.py     # REST blueprint (/api/plugins CRUD + transition), session gated
  marketplace.py     # token-gated GET /marketplace.json (Claude Code channel) + build_marketplace_document()
  github_publisher.py# vendors published plugins into the private GitHub monorepo (Cowork channel)
  github_access.py   # repo read-access check + catalog-scoped auto-accept of collaborator invites
  access_requests.py # pure mailto builder for the no-secrets "Request access" flow
  manage.py          # server-rendered UI: tool + plugin forms, transitions, sync, /admin/users
  routes.py          # / (login), /dashboard (grouped tools), /plugins (grouped), /logout
  tools.py           # SEED_TOOLS — one-time seed for an empty tool catalog
  plugins_seed.py    # SEED_PLUGINS — seed for the plugin catalog (5 real skill repos, with categories/tags)
  cli.py             # `flask seed-tools`, `flask seed-plugins`, `flask set-role`
  templates/         # base / login / dashboard / tool_form / plugins / plugin_form /
                     #   _repo_help (repo-structure modal) / admin_users (Tailwind CDN)
migrations/          # Flask-Migrate (Alembic) schema migrations
wsgi.py              # production entry (PythonAnywhere)
run.py               # local dev server
tests/               # pytest: auth, validation, repository, api, plugins, marketplace,
                     #   github (publisher + access), catalog_display, manage
```

> **Design conventions** (per the project's standards): validation is separated from
> processing into pure, unit-tested functions (`validation`, `plugin_validation`,
> `catalog_display`, `plugin_status`, `access_requests`); persistence and external
> integrations sit behind `Protocol`s (`*Repository`, `MarketplacePublisher`,
> `RepoWriter`, `GitHubAccess`) so they're swappable and fakeable in tests.
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
| POST | `/api/tools` | Create (201, or 400 `{errors:[...]}`); `category` required, `tags` optional; creator becomes owner |
| PUT | `/api/tools/<id>` | Update (200 / 403 / 404); admins may pass `owner_id`/`owner_email` to reassign |
| DELETE | `/api/tools/<id>` | Delete (204 / 403 / 404) |

Both `Tool` and `Plugin` carry a required `category` and optional `tags` (JSON list)
— see [Categories, tags & catalog views](#categories-tags--catalog-views).

**Schema & seed commands** (need `FLASK_APP=app`):

```bash
FLASK_APP=app flask db upgrade     # create/upgrade the schema (users + tools + plugins)
FLASK_APP=app flask seed-tools     # load placeholder tiles if the table is empty
FLASK_APP=app flask seed-plugins   # load the 5 real skill-repo plugins as drafts (idempotent per-name)
FLASK_APP=app flask set-role someone@ipullrank.com admin   # change a role (after they've logged in once)
```

> Seeded plugins land as **drafts** — an admin publishes them (Submit → Approve in
> `/plugins`). Only published plugins appear in `marketplace.json`.

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

## Categories, tags & catalog views

Every **tool and plugin** has a **required `category`** and **optional `tags`**
(stored as a JSON list). The pure helpers in `app/catalog_display.py` drive the UI:

- **Grouped views** — the dashboard (`/dashboard`) and the plugin catalog
  (`/plugins`) render an `<h2>` per category via `group_by_category()`
  (`Uncategorized` sorts last). A **category filter** (toggle chips) shows/hides
  sections client-side.
- **Detail modal** — clicking an entry opens a modal with its category, description,
  and **tag chips**, plus actions: "Open tool" for tools, and **install
  instructions** (Desktop/Cowork + Claude Code) for a published plugin.
- **WIP stamp** — `wip_stamp()` shows a red **WIP** stamp on any card tagged `WIP`,
  and automatically on any plugin that isn't `published`. The reserved `WIP` tag is
  hidden from the normal tag list (`display_tags()`).

Forms have a required Category field (a `<datalist>` suggests categories already in
use — `distinct_categories()`) and an optional comma-separated Tags field. The
marketplace document carries `category`/`tags` too (both are spec-supported fields).

## Claude Code plugin marketplace (Phase 3)

The IDP doubles as an internal **Claude Code plugin marketplace**. The catalog is
the `Plugin` model (`app/models.py`) — it mirrors `Tool` but adds a unique
kebab-case `name` (the install id), a `repo` (`owner/repo`), a `version`, and a
lifecycle `status`. **Flask hosts the catalog; GitHub hosts the plugin code** — the
Claude CLI clones each plugin repo with the developer's own `gh` credentials, which
is also where access control really lives.

**Approval workflow** (`app/plugin_status.py`, a pure data-driven state machine).
Members create/edit/own drafts and **submit** them; **only admins approve** →
`published`. Only `published` plugins appear in `marketplace.json`. Edit permission
is `can_edit_plugin()` (owner-or-admin); transition permission is
`can_transition_plugin()`.

| From | Action | To | Who |
|------|--------|----|-----|
| `draft` / `rejected` | Submit — **repo readable** | `pending` | owner/admin |
| `draft` / `rejected` | Submit — **no repo access** | `access_pending` | owner/admin |
| `access_pending` | Check access (now readable) | `pending` | owner/admin |
| `access_pending` | Withdraw | `draft` | owner/admin |
| `pending` | Approve | `published` | **admin** |
| `pending` | Reject | `rejected` | **admin** |
| `pending` | Withdraw | `draft` | owner/admin |
| `published` | Unpublish | `draft` | **admin** |

Approving (and unpublishing) auto-syncs the GitHub monorepo; submitting runs the
**repo-access gate** (see below). Both surface a blocking "syncing…" overlay while
the GitHub call runs, then redirect back to a refreshed `/plugins`.

**Two distribution channels, one catalog** (`build_marketplace_document()` in
`app/marketplace.py` generates the identical document for both):

| Channel | How it's consumed | Source |
|---------|-------------------|--------|
| **Claude Code (terminal)** | `/plugin marketplace add https://you:TOKEN@<host>/marketplace.json` | Flask `GET /marketplace.json`, gated by `MARKETPLACE_TOKEN` (HTTP Basic). Fail-closed: **401** wrong, **503** unset |
| **Claude Desktop / Cowork** | Org settings → Plugins → GitHub sync (Team plan) | A **private GitHub monorepo** (`MARKETPLACE_REPO`) the IDP vendors each published plugin into and commits `marketplace.json` to via `app/github_publisher.py` (auto-sync on publish/unpublish + an admin "Sync to GitHub" button) |

The monorepo is a full rebuild on each sync (`app/github_publisher.py`): every
published plugin's source repo is vendored into `plugins/<name>/`, and
`.claude-plugin/marketplace.json` is regenerated with **relative `./plugins/<name>`
sources** and `"strict": false` + `"skills": ["./"]` (org marketplaces only sync
private content that lives *inside* the connected repo, and require an inline manifest
for a bare-`SKILL.md` plugin). It commits via the Git Data API as one atomic commit.

The GitHub mirror uses `GITHUB_MARKETPLACE_TOKEN` — a **classic PAT** with the `repo`
scope, owned by the account that owns `MARKETPLACE_REPO`. Because the IDP vendors each
plugin's *source* repo into the marketplace monorepo, the token must read every source
repo; a classic PAT reaches all repos its owner can access, **including repos where the
owner is a collaborator**. (A fine-grained PAT can't reach other owners' repos, which is
why the classic PAT is used.)

### Repo-access automation (`app/github_access.py`)

So nobody publishes a plugin the marketplace can't actually read, **submitting** is
gated on repo access. On submit (or the **Check access** retry), `ensure_repo_access()`:

1. If the token can already read the repo (`GET /repos/{repo}`) → proceed to `pending`.
2. Otherwise it looks for the **pending collaborator invitation whose repo matches that
   exact catalog plugin** and **auto-accepts** it (`GET`/`PATCH
   /user/repository_invitations`), then re-checks. (It never auto-joins a repo that
   isn't in the catalog.)
3. Still no access → the plugin parks in **`access_pending`**, and its `/plugins` card
   shows a link to `github.com/<owner>/<repo>/settings/access` telling the owner to add
   the IDP's GitHub account (`marketplace_account`) as a collaborator.

So the teammate grants access on GitHub once; the IDP accepts the invite itself — the
token owner never clicks "accept." The gate is fail-open when no token is configured
(it's a publish-readiness convenience; real enforcement is the vendor step at publish).

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/marketplace.json` | Published catalog — **token-gated, not the Google session** |
| GET | `/plugins` | Management listing (status badges, transition + request-access controls) |
| GET/POST | `/plugins/new`, `/plugins/<id>/edit` | Plugin forms (owner/admin) |
| POST | `/plugins/<id>/transition` | One route for submit/withdraw/approve/reject/unpublish (`target` field) |
| POST | `/plugins/<id>/delete` | Delete (owner/admin) |
| POST | `/plugins/sync-github` | Force a resync to the GitHub repo (admin) |
| GET/POST/PUT/DELETE | `/api/plugins[/<id>]` | JSON API mirroring `/api/tools` (session-gated) |
| POST | `/api/plugins/<id>/transition` | Status change via API |

**Request access (no secrets):** the IDP stores **no GitHub credential for plugin
payloads**. Plugin repos are private, so an installing developer needs `gh` access;
the **"Request access"** link on each plugin opens a pre-filled email to the owner
(cc admins) via the pure `build_access_request_mailto()` (`app/access_requests.py`).

**What a plugin repo must look like:** a Git repo with `.claude-plugin/plugin.json`
at the root (only `name` required), with skills under `skills/<name>/SKILL.md`,
commands in `commands/`, agents in `agents/`, etc. A repo with a single root-level
`SKILL.md` (no manifest) auto-loads as a one-skill plugin — this is how the seeded
repos are arranged. For the Cowork/monorepo channel, the IDP emits an inline manifest
(`strict:false` + `skills:["./"]`) per plugin, so a bare-`SKILL.md` repo works there
too. The `/plugins` UI has a **"required repo structure"** help modal
(`templates/_repo_help.html`) explaining all of this.

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

**Phase 3 — the Claude Code plugin marketplace — is done** (see the section above
and [`Phase 3 Game Plan_ Claude Marketplace.md`](./Phase%203%20Game%20Plan_%20Claude%20Marketplace.md)),
including both channels, categories/tags + grouped UI, monorepo vendoring (Option A),
and the collaborator-access automation. The only deliberately-deferred piece is a
*scheduled* invite-accept (a cron that accepts before anyone hits **Check access**);
the chosen trigger is on-submit, so it's optional.

**Phase 4 — GitHub scaffolding (PyGithub)** is up next on PythonAnywhere: dynamic
"create a new plugin/service repo" forms that scaffold a compliant repo
(`.claude-plugin/plugin.json` + `skills/`) and register it back in this catalog —
closing the loop so the marketplace points at repos the IDP itself created. It
builds on the GitHub integration in `app/github_publisher.py` / `app/github_access.py`.

**Phase 2 is deferred.** It moves the app into containers with **NGINX +
oauth2-proxy** doing edge auth (true cross-tool SSO; Flask-Dance removed in favor
of a trusted `X-Forwarded-Email` header). That stack cannot run on PythonAnywhere
— no Docker, no control over the ingress NGINX, and arbitrary ports aren't routed
— so it waits until a Docker-capable VM is provisioned. Full rationale and the
migration steps are in
[`Phase 2 Game Plan_ Containerized IAP.md`](./Phase%202%20Game%20Plan_%20Containerized%20IAP.md).
