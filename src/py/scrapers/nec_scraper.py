"""
NEC / NFPA 70 State Adoption Scraper
=====================================
Sources:
  Primary:   https://www.nfpa.org/education-and-research/electrical/nec-enforcement-maps
             (Official NFPA publisher page; most authoritative source)
  Secondary: https://citel.us/en/where-is-the-national-electrical-code-in-effect-as-of-2025
             (Structured table; updated ~annually; used as fallback)
  Tertiary:  https://www.mikeholt.com/necadoptionlist.php

The NEC is published every 3 years (2017, 2020, 2023, 2026…).
States adopt different editions; some have split adoptions (commercial vs residential).
Some states delegate entirely to local jurisdictions.

Run:
  python -m scrapers.nec_scraper
  python -m scrapers.nec_scraper --html /path/to/saved.html --db /path/to/ahj.db
"""

import re
import sys
import json
import pathlib
import argparse
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db.schema import init_db, get_connection, DB_PATH

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("beautifulsoup4 required: pip install beautifulsoup4")


# ── Constants ─────────────────────────────────────────────────────────────────

PRIMARY_URL   = "https://www.nfpa.org/education-and-research/electrical/nec-enforcement-maps"
SECONDARY_URL = "https://citel.us/en/where-is-the-national-electrical-code-in-effect-as-of-2025"

