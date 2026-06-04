# iPullRank Internal Developer Portal (IDP) — Phase 1

A minimal Flask app, secured by Google OAuth 2.0, that serves as a single
landing page and tool directory for internal developers. Primary host:
**PythonAnywhere**.

This is Phase 1 only. Later phases (NGINX + oauth2-proxy SSO, GitHub
scaffolding, a Claude Code plugin marketplace) are documented in
`Long-Term IDP Vision.md` and are intentionally out of scope here.

## How it works

- **Flask-Dance** runs the Google OAuth dance.
- The `oauth_authorized` handler in `app/auth.py` fetches the user's Google
  profile and only logs them in if their email is on `ALLOWED_EMAIL_DOMAIN`
  (default `ipullrank.com`). The check lives in the pure, unit-tested
  `is_allowed_email()`.
- **Flask-Login** persists the session in a signed HTTP-only cookie. There is
  no database — a `User` is rebuilt from the email in the session each request.
- The dashboard renders the editable tool list in `app/tools.py`.

## Project layout

```
app/
  __init__.py    # app factory: .env load, ProxyFix, blueprint registration
  extensions.py  # shared LoginManager singleton
  auth.py        # Google blueprint, domain check, login handler
  models.py      # transient User(UserMixin)
  routes.py      # / (login), /dashboard, /logout
  tools.py       # TOOLS registry — edit this to change dashboard tiles
  templates/     # base / login / dashboard (Tailwind via CDN)
wsgi.py          # production entry (PythonAnywhere)
run.py           # local dev server
tests/           # pytest
```

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

5. **Reload** the web app and visit `https://<username>.pythonanywhere.com`.

The `ProxyFix` middleware in the app factory makes Flask honor PythonAnywhere's
`X-Forwarded-Proto` header so the OAuth redirect URI is built as `https://`,
avoiding Google's `redirect_uri_mismatch` error.
