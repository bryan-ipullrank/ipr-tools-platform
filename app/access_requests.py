"""Build repo-access request links — pure, no Flask/DB, so it is unit-testable.

The IDP stores no GitHub credentials. When a developer lacks access to a
plugin's private repo (where the CLI clone fails), they click "Request access",
which opens a pre-filled email to the plugin's owner (cc'ing admins) so a human
grants the repo access on GitHub. This keeps the high-value org-admin credential
out of the IDP entirely.
"""

from __future__ import annotations

from typing import Iterable
from urllib.parse import quote, urlencode


def build_access_request_mailto(
    repo: str,
    plugin_label: str,
    requester_email: str,
    owner_email: str | None,
    admin_emails: Iterable[str],
) -> str:
    """Return a ``mailto:`` URL requesting access to ``repo``.

    Routing: the owner is the primary recipient (they're the natural approver);
    admins are cc'd. For an unowned plugin, admins become the recipients. The
    requester is always named in the body for an audit trail in the inbox.
    """
    admins = [e for e in admin_emails if e]

    if owner_email:
        recipients = [owner_email]
        cc = [e for e in admins if e != owner_email]
    else:
        recipients = admins
        cc = []

    subject = f"Repo access request: {repo}"
    body = (
        f"Hi,\n\n"
        f"{requester_email} would like access to the GitHub repository "
        f'"{repo}" in order to install the "{plugin_label}" Claude Code plugin.\n\n'
        f"Repo: https://github.com/{repo}\n"
        f"Requested by: {requester_email}\n\n"
        f"Thanks!"
    )

    params: dict[str, str] = {"subject": subject, "body": body}
    if cc:
        params["cc"] = ",".join(cc)
    # quote_via=quote so spaces become %20 (mail clients are happier than with +).
    query = urlencode(params, quote_via=quote)
    return f"mailto:{','.join(recipients)}?{query}"