# Hardcoded fallback data (used when live fetch fails)
# Originally sourced from CITEL table (February 2025); cross-checked against NFPA enforcement maps
NEC_FALLBACK: list[dict] = [
    {"state": "Alabama",          "abbr": "AL", "edition": 2020, "effective": "2022-07-01", "notes": "Alabama Division of Construction Management", "status": "adopted"},
    {"state": "Alaska",           "abbr": "AK", "edition": 2020, "effective": "2020-04-16", "notes": "", "status": "adopted"},
    {"state": "Arizona",          "abbr": "AZ", "edition": None, "effective": None,         "notes": "Local adoption only — no statewide NEC", "status": "local_only"},
    {"state": "Arkansas",         "abbr": "AR", "edition": 2020, "effective": "2022-08-01", "notes": "AR amendments", "status": "adopted"},
    {"state": "California",       "abbr": "CA", "edition": 2020, "effective": "2023-01-01", "notes": "CA amendments (CEC); 2023 update projected 2026", "status": "adopted"},
    {"state": "Colorado",         "abbr": "CO", "edition": 2023, "effective": "2023-08-01", "notes": "", "status": "adopted"},
    {"state": "Connecticut",      "abbr": "CT", "edition": 2020, "effective": "2022-10-01", "notes": "CT amendments; 2023 update underway", "status": "adopted"},
    {"state": "Delaware",         "abbr": "DE", "edition": 2020, "effective": "2021-09-01", "notes": "", "status": "adopted"},
    {"state": "District of Columbia","abbr":"DC","edition": 2020, "effective": "2022-01-01", "notes": "", "status": "adopted"},
    {"state": "Florida",          "abbr": "FL", "edition": 2020, "effective": "2023-12-31", "notes": "", "status": "adopted"},
    {"state": "Georgia",          "abbr": "GA", "edition": 2023, "effective": "2025-01-01", "notes": "", "status": "adopted"},
    {"state": "Hawaii",           "abbr": "HI", "edition": 2020, "effective": "2023-03-14", "notes": "", "status": "adopted"},
    {"state": "Idaho",            "abbr": "ID", "edition": 2023, "effective": "2023-07-01", "notes": "ID amendments; 2017 NEC permitted via temporary rules", "status": "adopted"},
    {"state": "Illinois",         "abbr": "IL", "edition": 2008, "effective": "2011-07-01", "notes": "Commercial only, outside local jurisdictions; Chicago: 2017 NEC w/amendments", "status": "adopted"},
    {"state": "Indiana",          "abbr": "IN", "edition": 2008, "effective": "2009-08-26", "notes": "Commercial w/IN amendments; residential: 2017 NEC (2019-12-26). 2023 update underway", "status": "adopted"},
    {"state": "Iowa",             "abbr": "IA", "edition": 2020, "effective": "2021-04-01", "notes": "IA amendments; 2023 update underway", "status": "adopted"},
    {"state": "Kansas",           "abbr": "KS", "edition": 2008, "effective": "2011-02-04", "notes": "State Fire Marshal; locals vary", "status": "adopted"},
    {"state": "Kentucky",         "abbr": "KY", "edition": 2023, "effective": "2025-01-01", "notes": "", "status": "adopted"},
    {"state": "Louisiana",        "abbr": "LA", "edition": 2020, "effective": "2023-01-01", "notes": "", "status": "adopted"},
    {"state": "Maine",            "abbr": "ME", "edition": 2023, "effective": "2024-07-01", "notes": "Maine amendments", "status": "adopted"},
    {"state": "Maryland",         "abbr": "MD", "edition": 2017, "effective": "2020-02-07", "notes": "", "status": "adopted"},
    {"state": "Massachusetts",    "abbr": "MA", "edition": 2023, "effective": "2023-02-17", "notes": "MA amendments (527 CMR 12.00)", "status": "adopted"},
    {"state": "Michigan",         "abbr": "MI", "edition": 2023, "effective": "2024-03-12", "notes": "Commercial; residential 2017 NEC. Residential 2023 update underway", "status": "adopted"},
    {"state": "Minnesota",        "abbr": "MN", "edition": 2023, "effective": "2023-07-01", "notes": "", "status": "adopted"},
    {"state": "Mississippi",      "abbr": "MS", "edition": None, "effective": None,         "notes": "Local adoption only", "status": "local_only"},
    {"state": "Missouri",         "abbr": "MO", "edition": None, "effective": None,         "notes": "Local adoption only", "status": "local_only"},
    {"state": "Montana",          "abbr": "MT", "edition": 2020, "effective": "2022-06-10", "notes": "MT amendments", "status": "adopted"},
    {"state": "Nebraska",         "abbr": "NE", "edition": 2023, "effective": "2024-08-01", "notes": "", "status": "adopted"},
    {"state": "Nevada",           "abbr": "NV", "edition": 2017, "effective": "2018-07-01", "notes": "Nevada State Public Works Division", "status": "adopted"},
    {"state": "New Hampshire",    "abbr": "NH", "edition": 2020, "effective": "2022-07-01", "notes": "NH amendments; 2023 update projected 2025", "status": "adopted"},
    {"state": "New Jersey",       "abbr": "NJ", "edition": 2020, "effective": "2022-09-06", "notes": "NJ amendments", "status": "adopted"},
    {"state": "New Mexico",       "abbr": "NM", "edition": 2020, "effective": "2023-03-28", "notes": "", "status": "adopted"},
    {"state": "New York",         "abbr": "NY", "edition": 2017, "effective": "2020-05-12", "notes": "NYSEC; NYC uses 2008 NEC w/amendments. 2023 update underway", "status": "adopted"},
    {"state": "North Carolina",   "abbr": "NC", "edition": 2020, "effective": "2021-11-01", "notes": "NC amendments (commercial); 2023 update projected 2025", "status": "adopted"},
    {"state": "North Dakota",     "abbr": "ND", "edition": 2023, "effective": "2024-07-01", "notes": "", "status": "adopted"},
    {"state": "Ohio",             "abbr": "OH", "edition": 2023, "effective": "2024-03-01", "notes": "Commercial; residential underway", "status": "adopted"},
    {"state": "Oklahoma",         "abbr": "OK", "edition": 2023, "effective": "2024-09-14", "notes": "", "status": "adopted"},
    {"state": "Oregon",           "abbr": "OR", "edition": 2023, "effective": "2023-10-01", "notes": "OR amendments", "status": "adopted"},
    {"state": "Pennsylvania",     "abbr": "PA", "edition": 2017, "effective": "2022-02-14", "notes": "2020 update underway, projected 2025", "status": "adopted"},
    {"state": "Rhode Island",     "abbr": "RI", "edition": 2020, "effective": "2022-02-01", "notes": "", "status": "adopted"},
    {"state": "South Carolina",   "abbr": "SC", "edition": 2020, "effective": "2023-01-01", "notes": "SC amendments", "status": "adopted"},
    {"state": "South Dakota",     "abbr": "SD", "edition": 2023, "effective": "2024-11-12", "notes": "SD amendments", "status": "adopted"},
    {"state": "Tennessee",        "abbr": "TN", "edition": 2017, "effective": "2018-10-01", "notes": "TN amendments", "status": "adopted"},
    {"state": "Texas",            "abbr": "TX", "edition": 2023, "effective": "2023-09-01", "notes": "TECL licensing", "status": "adopted"},
    {"state": "Utah",             "abbr": "UT", "edition": 2020, "effective": "2021-07-01", "notes": "Commercial w/UT amendments; residential 2014 NEC (2016)", "status": "adopted"},
    {"state": "Vermont",          "abbr": "VT", "edition": 2020, "effective": "2022-04-15", "notes": "VT amendments", "status": "adopted"},
    {"state": "Virginia",         "abbr": "VA", "edition": 2020, "effective": "2024-01-18", "notes": "", "status": "adopted"},
    {"state": "Washington",       "abbr": "WA", "edition": 2023, "effective": "2024-04-01", "notes": "", "status": "adopted"},
    {"state": "West Virginia",    "abbr": "WV", "edition": 2020, "effective": "2022-08-01", "notes": "WV amendments", "status": "adopted"},
    {"state": "Wisconsin",        "abbr": "WI", "edition": 2017, "effective": "2018-08-01", "notes": "Commercial; residential 2017 (2020-01-01)", "status": "adopted"},
    {"state": "Wyoming",          "abbr": "WY", "edition": 2023, "effective": "2023-07-01", "notes": "", "status": "adopted"},
    # Special cases
    {"state": "New York City",    "abbr": "NY", "edition": 2008, "effective": "2011-07-01", "notes": "NYC Electrical Code w/NYC amendments. 2020 update underway", "status": "adopted", "jur_type": "city"},
    {"state": "Chicago",          "abbr": "IL", "edition": 2017, "effective": "2018-03-01", "notes": "Chicago Electrical Code w/amendments", "status": "adopted", "jur_type": "city"},
]


