# **Phase 1 Game Plan: Minimal Flask Internal Developer Portal**

> ✅ **STATUS: COMPLETE — live on PythonAnywhere with working Google OAuth.**
> This document is the original plan, kept for reference. The shipped app follows
> it closely with a few additions made during build/deploy:
> - `app/extensions.py` holds the shared `LoginManager` to avoid circular imports.
> - The app factory wraps `ProxyFix` and sets `PREFERRED_URL_SCHEME=https` so OAuth
>   works behind PythonAnywhere's TLS-terminating proxy (no `redirect_uri_mismatch`).
> - `.env` is loaded by absolute path and validated with a **self-diagnosing**
>   error (names the exact path checked) because `.env` is gitignored and must be
>   created on the server, not uploaded.
> - Auth is **domain-check only, no database** (`is_allowed_email`, unit-tested).
> - Tooling added: `conftest.py` (test path), `mypy.ini` (stub-noise config),
>   `tests/test_auth.py`.
>
> See `README.md` for run/deploy instructions and the Phase 2 game plan for what's next.

**Objective:** Build a lightweight, centralized Flask web application secured by Google OAuth 2.0 to serve as the landing page and tool registry for internal developers. Defer reverse-proxy downstream authentication to Phase 2\.

## **1\. Prerequisites & Google Console Setup**

Before writing code, we need to establish the identity provider perimeter.

* **Action:** Create a new project in the [Google Cloud Console](https://console.cloud.google.com/).  
* **Action:** Configure the OAuth Consent Screen (Set to **Internal** so only users within your Google Workspace organization can authenticate).  
* **Action:** Generate OAuth 2.0 Client Credentials (Client ID and Client Secret).  
* **Action:** Add authorized redirect URIs for local development (e.g., http://localhost:5000/login/google/authorized).

## **2\. Tech Stack & Dependencies**

Based on the provided architectural evaluation, we will use the standard, vetted Python libraries for this flow to avoid manually handling cryptography.

* **Framework:** Flask  
* **OAuth Abstraction:** Flask-Dance (Specifically make\_google\_blueprint as referenced in the doc).  
* **Session Management:** Flask-Login (To persist the authenticated state via HTTP-only cookies).  
* **Environment Management:** python-dotenv (To securely load GOOGLE\_OAUTH\_CLIENT\_ID and GOOGLE\_OAUTH\_CLIENT\_SECRET).

## **3\. Proposed Directory Structure**

Keeping it simple but scalable for when we add local Python tools or API endpoints later.

flask-idp/  
│  
├── app/  
│   ├── \_\_init\_\_.py          \# App factory and Flask-Login init  
│   ├── auth.py              \# Flask-Dance Google blueprint setup  
│   ├── routes.py            \# Protected dashboard and tool links  
│   └── templates/  
│       ├── base.html        \# Main layout (Tailwind/Bootstrap)  
│       ├── login.html       \# Public login prompt  
│       └── dashboard.html   \# The portal hub (requires auth)  
│  
├── .env                     \# Secrets (NOT committed to git)  
├── requirements.txt         \# Dependencies  
└── run.py                   \# Application entry point

## **4\. Execution Steps**

### **Step 1: The Core App & Environment**

* Initialize the Flask application using an app factory pattern.  
* Configure the secret key (required for Flask sessions).  
* Set OAUTHLIB\_INSECURE\_TRANSPORT=1 in .env *strictly* for local testing over HTTP.

### **Step 2: Implementing the OAuth Dance**

* Register the google\_bp blueprint using Flask-Dance.  
* Create a simple User model. (Since this is a lightweight app, we can use a mock database or an in-memory dictionary for now, matching the Google email to a UserMixin object).  
* Implement the /login route that redirects to Google.

### **Step 3: Session Binding with Flask-Login**

* Once Google redirects back to our callback, extract the user's info using google.get("/oauth2/v2/userinfo").  
* Parse the email. If the domain matches your company domain (e.g., @yourcompany.com), instantiate the User object and call login\_user(user).  
* Apply the @login\_required decorator to the main /dashboard route.

### **Step 4: Building the UI Hub**

* Create a clean dashboard.html template.  
* For Phase 1, simply list standard hyperlinks to your existing downstream tools (Grafana, GitHub repos, CI/CD pipelines, etc.).  
* *Note on constraint:* Because we are deferring downstream auth, users clicking these links will still have to log into those secondary tools if they aren't already authenticated, but they will have a single place to find them.

## **5\. Phase 2 Lookahead (For Later)**

When we are ready to tackle downstream authentication:

* We will introduce Docker/docker-compose.  
* We will place oauth2-proxy and NGINX in front of this Flask app.  
* At that point, we will strip Flask-Dance out of this application, as the proxy will handle the OAuth flow and simply pass X-Forwarded-Email headers down to Flask.