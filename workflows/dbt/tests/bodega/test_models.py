"""Inspect bodega model SQL for correct refs, sources, and key columns."""
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.parent / "projects" / "bodega"
MODELS_DIR  = PROJECT_DIR / "models"


class TestSilverInvoices:
    def setup_method(self):
        self.sql = (MODELS_DIR / "silver" / "invoices.sql").read_text()

    def test_reads_from_bronze_source(self):
        assert "source('bodega', 'raw_invoices')" in self.sql

    def test_parses_invoice_date(self):
        assert "bodega_parse_dt" in self.sql
        assert "invoice_date" in self.sql

    def test_exposes_time_dimensions(self):
        lower = self.sql.lower()
        for col in ("invoice_year", "invoice_month", "invoice_week"):
            assert col in lower, f"missing column {col}"

    def test_computes_tax_amounts_from_json(self):
        assert "taxes_json" in self.sql
        assert "total_tax_amount" in self.sql
        assert "total_base_amount" in self.sql

    def test_exposes_item_count(self):
        assert "item_count" in self.sql
        assert "bodega_json_len" in self.sql


class TestSilverInvoiceItems:
    def setup_method(self):
        self.sql = (MODELS_DIR / "silver" / "invoice_items.sql").read_text()

    def test_reads_from_bronze_source(self):
        assert "source('bodega', 'raw_invoices')" in self.sql

    def test_unnests_items_json(self):
        assert "items_json" in self.sql
        assert "bodega_explode_json" in self.sql
        assert "_it.pos" in self.sql

    def test_extracts_item_fields(self):
        lower = self.sql.lower()
        for col in ("description_raw", "description_clean", "quantity", "unit", "unit_price", "total_amount"):
            assert col in lower, f"missing column {col}"

    def test_derives_kg_vs_ea_unit(self):
        assert "KG" in self.sql
        assert "EA" in self.sql
        assert "FLOOR" in self.sql


class TestSilverInvoiceTaxes:
    def setup_method(self):
        self.sql = (MODELS_DIR / "silver" / "invoice_taxes.sql").read_text()

    def test_reads_from_bronze_source(self):
        assert "source('bodega', 'raw_invoices')" in self.sql

    def test_unnests_taxes_json(self):
        assert "taxes_json" in self.sql
        assert "bodega_explode_json" in self.sql

    def test_extracts_tax_fields(self):
        lower = self.sql.lower()
        for col in ("tax_rate", "base_amount", "tax_amount"):
            assert col in lower, f"missing column {col}"


class TestSilverStores:
    def setup_method(self):
        self.sql = (MODELS_DIR / "silver" / "stores.sql").read_text()

    def test_reads_from_bronze_source(self):
        assert "source('bodega', 'raw_invoices')" in self.sql

    def test_groups_by_vat_id(self):
        assert "store_vat_id" in self.sql
        assert "GROUP BY" in self.sql.upper()

    def test_exposes_first_and_last_seen(self):
        lower = self.sql.lower()
        assert "first_seen_date" in lower
        assert "last_seen_date" in lower


class TestGoldSpendingByDay:
    def setup_method(self):
        self.sql = (MODELS_DIR / "gold" / "spending_by_day.sql").read_text()

    def test_refs_invoices(self):
        assert "ref('invoices')" in self.sql

    def test_exposes_key_metrics(self):
        lower = self.sql.lower()
        for col in ("invoice_count", "total_amount", "total_tax", "total_items", "avg_basket_amount"):
            assert col in lower, f"missing column {col}"


class TestGoldSpendingByWeek:
    def setup_method(self):
        self.sql = (MODELS_DIR / "gold" / "spending_by_week.sql").read_text()

    def test_refs_invoices(self):
        assert "ref('invoices')" in self.sql

    def test_uses_week_truncation(self):
        assert "date_trunc" in self.sql
        assert "week" in self.sql
        assert "week_start" in self.sql


class TestGoldTopProducts:
    def setup_method(self):
        self.sql = (MODELS_DIR / "gold" / "top_products.sql").read_text()

    def test_refs_invoice_items(self):
        assert "ref('invoice_items')" in self.sql

    def test_joins_products_source(self):
        assert "source('bodega_enrich', 'products')" in self.sql

    def test_exposes_purchase_and_spend_metrics(self):
        lower = self.sql.lower()
        for col in ("purchase_count", "total_spent", "avg_unit_price"):
            assert col in lower, f"missing column {col}"


