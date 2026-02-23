"""
Municipal Code Adoption Scraper — Municode / eCode360 / City Websites
======================================================================
This scraper queries municipal code portals to find building code adoption
ordinances within a jurisdiction's code of ordinances.

Sources:
  - Municode Library: https://library.municode.com/
    * REST-ish API: /api/prodcontent/GetNodeChildren?nodeId={id}
    * Full-text search: /api/search?q=building+code&clientId={clientId}
  - eCode360: https://ecode360.com/
    * No public API; HTML scraping with CSS selectors
  - Direct city/county building department pages

Strategy:
  1. Search Municode for each jurisdiction name
  2. Find "building" or "construction" chapter in their code
  3. Parse chapter for "adopted", "IBC", "NEC", "IFC", version years
  4. Extract ordinance numbers and effective dates

Rate limiting:
  - Municode: ~1 req/sec is polite
  - eCode360: ~0.5 req/sec
  - Always respect robots.txt

Run:
  python -m scrapers.municipal_scraper --state TX --cities "Dallas,Austin"
  python -m scrapers.municipal_scraper --jurisdiction-file /path/to/cities.csv
"""

import re
import sys
import json
import time
import pathlib
import argparse
import sqlite3
import csv
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Generator

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db.schema import init_db, DB_PATH

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


# ── Constants ─────────────────────────────────────────────────────────────────

MUNICODE_API_BASE  = "https://library.municode.com"
ECODE360_API_BASE  = "https://ecode360.com"
REQUEST_DELAY_SEC  = 1.2  # polite delay between requests

HEADERS = {
    "User-Agent": (
        "AHJ-Registry-Ingest/1.0 (Building Code Research Tool; "
        "contact: admin@yourdomain.example)"
    ),
    "Accept": "application/json, text/html, */*",
}

# Patterns to detect building code adoptions in ordinance text
CODE_DETECTION_PATTERNS = {
    "IBC":   re.compile(r"International\s+Building\s+Code[,\s]+(\d{4})\s+[Ee]dition|"
                        r"IBC[,\s]+(\d{4})|"
                        r"(\d{4})\s+International\s+Building\s+Code", re.I),
    "IRC":   re.compile(r"International\s+Residential\s+Code[,\s]+(\d{4})|IRC[,\s]+(\d{4})", re.I),
    "IFC":   re.compile(r"International\s+Fire\s+Code[,\s]+(\d{4})|IFC[,\s]+(\d{4})", re.I),
    "NEC":   re.compile(r"National\s+Electrical\s+Code[,\s]+(\d{4})|NFPA\s*70[,\s]+(\d{4})|NEC[,\s]+(\d{4})", re.I),
    "IMC":   re.compile(r"International\s+Mechanical\s+Code[,\s]+(\d{4})|IMC[,\s]+(\d{4})", re.I),
    "IPC":   re.compile(r"International\s+Plumbing\s+Code[,\s]+(\d{4})|IPC[,\s]+(\d{4})", re.I),
    "IECC":  re.compile(r"International\s+Energy\s+Conservation\s+Code[,\s]+(\d{4})|IECC[,\s]+(\d{4})", re.I),
    "IEBC":  re.compile(r"International\s+Existing\s+Building\s+Code[,\s]+(\d{4})|IEBC[,\s]+(\d{4})", re.I),
    "IFGC":  re.compile(r"International\s+Fuel\s+Gas\s+Code[,\s]+(\d{4})|IFGC[,\s]+(\d{4})", re.I),
    "NFPA1": re.compile(r"NFPA\s*1[,\s]+(\d{4})|NFPA\s*1\s+Fire\s+Code[,\s]+(\d{4})", re.I),
    "UPC":   re.compile(r"Uniform\s+Plumbing\s+Code[,\s]+(\d{4})|UPC[,\s]+(\d{4})", re.I),
    "UMC":   re.compile(r"Uniform\s+Mechanical\s+Code[,\s]+(\d{4})|UMC[,\s]+(\d{4})", re.I),
}

