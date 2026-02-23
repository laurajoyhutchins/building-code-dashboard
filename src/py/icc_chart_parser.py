"""
ICC Master I-Code Adoption Chart Parser
=======================================
Source: https://www.iccsafe.org/wp-content/uploads/Master-I-Code-Adoption-Chart.pdf
        (ICC updates this PDF ~monthly; MiTek mirrors at a stable URL)

What it does:
  1. Downloads the PDF from the canonical ICC/mirror URL
  2. Parses the tabular data with pdfplumber
  3. Maps each state row → multiple code_adoption records
  4. Upserts into the database

Column legend (from ICC PDF):
  IBC IRC IFC IMC IPC IPSDC IFGC IgCC IECC-R IECC-C IPMC IEBC ISPSC ICCPC IWUIC IZC ICC700
  Values: '21' = 2021 ed mandatory, 'X' = locally adopted but not statewide mandatory,
          '(21)' = stretch code, blank = not adopted

Run:
  python -m scrapers.icc_chart_parser
  python -m scrapers.icc_chart_parser --db /path/to/ahj_registry.db --url https://...
"""

import re
import sys
import json
import hashlib
import pathlib
import argparse
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, date
from typing import Optional

# Add parent to path when run as script
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db.schema import init_db, get_connection, DB_PATH

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber required: pip install pdfplumber")


# ── Constants ─────────────────────────────────────────────────────────────────

# ICC canonical URL (updates monthly) — MiTek mirror is usually stable
PDF_URLS = [
    "https://www.iccsafe.org/wp-content/uploads/Master-I-Code-Adoption-Chart.pdf",
    "https://www.mitek-us.com/wp-content/uploads/2025/08/Master-I-Code-Adoption-Chart.pdf",
]

# Column order in the ICC PDF (as of 2024–2025 editions)
ICC_COLUMNS = [
    "IBC", "IRC", "IFC", "IMC", "IPC", "IPSDC", "IFGC",
    "IgCC", "IECC-R", "IECC-C", "IPMC", "IEBC", "ISPSC",
    "ICCPC", "IWUIC", "IZC", "ICC700",
]

ICC_CODE_META = {
    "IBC":    ("International Building Code",             "ICC"),
    "IRC":    ("International Residential Code",          "ICC"),
    "IFC":    ("International Fire Code",                 "ICC"),
    "IMC":    ("International Mechanical Code",           "ICC"),
    "IPC":    ("International Plumbing Code",             "ICC"),
    "IPSDC":  ("Int'l Private Sewage Disposal Code",      "ICC"),
    "IFGC":   ("International Fuel Gas Code",             "ICC"),
    "IgCC":   ("International Green Construction Code",   "ICC"),
    "IECC-R": ("Int'l Energy Conservation Code (Res.)",   "ICC"),
    "IECC-C": ("Int'l Energy Conservation Code (Comm.)",  "ICC"),
    "IPMC":   ("Int'l Property Maintenance Code",         "ICC"),
    "IEBC":   ("Int'l Existing Building Code",            "ICC"),
    "ISPSC":  ("Int'l Swimming Pool & Spa Code",          "ICC"),
    "ICCPC":  ("Int'l Code Council Performance Code",     "ICC"),
    "IWUIC":  ("Int'l Wildland-Urban Interface Code",     "ICC"),
    "IZC":    ("International Zoning Code",               "ICC"),
    "ICC700": ("ICC 700 National Green Building Standard","ICC"),
}

STATE_ABBR_MAP = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "Guam": "GU", "Puerto Rico": "PR",
    "U.S. Virgin Islands": "VI", "American Samoa": "AS", "Northern Mariana Islands": "MP",
}


# ── PDF Download ─────────────────────────────────────────────────────────────

