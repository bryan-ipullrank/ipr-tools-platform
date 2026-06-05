# **Phase 2 Game Plan: Containerized Identity-Aware Proxy (IAP)**

> **STATUS: DEFERRED — blocked on infrastructure.** Phase 1 remains live on
> PythonAnywhere throughout. Do not strip OAuth from the Flask app until the
> containerized stack is validated and ready to cut over.
>
> ⚠️ **This cannot run on PythonAnywhere — even on a paid plan.** The edge-proxy
> design needs things PythonAnywhere does not provide at any tier:
> - **No Docker** (it's a managed WSGI PaaS, not a container host).
> - **No control over the ingress NGINX** — you can't add the `auth_request`
>   directive; PythonAnywhere owns the front-end proxy.
> - **Arbitrary ports aren't routed** — oauth2-proxy could never be reached as the
>   edge ([confirmed on the PythonAnywhere forums](https://www.pythonanywhere.com/forums/topic/14884/)).
> - **No managed Redis** for the session store.
>
> **Decision (2026-06-05):** roadmap resequenced. Phase 2 waits until a small
> Docker-capable VM is provisioned; **Phases 3 and 4 (both PythonAnywhere-friendly)
> are done first.** The paid PythonAnywhere account's value — no outbound
> whitelist, always-on tasks, custom domains — applies to Phases 3/4, not to this
> edge-infrastructure phase.

**Objective:** Move the IDP off PythonAnywhere into a self-hosted container
stack where **authentication happens at the network edge**. NGINX +
oauth2-proxy handle the Google OAuth flow and inject the authenticated user's
identity downstream as a trusted header. Flask-Dance is removed from the app —
Flask simply trusts the `X-Forwarded-Email` header the proxy provides. This is
the foundation for true SSO across *all* internal tools (Grafana, pgWeb, etc.)
with zero code changes in those downstream apps.

This realizes **Pillar 1** of `Long-Term IDP Vision.md`.

## **1. Why this changes the architecture**

In Phase 1, each Flask route is protected by Flask-Dance/Flask-Login *inside*
the app. That only protects the Flask app itself — clicking through to Grafana
still requires a separate login. In Phase 2, the proxy sits in front of
**everything**: it authenticates once, then forwards identity to any upstream.

```
Phase 1 (now):   Browser ──HTTPS──> PythonAnywhere ──> Flask (does its own OAuth)

Phase 2 (goal):  Browser ──HTTPS──> NGINX ──auth_request──> oauth2-proxy ──> Google
                                      │                          │
                                      │  (on success: X-Auth-Request-Email)
                                      └──> Flask / Grafana / pgWeb  (trust the header)
```

## **2. Prerequisites**

* **Host:** a Linux VM or container host (the PythonAnywhere free tier cannot run
  Docker / arbitrary listeners). Decide the target (e.g. a small cloud VM, or
  internal infra) before starting.
* **DNS:** an internal hostname for the hub (e.g. `idp.internal.ipullrank.com`)
  and a wildcard plan for downstream tools (`*.internal.ipullrank.com`).
* **TLS:** certificates for those hostnames (Let's Encrypt or internal CA).
* **Google Console:** add a new **Authorized redirect URI** for oauth2-proxy:
  `https://idp.internal.ipullrank.com/oauth2/callback`. Keep the Phase 1 URIs
  until cutover is complete.

## **3. Tech Stack & Components**

| Component | Role |
|-----------|------|
| **NGINX** | Single ingress. Uses the `auth_request` directive to gate every request. |
| **oauth2-proxy** | Runs the Google OAuth dance; restricts to `--email-domain=ipullrank.com`; issues the session cookie. |
| **Redis** | Distributed session store for oauth2-proxy (`--session-store-type=redis`) to avoid cookie bloat. |
| **Flask (gunicorn)** | The hub app, now auth-free — reads identity from `X-Forwarded-Email`. |
| **Docker Compose** | Orchestrates the four services on one private network. |

## **4. Proposed Structure**

Phase 2 artifacts live alongside the existing app; nothing is deleted until
cutover.

```
ipr-tools-platform/
├── app/                      # existing Flask app (auth.py simplified in Step 4)
├── deploy/
│   ├── docker-compose.yml    # nginx + oauth2-proxy + redis + web
│   ├── Dockerfile            # Flask app image (gunicorn)
│   ├── nginx/
│   │   └── idp.conf          # auth_request config + header forwarding
│   └── oauth2-proxy/
│       └── oauth2-proxy.cfg  # Google provider, email-domain, redis, cookie
├── .env.docker.example       # compose-level secrets template
└── ... (Phase 1 files unchanged)
```

## **5. Execution Steps**

### **Step 1: Containerize the Flask app**
* Write a `Dockerfile` running the app under **gunicorn** (not the dev server):
  `gunicorn --bind 0.0.0.0:8000 "app:create_app()"`.
* The app listens only on the internal Docker network — **never** published to
  the host directly. NGINX is the sole public entry point.

### **Step 2: Stand up oauth2-proxy + Redis**
* Configure oauth2-proxy: `provider = "google"`, `email_domains = ["ipullrank.com"]`,
  client id/secret (reuse the Phase 1 Google credentials), a generated
  `cookie_secret`, and `session_store_type = "redis"` pointed at the Redis service.
* Set `redirect_url = "https://idp.internal.ipullrank.com/oauth2/callback"`.

### **Step 3: Configure NGINX `auth_request`**
* Define an internal `/oauth2/auth` location proxied to oauth2-proxy.
* In the protected `location /`, add `auth_request /oauth2/auth;` and capture the
  identity:
  ```nginx
  auth_request_set $email $upstream_http_x_auth_request_email;
  proxy_set_header  X-Forwarded-Email $email;
  ```
* On a `401` from `auth_request`, redirect the browser to oauth2-proxy's sign-in
  (`error_page 401 = @oauth2_signin;`).
* **Critical:** explicitly clear any client-supplied identity header so it can't
  be spoofed — `proxy_set_header X-Forwarded-Email $email;` overwrites it, but
  also strip it at ingress before auth runs.

### **Step 4: Strip OAuth out of Flask**
* Remove `flask_dance` usage: delete the `google_bp`, the `oauth_authorized`
  handler, and the `/login/google*` routes from `app/auth.py`.
* Replace login with a `before_request` hook (or a thin `proxy_auth.py`) that
  reads `request.headers["X-Forwarded-Email"]`, runs the **existing**
  `is_allowed_email()` as defense-in-depth, and builds the transient `User`.
* Keep `is_allowed_email()` and the `User` model — they are reused as-is.
* Drop `Flask-Dance` from `requirements.txt`; `Flask-Login` becomes optional
  (identity now comes from the header each request, so it can be removed or kept
  for `current_user` ergonomics).
* Remove `OAUTHLIB_INSECURE_TRANSPORT` and the Google client vars from the app's
  own env (they move to oauth2-proxy).

### **Step 5: Wire it together with Compose**
* `docker-compose.yml` defines `web`, `oauth2-proxy`, `redis`, `nginx` on a
  shared network; only `nginx` publishes ports 80/443.
* Secrets come from `.env.docker` (compose `env_file`), never committed.

## **6. Verification**

1. **Local compose smoke test:** `docker compose up`, hit the hub on localhost,
   confirm an unauthenticated request bounces to Google and an `@ipullrank.com`
   login lands on the dashboard.
2. **Header trust test:** confirm a request that *manually* sets
   `X-Forwarded-Email` from the client is ignored (NGINX overwrites it) — this is
   the spoofing guard and must pass.
3. **Downstream SSO test:** put a second dummy upstream behind the same proxy and
   confirm it receives the identity header without its own login.
4. **Domain restriction:** confirm a non-`ipullrank.com` Google account is
   rejected by oauth2-proxy before ever reaching Flask.

## **7. Cutover Plan (zero-downtime intent)**

1. Deploy and validate the container stack on its own hostname while
   PythonAnywhere keeps serving production.
2. Switch DNS / internal links to the new host once tests pass.
3. Decommission the PythonAnywhere web app and remove the Phase 1 Google
   redirect URIs.

## **8. Phase 3 Lookahead**

With the proxy in place and Flask freed of auth concerns, Phase 3 adds the
Claude Code plugin **marketplace** endpoints (`/api/marketplace.json`) to the
same Flask app — now trivially protected by the same edge proxy. See
`Long-Term IDP Vision.md`, Pillar 3.