class TestGoldPriceTrends:
    def setup_method(self):
        self.sql = (MODELS_DIR / "gold" / "price_trends.sql").read_text()

    def test_refs_invoice_items(self):
        assert "ref('invoice_items')" in self.sql

    def test_joins_products_source(self):
        assert "source('bodega_enrich', 'products')" in self.sql

    def test_filters_to_repeat_products(self):
        assert "HAVING" in self.sql.upper()
        assert ">= 2" in self.sql


class TestGoldCategorySpending:
    def setup_method(self):
        self.sql = (MODELS_DIR / "gold" / "category_spending.sql").read_text()

    def test_refs_invoice_items(self):
        assert "ref('invoice_items')" in self.sql

    def test_joins_products_source(self):
        assert "source('bodega_enrich', 'products')" in self.sql

    def test_coalesces_category_to_other(self):
        assert "COALESCE" in self.sql
        assert "'OTHER'" in self.sql

    def test_exposes_time_granularities(self):
        assert "week_start" in self.sql
        assert "month_start" in self.sql


class TestGoldTaxSummary:
    def setup_method(self):
        self.sql = (MODELS_DIR / "gold" / "tax_summary.sql").read_text()

    def test_refs_invoice_taxes(self):
        assert "ref('invoice_taxes')" in self.sql

    def test_truncates_to_month(self):
        assert "date_trunc" in self.sql
        assert "month_start" in self.sql

    def test_sums_tax_components(self):
        lower = self.sql.lower()
        assert "base_amount" in lower
        assert "tax_amount" in lower


class TestAddressParsing:
    """The address regex, executed rather than pattern-matched.

    The pattern is extracted from the macro so the test cannot drift from what the
    models actually run. It is asserted on DuckDB; Trino agrees on every case here,
    except that a non-match yields NULL there and '' on DuckDB — which is why the
    models wrap it in `bodega_blank_to_null`.
    """

    def setup_method(self):
        import re

        macro = (PROJECT_DIR / "macros" / "cross_engine.sql").read_text()
        patterns = re.findall(r"regexp_extract\(\{\{ col \}\}, '([^']+)'", macro)
        assert len(set(patterns)) == 1, f"dialects disagree on the pattern: {set(patterns)}"
        self.pattern = patterns[0]

    def _parse(self, address: str) -> tuple[str, str]:
        """(postal_code, town) as the models compute them, '' when unparsed."""
        import duckdb

        con = duckdb.connect()
        cp1, cp2, town = con.execute(
            "SELECT regexp_extract(?, ?, 1), regexp_extract(?, ?, 2), "
            "trim(regexp_extract(?, ?, 3))",
            [address, self.pattern] * 3,
        ).fetchone()
        con.close()
        return (cp1 + cp2 if cp1 else ""), town

    def test_parses_the_documented_address_shape(self):
        assert self._parse("C/ TEST 1, 28001 MADRID") == ("28001", "MADRID")

    def test_parses_a_no_comma_sin_numero_address(self):
        assert self._parse("C/ MAYOR S/N 28522 RIVAS-VACIAMADRID") == (
            "28522", "RIVAS-VACIAMADRID",
        )

    def test_postal_code_wins_over_an_earlier_five_digit_house_number(self):
        # The pattern is tail-anchored for exactly this: the parser prints the
        # postal code last, so a leading match would take the wrong number.
        assert self._parse("C/ GRAN VIA 28001, 03700 DENIA") == ("03700", "DENIA")

    def test_drops_a_trailing_country(self):
        assert self._parse("PLAZA MAYOR 12, 28001 MADRID, ESPANA") == ("28001", "MADRID")

    def test_unparseable_addresses_yield_nothing(self):
        # No postal code at all, a phone fragment, and an out-of-range province
        # code — each must fall through to the models' UNKNOWN sentinel.
        for address in ("Calle Mayor, 1", "C/ TEST 1, 91757 8853", "POLIGONO 45, 99999 NOWHERE"):
            assert self._parse(address) == ("", ""), address

    def test_province_code_bounds_are_the_ine_range(self):
        assert self._parse("C/ X 1, 01001 VITORIA") == ("01001", "VITORIA")
        assert self._parse("C/ X 1, 52001 MELILLA") == ("52001", "MELILLA")
        assert self._parse("C/ X 1, 53001 NOWHERE") == ("", "")


class TestProvinceList:
    def setup_method(self):
        import re

        macro = (PROJECT_DIR / "macros" / "cross_engine.sql").read_text()
        body = macro.split("macro bodega_provinces()")[1]
        self.rows = re.findall(r"\('(\d{2})', '([^']+)'\)", body)

    def test_covers_every_ine_province_code(self):
        assert [code for code, _ in self.rows] == [f"{n:02d}" for n in range(1, 53)]

    def test_names_are_unique(self):
        names = [name for _, name in self.rows]
        assert len(set(names)) == len(names)