AMENDMENT_PATTERNS = [
    re.compile(r"(?:amended|modified|deleted|added|revised)\s+(?:as\s+follows|:)[^.]+\.", re.I),
    re.compile(r"[Ss]ection\s+[\d.]+\s+(?:is\s+)?(?:amended|deleted|added)\s+to\s+read", re.I),
    re.compile(r"[Ss]ubstitute\s+(?:the\s+following|.*?)\s+for\s+[Ss]ection", re.I),
]

ORDINANCE_PATTERN = re.compile(
    r"[Oo]rdinance\s+(?:No\.?\s*)?([A-Z0-9\-]+)\s*,?\s*"
    r"(?:(?:passed|approved|adopted|effective)\s+(?:on\s+)?)?"
    r"(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})"
)


# ── HTTP Utilities ─────────────────────────────────────────────────────────────

def fetch(url: str, delay: float = REQUEST_DELAY_SEC, max_retries: int = 3) -> Optional[str]:
    """Fetch URL with retry + rate limiting."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()
                if "json" in content_type:
                    return raw.decode("utf-8")
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:  # Rate limited
                wait = 5 * (attempt + 1)
                print(f"  [rate-limit] 429 on {url}, waiting {wait}s")
                time.sleep(wait)
            elif e.code in (403, 404):
                return None
            else:
                print(f"  [http-error] {e.code} on {url} (attempt {attempt+1})")
                time.sleep(2)
        except urllib.error.URLError as e:
            print(f"  [url-error] {e} on {url} (attempt {attempt+1})")
            time.sleep(2)
    return None


def fetch_json(url: str, delay: float = REQUEST_DELAY_SEC) -> Optional[dict]:
    raw = fetch(url, delay)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


# ── Municode API ──────────────────────────────────────────────────────────────

def municode_search_jurisdiction(jurisdiction_name: str, state_abbr: str) -> list[dict]:
    """
    Search Municode for a jurisdiction's client entry.
    Returns list of matching clients with their IDs.
    """
    query = urllib.parse.quote(f"{jurisdiction_name} {state_abbr}")
    url = f"{MUNICODE_API_BASE}/api/search/suggest?query={query}&count=5"
    time.sleep(REQUEST_DELAY_SEC)
    data = fetch_json(url)
    if not data:
        return []

    results = []
    # Municode returns { "suggestions": [...] } or list directly
    suggestions = data if isinstance(data, list) else data.get("suggestions", data.get("results", []))
    for item in suggestions:
        name = item.get("name") or item.get("label") or item.get("clientName") or ""
        state = item.get("state") or item.get("stateCode") or ""
        client_id = item.get("clientId") or item.get("id") or item.get("nodeId")
        if state_abbr.lower() in state.lower():
            results.append({
                "name": name,
                "state": state,
                "client_id": client_id,
                "url": item.get("url", ""),
            })
    return results


def municode_get_toc(client_id: str) -> list[dict]:
    """Get table of contents for a Municode client."""
    url = f"{MUNICODE_API_BASE}/api/prodcontent/GetNodeChildren?nodeId={client_id}"
    time.sleep(REQUEST_DELAY_SEC)
    data = fetch_json(url)
    if not data:
        return []
    return data if isinstance(data, list) else data.get("nodes", [])


def municode_find_building_chapter(client_id: str) -> Optional[dict]:
    """
    Walk the table of contents to find the Building/Construction chapter.
    Returns the node dict for the building chapter, or None.
    """
    BUILDING_KEYWORDS = {"building", "construction", "technical", "fire", "electrical"}

    def walk_nodes(nodes: list, depth: int = 0) -> Optional[dict]:
        if depth > 4:  # Don't go too deep
            return None
        for node in nodes:
            label = (node.get("label") or node.get("name") or "").lower()
            if any(kw in label for kw in BUILDING_KEYWORDS):
                return node
            # Recurse
            children = node.get("children", [])
            if not children and node.get("id"):
                time.sleep(0.5)
                children = municode_get_toc(node["id"])
            found = walk_nodes(children, depth + 1)
            if found:
                return found
        return None

    toc = municode_get_toc(client_id)
    return walk_nodes(toc)


def municode_get_section_text(node_id: str) -> Optional[str]:
    """Get full text of a Municode node/section."""
    url = f"{MUNICODE_API_BASE}/api/prodcontent/GetNodeContent?nodeId={node_id}"
    time.sleep(REQUEST_DELAY_SEC)
    data = fetch_json(url)
    if not data:
        return None
    # Content may be in 'content', 'html', 'text', or direct string
    if isinstance(data, str):
        return data
    return data.get("content") or data.get("html") or data.get("text")


# ── eCode360 Scraper ──────────────────────────────────────────────────────────

def ecode360_search(jurisdiction_name: str, state_abbr: str) -> list[dict]:
    """Search eCode360 for a jurisdiction."""
    if not BS4_AVAILABLE:
        return []
    query = urllib.parse.quote(f"{jurisdiction_name}")
    url = f"{ECODE360_API_BASE}/api/jurisdictions?q={query}&state={state_abbr}"
    time.sleep(REQUEST_DELAY_SEC)
    raw = fetch(url)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def ecode360_search_code_text(
    ecode_url: str,
    search_term: str = "International Building Code"
) -> Optional[str]:
    """
    Search within a jurisdiction's eCode360 for code adoption text.
    """
    if not BS4_AVAILABLE:
        return None
    encoded = urllib.parse.quote(search_term)
    search_url = f"{ecode_url}/search?q={encoded}"
    time.sleep(REQUEST_DELAY_SEC)
    html = fetch(search_url)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    # Extract result snippets
    snippets = []
    for result in soup.select(".search-result, .result-snippet, article.result"):
        snippets.append(result.get_text(separator=" ", strip=True))
    return "\n\n".join(snippets[:5]) if snippets else None


# ── Text Analysis ─────────────────────────────────────────────────────────────

def extract_adoptions_from_text(text: str) -> list[dict]:
    """
    Parse raw ordinance/code text to extract building code adoptions.
    Returns list of dicts: {code_key, edition_year, section_ref, context}
    """
    if not text:
        return []

    adoptions = []

    for code_key, pattern in CODE_DETECTION_PATTERNS.items():
        for match in pattern.finditer(text):
            # Extract year from first non-None group
            year_str = next((g for g in match.groups() if g), None)
            if not year_str:
                continue
            try:
                year = int(year_str)
                if not 1990 <= year <= 2030:
                    continue
            except ValueError:
                continue

            # Get surrounding context (100 chars before and after)
            start = max(0, match.start() - 100)
            end   = min(len(text), match.end() + 150)
            context = " ".join(text[start:end].split())

            # Try to find section reference near the match
            section_match = re.search(
                r"(?:Section|Sec\.?|§)\s*([\d.]+(?:\.\d+)*)",
                text[max(0, match.start()-200):match.start()],
                re.I
            )
            section_ref = section_match.group(1) if section_match else None

            adoptions.append({
                "code_key":    code_key,
                "edition_year": year,
                "section_ref": section_ref,
                "context":     context,
                "match_pos":   match.start(),
            })

    # Deduplicate: keep highest year per code_key
    best = {}
    for a in adoptions:
        k = a["code_key"]
        if k not in best or a["edition_year"] > best[k]["edition_year"]:
            best[k] = a

    return list(best.values())


def extract_amendments_from_text(text: str, code_key: str) -> list[dict]:
    """
    Extract amendment snippets from ordinance text.
    """
    if not text:
        return []
    amendments = []
    for pattern in AMENDMENT_PATTERNS:
        for match in pattern.finditer(text):
            context = text[match.start():min(len(text), match.end() + 200)]
            # Find section reference
            section_match = re.search(r"Section\s+([\d.]+)", context[:50], re.I)
            amendments.append({
                "amendment_type": "modification",
                "section_ref":    section_match.group(1) if section_match else None,
                "description":    " ".join(context.split())[:500],
            })
    return amendments[:10]  # Cap at 10 per code/jurisdiction


def extract_ordinance_metadata(text: str) -> dict:
    """Extract ordinance number and date from text."""
    match = ORDINANCE_PATTERN.search(text)
    if match:
        return {
            "ordinance_number": match.group(1),
            "ordinance_date":   match.group(2),
        }
    return {}


# ── Database Operations ────────────────────────────────────────────────────────

CODE_META = {
    "IBC":   ("International Building Code",             "ICC"),
    "IRC":   ("International Residential Code",          "ICC"),
    "IFC":   ("International Fire Code",                 "ICC"),
    "NEC":   ("National Electrical Code (NFPA 70)",      "NFPA"),
    "IMC":   ("International Mechanical Code",           "ICC"),
    "IPC":   ("International Plumbing Code",             "ICC"),
    "IECC":  ("Int'l Energy Conservation Code",          "ICC"),
    "IEBC":  ("Int'l Existing Building Code",            "ICC"),
    "IFGC":  ("International Fuel Gas Code",             "ICC"),
    "NFPA1": ("NFPA 1 Fire Code",                        "NFPA"),
    "UPC":   ("Uniform Plumbing Code",                   "IAPMO"),
    "UMC":   ("Uniform Mechanical Code",                 "IAPMO"),
}


def get_or_create_jurisdiction(
    conn: sqlite3.Connection,
    state_abbr: str,
    state_name: str,
    jur_name: str,
    jur_type: str,
    county_name: Optional[str] = None,
) -> int:
    cur = conn.execute("""
        INSERT INTO jurisdictions
            (state_abbr, state_name, jurisdiction_name, jurisdiction_type, county_name)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(state_abbr, county_name, jurisdiction_name, jurisdiction_type)
        DO UPDATE SET updated_at=datetime('now')
        RETURNING id
    """, (state_abbr, state_name, jur_name, jur_type, county_name))
    row = cur.fetchone()
    if row:
        return row[0]
    return conn.execute("""
        SELECT id FROM jurisdictions
        WHERE state_abbr=? AND jurisdiction_name=? AND jurisdiction_type=?
    """, (state_abbr, jur_name, jur_type)).fetchone()[0]


def save_adoption_with_amendments(
    conn: sqlite3.Connection,
    jur_id: int,
    adoption: dict,
    amendments: list[dict],
    run_id: int,
    source_id: Optional[int],
    ordinance: dict,
):
    code_key = adoption["code_key"]
    full_name, org = CODE_META.get(code_key, (code_key, "unknown"))
    year = adoption["edition_year"]

    cur = conn.execute("""
        INSERT INTO code_adoptions
            (jurisdiction_id, code_key, code_full_name, publishing_org,
             edition_year, edition_label, status, source_text, ingest_run_id, source_id)
        VALUES (?, ?, ?, ?, ?, ?, 'adopted', ?, ?, ?)
        ON CONFLICT(jurisdiction_id, code_key, edition_year, status)
        DO UPDATE SET source_text=excluded.source_text, updated_at=datetime('now')
        RETURNING id
    """, (jur_id, code_key, full_name, org, year, str(year),
          adoption.get("context", "")[:1000], run_id, source_id))
    row = cur.fetchone()
    if not row:
        cur = conn.execute("""
            SELECT id FROM code_adoptions
            WHERE jurisdiction_id=? AND code_key=? AND edition_year=?
        """, (jur_id, code_key, year))
        row = cur.fetchone()
    if not row:
        return

    adoption_id = row[0]
    for amend in amendments:
        conn.execute("""
            INSERT OR IGNORE INTO amendments
                (adoption_id, amendment_type, section_ref, description,
                 ordinance_number, ordinance_date, ingest_run_id, source_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            adoption_id,
            amend.get("amendment_type", "modification"),
            amend.get("section_ref"),
            amend.get("description", "")[:1000],
            ordinance.get("ordinance_number"),
            ordinance.get("ordinance_date"),
            run_id,
            source_id,
        ))


