# **Phase 3 Game Plan: The Native Claude Code Marketplace**

> **STATUS: ✅ BUILT (2026-06-06).** Implemented on top of the live catalog +
> roles/ownership + management UI. 124 tests pass. Deployed to PythonAnywhere;
> the GitHub/Cowork mirror (Phase 3.6) needs its server env vars set (see below).
> The sections below are the original plan; **"What actually shipped"** records
> how it was built and the decisions that refined it.

## **What actually shipped (and decisions vs. the original plan)**

- **Approval workflow, not a boolean.** Instead of a simple `is_published` flag, a
  pure state machine in `app/plugin_status.py`: `draft → pending → published`
  (+`rejected`). Members own/edit drafts and **submit**; **only admins approve**.
  Only `published` plugins reach `marketplace.json`. (Decision: user wanted a
  submit-for-approval step before publishing.)
- **Endpoint auth = one shared token.** `MARKETPLACE_TOKEN` via HTTP Basic, **fail
  closed**: 401 wrong, **503 unset**. Per-user tokens deferred.
- **Both optional surfaces shipped:** the `/plugins` listing/management UI **and**
  the `/api/plugins` JSON API.
- **"Request access" (no secrets).** Plugin repos are private; the IDP holds no
  GitHub credential for payloads. A mailto link to the owner/admins
  (`app/access_requests.py`) handles access requests instead of an automated grant.
- **Repo-structure help modal** (`templates/_repo_help.html`) — explains that a
  plugin repo needs `.claude-plugin/plugin.json` (or a single root `SKILL.md`),
  *not* a bare `.skill` file; verified against the live Claude Code docs.
- **Seeded 5 real private skill repos** (`app/plugins_seed.py`,
  `bryan-ipullrank/{wikipedia-entity-builder, wikidata-querier, screaming-frog-crawl,
  schema-markup, backlink-404-redirect-map}`) via `flask seed-plugins`.
