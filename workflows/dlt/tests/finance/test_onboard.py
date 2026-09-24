"""Unit tests for the finance.onboarding CLI.

No live API: every HTTP call goes through ``httpx.MockTransport`` and every
fixture is synthetic — no real account, IBAN, holder name or transaction text
appears here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from finance import onboard
from finance.providers.base import RateLimitError

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()

APP_ID = "00000000-0000-0000-0000-0000000000aa"

ASPSPS_BODY = {
    "aspsps": [
        {"name": "Zed Bank", "country": "ES"},
        {"name": "Alpha Bank", "country": "ES"},
    ]
}

AUTH_RESPONSE = {
    "url": "https://auth.enablebanking.com/ais/start?sessionid=00000000-0000-0000-0000-0000000000bb",
    "authorization_id": "00000000-0000-0000-0000-00000000000cc",
    "psu_id_hash": "hash",
}

SESSION_RESPONSE = {
    "session_id": "00000000-0000-0000-0000-0000000000dd",
    "accounts": [
        {
            "account_id": {"iban": "ES0000000000000000000000", "other": None},
            "uid": "00000000-0000-0000-0000-000000000001",
            "currency": "EUR",
            "product": "CUENTA CORRIENTE",
            "name": "SAMPLE HOLDER",
        }
    ],
    "aspsp": {"name": "Sample Bank", "country": "ES"},
    "access": {"valid_until": "2027-01-01T00:00:00Z"},
}


def _client(routes: dict[str, httpx.Response], captured: list[httpx.Request] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return routes[request.url.path]

    return httpx.Client(base_url="https://api.enablebanking.com", transport=httpx.MockTransport(handler))


def _run(client: httpx.Client, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setenv("ENABLEBANKING_PRIVATE_KEY", PRIVATE_KEY_PEM)
    monkeypatch.setenv("ENABLEBANKING_APP_ID", APP_ID)
    monkeypatch.setattr(onboard, "build_client", lambda: client)
    onboard.main(argv)


class TestListAspsps:
    def test_prints_available_banks_sorted(self, capsys, monkeypatch):
        client = _client({"/aspsps": httpx.Response(200, json=ASPSPS_BODY)})
        _run(client, monkeypatch, ["aspsps", "--country", "ES"])
        out = capsys.readouterr().out
        assert out.index("Alpha Bank") < out.index("Zed Bank")

    def test_sends_the_country_parameter(self):
        captured: list[httpx.Request] = []
        client = _client({"/aspsps": httpx.Response(200, json=ASPSPS_BODY)}, captured)
        with client:
            onboard.list_aspsps(client, PRIVATE_KEY_PEM, APP_ID, "FI")
        assert captured[0].url.params["country"] == "FI"


class TestStartAuthorization:
    def test_prints_the_consent_url_and_next_command(self, capsys, monkeypatch):
        client = _client({"/auth": httpx.Response(200, json=AUTH_RESPONSE)})
        _run(client, monkeypatch, ["auth", "--aspsp", "Sample Bank", "--redirect-url", "https://x/cb"])
        out = capsys.readouterr().out
        assert "Open this URL in a browser" in out
        assert AUTH_RESPONSE["url"] in out
        assert "--code" in out and "--alias" in out

    def test_request_body_carries_consent_parameters(self, monkeypatch):
        captured: list[httpx.Request] = []
        client = _client({"/auth": httpx.Response(200, json=AUTH_RESPONSE)}, captured)
        before = datetime.now(UTC)
        _run(
            client,
            monkeypatch,
            ["auth", "--aspsp", "Sample Bank", "--country", "ES",
             "--redirect-url", "https://x/cb", "--days", "30"],
        )
        body = json.loads(captured[0].read())
        assert body["aspsp"] == {"name": "Sample Bank", "country": "ES"}
        assert body["redirect_url"] == "https://x/cb"
        assert body["psu_type"] == "personal"
        requested = datetime.fromisoformat(body["access"]["valid_until"])
        assert (requested - before).total_seconds() == pytest.approx(30 * 86400, abs=5)

    def test_missing_redirect_url_exits_with_a_message(self, monkeypatch):
        monkeypatch.delenv("ENABLEBANKING_REDIRECT_URL", raising=False)
        client = _client({})
        with pytest.raises(SystemExit):
            _run(client, monkeypatch, ["auth", "--aspsp", "Sample Bank"])


class TestAuthorizeSession:
    def test_posts_the_code(self):
        captured: list[httpx.Request] = []
        client = _client({"/sessions": httpx.Response(200, json=SESSION_RESPONSE)}, captured)
        with client:
            onboard.authorize_session(client, PRIVATE_KEY_PEM, APP_ID, "the-code")
        assert json.loads(captured[0].read()) == {"code": "the-code"}


class TestAccountFragments:
    def test_single_account_uses_the_alias(self):
        fragments = onboard.account_fragments(SESSION_RESPONSE, alias="acct_a", app_id=APP_ID)
        assert list(fragments) == ["acct_a"]
        fragment = fragments["acct_a"]
        assert fragment["iban"] == "ES0000000000000000000000"
        assert fragment["app_id"] == APP_ID
        assert fragment["institution_id"] == "Sample Bank"
        assert set(fragment) == {"iban", "app_id", "institution_id"}

    def test_token_fragments_carry_the_session_scoped_material(self):
        fragments = onboard.token_fragments(SESSION_RESPONSE, alias="acct_a")
        fragment = fragments["acct_a"]
        assert fragment["uid"] == "00000000-0000-0000-0000-000000000001"
        assert fragment["valid_until"] == "2027-01-01T00:00:00Z"
        assert fragment["session_id"] == "00000000-0000-0000-0000-0000000000dd"
        assert set(fragment) == {"uid", "valid_until", "session_id"}

    def test_multiple_accounts_get_distinct_numbered_keys(self):
        accounts = SESSION_RESPONSE["accounts"] * 3
        multi = {**SESSION_RESPONSE, "accounts": accounts}
        fragments = onboard.account_fragments(multi, alias="acct_a", app_id=APP_ID)
        assert list(fragments) == ["acct_a", "acct_a_2", "acct_a_3"]

    def test_no_accounts_yields_no_fragments(self):
        empty = {**SESSION_RESPONSE, "accounts": []}
        assert onboard.account_fragments(empty, alias="acct_a", app_id=APP_ID) == {}


class TestMaskIban:
    def test_keeps_only_the_last_four(self):
        assert onboard.mask_iban("ES0000000000000000000000") == "****0000"

    def test_unknown_iban_is_explicit(self):
        assert onboard.mask_iban("") == "<unknown>"


class TestSessionCommand:
    def test_prints_a_masked_listing_and_two_paste_blocks(self, capsys, monkeypatch):
        client = _client({"/sessions": httpx.Response(200, json=SESSION_RESPONSE)})
        _run(client, monkeypatch, ["session", "--code", "abc", "--alias", "acct_a"])
        out = capsys.readouterr().out
        stable_marker = "Paste into finance-enablebanking under accounts.json\n"
        token_marker = "Paste into finance-enablebanking-token under tokens.json (same keys):\n"
        listing, stable_part = out.split(stable_marker, 1)
        stable_json, token_json = stable_part.split(token_marker, 1)
        assert "****0000" in listing
        assert "ES0000000000000000000000" not in listing
        stable = json.loads(stable_json)
        assert stable["acct_a"]["iban"] == "ES0000000000000000000000"
        assert "uid" not in stable["acct_a"]
        token = json.loads(token_json)
        assert token["acct_a"]["uid"] == "00000000-0000-0000-0000-000000000001"
        assert token["acct_a"]["valid_until"] == "2027-01-01T00:00:00Z"
        assert token["acct_a"]["session_id"] == "00000000-0000-0000-0000-0000000000dd"

    def test_rate_limit_from_the_bank_surfaces_as_rate_limit_error(self, monkeypatch):
        client = _client({"/sessions": httpx.Response(
            429, json={"code": 429, "error": "ASPSP_RATE_LIMIT_EXCEEDED", "message": "limit"}
        )})
        with pytest.raises(RateLimitError):
            _run(client, monkeypatch, ["session", "--code", "abc", "--alias", "x"])