# ── Jurisdiction Processor ────────────────────────────────────────────────────

def process_jurisdiction(
    conn: sqlite3.Connection,
    state_abbr: str,
    state_name: str,
    jur_name: str,
    jur_type: str,
    run_id: int,
    verbose: bool = False,
) -> dict:
    """
    Full pipeline for one jurisdiction:
      1. Search Municode
      2. Find building chapter
      3. Extract adoptions + amendments
      4. Save to DB
    """
    stats = {"found": False, "adoptions": 0, "amendments": 0, "source": None}
    print(f"  Processing: {jur_name}, {state_abbr} ({jur_type})")

    # ── Municode search ──────────────────────────────────────────────────────
    clients = municode_search_jurisdiction(jur_name, state_abbr)
    if not clients:
        if verbose:
            print(f"    No Municode entry found for {jur_name}")
        return stats

    client = clients[0]
    stats["source"] = "municode"
    stats["found"] = True
    code_url = client.get("url", f"{MUNICODE_API_BASE}/{state_abbr.lower()}/{jur_name.lower().replace(' ','-')}")

    # Register source URL
    src_cur = conn.execute("""
        INSERT OR IGNORE INTO source_urls
            (source_type, url, label, last_fetched, last_status_code)
        VALUES ('municipal_code', ?, ?, datetime('now'), 200)
        RETURNING id
    """, (code_url, f"Municode: {jur_name}, {state_abbr}"))
    src_row = src_cur.fetchone()
    source_id = src_row[0] if src_row else None

    # ── Find building chapter ────────────────────────────────────────────────
    client_id = client.get("client_id")
    chapter = municode_find_building_chapter(client_id) if client_id else None
    text = None

    if chapter and chapter.get("id"):
        text = municode_get_section_text(chapter["id"])

    if not text:
        # Fallback: search directly
        search_url = f"{MUNICODE_API_BASE}/api/search?q=International+Building+Code&clientId={client_id}"
        time.sleep(REQUEST_DELAY_SEC)
        search_data = fetch_json(search_url)
        if search_data:
            # Extract snippets from search results
            results = search_data if isinstance(search_data, list) else search_data.get("results", [])
            text = " ".join(
                r.get("snippet") or r.get("text") or r.get("content") or ""
                for r in results[:5]
            )

    if not text:
        if verbose:
            print(f"    Could not retrieve building code text for {jur_name}")
        return stats

    # ── Extract adoptions ────────────────────────────────────────────────────
    adoptions = extract_adoptions_from_text(text)
    ordinance = extract_ordinance_metadata(text)

    if verbose:
        print(f"    Found {len(adoptions)} code adoptions in {jur_name}")

    if not adoptions:
        return stats

    # ── Save to DB ────────────────────────────────────────────────────────────
    jur_id = get_or_create_jurisdiction(
        conn, state_abbr, state_name, jur_name, jur_type
    )

    for adoption in adoptions:
        amendments = extract_amendments_from_text(text, adoption["code_key"])
        save_adoption_with_amendments(
            conn, jur_id, adoption, amendments, run_id, source_id, ordinance
        )
        stats["adoptions"] += 1
        stats["amendments"] += len(amendments)

    conn.commit()
    return stats


