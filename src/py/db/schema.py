"""
AHJ Code Adoption Registry — Database Schema
SQLite with full-text search and versioned history.

Tables:
  jurisdictions       — Every AHJ: state, county, city, fire district, etc.
  code_adoptions      — One row per (jurisdiction × code_book)
  amendments          — Local amendments attached to a code_adoption
  ingest_runs         — Provenance log: what was scraped, when, from where
  source_urls         — Canonical source links per jurisdiction × source
"""

import sqlite3
import pathlib
from datetime import datetime

DB_PATH = pathlib.Path(__file__).parent.parent / "ahj_registry.db"


DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Jurisdictions ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jurisdictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fips_state      TEXT,           -- 2-digit FIPS state code  (e.g. '06' = CA)
    fips_county     TEXT,           -- 5-digit FIPS county code (state+county)
    fips_place      TEXT,           -- 7-digit FIPS place code  (incorporated places)
    state_abbr      TEXT NOT NULL,  -- 'CA', 'TX', etc.
    state_name      TEXT NOT NULL,
    county_name     TEXT,           -- NULL for state-level rows
    jurisdiction_name TEXT NOT NULL,-- Canonical display name
    jurisdiction_type TEXT NOT NULL CHECK(jurisdiction_type IN (
        'state', 'county', 'city', 'town', 'village', 'township',
        'borough', 'fire_district', 'utility_district', 'special_district',
        'tribal', 'territory', 'consolidated_city_county'
    )),
    -- Geographic context
    region          TEXT,           -- 'Northeast', 'Southeast', etc.
    population      INTEGER,        -- Most recent census estimate
    -- Governance flags
    has_own_code    INTEGER DEFAULT 0,  -- 1 = proprietary code (NYC, Chicago, LA)
    home_rule       INTEGER DEFAULT 0,  -- 1 = local adoption authority
    -- Metadata
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    -- Unique constraint: a jurisdiction is uniquely identified by its name+type+state
    UNIQUE(state_abbr, county_name, jurisdiction_name, jurisdiction_type)
);

CREATE INDEX IF NOT EXISTS idx_jur_state   ON jurisdictions(state_abbr);
CREATE INDEX IF NOT EXISTS idx_jur_fips    ON jurisdictions(fips_place);
CREATE INDEX IF NOT EXISTS idx_jur_type    ON jurisdictions(jurisdiction_type);

-- ── Code Adoptions ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS code_adoptions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    jurisdiction_id     INTEGER NOT NULL REFERENCES jurisdictions(id) ON DELETE CASCADE,
    -- Code identification
    code_key            TEXT NOT NULL,  -- 'IBC', 'NEC', 'IFC', 'IECC', 'CBC', etc.
    code_full_name      TEXT NOT NULL,  -- 'International Building Code'
    publishing_org      TEXT NOT NULL,  -- 'ICC', 'NFPA', 'IAPMO', 'CA-BSC', etc.
    -- Edition
    edition_year        INTEGER,        -- 2021, 2018, etc. NULL = no adoption
    edition_label       TEXT,           -- '2021', '9th Ed.', 'Title 24 Pt.2 2022'
    -- Adoption status
    status              TEXT NOT NULL CHECK(status IN (
        'adopted',          -- Code in force as a mandatory minimum
        'adopted_stretch',  -- Adopted as optional/stretch code
        'local_only',       -- Some locals adopted but no statewide standard
        'not_adopted',      -- Never adopted
        'own_code',         -- Jurisdiction uses proprietary code
        'pending',          -- In rulemaking / effective date not yet reached
        'superseded',       -- Replaced by a newer entry
        'withdrawn'         -- Adoption revoked
    )),
    is_mandatory        INTEGER DEFAULT 1,  -- 0 = optional/voluntary
    effective_date      TEXT,               -- ISO-8601 date adopted took effect
    expiry_date         TEXT,               -- If sunset provision exists
    -- Supersession chain
    supersedes_id       INTEGER REFERENCES code_adoptions(id),
    -- Raw source text for audit
    source_text         TEXT,
    -- Provenance
    source_id           INTEGER REFERENCES source_urls(id),
    ingest_run_id       INTEGER REFERENCES ingest_runs(id),
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(jurisdiction_id, code_key, edition_year, status)
);

