"""Unit tests for the Enable Banking provider adapter.

No live API: every HTTP call goes through ``httpx.MockTransport`` and every
fixture is synthetic — no real account, IBAN, holder name or transaction text
appears here (the operator's live data lives only in the k8s secret).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from finance.providers.base import (
    AccessExpiredError,
    AuthError,
    ProviderError,
    RateLimitError,
    TokenMissingError,
)
from finance.providers.enablebanking import (
    AccountConfig,
    EnableBankingProvider,
    TokenConfig,
)

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()

ACCOUNT = AccountConfig(
    alias="sample_account",
    iban="ES0000000000000000000000",
    app_id="00000000-0000-0000-0000-0000000000aa",
    institution_id="Sample Bank",
)

TOKEN = TokenConfig(
    alias="sample_account",
    uid="00000000-0000-0000-0000-000000000001",
    valid_until=datetime(2027, 1, 1, tzinfo=UTC),
)


def _txn(**overrides):
    resource = {
        "entry_reference": None,
        "transaction_amount": {"currency": "EUR", "amount": "12.34"},
        "credit_debit_indicator": "DBIT",
        "status": "BOOK",
        "booking_date": "2026-01-15",
        "value_date": "2026-01-14",
        "remittance_information": ["SAMPLE SHOP"],
        "creditor": None,
        "debtor": None,
        "creditor_account": None,
        "debtor_account": {"iban": "ES0000000000000000000000", "other": None},
        "bank_transaction_code": None,
        "transaction_id": None,
    }
    resource.update(overrides)
    return resource


def _content(payload):
    return json.dumps(payload)


def _provider(handler, tokens=(TOKEN,), **kwargs):
    client = httpx.Client(
        base_url="https://api.enablebanking.com",
        transport=httpx.MockTransport(handler),
    )
    return EnableBankingProvider(
        private_key=PRIVATE_KEY_PEM, accounts=[ACCOUNT], tokens=list(tokens), client=client, **kwargs
    )


def _details_handler(captured=None):
    def handler(request):
        if captured is not None:
            captured.append(request)
        return httpx.Response(200, json={
            "account_id": {"iban": ACCOUNT.iban, "other": None},
            "name": "SAMPLE HOLDER",
            "currency": "EUR",
        })
    return handler


class TestAuth:
    def test_jwt_is_rs256_with_kid_and_enablebanking_claims(self):
        captured = {}

        def handler(request):
            captured["auth"] = request.headers["Authorization"]
            return httpx.Response(200, json={"balances": []})

        _provider(handler).fetch_balances(ACCOUNT.alias)
        token = captured["auth"].removeprefix("Bearer ")
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(
            token,
            _PRIVATE_KEY.public_key(),
            algorithms=["RS256"],
            audience="api.enablebanking.com",
            issuer="enablebanking.com",
        )
        assert header["kid"] == ACCOUNT.app_id
        assert payload["exp"] - payload["iat"] == 3600

    def test_mints_a_fresh_jwt_per_request(self):
        seen = []

        def handler(request):
            seen.append(request.headers["Authorization"])
            return httpx.Response(200, json={"balances": []})

        provider = _provider(handler)
        provider.fetch_balances(ACCOUNT.alias)
        provider.fetch_balances(ACCOUNT.alias)
        assert len(seen) == 2


class TestListAccounts:
    def test_reads_details_and_uses_the_alias_as_identity(self):
        accounts = _provider(_details_handler()).list_accounts()
        assert len(accounts) == 1
        account = accounts[0]
        assert account.account_id == "sample_account"
        assert account.institution_id == "Sample Bank"
        assert account.iban == ACCOUNT.iban
        assert account.currency == "EUR"
        assert account.owner_name == "SAMPLE HOLDER"
        assert account.status == "AUTHORIZED"
        assert json.loads(account.payload_json)["currency"] == "EUR"

    def test_hits_the_account_uid_path(self):
        captured = []
        _provider(_details_handler(captured)).list_accounts()
        assert captured[0].url.path == f"/accounts/{TOKEN.uid}/details"


class TestFetchTransactions:
    def _handler_for(self, *pages, captured=None):
        pages = iter(pages)

        def handler(request):
            if captured is not None:
                captured.append(request)
            return httpx.Response(200, json=next(pages))

        return handler

    def test_normalises_and_signs_debit(self):
        provider = _provider(self._handler_for({"transactions": [_txn()]}))
        txn = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        assert txn.account_id == "sample_account"
        assert txn.amount == Decimal("-12.34")
        assert txn.currency == "EUR"
        assert txn.booking_date == date(2026, 1, 15)
        assert txn.value_date == date(2026, 1, 14)

    def test_credit_is_positive(self):
        provider = _provider(self._handler_for({"transactions": [_txn(credit_debit_indicator="CRDT")]}))
        txn = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        assert txn.amount == Decimal("12.34")

    def test_remittance_list_is_joined(self):
        resource = _txn(remittance_information=["PART ONE", "PART TWO"])
        provider = _provider(self._handler_for({"transactions": [resource]}))
        txn = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        assert txn.remittance_info == "PART ONE PART TWO"

    def test_party_and_account_fields_are_flattened(self):
        resource = _txn(
            creditor={"name": "SAMPLE MERCHANT"},
            creditor_account={"iban": "ES1111111111111111111111", "other": None},
            bank_transaction_code={"code": "12", "sub_code": "32"},
        )
        provider = _provider(self._handler_for({"transactions": [resource]}))
        txn = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        assert txn.creditor_name == "SAMPLE MERCHANT"
        assert txn.creditor_iban == "ES1111111111111111111111"
        assert txn.bank_transaction_code == "12"

    def test_entry_reference_is_the_stable_id(self):
        resource = _txn(entry_reference="ASPSP-REF-1")
        provider = _provider(self._handler_for({"transactions": [resource]}))
        txn = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        assert txn.stable_id == "ASPSP-REF-1"

    def test_hash_is_stable_across_identical_fetches(self):
        page = {"transactions": [_txn()]}
        provider = _provider(self._handler_for(page, page))
        first = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        second = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        assert first.stable_id == second.stable_id
        assert len(first.stable_id) == 32

    def test_transaction_id_does_not_affect_identity(self):
        one = _txn(transaction_id="00000000-0000-0000-0000-00000000000a")
        two = _txn(transaction_id="00000000-0000-0000-0000-00000000000b")
        provider = _provider(self._handler_for({"transactions": [one]}, {"transactions": [two]}))
        first = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        second = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))[0]
        assert first.stable_id == second.stable_id

    def test_non_booked_transactions_are_skipped(self):
        resources = [_txn(status="BOOK"), _txn(status="PDNG"), _txn(status="CNCL")]
        provider = _provider(self._handler_for({"transactions": resources}))
        txns = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))
        assert len(txns) == 1

    def test_follows_continuation_key_until_exhausted(self):
        captured = []
        pages = [
            {"transactions": [_txn()], "continuation_key": "next"},
            {"transactions": [_txn(entry_reference="REF-2")]},
        ]
        provider = _provider(self._handler_for(*pages, captured=captured))
        txns = provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))
        assert len(txns) == 2
        assert len(captured) == 2
        assert captured[0].url.params.get("continuation_key") is None
        assert captured[1].url.params.get("continuation_key") == "next"

    def test_window_and_strategy_are_sent(self):
        captured = []
        handler = self._handler_for({"transactions": []}, captured=captured)
        _provider(handler, strategy="longest").fetch_transactions(
            ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31)
        )
        params = captured[0].url.params
        assert params["date_from"] == "2026-01-01"
        assert params["date_to"] == "2026-01-31"
        assert params["strategy"] == "longest"

    def test_omitted_window_is_not_sent(self):
        # longest with no dates: the API determines the earliest available itself
        captured = []
        handler = self._handler_for({"transactions": []}, captured=captured)
        _provider(handler, strategy="longest").fetch_transactions(ACCOUNT.alias, None, None)
        params = captured[0].url.params
        assert "date_from" not in params
        assert "date_to" not in params
        assert params["strategy"] == "longest"


class TestFetchBalances:
    def test_normalises_balance(self):
        def handler(request):
            return httpx.Response(200, json={"balances": [
                {
                    "name": "Booked balance",
                    "balance_type": "CLBD",
                    "balance_amount": {"currency": "EUR", "amount": "100.00"},
                    "reference_date": None,
                }
            ]})

        balance = _provider(handler).fetch_balances(ACCOUNT.alias)[0]
        assert balance.account_id == "sample_account"
        assert balance.balance_type == "CLBD"
        assert balance.amount == 100
        assert balance.reference_date is None


class TestErrors:
    def _failing(self, status, body):
        def handler(request):
            return httpx.Response(status, json=body)

        return _provider(handler)

    def test_429_is_a_rate_limit_error(self):
        provider = self._failing(429, {"code": 429, "error": "ASPSP_RATE_LIMIT_EXCEEDED", "message": "Daily limit"})
        with pytest.raises(RateLimitError):
            provider.fetch_transactions(ACCOUNT.alias, date(2026, 1, 1), date(2026, 1, 31))

    def test_expired_session_is_an_access_expired_error(self):
        provider = self._failing(401, {"error": "SESSION_EXPIRED", "message": "session is expired"})
        with pytest.raises(AccessExpiredError):
            provider.fetch_balances(ACCOUNT.alias)

    def test_rejected_credential_is_an_auth_error(self):
        provider = self._failing(401, {"error": "INVALID_JWT", "message": "bad signature"})
        with pytest.raises(AuthError):
            provider.fetch_balances(ACCOUNT.alias)

    def test_unknown_account_alias_is_a_provider_error(self):
        provider = _provider(_details_handler())
        with pytest.raises(ProviderError, match="unknown finance account"):
            provider.fetch_balances("nope")

    def test_error_message_carries_the_provider_detail(self):
        # detail is the ASPSP's own reason; losing it makes a revoked consent
        # read the same as a transient bank fault
        provider = self._failing(400, {
            "error": "ASPSP_ERROR",
            "message": "Error interacting with ASPSP",
            "detail": {"reason": "consent revoked at the bank"},
        })
        with pytest.raises(AccessExpiredError, match="consent revoked at the bank"):
            provider.fetch_balances(ACCOUNT.alias)


class TestSplitSecrets:
    def test_account_alias_without_token_is_a_named_loud_failure(self):
        provider = _provider(_details_handler(), tokens=())
        with pytest.raises(TokenMissingError, match="finance-enablebanking-token"):
            provider.fetch_balances(ACCOUNT.alias)

    def test_missing_token_names_the_renewal_path_even_before_a_call(self):
        # list_accounts is the first call made by ingest's preflight companion; both
        # endpoints must fail the same way when the token Secret is absent.
        provider = _provider(_details_handler(), tokens=())
        with pytest.raises(TokenMissingError):
            provider.list_accounts()

    def test_missing_token_subclasses_access_expired(self):
        # one failure class for every "unusable session" consumer (goal 6)
        assert issubclass(TokenMissingError, AccessExpiredError)

    def test_stable_and_dynamic_maps_are_exposed(self):
        provider = _provider(lambda request: httpx.Response(200, json={}))
        assert list(provider.accounts) == ["sample_account"]
        assert provider.tokens["sample_account"].uid == TOKEN.uid