# ── Batch Processor ───────────────────────────────────────────────────────────

STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
    "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas",
    "KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts",
    "MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana",
    "NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico",
    "NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma",
    "OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina",
    "SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont",
    "VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming",
    "DC":"District of Columbia",
}


def load_jurisdictions_from_csv(csv_path: pathlib.Path) -> list[dict]:
    """
    Load jurisdiction list from CSV.
    Expected columns: state_abbr, jurisdiction_name, jurisdiction_type[, county_name]
    """
    jurisdictions = []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            jurisdictions.append({
                "state_abbr":       row.get("state_abbr", "").strip().upper(),
                "jurisdiction_name": row.get("jurisdiction_name", "").strip(),
                "jurisdiction_type": row.get("jurisdiction_type", "city").strip(),
                "county_name":       row.get("county_name", "").strip() or None,
            })
    return jurisdictions


def run(
    db_path: pathlib.Path = DB_PATH,
    state_abbr: Optional[str] = None,
    city_names: Optional[list[str]] = None,
    jurisdiction_csv: Optional[pathlib.Path] = None,
    dry_run: bool = False,
    verbose: bool = False,
    max_jurisdictions: int = 50,
) -> dict:
    conn = init_db(db_path)
    import uuid
    run_id_str = str(uuid.uuid4())
    cur = conn.execute("""
        INSERT INTO ingest_runs (run_id, scraper_name, started_at, status)
        VALUES (?, 'municipal_scraper', datetime('now'), 'running') RETURNING id
    """, (run_id_str,))
    conn.commit()
    run_id = cur.fetchone()[0]

    errors = []
    total_adoptions = total_amendments = 0

    # ── Build jurisdiction list ───────────────────────────────────────────────
    jurisdictions: list[dict] = []

    if jurisdiction_csv:
        jurisdictions = load_jurisdictions_from_csv(jurisdiction_csv)
    elif state_abbr and city_names:
        for city in city_names:
            jurisdictions.append({
                "state_abbr": state_abbr.upper(),
                "jurisdiction_name": city.strip(),
                "jurisdiction_type": "city",
                "county_name": None,
            })
    else:
        # Default demo set — major cities with Municode presence
        jurisdictions = [
            {"state_abbr": "TX", "jurisdiction_name": "Houston",     "jurisdiction_type": "city"},
            {"state_abbr": "TX", "jurisdiction_name": "Austin",      "jurisdiction_type": "city"},
            {"state_abbr": "TX", "jurisdiction_name": "San Antonio", "jurisdiction_type": "city"},
            {"state_abbr": "CO", "jurisdiction_name": "Denver",      "jurisdiction_type": "city"},
            {"state_abbr": "CO", "jurisdiction_name": "Boulder",     "jurisdiction_type": "city"},
            {"state_abbr": "GA", "jurisdiction_name": "Atlanta",     "jurisdiction_type": "city"},
            {"state_abbr": "OH", "jurisdiction_name": "Columbus",    "jurisdiction_type": "city"},
            {"state_abbr": "OH", "jurisdiction_name": "Cleveland",   "jurisdiction_type": "city"},
            {"state_abbr": "MN", "jurisdiction_name": "Minneapolis", "jurisdiction_type": "city"},
            {"state_abbr": "MN", "jurisdiction_name": "Saint Paul",  "jurisdiction_type": "city"},
        ]

    jurisdictions = jurisdictions[:max_jurisdictions]
    print(f"[municipal_scraper] Processing {len(jurisdictions)} jurisdictions")

    if dry_run:
        for j in jurisdictions:
            print(" ", j)
        conn.execute("UPDATE ingest_runs SET status='success', finished_at=datetime('now') WHERE id=?", (run_id,))
        conn.commit()
        return {"status": "dry_run", "count": len(jurisdictions)}

    for jur in jurisdictions:
        abbr = jur["state_abbr"]
        state_name = STATE_NAMES.get(abbr, abbr)
        try:
            stats = process_jurisdiction(
                conn, abbr, state_name,
                jur["jurisdiction_name"],
                jur.get("jurisdiction_type", "city"),
                run_id,
                verbose=verbose,
            )
            total_adoptions  += stats["adoptions"]
            total_amendments += stats["amendments"]
        except Exception as e:
            err = f"{jur['jurisdiction_name']}, {abbr}: {e}"
            errors.append(err)
            print(f"  [ERROR] {err}")
        finally:
            time.sleep(REQUEST_DELAY_SEC)

    final_status = "partial" if errors else "success"
    conn.execute("""
        UPDATE ingest_runs
        SET finished_at=datetime('now'), status=?, rows_inserted=?, errors=?
        WHERE id=?
    """, (final_status, total_adoptions, json.dumps(errors[:20]), run_id))
    conn.commit()

    summary = {
        "status": final_status,
        "jurisdictions_attempted": len(jurisdictions),
        "total_adoptions_found": total_adoptions,
        "total_amendments_found": total_amendments,
        "errors": errors[:10],
    }
    print(f"[municipal_scraper] Done: {summary}")
    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scrape municipal code adoption ordinances")
    ap.add_argument("--db",         default=str(DB_PATH))
    ap.add_argument("--state",      help="State abbreviation (e.g. TX)")
    ap.add_argument("--cities",     help="Comma-separated city names")
    ap.add_argument("--csv",        help="CSV file of jurisdictions")
    ap.add_argument("--max",        type=int, default=50, help="Max jurisdictions to process")
    ap.add_argument("--dry-run",    action="store_true")
    ap.add_argument("--verbose",    action="store_true")
    args = ap.parse_args()

    city_list = [c.strip() for c in args.cities.split(",")] if args.cities else None

    result = run(
        db_path=pathlib.Path(args.db),
        state_abbr=args.state,
        city_names=city_list,
        jurisdiction_csv=pathlib.Path(args.csv) if args.csv else None,
        dry_run=args.dry_run,
        verbose=args.verbose,
        max_jurisdictions=args.max,
    )
    sys.exit(0 if result["status"] in ("success", "dry_run") else 1)
