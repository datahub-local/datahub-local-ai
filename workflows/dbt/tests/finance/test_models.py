"""Inspect finance model SQL for correct refs, sources and derived columns."""
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.parent / "projects" / "finance"
MODELS_DIR = PROJECT_DIR / "models"


class TestSilverTransactions:
    def setup_method(self):
        self.sql = (MODELS_DIR / "silver" / "transactions.sql").read_text()

    def test_reads_from_bronze_source(self):
        assert "source('finance', 'raw_transactions')" in self.sql

    def test_joins_accounts_for_the_masked_iban(self):
        assert "ref('accounts')" in self.sql
        assert "iban_masked" in self.sql

    def test_derives_direction_from_the_sign(self):
        assert "direction" in self.sql
        assert "outflow" in self.sql

    def test_cleans_the_payee_join_key(self):
        assert "payee_clean" in self.sql
        assert "finance_clean_key" in self.sql

    def test_extracts_the_card_merchant_before_falling_back(self):
        # without this the key would carry the date and card digits, fragmenting a
        # merchant into one key per transaction and defeating the enrich reuse
        assert "COMPRA EN (.*?), CON LA TARJETA" in self.sql
        assert "regexp_extract" in self.sql

    def test_casts_dates_and_amounts(self):
        assert "CAST(t.booking_date AS DATE)" in self.sql
        assert "DECIMAL(18, 2)" in self.sql


class TestSilverAccounts:
    def setup_method(self):
        self.sql = (MODELS_DIR / "silver" / "accounts.sql").read_text()

    def test_reads_from_bronze_source(self):
        assert "source('finance', 'raw_accounts')" in self.sql

    def test_masks_the_iban(self):
        assert "'****'" in self.sql
        assert "iban_masked" in self.sql

    def test_keeps_only_the_latest_snapshot(self):
        assert "ROW_NUMBER()" in self.sql
        assert "snapshot_rank = 1" in self.sql


class TestSilverBalances:
    def setup_method(self):
        self.sql = (MODELS_DIR / "silver" / "balances.sql").read_text()

    def test_reads_from_bronze_source(self):
        assert "source('finance', 'raw_balances')" in self.sql

    def test_falls_back_to_the_ingestion_date(self):
        assert "finance_iso_date" in self.sql
        assert "TRY_CAST(reference_date AS DATE)" in self.sql

    def test_balance_type_is_part_of_the_key(self):
        assert "PARTITION BY account_id, balance_date, balance_type" in self.sql


class TestGoldMonthlyCategorySpend:
    def setup_method(self):
        self.sql = (MODELS_DIR / "gold" / "monthly_category_spend.sql").read_text()

    def test_joins_transactions_to_the_enrich_source(self):
        assert "ref('transactions')" in self.sql
        assert "source('finance_enrich', 'merchant_categories')" in self.sql

    def test_keeps_an_uncategorised_sentinel(self):
        assert "UNCATEGORISED" in self.sql

    def test_amounts_are_positive_magnitudes_split_by_direction(self):
        assert "SUM(ABS(t.amount))" in self.sql
        assert "direction" in self.sql

    def test_dedupes_the_append_mode_categories(self):
        assert "max_by(category, categorized_at)" in self.sql


class TestGoldAccountBalanceSeries:
    def setup_method(self):
        self.sql = (MODELS_DIR / "gold" / "account_balance_series.sql").read_text()

    def test_joins_balances_to_accounts(self):
        assert "ref('balances')" in self.sql
        assert "ref('accounts')" in self.sql

    def test_labels_rows_with_masked_iban_and_institution(self):
        assert "iban_masked" in self.sql
        assert "institution_id" in self.sql
