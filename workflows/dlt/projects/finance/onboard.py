"""Onboarding CLI for Enable Banking (spec 005 §4.2).

Operator laptop, never in-cluster: the bank consent is a browser flow (PSD2
strong customer authentication), so this CLI walks the three manual steps and
prints exactly what to paste into the ``finance-enablebanking`` secret::

    uv run python -m finance.onboard aspsps
    uv run python -m finance.onboard auth --aspsp "<bank name from aspsps>"
    uv run python -m finance.onboard session --code <code> --alias <alias>

Required env (besides the shared ``ENABLEBANKING_*`` variables):
``ENABLEBANKING_PRIVATE_KEY`` (PEM) or ``ENABLEBANKING_PRIVATE_KEY_FILE``, and
``ENABLEBANKING_APP_ID`` — the application id issued at registration, which is
also the JWT ``kid``. ``ENABLEBANKING_REDIRECT_URL`` must be one of the URLs
whitelisted on the application.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .providers.enablebanking import DEFAULT_BASE_URL, mint_jwt, raise_for_status

DEFAULT_COUNTRY = "ES"
DEFAULT_CONSENT_DAYS = 180


# -- shared client -----------------------------------------------------------
def _private_key() -> str:
    pem = os.environ.get("ENABLEBANKING_PRIVATE_KEY")
    if pem:
        return pem
    path = os.environ.get("ENABLEBANKING_PRIVATE_KEY_FILE")
    if path:
        with open(path) as handle:
            return handle.read().strip()
    sys.exit("set ENABLEBANKING_PRIVATE_KEY (PEM text) or ENABLEBANKING_PRIVATE_KEY_FILE")


def _app_id() -> str:
    app_id = os.environ.get("ENABLEBANKING_APP_ID")
    if not app_id:
        sys.exit("set ENABLEBANKING_APP_ID (the application id / JWT kid)")
    return app_id


def build_client() -> httpx.Client:
    base_url = os.environ.get("ENABLEBANKING_BASE_URL", DEFAULT_BASE_URL)
    return httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)


def _request(
    client: httpx.Client,
    private_key: str,
    app_id: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    context: str = "onboarding",
) -> dict:
    response = client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {mint_jwt(private_key, app_id)}"},
        params={k: v for k, v in (params or {}).items() if v is not None},
        json=json_body,
    )
    raise_for_status(response, context=context)
    return response.json()


# -- steps -------------------------------------------------------------------
def list_aspsps(
    client: httpx.Client, private_key: str, app_id: str, country: str
) -> list[dict]:
    """Print the ASPSPs available in ``country`` (exact names for ``auth``)."""
    body = _request(client, private_key, app_id, "GET", "/aspsps", params={"country": country})
    aspsps = sorted(body.get("aspsps") or [], key=lambda entry: entry["name"])
    for entry in aspsps:
        print(f"{entry['name']} ({entry['country']})")
    return aspsps


def start_authorization(
    client: httpx.Client,
    private_key: str,
    app_id: str,
    *,
    aspsp: str,
    country: str,
    redirect_url: str | None,
    days: int = DEFAULT_CONSENT_DAYS,
    psu_type: str = "personal",
) -> dict:
    """Start the consent flow and tell the operator what to do with the URL."""
    if not redirect_url:
        sys.exit("set --redirect-url or ENABLEBANKING_REDIRECT_URL (must be whitelisted on the application)")
    valid_until = (datetime.now(UTC) + timedelta(days=days)).isoformat()
    state = str(uuid.uuid4())
    body = _request(
        client,
        private_key,
        app_id,
        "POST",
        "/auth",
        json_body={
            "access": {"valid_until": valid_until},
            "aspsp": {"name": aspsp, "country": country},
            "state": state,
            "redirect_url": redirect_url,
            "psu_type": psu_type,
        },
    )
    print(f"Open this URL in a browser and approve the consent for {aspsp}:")
    print(body["url"])
    print(
        "\nThe browser lands on the redirect URL with ?code=... (the page itself will\n"
        "not load — nothing is listening). Then run:\n"
        f"  uv run python -m finance.onboard session --code <code> --alias <alias>\n"
        f"(authorization id {body['authorization_id']}, state {state})"
    )
    return body


def authorize_session(client: httpx.Client, private_key: str, app_id: str, code: str) -> dict:
    """Exchange the consent ``code`` for the session holding the account uids."""
    return _request(
        client,
        private_key,
        app_id,
        "POST",
        "/sessions",
        json_body={"code": code},
    )


def mask_iban(iban: str) -> str:
    return f"****{iban[-4:]}" if iban else "<unknown>"


def account_fragments(
    session: dict, *, alias: str, app_id: str
) -> dict[str, dict[str, str | None]]:
    """Build the stable ``accounts.json`` entries for ``finance-enablebanking``.

    With more than one authorised account the keys are numbered; the operator
    renames them to the aliases they want before pasting.
    """
    institution_id = (session.get("aspsp") or {}).get("name")
    fragments: dict[str, dict[str, str | None]] = {}
    for index, resource in enumerate(session.get("accounts") or []):
        key = alias if index == 0 else f"{alias}_{index + 1}"
        fragments[key] = {
            "iban": (resource.get("account_id") or {}).get("iban"),
            "app_id": app_id,
            "institution_id": institution_id,
        }
    return fragments


def token_fragments(
    session: dict, *, alias: str
) -> dict[str, dict[str, str | None]]:
    """Build the session-scoped ``tokens.json`` entries for
    ``finance-enablebanking-token`` — uid, ``access.valid_until`` and the session
    id, keyed by the same alias the stable fragment used. The session id lets the
    §4.2.1 daily check read the session's status without a data call (an Enable
    Banking lookup, no ASPSP consultation)."""
    valid_until = (session.get("access") or {}).get("valid_until")
    session_id = session.get("session_id")
    fragments: dict[str, dict[str, str | None]] = {}
    for index, resource in enumerate(session.get("accounts") or []):
        key = alias if index == 0 else f"{alias}_{index + 1}"
        fragments[key] = {
            "uid": resource.get("uid"),
            "valid_until": valid_until,
            "session_id": session_id,
        }
    return fragments


def _print_session(session: dict, alias: str, app_id: str) -> None:
    accounts = session.get("accounts") or []
    print("Authorized accounts:")
    for index, resource in enumerate(accounts):
        iban = (resource.get("account_id") or {}).get("iban")
        print(
            f"  [{index + 1}] {mask_iban(iban)}  uid={resource.get('uid')}  "
            f"currency={resource.get('currency')}  product={resource.get('product')}"
        )
    print("\nPaste into finance-enablebanking under accounts.json")
    if len(accounts) > 1:
        print("(keys are numbered — rename them to the aliases you want):")
    print(json.dumps(account_fragments(session, alias=alias, app_id=app_id), indent=2))
    print("\nPaste into finance-enablebanking-token under tokens.json (same keys):")
    print(json.dumps(token_fragments(session, alias=alias), indent=2))


# -- entry point -------------------------------------------------------------
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="finance.onboard",
        description="Walk the manual Enable Banking onboarding steps (spec 005 §4.2).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    aspsps = subparsers.add_parser("aspsps", help="list available banks for a country")
    aspsps.add_argument("--country", default=DEFAULT_COUNTRY)

    auth = subparsers.add_parser("auth", help="start the consent flow and print the URL")
    auth.add_argument("--aspsp", required=True, help="exact bank name, as printed by 'aspsps'")
    auth.add_argument("--country", default=DEFAULT_COUNTRY)
    auth.add_argument("--redirect-url", default=os.environ.get("ENABLEBANKING_REDIRECT_URL"))
    auth.add_argument("--days", type=int, default=DEFAULT_CONSENT_DAYS)
    auth.add_argument("--psu-type", default="personal", choices=["personal", "business"])

    session = subparsers.add_parser("session", help="exchange the consent code for a session")
    session.add_argument("--code", required=True, help="code query parameter from the redirect")
    session.add_argument("--alias", required=True, help="stable pipeline name for the account")

    parsed = parser.parse_args(argv)
    client = build_client()
    try:
        private_key, app_id = _private_key(), _app_id()
        if parsed.command == "aspsps":
            list_aspsps(client, private_key, app_id, parsed.country)
        elif parsed.command == "auth":
            start_authorization(
                client,
                private_key,
                app_id,
                aspsp=parsed.aspsp,
                country=parsed.country,
                redirect_url=parsed.redirect_url,
                days=parsed.days,
                psu_type=parsed.psu_type,
            )
        elif parsed.command == "session":
            body = authorize_session(client, private_key, app_id, parsed.code)
            _print_session(body, parsed.alias, app_id)
    finally:
        client.close()


if __name__ == "__main__":
    main()