# ── Live Scraper ──────────────────────────────────────────────────────────────

def fetch_html(url: str) -> Optional[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (AHJ-Registry-Ingest/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"[nec_scraper] WARN: fetch failed for {url}: {e}")
        return None


def parse_html_table(html: str) -> list[dict]:
    """
    Parse a NEC adoption HTML table (NFPA or CITEL format).
    Expected columns: State | Current Edition (with optional date) | Notes/Status
    """
    soup = BeautifulSoup(html, "lxml")
    records = []

    tables = soup.find_all("table")
    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if not headers:
            # Try first row as header
            rows = table.find_all("tr")
            if rows:
                headers = [td.get_text(strip=True) for td in rows[0].find_all(["td","th"])]

        if not any("State" in h or "Edition" in h for h in headers):
            continue

        for tr in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all(["td","th"])]
            if len(cells) < 2:
                continue
            state_name = cells[0].strip()
            if not state_name:
                continue

            edition_raw = cells[1] if len(cells) > 1 else ""
            notes_raw   = cells[2] if len(cells) > 2 else ""

            # Parse edition year and effective date from cell like "2020 (7/1/2022)"
            edition_match = re.search(r"(20\d\d)", edition_raw)
            date_match    = re.search(r"\((\d{1,2}/\d{1,2}/\d{4})\)", edition_raw)

            edition_year = int(edition_match.group(1)) if edition_match else None
            effective_dt = None
            if date_match:
                m, d, y = date_match.group(1).split("/")
                effective_dt = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

            # Determine status
            lower = edition_raw.lower()
            if "local" in lower or "no statewide" in lower:
                status = "local_only"
                edition_year = None
            else:
                status = "adopted" if edition_year else "not_adopted"

            records.append({
                "state": state_name,
                "edition": edition_year,
                "effective": effective_dt,
                "notes": f"{notes_raw} {cells[2] if len(cells)>2 else ''}".strip(),
                "status": status,
            })

    return records


