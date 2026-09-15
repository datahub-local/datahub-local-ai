"""Tests for the finance pipeline configuration helpers."""

from __future__ import annotations

import json

import pytest
from finance import config

ACCOUNTS_JSON = json.dumps(
    {
        "sample_account": {
            "iban": "ES0000000000000000000000",
            "app_id": "00000000-0000-0000-0000-0000000000aa",
            "institution_id": "Sample Bank",
        }
    }
)

TOKENS_JSON = json.dumps(
    {
        "sample_account": {
            "uid": "00000000-0000-0000-0000-000000000001",
            "valid_until": "2027-01-01T00:00:00Z",
        }
    }
)


def test_stable_accounts_are_parsed_from_the_secret_shape(monkeypatch):
    monkeypatch.setenv("ENABLEBANKING_ACCOUNTS", ACCOUNTS_JSON)
    accounts = config.enablebanking_accounts()
    assert len(accounts) == 1
    account = accounts[0]
    assert account.alias == "sample_account"
    assert account.iban == "ES0000000000000000000000"
    assert account.app_id == "00000000-0000-0000-0000-0000000000aa"
    assert account.institution_id == "Sample Bank"


def test_accounts_env_is_required(monkeypatch):
    monkeypatch.delenv("ENABLEBANKING_ACCOUNTS", raising=False)
    with pytest.raises(KeyError):
        config.enablebanking_accounts()


def test_tokens_env_is_optional(monkeypatch):
    monkeypatch.setenv("ENABLEBANKING_ACCOUNTS", ACCOUNTS_JSON)
    monkeypatch.delenv("ENABLEBANKING_TOKENS", raising=False)
    assert config.enablebanking_tokens() == []


def test_tokens_env_empty_string_means_no_tokens(monkeypatch):
    # the token Secret may be absent (renewal-owned, spec 005 §4.2.1): the env var
    # then resolves empty and must not crash config parsing
    monkeypatch.setenv("ENABLEBANKING_ACCOUNTS", ACCOUNTS_JSON)
    monkeypatch.setenv("ENABLEBANKING_TOKENS", "")
    assert config.enablebanking_tokens() == []


def test_tokens_are_parsed_with_utc_expiry(monkeypatch):
    monkeypatch.setenv("ENABLEBANKING_TOKENS", TOKENS_JSON)
    tokens = config.enablebanking_tokens()
    assert tokens[0].alias == "sample_account"
    assert tokens[0].uid == "00000000-0000-0000-0000-000000000001"
    assert tokens[0].valid_until is not None
    assert tokens[0].valid_until.year == 2027


def test_provider_composes_both_secret_halves(monkeypatch):
    monkeypatch.setenv("ENABLEBANKING_ACCOUNTS", ACCOUNTS_JSON)
    monkeypatch.setenv("ENABLEBANKING_TOKENS", TOKENS_JSON)
    monkeypatch.setenv("ENABLEBANKING_PRIVATE_KEY", "fake-pem")
    provider = config.enablebanking_provider()
    assert list(provider.accounts) == ["sample_account"]
    assert provider.tokens["sample_account"].uid == "00000000-0000-0000-0000-000000000001"


def test_fetch_strategy_defaults_to_default(monkeypatch):
    monkeypatch.delenv("FINANCE_FETCH_STRATEGY", raising=False)
    assert config.fetch_strategy() == "default"


def test_fetch_strategy_can_be_overridden(monkeypatch):
    monkeypatch.setenv("FINANCE_FETCH_STRATEGY", "longest")
    assert config.fetch_strategy() == "longest"
