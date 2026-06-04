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
4. **Cloud Synchronization (Chat & Cowork):** While the marketplace.json handles the local CLI experience, the IDP backend will simultaneously leverage Anthropic Enterprise APIs to mirror these active skills into the user's web-based Claude Projects and Cowork shared contexts.

**Outcome:** A ubiquitous, frictionless AI experience. A developer browses the internal marketplace, installs an organizational skill, and immediately has access to that context across their local IDE, terminal, and web-based collaborative sessions.

## **Implementation Roadmap**

* **Phase 1 (Current):** Standalone Flask Hub \+ Flask-Dance Google OAuth (Hosted on PythonAnywhere).  
* **Phase 2 (Infrastructure Migration):** Containerize the Flask app. Deploy NGINX and oauth2-proxy to handle edge authentication. Strip OAuth out of the Flask layer.  
* **Phase 3 (The Claude Marketplace):** Build the REST endpoints in Flask to dynamically generate and serve a valid marketplace.json catalog. Construct the internal directory structure to host the plugin payloads (SKILL.md files, manifests, etc.) directly from the server.  
* **Phase 4 (GitHub Scaffolding):** Integrate PyGithub. Build the UI forms and background workers to automate repository generation.