def merge_with_fallback(live_records: list[dict]) -> list[dict]:
    """
    Merge live-scraped records with the hardcoded fallback.
    Live records override fallback if they parsed a valid edition year.
    """
    if not live_records:
        print("[nec_scraper] Using hardcoded fallback data")
        return NEC_FALLBACK

    fallback_by_state = {r["state"]: r for r in NEC_FALLBACK}
    live_by_state = {r["state"]: r for r in live_records}

    merged = []
    for state, fallback in fallback_by_state.items():
        live = live_by_state.get(state)
        if live and live.get("edition"):
            # Prefer live data
            record = {**fallback, **live}
        else:
            record = fallback
        merged.append(record)
    return merged


# ── Database Upsert ──────────────────────────────────────────────────────────

def get_or_create_jurisdiction(
    conn: sqlite3.Connection,
    state_name: str,
    state_abbr: str,
    jur_name: Optional[str] = None,
    jur_type: str = "state",
) -> int:
    name = jur_name or state_name
    cur = conn.execute("""
        INSERT INTO jurisdictions
            (state_abbr, state_name, jurisdiction_name, jurisdiction_type)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(state_abbr, county_name, jurisdiction_name, jurisdiction_type)
        DO UPDATE SET updated_at = datetime('now')
        RETURNING id
    """, (state_abbr, state_name, name, jur_type))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("""
        SELECT id FROM jurisdictions
        WHERE state_abbr=? AND jurisdiction_name=? AND jurisdiction_type=?
    """, (state_abbr, name, jur_type))
    return cur.fetchone()[0]


def upsert_nec_adoption(
    conn: sqlite3.Connection,
    jur_id: int,
    edition_year: Optional[int],
    status: str,
    effective_date: Optional[str],
    notes: str,
    run_id: int,
    source_id: Optional[int],
):
    conn.execute("""
        INSERT INTO code_adoptions
            (jurisdiction_id, code_key, code_full_name, publishing_org,
             edition_year, edition_label, status, effective_date,
             source_text, ingest_run_id, source_id)
        VALUES (?, 'NEC', 'National Electrical Code (NFPA 70)', 'NFPA',
                ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(jurisdiction_id, code_key, edition_year, status)
        DO UPDATE SET
            status        = excluded.status,
            effective_date= excluded.effective_date,
            source_text   = excluded.source_text,
            updated_at    = datetime('now')
    """, (
        jur_id,
        edition_year,
        str(edition_year) if edition_year else None,
        status,
        effective_date,
        notes or None,
        run_id,
        source_id,
    ))


# ── Ingest Helpers ────────────────────────────────────────────────────────────

def start_run(conn, name):
    import uuid
    rid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO ingest_runs (run_id, scraper_name, started_at, status) "
        "VALUES (?, ?, datetime('now'), 'running')", (rid, name))
    conn.commit()
    return conn.execute("SELECT id FROM ingest_runs WHERE run_id=?", (rid,)).fetchone()[0]


def finish_run(conn, rid, status, ins, upd, skip, errors):
    conn.execute("""
        UPDATE ingest_runs
        SET finished_at=datetime('now'), status=?, rows_inserted=?,
            rows_updated=?, rows_skipped=?, errors=?
        WHERE id=?
    """, (status, ins, upd, skip, json.dumps(errors), rid))
    conn.commit()