def download_pdf(urls: list[str], dest: pathlib.Path) -> Optional[pathlib.Path]:
    """Try each URL in order; return path to saved file or None."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AHJ-Registry-Ingest/1.0; "
            "+https://github.com/youroreg/ahj-registry)"
        )
    }
    for url in urls:
        try:
            print(f"[icc_chart] Downloading {url}")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            dest.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()[:12]
            print(f"[icc_chart] Saved {len(data):,} bytes (sha256 prefix: {sha})")
            return dest
        except urllib.error.URLError as e:
            print(f"[icc_chart] WARN: Could not fetch {url}: {e}")
    return None


# ── PDF Parsing ──────────────────────────────────────────────────────────────

def parse_cell_value(raw: str) -> tuple[Optional[int], str]:
    """
    Parse a cell from the ICC chart.
    Returns (edition_year_int_or_None, status_string)

    Examples:
      '21'   → (2021, 'adopted')
      'X'    → (None, 'local_only')
      '(21)' → (2021, 'adopted_stretch')
      '18'   → (2018, 'adopted')
      ''     → (None, 'not_adopted')
      '09'   → (2009, 'adopted')
      '90.1-2019' → (2019, 'adopted')   # ASHRAE reference
    """
    raw = (raw or "").strip()
    if not raw:
        return None, "not_adopted"

    # Stretch / optional codes in parentheses
    stretch = raw.startswith("(") and raw.endswith(")")
    inner = raw.strip("()")

    if inner.upper() == "X":
        return None, "local_only"

    # ASHRAE references like '90.1-2019'
    ashrae_match = re.search(r"90\.1[-–](\d{4})", inner)
    if ashrae_match:
        yr = int(ashrae_match.group(1))
        return yr, "adopted_stretch" if stretch else "adopted"

    # Two-digit year shorthand: '21' → 2021, '09' → 2009, '00' → 2000
    two_digit = re.fullmatch(r"(\d{2})", inner)
    if two_digit:
        yy = int(two_digit.group(1))
        yr = 2000 + yy if yy < 100 else yy
        # Sanity-check: ICC codes started in 2000
        if 2000 <= yr <= 2035:
            return yr, "adopted_stretch" if stretch else "adopted"

    # Four-digit year
    four_digit = re.fullmatch(r"(\d{4})", inner)
    if four_digit:
        yr = int(four_digit.group(1))
        return yr, "adopted_stretch" if stretch else "adopted"

    # Unparseable but not empty — treat as local_only marker
    return None, "local_only"


def extract_rows_from_pdf(pdf_path: pathlib.Path) -> list[dict]:
    """
    Extract structured rows from ICC adoption chart PDF.
    Returns list of dicts: {state_name, IBC, IRC, ...}
    """
    rows = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables({
                "vertical_strategy":   "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance":      5,
                "join_tolerance":      3,
            })
            if not tables:
                # Fallback: text-based extraction
                tables = page.extract_tables()

            for table in tables:
                for row in table:
                    if not row or not row[0]:
                        continue
                    first_cell = str(row[0]).strip()
                    if first_cell in STATE_ABBR_MAP or first_cell == "State":
                        # Header row — skip
                        if first_cell == "State":
                            continue
                        # Data row: pad to at least 18 cells
                        cells = [str(c or "").strip() for c in row]
                        while len(cells) < 18:
                            cells.append("")
                        record = {"state_name": first_cell}
                        for i, col in enumerate(ICC_COLUMNS):
                            record[col] = cells[i + 1] if i + 1 < len(cells) else ""
                        rows.append(record)

    # Deduplicate by state name (keep last occurrence per page)
    seen = {}
    for r in rows:
        seen[r["state_name"]] = r
    return list(seen.values())


def parse_pdf_text_fallback(pdf_path: pathlib.Path) -> list[dict]:
    """
    Text-extraction fallback when table detection fails.
    Reads lines and matches state names at line start.
    """
    rows = []
    current_state = None
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                # Check if line starts with a known state name
                for state_name in STATE_ABBR_MAP:
                    if line.startswith(state_name):
                        remainder = line[len(state_name):].strip()
                        tokens = remainder.split()
                        record = {"state_name": state_name}
                        for i, col in enumerate(ICC_COLUMNS):
                            record[col] = tokens[i] if i < len(tokens) else ""
                        rows.append(record)
                        break
    # Deduplicate
    seen = {}
    for r in rows:
        seen[r["state_name"]] = r
    return list(seen.values())


# ── Database Upsert ──────────────────────────────────────────────────────────

def upsert_state_jurisdiction(conn: sqlite3.Connection, state_name: str, state_abbr: str) -> int:
    """Ensure state-level jurisdiction row exists; return its id."""
    cur = conn.execute("""
        INSERT INTO jurisdictions
            (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
        VALUES (?, ?, ?, 'state')
        ON CONFLICT(state_abbr, county_name, jurisdiction_name, jurisdiction_type)
        DO UPDATE SET updated_at = datetime('now')
        RETURNING id
    """, (state_abbr, state_name, state_name))
    row = cur.fetchone()
    if row:
        return row[0]
    # Already existed — fetch
    cur = conn.execute("""
        SELECT id FROM jurisdictions
        WHERE state_abbr = ? AND jurisdiction_type = 'state'
    """, (state_abbr,))
    return cur.fetchone()[0]


def upsert_adoption(
    conn: sqlite3.Connection,
    jurisdiction_id: int,
    code_key: str,
    edition_year: Optional[int],
    status: str,
    ingest_run_id: int,
    source_id: Optional[int] = None,
) -> tuple[int, bool]:
    """
    Upsert a code adoption. Returns (adoption_id, was_inserted).
    On conflict, updates status/edition/updated_at.
    """
    full_name, org = ICC_CODE_META.get(code_key, (code_key, "ICC"))
    cur = conn.execute("""
        INSERT INTO code_adoptions
            (jurisdiction_id, code_key, code_full_name, publishing_org,
             edition_year, edition_label, status, ingest_run_id, source_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(jurisdiction_id, code_key, edition_year, status)
        DO UPDATE SET
            status        = excluded.status,
            updated_at    = datetime('now'),
            ingest_run_id = excluded.ingest_run_id
        RETURNING id
    """, (
        jurisdiction_id, code_key, full_name, org,
        edition_year,
        str(edition_year) if edition_year else None,
        status,
        ingest_run_id,
        source_id,
    ))
    row = cur.fetchone()
    was_inserted = (row is not None)
    if row:
        return row[0], True
    cur = conn.execute("""
        SELECT id FROM code_adoptions
        WHERE jurisdiction_id=? AND code_key=? AND edition_year IS ? AND status=?
    """, (jurisdiction_id, code_key, edition_year, status))
    return cur.fetchone()[0], False


def start_ingest_run(conn: sqlite3.Connection, scraper_name: str) -> int:
    import uuid
    run_id = str(uuid.uuid4())
    cur = conn.execute("""
        INSERT INTO ingest_runs (run_id, scraper_name, started_at, status)
        VALUES (?, ?, datetime('now'), 'running')
        RETURNING id
    """, (run_id, scraper_name))
    conn.commit()
    return cur.fetchone()[0]


def finish_ingest_run(
    conn: sqlite3.Connection,
    run_db_id: int,
    status: str,
    inserted: int,
    updated: int,
    skipped: int,
    errors: list[str],
):
    conn.execute("""
        UPDATE ingest_runs
        SET finished_at  = datetime('now'),
            status       = ?,
            rows_inserted= ?,
            rows_updated = ?,
            rows_skipped = ?,
            errors       = ?
        WHERE id = ?
    """, (status, inserted, updated, skipped, json.dumps(errors), run_db_id))
    conn.commit()


# ── Main Ingestion Logic ─────────────────────────────────────────────────────

def run(
    db_path: pathlib.Path = DB_PATH,
    pdf_source: Optional[pathlib.Path] = None,
    urls: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict:
    """
    Full pipeline:
      1. Download PDF (unless local path provided)
      2. Parse rows
      3. Upsert into DB
    Returns summary dict.
    """
    conn = init_db(db_path)
    run_id = start_ingest_run(conn, "icc_chart_parser")

    errors: list[str] = []
    inserted = updated = skipped = 0

    # ── Step 1: Get PDF ──────────────────────────────────────────────────────
    if pdf_source is None:
        tmp_pdf = pathlib.Path("/tmp/icc_master_adoption_chart.pdf")
        pdf_source = download_pdf(urls or PDF_URLS, tmp_pdf)
        if pdf_source is None:
            msg = "Failed to download ICC chart PDF from all URLs"
            print(f"[icc_chart] ERROR: {msg}")
            finish_ingest_run(conn, run_id, "failed", 0, 0, 0, [msg])
            return {"status": "failed", "errors": [msg]}

    # ── Step 2: Parse PDF ────────────────────────────────────────────────────
    print(f"[icc_chart] Parsing {pdf_source}")
    rows = extract_rows_from_pdf(pdf_source)
    if not rows:
        print("[icc_chart] Table extraction returned no rows; trying text fallback...")
        rows = parse_pdf_text_fallback(pdf_source)

    print(f"[icc_chart] Extracted {len(rows)} state rows")
    if not rows:
        msg = "No rows extracted from PDF"
        finish_ingest_run(conn, run_id, "failed", 0, 0, 0, [msg])
        return {"status": "failed", "errors": [msg]}

    if dry_run:
        print("[icc_chart] DRY RUN — printing parsed rows:")
        for r in rows:
            print(" ", r)
        finish_ingest_run(conn, run_id, "success", 0, 0, len(rows), [])
        return {"status": "dry_run", "rows": rows}

    # ── Step 3: Upsert ───────────────────────────────────────────────────────
    # Register source URL
    src_cur = conn.execute("""
        INSERT OR IGNORE INTO source_urls (source_type, url, label, last_fetched, last_status_code)
        VALUES ('icc_chart', ?, 'ICC Master I-Code Adoption Chart', datetime('now'), 200)
        RETURNING id
    """, (PDF_URLS[0],))
    src_row = src_cur.fetchone()
    source_id = src_row[0] if src_row else None

    for row in rows:
        state_name = row["state_name"]
        state_abbr = STATE_ABBR_MAP.get(state_name)
        if not state_abbr:
            errors.append(f"Unknown state name: {state_name!r}")
            skipped += 1
            continue

        try:
            jur_id = upsert_state_jurisdiction(conn, state_name, state_abbr)
        except Exception as e:
            errors.append(f"Jurisdiction upsert failed for {state_name}: {e}")
            skipped += 1
            continue

        for code_key in ICC_COLUMNS:
            raw_val = row.get(code_key, "")
            edition_year, status = parse_cell_value(raw_val)

            try:
                _adopt_id, was_new = upsert_adoption(
                    conn, jur_id, code_key, edition_year, status, run_id, source_id
                )
                if was_new:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(f"{state_name}/{code_key}: {e}")
                skipped += 1

    conn.commit()

    final_status = "partial" if errors else "success"
    finish_ingest_run(conn, run_id, final_status, inserted, updated, skipped, errors)

    summary = {
        "status": final_status,
        "states_processed": len(rows),
        "adoptions_inserted": inserted,
        "adoptions_updated": updated,
        "skipped": skipped,
        "errors": errors[:20],  # Truncate for readability
    }
    print(f"[icc_chart] Done: {summary}")
    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Parse ICC Master Adoption Chart PDF into DB")
    ap.add_argument("--db",  default=str(DB_PATH), help="Path to SQLite database")
    ap.add_argument("--pdf", default=None, help="Local PDF path (skip download)")
    ap.add_argument("--url", default=None, nargs="+", help="Override PDF URL(s)")
    ap.add_argument("--dry-run", action="store_true", help="Parse only; do not write to DB")
    args = ap.parse_args()

    result = run(
        db_path=pathlib.Path(args.db),
        pdf_source=pathlib.Path(args.pdf) if args.pdf else None,
        urls=args.url,
        dry_run=args.dry_run,
    )
    sys.exit(0 if result["status"] in ("success", "dry_run") else 1)
