"""The Claude Code plugin marketplace endpoint.

Serves a spec-valid ``marketplace.json`` so developers can run
``/plugin marketplace add https://user:TOKEN@<host>/marketplace.json`` once and
then browse + install internal plugins natively.

The Claude CLI sends NO Google-session cookie, so this route cannot sit behind
the app's OAuth login. It is gated instead by a single shared token presented via
HTTP Basic auth (password slot). The gate is **fail-closed**: a missing/wrong
token is 401, and an *unconfigured* ``MARKETPLACE_TOKEN`` is 503 so the catalog
is never accidentally world-readable.

Flask hosts only this metadata catalog; the plugin payloads live in GitHub repos
that the CLI clones with the developer's own git credentials.
"""

from __future__ import annotations

import hmac
import logging
from functools import wraps
from typing import Any, Callable, Iterable, Mapping

from flask import Blueprint, Response, current_app, jsonify

from .plugin_status import PLUGIN_PUBLISHED
from .repositories import SqlAlchemyPluginRepository

logger = logging.getLogger(__name__)

marketplace = Blueprint("marketplace", __name__)

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": 'Basic realm="ipr-marketplace"'}


def marketplace_token_required(view: Callable) -> Callable:
    """Gate a route behind the shared marketplace token (HTTP Basic password).

    Fail-closed: 503 when no token is configured, 401 when the request omits or
    mismatches it. The username is ignored — only the password is checked, with a
    constant-time compare to avoid leaking it via timing.
    """

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        from flask import request

        expected = current_app.config.get("MARKETPLACE_TOKEN")
        if not expected:
            logger.error("MARKETPLACE_TOKEN is not configured; refusing to serve catalog.")
            return jsonify({"error": "Marketplace is not configured."}), 503

        auth = request.authorization
        provided = auth.password if auth else None
        if not provided or not hmac.compare_digest(provided, expected):
            logger.info("Rejected marketplace request: missing or invalid token.")
            return jsonify({"error": "Unauthorized."}), 401, _UNAUTHORIZED_HEADERS

        return view(*args, **kwargs)

    return wrapped


def build_marketplace_document(config: Mapping[str, Any], plugins: Iterable[Any]) -> dict[str, Any]:
    """Build the spec-valid marketplace document from config + published plugins.

    Shared by the Flask ``/marketplace.json`` endpoint (Claude Code channel) and
    the GitHub publisher (Claude Desktop/Cowork channel) so both emit an identical
    document.
    """
    return {
        "name": config["MARKETPLACE_NAME"],
        "owner": {"name": config["MARKETPLACE_OWNER_NAME"]},
        "description": config["MARKETPLACE_DESCRIPTION"],
        "plugins": [plugin.to_marketplace_entry() for plugin in plugins],
    }


@marketplace.route("/marketplace.json", methods=["GET"])
@marketplace_token_required
def marketplace_json() -> tuple[Response, int]:
    """Return the spec-valid marketplace document of published plugins."""
    plugins = SqlAlchemyPluginRepository().list(status=PLUGIN_PUBLISHED)
    return jsonify(build_marketplace_document(current_app.config, plugins)), 200
