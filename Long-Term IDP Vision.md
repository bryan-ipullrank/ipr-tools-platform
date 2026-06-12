# **Phase 2 & Beyond: Strategic Architecture for the Internal Developer Platform (IDP)**

While Phase 1 successfully establishes a unified landing zone and centralizes Google OAuth authentication via a lightweight Flask application, the long-term vision requires a shift from a **passive directory** to an **active orchestration engine**.

This document outlines the architectural roadmap for scaling the IDP. The end-state architecture is divided into three strategic pillars: Network-Edge Authentication, Infrastructure Orchestration (GitHub), and the Claude Skill Marketplace.

## **Pillar 1: The Identity-Aware Proxy (IAP) Architecture**

*Goal: True Single Sign-On (SSO) for all internal tools without modifying legacy codebases.*

Currently, clicking a link to Grafana or a legacy internal tool requires a separate login. To solve this, we will implement the **Identity-Aware Proxy** pattern utilizing NGINX, oauth2-proxy, and Redis.

**The Future Flow:**

1. **The Ingress Controller:** NGINX will act as the unified entry point for all internal traffic (e.g., \*.internal.yourcompany.com).  
2. **Sub-request Authentication:** Utilizing the auth\_request directive, NGINX will pause incoming traffic and ping oauth2-proxy.  
3. **Session Management:** oauth2-proxy handles the Google OAuth flow (replacing Flask-Dance from Phase 1). Session state is stored in a distributed Redis cache to prevent cookie bloat.  
4. **Header Injection:** Upon successful authentication, oauth2-proxy injects the X-Forwarded-Email header and passes the traffic back to NGINX, which routes it to the target app (Grafana, pgWeb, etc.).

**Outcome:** The Flask Hub simply links to https://grafana.internal.yourcompany.com. The proxy transparently authenticates the user and passes their identity downstream. Zero code changes are required in the downstream applications.

## **Pillar 2: GitHub Orchestration & Scaffolding**

*Goal: Automate repository creation, standardize infrastructure, and eliminate boilerplate.*

The IDP must evolve to handle self-service scaffolding, similar to Backstage or Port, but orchestrated entirely in Python.

**The Future Flow:**

1. **Dynamic Forms:** The Flask UI will host dynamic forms (e.g., "Create New Microservice") requesting parameters like service\_name, team\_owner, and database\_required.  
2. **The Orchestration Runner:** When submitted, the Flask backend validates the payload and dispatches a task (likely via Celery or a webhook-triggered Python runner).  
3. **PyGithub Automation:** A dedicated backend service utilizing the PyGithub library executes the logic:  
   * Authenticates with the GitHub Organization as a GitHub App.  
   * Clones a standardized template repository based on the user's inputs.  
   * Uses a templating engine (like Jinja2) to inject the variables into the codebase (e.g., README.md, docker-compose.yml).  
   * Pushes the new code to a freshly generated repository.  
   * Registers the new service in the IDP's catalog database.

**Outcome:** Developers can spin up fully compliant, standardized microservices in minutes with CI/CD pipelines pre-configured, drastically reducing onboarding and setup time.

## **Pillar 3: The Native Claude Code Marketplace**

*Goal: Host an official Claude Code Plugin Marketplace directly via the Flask IDP, allowing developers to natively browse, install, and auto-update internal organizational skills.*

By adhering to Anthropic's official Plugin Marketplace specification, we eliminate the need for custom synchronization scripts. The Flask IDP will natively serve as a Remote URL Marketplace.

**The Future Flow:**

