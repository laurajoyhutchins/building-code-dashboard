"""
AHJ Registry — Test Suite
==========================
Tests for schema integrity, parser correctness, and data quality.

Run:
  python -m tests.test_suite
  python -m tests.test_suite --verbose
"""

import sys
import json
import pathlib
import sqlite3
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db.schema import init_db, DB_PATH


class TestSchema(unittest.TestCase):
    """Test database schema creation and constraints."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = pathlib.Path(self.tmp.name)
        self.conn = init_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.db_path.unlink(missing_ok=True)

    def test_tables_created(self):
        tables = {row[0] for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        required = {"jurisdictions", "code_adoptions", "amendments",
                    "source_urls", "ingest_runs"}
        self.assertTrue(required.issubset(tables), f"Missing tables: {required - tables}")

    def test_insert_state_jurisdiction(self):
        self.conn.execute("""
            INSERT INTO jurisdictions
                (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
            VALUES ('CA', 'California', 'California', 'state')
        """)
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM jurisdictions WHERE state_abbr='CA'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["jurisdiction_type"], "state")

    def test_insert_city_jurisdiction(self):
        self.conn.execute("""
            INSERT INTO jurisdictions
                (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
            VALUES ('CA', 'California', 'Los Angeles', 'city')
        """)
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM jurisdictions WHERE jurisdiction_name='Los Angeles'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_invalid_jurisdiction_type_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("""
                INSERT INTO jurisdictions
                    (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
                VALUES ('CA', 'California', 'Test', 'invalid_type')
            """)
            self.conn.commit()

    def test_code_adoption_foreign_key(self):
        """Code adoption without a valid jurisdiction should fail."""
        with self.assertRaises((sqlite3.IntegrityError, sqlite3.OperationalError)):
            self.conn.execute("""
                INSERT INTO code_adoptions
                    (jurisdiction_id, code_key, code_full_name, publishing_org,
                     edition_year, status)
                VALUES (99999, 'IBC', 'International Building Code', 'ICC', 2021, 'adopted')
            """)
            self.conn.commit()

    def test_invalid_adoption_status_rejected(self):
        self.conn.execute("""
            INSERT INTO jurisdictions
                (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
            VALUES ('TX', 'Texas', 'Texas', 'state')
        """)
        self.conn.commit()
        jur_id = self.conn.execute(
            "SELECT id FROM jurisdictions WHERE state_abbr='TX'"
        ).fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("""
                INSERT INTO code_adoptions
                    (jurisdiction_id, code_key, code_full_name, publishing_org,
                     edition_year, status)
                VALUES (?, 'IBC', 'International Building Code', 'ICC', 2021, 'invalid_status')
            """, (jur_id,))
            self.conn.commit()

    def test_duplicate_adoption_upsert(self):
        """ON CONFLICT should update, not error."""
        self.conn.execute("""
            INSERT INTO jurisdictions
                (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
            VALUES ('CO', 'Colorado', 'Colorado', 'state')
        """)
        self.conn.commit()
        jur_id = self.conn.execute(
            "SELECT id FROM jurisdictions WHERE state_abbr='CO'"
        ).fetchone()[0]

        # First insert
        self.conn.execute("""
            INSERT INTO code_adoptions
                (jurisdiction_id, code_key, code_full_name, publishing_org,
                 edition_year, status)
            VALUES (?, 'IBC', 'International Building Code', 'ICC', 2021, 'adopted')
        """, (jur_id,))
        self.conn.commit()

        # Upsert same record
        self.conn.execute("""
            INSERT INTO code_adoptions
                (jurisdiction_id, code_key, code_full_name, publishing_org,
                 edition_year, status)
            VALUES (?, 'IBC', 'International Building Code', 'ICC', 2021, 'adopted')
            ON CONFLICT(jurisdiction_id, code_key, edition_year, status)
            DO UPDATE SET updated_at=datetime('now')
        """, (jur_id,))
        self.conn.commit()

        count = self.conn.execute(
            "SELECT COUNT(*) FROM code_adoptions WHERE jurisdiction_id=? AND code_key='IBC'",
            (jur_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1, "Upsert should not duplicate records")

    def test_fts_search(self):
        self.conn.execute("""
            INSERT INTO jurisdictions
                (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
            VALUES ('NY', 'New York', 'New York City', 'city')
        """)
        self.conn.commit()
        results = self.conn.execute("""
            SELECT rowid FROM fts_jurisdictions WHERE fts_jurisdictions MATCH 'New York'
        """).fetchall()
        self.assertGreater(len(results), 0, "FTS should find 'New York City'")


class TestICCParser(unittest.TestCase):
    """Test ICC chart parsing logic."""

    def setUp(self):
        # Import inline to avoid circular dependency
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
        from scrapers.icc_chart_parser import parse_cell_value, STATE_ABBR_MAP
        self.parse_cell_value = parse_cell_value
        self.STATE_ABBR_MAP = STATE_ABBR_MAP

    def test_parse_adopted_21(self):
        year, status = self.parse_cell_value("21")
        self.assertEqual(year, 2021)
        self.assertEqual(status, "adopted")

    def test_parse_adopted_18(self):
        year, status = self.parse_cell_value("18")
        self.assertEqual(year, 2018)
        self.assertEqual(status, "adopted")

    def test_parse_stretch_code(self):
        year, status = self.parse_cell_value("(21)")
        self.assertEqual(year, 2021)
        self.assertEqual(status, "adopted_stretch")

    def test_parse_local_only(self):
        year, status = self.parse_cell_value("X")
        self.assertIsNone(year)
        self.assertEqual(status, "local_only")

    def test_parse_not_adopted_empty(self):
        year, status = self.parse_cell_value("")
        self.assertIsNone(year)
        self.assertEqual(status, "not_adopted")

    def test_parse_not_adopted_none(self):
        year, status = self.parse_cell_value(None)
        self.assertIsNone(year)
        self.assertEqual(status, "not_adopted")

    def test_parse_old_edition(self):
        year, status = self.parse_cell_value("09")
        self.assertEqual(year, 2009)
        self.assertEqual(status, "adopted")

    def test_parse_2000_edition(self):
        year, status = self.parse_cell_value("00")
        self.assertEqual(year, 2000)
        self.assertEqual(status, "adopted")

    def test_parse_ashrae_reference(self):
        year, status = self.parse_cell_value("90.1-2019")
        self.assertEqual(year, 2019)
        self.assertEqual(status, "adopted")

    def test_all_50_states_in_map(self):
        self.assertIn("Alabama", self.STATE_ABBR_MAP)
        self.assertIn("Wyoming", self.STATE_ABBR_MAP)
        self.assertEqual(self.STATE_ABBR_MAP["California"], "CA")
        self.assertEqual(self.STATE_ABBR_MAP["Texas"], "TX")


class TestTextExtraction(unittest.TestCase):
    """Test code adoption extraction from ordinance text."""

    def setUp(self):
        from scrapers.municipal_scraper import (
            extract_adoptions_from_text,
            extract_amendments_from_text,
            extract_ordinance_metadata,
        )
        self.extract_adoptions    = extract_adoptions_from_text
        self.extract_amendments   = extract_amendments_from_text
        self.extract_ordinance    = extract_ordinance_metadata

    def test_extract_ibc_from_ordinance(self):
        text = """
        The City hereby adopts the International Building Code, 2021 Edition,
        as published by the International Code Council, as the building code
        for all construction within city limits.
        """
        adoptions = self.extract_adoptions(text)
        ibc = next((a for a in adoptions if a["code_key"] == "IBC"), None)
        self.assertIsNotNone(ibc, "Should find IBC adoption")
        self.assertEqual(ibc["edition_year"], 2021)

    def test_extract_multiple_codes(self):
        text = """
        The following codes are hereby adopted:
        (a) International Building Code 2021 Edition
        (b) International Fire Code, 2021 Edition
        (c) National Electrical Code 2020
        (d) International Residential Code, 2021 Edition
        """
        adoptions = self.extract_adoptions(text)
        code_keys = {a["code_key"] for a in adoptions}
        self.assertIn("IBC", code_keys)
        self.assertIn("IFC", code_keys)
        self.assertIn("NEC", code_keys)
        self.assertIn("IRC", code_keys)

    def test_extract_nfpa_70(self):
        text = "The City adopts NFPA 70, 2020 Edition, as the electrical code."
        adoptions = self.extract_adoptions(text)
        nec = next((a for a in adoptions if a["code_key"] == "NEC"), None)
        self.assertIsNotNone(nec)
        self.assertEqual(nec["edition_year"], 2020)

    def test_extract_ordinance_metadata(self):
        text = "Ordinance No. 2023-45, passed January 15, 2023"
        meta = self.extract_ordinance(text)
        self.assertEqual(meta.get("ordinance_number"), "2023-45")

    def test_empty_text(self):
        adoptions = self.extract_adoptions("")
        self.assertEqual(adoptions, [])

    def test_no_false_positives_on_unrelated_text(self):
        text = "The City Council discussed the budget for fiscal year 2023."
        adoptions = self.extract_adoptions(text)
        # "2023" alone shouldn't trigger code detection without code name
        ibc = next((a for a in adoptions if a["code_key"] == "IBC"), None)
        self.assertIsNone(ibc, "Should not false-positive on year without code name")


class TestExportJSON(unittest.TestCase):
    """Test JSON export functionality."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = pathlib.Path(self.tmp.name)
        self.conn = init_db(self.db_path)
        self._seed_test_data()

    def tearDown(self):
        self.conn.close()
        self.db_path.unlink(missing_ok=True)

    def _seed_test_data(self):
        """Insert minimal test data."""
        self.conn.execute("""
            INSERT INTO jurisdictions
                (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
            VALUES ('WA', 'Washington', 'Washington', 'state')
        """)
        self.conn.execute("""
            INSERT INTO jurisdictions
                (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
            VALUES ('WA', 'Washington', 'Seattle', 'city')
        """)
        self.conn.commit()

        wa_id = self.conn.execute(
            "SELECT id FROM jurisdictions WHERE state_abbr='WA' AND jurisdiction_type='state'"
        ).fetchone()[0]
        sea_id = self.conn.execute(
            "SELECT id FROM jurisdictions WHERE jurisdiction_name='Seattle'"
        ).fetchone()[0]

        for jid, code, year in [(wa_id, "IBC", 2021), (wa_id, "NEC", 2023),
                                  (sea_id, "IBC", 2021), (sea_id, "IFC", 2021)]:
            self.conn.execute("""
                INSERT INTO code_adoptions
                    (jurisdiction_id, code_key, code_full_name, publishing_org,
                     edition_year, status)
                VALUES (?, ?, 'Test Code', 'ICC', ?, 'adopted')
            """, (jid, code, year))
        self.conn.commit()

    def test_export_creates_valid_json(self):
        from orchestrator import export_to_json
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = pathlib.Path(f.name)
        try:
            result = export_to_json(self.db_path, out_path)
            self.assertEqual(result["status"], "success")
            data = json.loads(out_path.read_text())
            self.assertIn("meta", data)
            self.assertIn("jurisdictions", data)
            self.assertIn("WA", data["jurisdictions"])
            wa = data["jurisdictions"]["WA"]
            self.assertIn("IBC", wa["adopted"])
            self.assertIn("NEC", wa["adopted"])
            self.assertIn("Seattle", wa["cities"])
        finally:
            out_path.unlink(missing_ok=True)

    def test_export_state_adoption_structure(self):
        from orchestrator import export_to_json
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = pathlib.Path(f.name)
        try:
            export_to_json(self.db_path, out_path)
            data = json.loads(out_path.read_text())
            ibc = data["jurisdictions"]["WA"]["adopted"]["IBC"]
            self.assertEqual(ibc["year"], 2021)
            self.assertEqual(ibc["status"], "adopted")
            self.assertIn("amendments", ibc)
        finally:
            out_path.unlink(missing_ok=True)


class TestDataQuality(unittest.TestCase):
    """Test data quality checks on real fallback data."""

    def test_nec_fallback_all_states_have_abbr(self):
        from scrapers.nec_scraper import NEC_FALLBACK
        missing = [r["state"] for r in NEC_FALLBACK if not r.get("abbr")]
        self.assertEqual(missing, [], f"NEC records missing abbr: {missing}")

    def test_nec_fallback_valid_edition_years(self):
        from scrapers.nec_scraper import NEC_FALLBACK
        for rec in NEC_FALLBACK:
            if rec.get("edition"):
                self.assertIn(rec["edition"], [2008, 2011, 2014, 2017, 2020, 2023],
                              f"Unexpected NEC edition in {rec['state']}: {rec['edition']}")

    def test_iecc_fallback_residential_years(self):
        from scrapers.iecc_scraper import IECC_FALLBACK
        for rec in IECC_FALLBACK:
            if rec.get("res"):
                self.assertGreaterEqual(rec["res"], 2000)
                self.assertLessEqual(rec["res"], 2030)

    def test_icc_column_count(self):
        from scrapers.icc_chart_parser import ICC_COLUMNS
        self.assertEqual(len(ICC_COLUMNS), 17, "ICC chart should have 17 code columns")

    def test_icc_code_meta_coverage(self):
        from scrapers.icc_chart_parser import ICC_COLUMNS, ICC_CODE_META
        for col in ICC_COLUMNS:
            self.assertIn(col, ICC_CODE_META, f"Missing meta for ICC column: {col}")

    def test_detection_patterns_compile(self):
        from scrapers.municipal_scraper import CODE_DETECTION_PATTERNS
        # Verify all patterns actually match what they should
        test_cases = {
            "IBC":  "adopts the International Building Code 2021 Edition",
            "IRC":  "International Residential Code, 2021",
            "NEC":  "National Electrical Code 2020",
            "IFC":  "International Fire Code 2021",
            "IECC": "International Energy Conservation Code 2021",
        }
        for key, text in test_cases.items():
            pattern = CODE_DETECTION_PATTERNS[key]
            self.assertIsNotNone(pattern.search(text),
                                 f"Pattern for {key} failed to match: {text!r}")


# ── CLI Runner ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Run AHJ Registry test suite")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    verbosity = 2 if args.verbose else 1
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for cls in [TestSchema, TestICCParser, TestTextExtraction, TestExportJSON, TestDataQuality]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