- **Phase 3.6 — Claude Desktop/Cowork channel (added after research).** The Claude
  apps consume an **org-managed marketplace** that GitHub-syncs a **private repo**
  (Team plan), not an HTTP endpoint. So the IDP also mirrors the same generated
  `marketplace.json` into `bryan-ipullrank/ipr-marketplace` via
  `app/github_publisher.py` (auto-sync on publish/unpublish + an admin "Sync to
  GitHub" button). Needs `MARKETPLACE_REPO` + a fine-grained `GITHUB_MARKETPLACE_TOKEN`
  (Contents: rw on that one repo) in the server `.env`. Connect once in Claude:
  Org settings → Plugins → GitHub sync. This realizes Pillar 3 step 4 on the **Team**
  plan (GitHub sync) rather than the Enterprise APIs the vision originally assumed.

---

> **Original plan (for reference):** Builds directly on the live catalog +
> roles/ownership + management UI (the "Phase 1.5" work). Runs on PythonAnywhere.

**Objective:** Have the Flask IDP serve a valid Claude Code **plugin marketplace**
at a stable URL so developers run `/plugin marketplace add <url>` once and can
then browse and install internal org plugins (skills, commands, agents, hooks,
MCP servers) natively in their terminal. Realizes **Pillar 3** of
`Long-Term IDP Vision.md`.

## **1. What the spec actually requires (verified against Claude Code docs)**

- `/plugin marketplace add <URL>` accepts a **bare HTTPS URL** to a
  `marketplace.json` — perfect for a Flask endpoint.
- **The CLI sends no auth headers.** A marketplace URL behind our Google-OAuth
  session is unreachable by the CLI. It must be either public or carry an
  embedded credential: `https://user:token@host/marketplace.json` (HTTP basic).
- **Relative plugin `source` paths do NOT resolve** for an HTTP-served
  marketplace — only the JSON is fetched, not a repo. So each plugin's `source`
  must point at a **git repo** (e.g. `{"source":"github","repo":"ipullrank/x"}`),
  not files Flask serves. The CLI clones the repo using the developer's own git
  credentials (`gh auth`), which is also where the real access control lives.

**Implication:** Flask hosts the *catalog* (metadata + which repos are plugins);
**GitHub hosts the *payloads*** (the plugin code, in private repos). This dovetails
with Phase 4 (GitHub scaffolding) and keeps secrets out of the IDP.

### Minimal valid `marketplace.json`
```json
{
  "name": "ipr-tools",
  "owner": { "name": "iPullRank Engineering" },
  "description": "Internal SEO & engineering plugins",
  "plugins": [
    { "name": "backlink-analyzer", "displayName": "Backlink Analyzer",
      "description": "Backlink aggregation + scoring",
      "source": { "source": "github", "repo": "ipullrank/backlink-analyzer" },
      "version": "1.0.0" }
  ]
}
```

## **2. Key decisions to lock before building**

1. **Endpoint auth.** *Recommended:* a token-gated endpoint (HTTP basic / signed
   token in the URL), issued per developer, validated by Flask **independently of
   the Google session**. Keeps the internal plugin list from being world-readable
   while staying CLI-compatible. (Alternative: fully public marketplace.json,
   relying on private GitHub repos as the only gate.)
2. **Plugin payload location.** *Recommended:* private **GitHub repos** as plugin
   sources (works with the spec, reuses dev git creds, sets up Phase 4).
3. **Who publishes plugins.** *Recommended:* reuse the existing roles —
   members propose/own a plugin entry, admins approve/publish — mirroring the
   tool catalog's ownership model.

## **3. Architecture — reuse what Phase 1.5 already built**

The plugin marketplace is structurally the **tool catalog again**, so reuse the
patterns wholesale:

- **`Plugin` model** (`app/models.py`) — `name` (kebab-case, unique),
  `display_name`, `description`, `repo` (e.g. `ipullrank/backlink-analyzer`),
  `source_type` (default `github`), `version`, `is_published` (bool),
  `owner_id` FK → users, timestamps. Mirrors `Tool`.
- **`PluginRepository`** Protocol + SQLAlchemy impl (`app/repositories.py`),
  alongside the existing tool/user repos.
- **Validation** (`app/validation.py`): `validate_plugin_payload()` — pure,
  validates kebab-case name, `owner/repo` format, semver-ish version.
- **Management UI** (`app/manage.py`): plugin new/edit/delete + publish toggle,
  reusing `can_edit_tool`-style `can_edit_plugin` and `admin_required` for the
  publish action. A new `plugin_form.html`.
- **Marketplace generator** (`app/marketplace.py`, new blueprint): builds the
  spec-compliant dict from published `Plugin` rows and returns it as JSON.

## **4. New endpoints**

- `GET /marketplace.json` — **token-gated, not Google-session** — dynamically
  generated from `Plugin.is_published == True`. This is the URL devs register.
- Management routes under the existing UI: `GET/POST /plugins/new`,
  `/plugins/<id>/edit`, `/plugins/<id>/delete`, `POST /plugins/<id>/publish`
  (admin), and a `/plugins` listing page. Optionally a JSON API under `/api/plugins`
  mirroring `/api/tools`.

## **5. Execution steps**

1. **Model + migration**: add `Plugin`; `flask db migrate -m "plugins table"`;
   `flask db upgrade` (batch mode already configured for SQLite).
2. **Repository + validation** for plugins (copy the tool patterns).
3. **Marketplace endpoint**: `app/marketplace.py` building the `{name, owner,
   plugins[]}` document; cache headers optional. Add token auth middleware for
   this route only.
4. **Token issuance**: a `marketplace_token` per user (or one shared org token in
   env to start). Simplest start: `MARKETPLACE_TOKEN` env var checked via HTTP
   basic on `/marketplace.json`.
5. **Management UI** for publishing plugins (reuse `manage.py` + templates).
6. **Seed** a couple of real internal repos as plugin entries.

## **6. Verification**

1. `pytest` — plugin validation, repository, marketplace-JSON generation
   (asserts a spec-valid document), and token gating (401 without token, 200 with).
2. `curl -u user:$TOKEN https://<host>/marketplace.json` returns valid JSON; pipe
   through a JSON Schema check against the marketplace schema.
3. **Live**: in a terminal, `claude` → `/plugin marketplace add
   https://user:TOKEN@<host>/marketplace.json` → `/plugin` shows the internal
   plugins → `/plugin install backlink-analyzer@ipr-tools` clones the repo and
   the skill appears.

## **7. Out of scope / later**

- Cloud sync of skills into web Claude / Cowork via Enterprise APIs (vision
  Pillar 3, step 4) — separate effort.
- Per-user token management UI (start with one env token).
- Auto-update webhooks (the CLI polls; no push needed).

## **8. Relationship to other phases**

- **Phase 1.5 (done):** supplies the catalog/repository/roles/ownership/UI
  patterns this phase clones.
- **Phase 4 (GitHub scaffolding):** will *create* the plugin repos this
  marketplace points at — natural follow-on. Building Phase 3 first means Phase 4
  has a registry to publish into.