# ── Main ─────────────────────────────────────────────────────────────────────

def run(
    db_path: pathlib.Path = DB_PATH,
    html_source: Optional[pathlib.Path] = None,
    use_fallback: bool = False,
    dry_run: bool = False,
) -> dict:
    conn = init_db(db_path)
    run_id = start_run(conn, "nec_scraper")
    errors: list[str] = []
    inserted = updated = skipped = 0

    # Register source
    src_cur = conn.execute("""
        INSERT OR IGNORE INTO source_urls (source_type, url, label, last_fetched, last_status_code)
        VALUES ('nfpa_map', ?, 'NFPA NEC Enforcement Maps (Official)', datetime('now'), 200)
        RETURNING id
    """, (PRIMARY_URL,))
    src_row = src_cur.fetchone()
    source_id = src_row[0] if src_row else None

    # ── Get records ──────────────────────────────────────────────────────────
    records = None

    if not use_fallback:
        if html_source and pathlib.Path(html_source).exists():
            html = pathlib.Path(html_source).read_text(encoding="utf-8", errors="replace")
        else:
            html = fetch_html(PRIMARY_URL)

        if html:
            live = parse_html_table(html)
            print(f"[nec_scraper] Parsed {len(live)} live records")
            records = merge_with_fallback(live)
        else:
            print("[nec_scraper] Live fetch failed; falling back to embedded data")

    if records is None:
        records = NEC_FALLBACK

    print(f"[nec_scraper] Processing {len(records)} NEC adoption records")

    if dry_run:
        for r in records:
            print(" ", r)
        finish_run(conn, run_id, "success", 0, 0, len(records), [])
        return {"status": "dry_run", "count": len(records)}

    # ── Upsert ───────────────────────────────────────────────────────────────
    # State-level abbreviation lookup
    abbr_map = {r["state"]: r.get("abbr") for r in records if r.get("abbr")}

    for rec in records:
        state_name = rec["state"]
        state_abbr = rec.get("abbr")
        jur_type = rec.get("jur_type", "state")

        if not state_abbr:
            errors.append(f"No state_abbr for {state_name!r}")
            skipped += 1
            continue

        # For special city entries, we need the parent state name
        parent_state = state_name
        if jur_type == "city":
            # Cities like "New York City" — find parent state from abbr
            state_long = {v: k for k, v in abbr_map.items() if len(k) > 2}.get(state_abbr, state_name)
            parent_state = state_long

        try:
            jur_id = get_or_create_jurisdiction(
                conn, parent_state, state_abbr, state_name, jur_type
            )
            upsert_nec_adoption(
                conn, jur_id,
                rec.get("edition"),
                rec.get("status", "not_adopted"),
                rec.get("effective"),
                rec.get("notes", ""),
                run_id,
                source_id,
            )
            inserted += 1
        except Exception as e:
            errors.append(f"{state_name}: {e}")
            skipped += 1

    conn.commit()
    status = "partial" if errors else "success"
    finish_run(conn, run_id, status, inserted, updated, skipped, errors)

    summary = {
        "status": status,
        "records_processed": len(records),
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors[:20],
    }
    print(f"[nec_scraper] Done: {summary}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingest NEC adoption data")
    ap.add_argument("--db",       default=str(DB_PATH))
    ap.add_argument("--html",     default=None, help="Local HTML file (skip fetch)")
    ap.add_argument("--fallback", action="store_true", help="Use embedded fallback data only")
    ap.add_argument("--dry-run",  action="store_true")
    args = ap.parse_args()

    result = run(
        db_path=pathlib.Path(args.db),
        html_source=args.html,
        use_fallback=args.fallback,
        dry_run=args.dry_run,
    )
    sys.exit(0 if result["status"] in ("success", "dry_run") else 1)
