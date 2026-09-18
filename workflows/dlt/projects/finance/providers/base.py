"""Provider abstraction for bank-data ingestion.

A provider satisfies :class:`BankDataProvider` and returns the normalised
dataclasses below. Wire-format quirks (string amounts, list remittance
information, per-bank missing ids) are handled inside the adapter, never by dbt
or the ingest pipeline: ``docs/specs/005-personal-finance-datalake.md`` §4.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


class ProviderError(Exception):
    """Base class for a classified provider failure."""


class RateLimitError(ProviderError):
    """The ASPSP's per-endpoint daily budget is exhausted (PSD2 429)."""


class AccessExpiredError(ProviderError):
    """The consent or session is expired or revoked; the account needs re-linking."""


class TokenMissingError(AccessExpiredError):
    """No session token exists for an account.

    Subclasses ``AccessExpiredError`` so every consumer that treats an unusable
    session as one failure class handles it: the ``finance-enablebanking-token``
    Secret is maintained dynamically by the renewal workflow (spec 005 §4.2.1)
    and may be absent entirely between a fresh link and the first renewal, or
    mid-renewal. The remediation is the renewal flow, not a code fix.
    """


class AuthError(ProviderError):
    """The application credential (JWT/kid/redirect registration) was rejected."""


@dataclass(frozen=True)
class Account:
    account_id: str
    institution_id: str
    iban: str
    currency: str
    owner_name: str | None
    status: str
    payload_json: str


@dataclass(frozen=True)
class Transaction:
    account_id: str
    stable_id: str
    booking_date: date
    value_date: date | None
    amount: Decimal
    currency: str
    remittance_info: str | None
    creditor_name: str | None
    debtor_name: str | None
    creditor_iban: str | None
    debtor_iban: str | None
    bank_transaction_code: str | None
    payload_json: str


@dataclass(frozen=True)
class Balance:
    account_id: str
    balance_type: str
    amount: Decimal
    currency: str
    reference_date: date | None
    payload_json: str


class BankDataProvider(Protocol):
    def list_accounts(self) -> list[Account]: ...

    def fetch_transactions(
        self, account_id: str, date_from: date | None, date_to: date | None
    ) -> list[Transaction]: ...

    def fetch_balances(self, account_id: str) -> list[Balance]: ...