CREATE INDEX IF NOT EXISTS idx_adopt_jur    ON code_adoptions(jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_adopt_code   ON code_adoptions(code_key);
CREATE INDEX IF NOT EXISTS idx_adopt_year   ON code_adoptions(edition_year);
CREATE INDEX IF NOT EXISTS idx_adopt_status ON code_adoptions(status);

-- ── Amendments ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS amendments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    adoption_id     INTEGER NOT NULL REFERENCES code_adoptions(id) ON DELETE CASCADE,
    -- Classification
    amendment_type  TEXT CHECK(amendment_type IN (
        'addition',     -- New requirement not in base code
        'modification', -- Changed section of base code
        'deletion',     -- Removed section from base code
        'substitution', -- Replaced section with local equivalent
        'clarification',-- Interpretive note
        'exception'     -- Carved-out exception to base code
    )),
    -- Content
    section_ref     TEXT,       -- e.g. 'Section 903.2.1', 'Article 210', 'R301.2'
    title           TEXT,       -- Short descriptive title
    description     TEXT NOT NULL,
    -- Ordinance tracking
    ordinance_number TEXT,
    ordinance_date  TEXT,       -- ISO-8601 when ordinance was passed
    -- Provenance
    source_id       INTEGER REFERENCES source_urls(id),
    ingest_run_id   INTEGER REFERENCES ingest_runs(id),
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_amend_adoption ON amendments(adoption_id);
CREATE INDEX IF NOT EXISTS idx_amend_section  ON amendments(section_ref);

-- ── Source URLs ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS source_urls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    jurisdiction_id INTEGER REFERENCES jurisdictions(id),
    source_type     TEXT NOT NULL CHECK(source_type IN (
        'icc_chart',        -- ICC Master Adoption Chart PDF
        'icc_local_page',   -- ICC per-state local adoption page
        'nfpa_map',         -- NFPA NEC adoption page
        'doe_energy',       -- DOE/PNNL energycodes.gov
        'state_agency',     -- Official state agency site
        'municipal_code',   -- Municode / eCode360 / city website
        'fire_marshal',     -- State/local fire marshal site
        'legislative',      -- State legislature / admin code site
        'nahb',             -- NAHB tracking document
        'manual'            -- Hand-entered / verified by researcher
    )),
    url             TEXT NOT NULL,
    label           TEXT,
    last_fetched    TEXT,
    last_status_code INTEGER,
    content_hash    TEXT,   -- SHA-256 of fetched content for change detection
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(jurisdiction_id, source_type, url)
);

-- ── Ingest Runs ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingest_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL UNIQUE,   -- UUID
    scraper_name    TEXT NOT NULL,          -- 'icc_chart_parser', 'nfpa_scraper', etc.
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT CHECK(status IN ('running','success','partial','failed')),
    rows_inserted   INTEGER DEFAULT 0,
    rows_updated    INTEGER DEFAULT 0,
    rows_skipped    INTEGER DEFAULT 0,
    errors          TEXT,   -- JSON array of error messages
    notes           TEXT
);

-- ── Full-text search virtual table ─────────────────────────────────────────
CREATE VIRTUAL TABLE IF NOT EXISTS fts_jurisdictions USING fts5(
    jurisdiction_name,
    county_name,
    state_name,
    state_abbr,
    content='jurisdictions',
    content_rowid='id'
);

-- Trigger to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS jur_ai AFTER INSERT ON jurisdictions BEGIN
    INSERT INTO fts_jurisdictions(rowid, jurisdiction_name, county_name, state_name, state_abbr)
    VALUES (new.id, new.jurisdiction_name, new.county_name, new.state_name, new.state_abbr);
END;
CREATE TRIGGER IF NOT EXISTS jur_au AFTER UPDATE ON jurisdictions BEGIN
    INSERT INTO fts_jurisdictions(fts_jurisdictions, rowid, jurisdiction_name, county_name, state_name, state_abbr)
    VALUES ('delete', old.id, old.jurisdiction_name, old.county_name, old.state_name, old.state_abbr);
    INSERT INTO fts_jurisdictions(rowid, jurisdiction_name, county_name, state_name, state_abbr)
    VALUES (new.id, new.jurisdiction_name, new.county_name, new.state_name, new.state_abbr);
END;
"""


def get_connection(db_path: pathlib.Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: pathlib.Path = DB_PATH) -> sqlite3.Connection:
    """Create all tables if they don't exist. Idempotent."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(DDL)
    conn.commit()
    print(f"[schema] Database initialized at {db_path}")
    return conn


if __name__ == "__main__":
    init_db()