1. **The Dynamic Catalog Endpoint:** The Flask backend will be configured to serve a dynamic marketplace.json file at a dedicated endpoint (e.g., https://idp.internal.company.com/api/marketplace.json). This JSON will aggregate all internal tools—structured as standard Claude Code plugins (with .claude-plugin/plugin.json manifests, /skills, /hooks, and .mcp.json files).  
2. **Native CLI Integration:** Developers will connect their local environment to the internal hub using Claude Code's native commands:  
   * Run /plugin marketplace add https://idp.internal.company.com/api/marketplace.json to register the internal IDP.  
   * Toggle auto-updates via /plugin so their local skills always stay in sync with the central IDP repository.  
3. **Frictionless Installation:** Developers can now use the interactive /plugin UI natively within their terminal to browse our custom internal plugins. They can install domain-specific expertise effortlessly (e.g., /plugin install billing-api-docs@internal).  
4. **Cloud Synchronization (Chat & Cowork):** While the marketplace.json handles the local CLI experience, the IDP also mirrors the same catalog into the Claude web/desktop apps and Cowork.

> **✅ Realized (2026-06-06), and simpler than originally assumed.** No bespoke
> Enterprise APIs are needed: the Claude apps consume an **org-managed plugin
> marketplace** that **GitHub-syncs a private repo** (available on the **Team**
> plan). So the IDP commits the same generated `marketplace.json` into a private
> repo (`bryan-ipullrank/ipr-marketplace`, via `app/github_publisher.py`), and an
> admin connects it once under **Org settings → Plugins → GitHub sync**. Plugins
> then appear in every member's **Customize → Plugins** menu in Claude Desktop and
> Cowork. (Skills work in chat + Cowork; hooks/sub-agents are Cowork-only.)

**Outcome:** A ubiquitous, frictionless AI experience. A developer browses the internal marketplace, installs an organizational skill, and immediately has access to that context across their local IDE, terminal, and web-based collaborative sessions.

## **Implementation Roadmap**

> **Note (2026-06-05):** Execution order resequenced. Phase 2 needs a Docker-capable
> host, which PythonAnywhere is not, so it is deferred. Phases 3 and 4 run on the
> paid PythonAnywhere account and are being built first.

* **Phase 1 ✅ DONE:** Standalone Flask Hub \+ Flask-Dance Google OAuth, **live on PythonAnywhere**. See `Phase 1 Game Plan_ Minimal Flask IDP.md` and `README.md`.  
* **Phase 1.5 ✅ DONE (Catalog foundation):** DB-backed tool catalog (SQLite/SQLAlchemy) + REST API + persisted users with admin/member **roles & per-tool ownership** + server-rendered **management UI**. **Live on PythonAnywhere.** Provides the patterns Phases 3/4 reuse.  
* **Phase 3 ✅ DONE (The Claude Marketplace):** Flask serves a **token-gated** `marketplace.json` (Claude Code channel); plugin *payloads* live in **GitHub repos**. Adds a `Plugin` catalog with a `draft→pending→published` **approval workflow** (+`rejected`, +`access_pending`), a `/api/plugins` API, a management UI, and a no-secrets **"Request access"** flow. **Phase 3.6** mirrors the catalog into a private **GitHub monorepo** that feeds the Claude Desktop/Cowork org marketplace (Team-plan GitHub sync — realizing Pillar 3 step 4 without bespoke Enterprise APIs). **Phase 3.7** adds **categories + tags + grouped/filtered catalog views**, **Option-A vendoring** (the IDP commits each published plugin's files into the monorepo), and **collaborator-access automation** (submitting auto-accepts the catalog-matching GitHub repo invite). **Detailed plan + decisions + lessons: `Phase 3 Game Plan_ Claude Marketplace.md`.**  
* **Phase 4 ⏭️ NEXT (GitHub Scaffolding):** Integrate PyGithub. Build the UI forms and background workers to automate repository generation — scaffolding compliant plugin repos and registering them back in the catalog. Builds on the GitHub integration started in `app/github_publisher.py`. *(PythonAnywhere-friendly — always-on tasks + unrestricted outbound.)*  
* **Phase 2 ⏸️ DEFERRED (Infrastructure Migration):** Containerize the Flask app. Deploy NGINX and oauth2-proxy to handle edge authentication. Strip OAuth out of the Flask layer. **Requires a Docker VM (not PythonAnywhere). Detailed plan: `Phase 2 Game Plan_ Containerized IAP.md`.**