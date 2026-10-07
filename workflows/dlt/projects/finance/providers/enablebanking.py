"""Enable Banking provider adapter.

The only module that knows Enable Banking's wire format
(``openspec/changes/archive/2026-10-07-retire-docs-specs/designs/005-personal-finance-datalake.md`` §4.1):

- auth is a self-signed RS256 JWT minted per request from the application id
  (``kid``) and the RSA private key — no token is ever stored;
- accounts are the operator-linked ones, addressed by their session ``uid``
  (which changes on re-link), so the stable identity used downstream is the
  configured ``alias``;
- transactions are normalised (list ``remittance_information``, signed amount
  from ``credit_debit_indicator``, a validated ``entry_reference``-first stable
  id) and filtered to ``status=BOOK``;
- PSD2 failures become named exceptions (``RateLimitError``,
  ``AccessExpiredError``, ``AuthError``) rather than a generic HTTP error.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
import jwt

from .base import (
    AccessExpiredError,
    Account,
    AuthError,
    Balance,
    ProviderError,
    RateLimitError,
    TokenMissingError,
    Transaction,
)

logger = logging.getLogger(__name__)

STABLE_ID_LENGTH = 32
JWT_TTL_SECONDS = 3600
DEFAULT_BASE_URL = "https://api.enablebanking.com"
BOOK_STATUS = "BOOK"

# A booking-date-scoped positional ordinal: an ISO date, a literal dot and an
# integer, and nothing else. Anchored so a reference that merely contains
# punctuation is not mistaken for one.
_POSITIONAL_REFERENCE = re.compile(r"^\d{4}-\d{2}-\d{2}\.\d+$")


def _is_positional_reference(value: str) -> bool:
    """Whether a provider reference describes a position rather than a transaction.

    Some ASPSPs return a booking-date-scoped ordinal (``2026-09-28.9`` is the
    tenth transaction booked that day). It is renumbered whenever the list
    shifts, so it is not an identity.
    """
    return bool(_POSITIONAL_REFERENCE.match(value))


@dataclass(frozen=True)
class AccountConfig:
    """Stable account binding from the ``finance-enablebanking`` secret.

    ``alias`` is the pipeline's stable account identity; ``institution_id``
    labels the ASPSP the payload itself does not name. Session material (uid,
    valid_until) lives in :class:`TokenConfig` — it is rewritten on every
    renewal, so the alias, never the uid, is bronze's identity (spec §4.2.1).
    """

    alias: str
    iban: str
    app_id: str
    institution_id: str | None = None
    identification_hash: str | None = None


@dataclass(frozen=True)
class TokenConfig:
    """Session-scoped material from the ``finance-enablebanking-token`` secret.

    ``uid`` is Enable Banking's per-session account id, valid only while the
    session is authorized; expired tokens fail loudly before any data call.
    ``session_id`` is kept so the renewal workflow's daily check can read the
    session's own status — an Enable Banking call that never reaches the ASPSP,
    so it spends no PSD2 data-call budget. ``identification_hash``, ``currency``
    and ``owner_name`` are the account fields ``POST /sessions`` returns once and
    later calls do not, so they are captured here and make
    ``/accounts/{uid}/details`` optional rather than load-bearing.
    """

    alias: str
    uid: str
    valid_until: datetime | None = None
    session_id: str | None = None
    identification_hash: str | None = None
    currency: str | None = None
    owner_name: str | None = None

    def consent_expired(self, now: datetime | None = None) -> bool:
        if self.valid_until is None:
            return False
        now = now or datetime.now(UTC)
        return now >= self.valid_until


def mint_jwt(private_key: str, app_id: str) -> str:
    """Self-signed RS256 auth token for one API request.

    ``kid`` is the application id Enable Banking issued at registration; the
    token lives ``JWT_TTL_SECONDS`` and is minted fresh per request — nothing is
    persisted or refreshed (spec §4.1).
    """
    issued_at = int(datetime.now(UTC).timestamp())
    return jwt.encode(
        {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": issued_at,
            "exp": issued_at + JWT_TTL_SECONDS,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": app_id},
    )


def _error_message(body: dict, response: httpx.Response) -> str:
    """``message`` plus the ``detail`` Enable Banking attaches to a failure.

    ``detail`` is where the ASPSP's own reason lands, so dropping it makes a
    revoked consent read the same as a transient fault.
    """
    name = str(body.get("error") or body.get("code") or "")
    message = str(body.get("message") or name or response.reason_phrase)
    detail = body.get("detail")
    if detail in (None, "", [], {}):
        return message
    rendered = detail if isinstance(detail, str) else json.dumps(detail, sort_keys=True, default=str)
    return message if rendered in message else f"{message}: {rendered}"


def raise_for_status(response: httpx.Response, context: str) -> None:
    """Classify an Enable Banking error response into a named provider error."""
    if response.is_success:
        return
    try:
        body = response.json()
    except ValueError:
        body = {}
    name = str(body.get("error") or body.get("code") or "")
    message = _error_message(body, response)
    if response.status_code == 429 or "RATE_LIMIT" in name.upper():
        raise RateLimitError(
            f"{context}: PSD2 daily limit reached for this endpoint "
            f"({message}); the run does not retry, re-run after the bank's reset"
        )
    if "EXPIRED" in name.upper() or "expired" in message.lower() or "revoked" in message.lower():
        raise AccessExpiredError(
            f"{context}: consent expired or was revoked ({message}); "
            f"re-link it per workflows/dlt/README.md"
        )
    if response.status_code in (401, 403):
        raise AuthError(
            f"{context}: Enable Banking rejected the application credential "
            f"({message}); check app_id/private_key and the whitelisted redirect URLs"
        )
    raise ProviderError(f"{context}: Enable Banking returned {response.status_code} ({message})")


class EnableBankingProvider:
    """``BankDataProvider`` over the Enable Banking REST API."""

    def __init__(
        self,
        *,
        private_key: str,
        accounts: Iterable[AccountConfig],
        tokens: Iterable[TokenConfig] = (),
        base_url: str = DEFAULT_BASE_URL,
        strategy: str = "default",
        client: httpx.Client | None = None,
    ) -> None:
        self._private_key = private_key
        self._accounts = {account.alias: account for account in accounts}
        self._tokens = {token.alias: token for token in tokens}
        self._strategy = strategy
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self._base_url, timeout=30.0)

    # -- auth -----------------------------------------------------------------
    def _get(self, account: AccountConfig, token: TokenConfig, path: str,
             params: dict[str, Any] | None = None) -> dict:
        response = self._client.get(
            path,
            headers={"Authorization": f"Bearer {mint_jwt(self._private_key, account.app_id)}"},
            params={k: v for k, v in (params or {}).items() if v is not None},
        )
        raise_for_status(response, context=account.alias)
        return response.json()

    # -- protocol -------------------------------------------------------------
    def list_accounts(self) -> list[Account]:
        """One :class:`Account` per configured alias.

        ``/accounts/{uid}/details`` is skipped once the session-time fields it
        would add (``currency``, ``owner_name``) are stored in the token secret:
        they cannot change mid-session, and every call spends one of the
        ASPSP's ~4 background data fetches per day (spec 005 §4.2.1), which on
        Openbank is the scarce resource. The skipped call leaves the account
        row's ``payload_json`` empty; nothing downstream reads it. A secret
        written before those fields were captured still pays the call until
        the next renewal backfills them.

        When the call does happen it is best-effort: a bank that refuses
        ``/accounts/{uid}/details`` (an unsupported account, a transient ASPSP
        fault, a details-endpoint 429) must not abort the whole run, because
        the account's transactions and balances live on other endpoints. A
        fallback built from the configured secret keeps the alias, IBAN and
        institution; a genuinely unusable session still fails loudly on the
        data call, which is the backstop.
        """
        accounts = []
        for account, token in self._pair_for_every_alias():
            if token is not None and token.currency and token.owner_name:
                accounts.append(_configured_account(account, token))
                continue
            try:
                details = self._get(account, token, f"/accounts/{token.uid}/details")
            except (ProviderError, httpx.HTTPError) as error:
                logger.warning(
                    "%s: account details unavailable (%s); using the configured "
                    "alias/IBAN and continuing so transactions and balances still load",
                    account.alias,
                    error,
                )
                accounts.append(_configured_account(account, token))
                continue
            accounts.append(_normalise_account(account, token, details))
        return accounts

    def fetch_transactions(
        self, account_id: str, date_from: date | None, date_to: date | None
    ) -> list[Transaction]:
        account, token = self._pair(account_id)
        transactions: list[Transaction] = []
        continuation_key: str | None = None
        while True:
            page = self._get(
                account,
                token,
                f"/accounts/{token.uid}/transactions",
                {
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                    "strategy": self._strategy,
                    "continuation_key": continuation_key,
                },
            )
            transactions.extend(
                _normalise_transaction(account, resource)
                for resource in page.get("transactions") or []
                if resource.get("status") == BOOK_STATUS
            )
            continuation_key = page.get("continuation_key")
            if not continuation_key:
                break
        return transactions

    def fetch_balances(self, account_id: str) -> list[Balance]:
        account, token = self._pair(account_id)
        page = self._get(account, token, f"/accounts/{token.uid}/balances")
        return [_normalise_balance(account, resource) for resource in page.get("balances") or []]

    # -- lookups --------------------------------------------------------------
    def _pair(self, account_id: str) -> tuple[AccountConfig, TokenConfig]:
        account = self._accounts.get(account_id)
        if account is None:
            raise ProviderError(
                f"unknown finance account {account_id!r}; configured aliases: {sorted(self._accounts)}"
            )
        return account, self._token(account_id)

    def _pair_for_every_alias(self) -> list[tuple[AccountConfig, TokenConfig]]:
        return [self._pair(alias) for alias in self._accounts]

    def _token(self, alias: str) -> TokenConfig:
        token = self._tokens.get(alias)
        if token is None:
            raise TokenMissingError(
                f"{alias}: no session token in finance-enablebanking-token (the Secret may "
                "not exist yet); renew via the n8n workflow or finance.onboard session"
            )
        return token

    @property
    def accounts(self) -> dict[str, AccountConfig]:
        return self._accounts

    @property
    def tokens(self) -> dict[str, TokenConfig]:
        return self._tokens


def _configured_account(config: AccountConfig, token: TokenConfig | None = None) -> Account:
    """Fallback account row when ``/details`` cannot be read: the alias, IBAN and
    institution are stable secret values, and the session-time ``currency`` and
    ``owner_name`` (captured at authorisation) are used in place of the details
    response, so the account still lands populated."""
    return Account(
        account_id=config.alias,
        institution_id=config.institution_id or config.alias,
        iban=config.iban,
        currency=_currency(None, token),
        owner_name=token.owner_name if token else None,
        status="AUTHORIZED",
        payload_json="{}",
    )


def _currency(resource_value: Any, token: TokenConfig | None) -> str:
    """Details currency, falling back to the session-time value.

    ``XXX`` is the ISO code an ASPSP returns when it cannot state a currency, so
    it is treated as absent rather than as a real reading.
    """
    value = (resource_value or "").strip()
    if value and value.upper() != "XXX":
        return value
    return (token.currency if token else None) or ""


def _normalise_account(config: AccountConfig, token: TokenConfig | None, resource: dict) -> Account:
    return Account(
        account_id=config.alias,
        institution_id=config.institution_id or config.alias,
        iban=_account_iban(resource.get("account_id")) or config.iban,
        currency=_currency(resource.get("currency"), token),
        owner_name=resource.get("name") or (token.owner_name if token else None),
        status="AUTHORIZED",
        payload_json=json.dumps(resource, sort_keys=True, default=str),
    )


def _normalise_transaction(config: AccountConfig, resource: dict) -> Transaction:
    amount_object = resource.get("transaction_amount") or {}
    amount = _signed_amount(amount_object, resource.get("credit_debit_indicator"))
    currency = amount_object.get("currency") or ""
    remittance = _remittance(resource.get("remittance_information"))
    creditor = _party_name(resource.get("creditor"))
    debtor = _party_name(resource.get("debtor"))
    booking_date = date.fromisoformat(resource["booking_date"])
    return Transaction(
        account_id=config.alias,
        stable_id=_stable_id(
            resource.get("entry_reference"),
            config.alias,
            booking_date,
            amount,
            currency,
            remittance,
            creditor or debtor,
        ),
        booking_date=booking_date,
        value_date=_optional_date(resource.get("value_date")),
        amount=amount,
        currency=currency,
        remittance_info=remittance,
        creditor_name=creditor,
        debtor_name=debtor,
        creditor_iban=_account_iban(resource.get("creditor_account")),
        debtor_iban=_account_iban(resource.get("debtor_account")),
        bank_transaction_code=_bank_transaction_code(resource.get("bank_transaction_code")),
        payload_json=json.dumps(resource, sort_keys=True, default=str),
    )


def _normalise_balance(config: AccountConfig, resource: dict) -> Balance:
    amount_object = resource.get("balance_amount") or {}
    return Balance(
        account_id=config.alias,
        balance_type=resource.get("balance_type") or "OTHR",
        amount=Decimal(str(amount_object.get("amount", "0"))),
        currency=amount_object.get("currency") or "",
        reference_date=_optional_date(resource.get("reference_date")),
        payload_json=json.dumps(resource, sort_keys=True, default=str),
    )


def _stable_id(
    entry_reference: Any,
    account_id: str,
    booking_date: date,
    amount: Decimal,
    currency: str,
    remittance: str | None,
    counterparty: str | None,
) -> str:
    """``entry_reference`` when the ASPSP supplies a usable one, else a hash.

    The reference is trusted only when its shape is not a booking-date-scoped
    positional ordinal (see :func:`_is_positional_reference`); a positional
    value is not an identity and falls through to the hash. ``transaction_id``
    is never used: Enable Banking documents that it may change when the same
    transaction list is re-fetched.
    """
    if entry_reference and not _is_positional_reference(str(entry_reference)):
        return str(entry_reference)
    digest = hashlib.sha256(
        "|".join(
            [
                account_id,
                booking_date.isoformat(),
                f"{amount:.2f}",
                currency,
                remittance or "",
                counterparty or "",
            ]
        ).encode()
    ).hexdigest()
    return digest[:STABLE_ID_LENGTH]


def _signed_amount(amount_object: dict, indicator: Any) -> Decimal:
    amount = Decimal(str(amount_object.get("amount", "0")))
    return -amount if indicator == "DBIT" else amount


def _remittance(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return " ".join(str(part) for part in value if part) or None


def _party_name(party: Any) -> str | None:
    if isinstance(party, dict):
        return party.get("name")
    return party or None


def _account_iban(account: Any) -> str | None:
    if isinstance(account, dict):
        if account.get("iban"):
            return account["iban"]
        other = account.get("other")
        if isinstance(other, dict):
            return other.get("identification")
    return None


def _bank_transaction_code(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("code") or value.get("description")
    return value or None


def _optional_date(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None
