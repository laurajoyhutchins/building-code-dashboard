"""
AHJ Registry — Master Ingest Orchestrator
==========================================
Runs all scrapers in dependency order, handles errors gracefully,
and exports the final database to a JSON file consumable by the dashboard.

Pipeline order:
  1. icc_chart_parser   — state-level I-Code adoptions (ICC PDF)
  2. nec_scraper        — NEC/NFPA 70 state adoptions
  3. iecc_scraper       — IECC / ASHRAE 90.1 energy code adoptions
  4. municipal_scraper  — local jurisdiction code adoption ordinances (optional)
  5. export_json        — flatten DB → dashboard-ready JSON

Run full pipeline:
  python -m orchestrator

Run with options:
  python -m orchestrator --skip-municipal --export-only
  python -m orchestrator --db /path/to/ahj.db --output /path/to/data.json
"""

import sys
import json
import pathlib
import argparse
import sqlite3
from datetime import datetime
from typing import Optional

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db.schema import init_db, get_connection, DB_PATH

SCRAPER_DIR = pathlib.Path(__file__).parent / "scrapers"
DEFAULT_EXPORT = pathlib.Path(__file__).parent.parent / "ahj_data.json"


# ── Import scrapers ───────────────────────────────────────────────────────────

def import_scrapers():
    """Lazy-import scrapers; return dict of available modules."""
    modules = {}
    try:
        from scrapers import icc_chart_parser
        modules["icc"] = icc_chart_parser
    except ImportError as e:
        print(f"[orchestrator] WARNING: icc_chart_parser unavailable: {e}")
    try:
        from scrapers import nec_scraper
        modules["nec"] = nec_scraper
    except ImportError as e:
        print(f"[orchestrator] WARNING: nec_scraper unavailable: {e}")
    try:
        from scrapers import iecc_scraper
        modules["iecc"] = iecc_scraper
    except ImportError as e:
        print(f"[orchestrator] WARNING: iecc_scraper unavailable: {e}")
    try:
        from scrapers import municipal_scraper
        modules["municipal"] = municipal_scraper
    except ImportError as e:
        print(f"[orchestrator] WARNING: municipal_scraper unavailable: {e}")
    return modules


# ── Ingestion Pipeline ────────────────────────────────────────────────────────

def run_all_scrapers(
    db_path: pathlib.Path,
    skip_icc: bool = False,
    skip_nec: bool = False,
    skip_iecc: bool = False,
    skip_municipal: bool = True,  # Municipal is slow; off by default
    municipal_csv: Optional[pathlib.Path] = None,
    pdf_path: Optional[pathlib.Path] = None,
) -> dict:
    modules = import_scrapers()
    results = {}
    total_start = datetime.now()

    # 1. ICC Chart
    if not skip_icc and "icc" in modules:
        print("\n" + "─"*60)
        print("STEP 1/4: ICC Master Adoption Chart")
        print("─"*60)
        try:
            results["icc"] = modules["icc"].run(
                db_path=db_path,
                pdf_source=pdf_path,
            )
        except Exception as e:
            results["icc"] = {"status": "error", "error": str(e)}
            print(f"[orchestrator] ERROR in ICC scraper: {e}")

    # 2. NEC
    if not skip_nec and "nec" in modules:
        print("\n" + "─"*60)
        print("STEP 2/4: NEC / NFPA 70 State Adoptions")
        print("─"*60)
        try:
            results["nec"] = modules["nec"].run(db_path=db_path)
        except Exception as e:
            results["nec"] = {"status": "error", "error": str(e)}
            print(f"[orchestrator] ERROR in NEC scraper: {e}")

    # 3. IECC
    if not skip_iecc and "iecc" in modules:
        print("\n" + "─"*60)
        print("STEP 3/4: IECC / ASHRAE 90.1 Energy Codes")
        print("─"*60)
        try:
            results["iecc"] = modules["iecc"].run(db_path=db_path, use_fallback=True)
        except Exception as e:
            results["iecc"] = {"status": "error", "error": str(e)}
            print(f"[orchestrator] ERROR in IECC scraper: {e}")

    # 4. Municipal (optional)
    if not skip_municipal and "municipal" in modules:
        print("\n" + "─"*60)
        print("STEP 4/4: Municipal Code Adoption Scraping")
        print("─"*60)
        try:
            results["municipal"] = modules["municipal"].run(
                db_path=db_path,
                jurisdiction_csv=municipal_csv,
                max_jurisdictions=100,
            )
        except Exception as e:
            results["municipal"] = {"status": "error", "error": str(e)}
            print(f"[orchestrator] ERROR in municipal scraper: {e}")
    else:
        print("\n[orchestrator] Municipal scraping skipped (use --include-municipal to enable)")

    elapsed = (datetime.now() - total_start).total_seconds()
    print(f"\n[orchestrator] All scrapers completed in {elapsed:.1f}s")
    return results


# ── JSON Export ───────────────────────────────────────────────────────────────

def export_to_json(
    db_path: pathlib.Path,
    output_path: pathlib.Path,
    include_amendments: bool = True,
) -> dict:
    """
    Export the full database to a hierarchical JSON structure
    optimized for the dashboard front-end.

    Output structure:
    {
      "meta": { "generated_at": "...", "total_jurisdictions": N, ... },
      "jurisdictions": {
        "AL": {
          "name": "Alabama",
          "type": "state",
          "adopted": { "IBC": { "year": 2021, "status": "adopted", ... }, ... },
          "cities": {
            "Birmingham": { "type": "city", "adopted": {...}, "amendments": {...} }
          },
          "counties": { ... },
          "fire_districts": { ... }
        },
        ...
      }
    }
    """
    print(f"\n[export] Building JSON from {db_path}")
    conn = get_connection(db_path)

    # ── Build jurisdiction tree ───────────────────────────────────────────────
    all_jurs = conn.execute("""
        SELECT id, state_abbr, state_name, county_name, jurisdiction_name,
               jurisdiction_type, region, population, has_own_code, home_rule
        FROM jurisdictions
        ORDER BY state_abbr, jurisdiction_type, jurisdiction_name
    """).fetchall()

    # ── Fetch all adoptions with amendments ────────────────────────────────────
    all_adoptions = conn.execute("""
        SELECT
            ca.id, ca.jurisdiction_id, ca.code_key, ca.code_full_name,
            ca.publishing_org, ca.edition_year, ca.edition_label,
            ca.status, ca.is_mandatory, ca.effective_date, ca.source_text
        FROM code_adoptions ca
        WHERE ca.status NOT IN ('superseded', 'withdrawn')
        ORDER BY ca.jurisdiction_id, ca.code_key
    """).fetchall()

    adoption_map: dict[int, list] = {}
    for row in all_adoptions:
        jid = row["jurisdiction_id"]
        adoption_map.setdefault(jid, []).append(dict(row))

    if include_amendments:
        all_amendments = conn.execute("""
            SELECT
                a.adoption_id, a.amendment_type, a.section_ref,
                a.title, a.description, a.ordinance_number, a.ordinance_date
            FROM amendments a
            ORDER BY a.adoption_id
        """).fetchall()

        amendment_map: dict[int, list] = {}
        for row in all_amendments:
            aid = row["adoption_id"]
            amendment_map.setdefault(aid, []).append(dict(row))

    # ── Assemble hierarchy ────────────────────────────────────────────────────
    output: dict = {
        "meta": {
            "generated_at":      datetime.now().isoformat(),
            "source_db":         str(db_path),
            "total_jurisdictions": len(all_jurs),
            "total_adoptions":   len(all_adoptions),
            "data_sources": [
                "ICC Master I-Code Adoption Chart (iccsafe.org)",
                "CITEL NEC State Adoption Table",
                "DOE BECP energycodes.gov State Portal",
                "NAHB IECC Tracking (Nov 2024)",
                "Municode / eCode360 Municipal Codes",
            ],
            "disclaimer": (
                "Reference data only. Always verify with the AHJ before "
                "submitting construction documents. Adoption status changes frequently."
            ),
        },
        "jurisdictions": {},
    }

    def build_adoption_dict(jur_id: int) -> dict:
        adoptions = adoption_map.get(jur_id, [])
        result = {}
        for adop in adoptions:
            code_key = adop["code_key"]
            amends = []
            if include_amendments:
                raw_amends = amendment_map.get(adop["id"], [])
                amends = [
                    {
                        "type":        a.get("amendment_type"),
                        "section":     a.get("section_ref"),
                        "title":       a.get("title"),
                        "description": a.get("description"),
                        "ordinance":   a.get("ordinance_number"),
                        "date":        a.get("ordinance_date"),
                    }
                    for a in raw_amends
                ]
            result[code_key] = {
                "year":         adop["edition_year"],
                "label":        adop["edition_label"],
                "status":       adop["status"],
                "org":          adop["publishing_org"],
                "full_name":    adop["code_full_name"],
                "mandatory":    bool(adop["is_mandatory"]),
                "effective":    adop["effective_date"],
                "amendments":   amends,
                "amendment_count": len(amends),
            }
        return result

    # Group by state
    states: dict = {}
    for jur in all_jurs:
        jur = dict(jur)
        abbr = jur["state_abbr"]
        jtype = jur["jurisdiction_type"]
        jname = jur["jurisdiction_name"]
        jid = jur["id"]

        if abbr not in states:
            states[abbr] = {
                "name": jur["state_name"],
                "abbr": abbr,
                "region": jur.get("region"),
                "adopted": {},
                "cities": {},
                "counties": {},
                "fire_districts": {},
                "special_districts": {},
            }

        adoptions = build_adoption_dict(jid)

        if jtype == "state":
            states[abbr]["adopted"] = adoptions

        elif jtype in ("city", "town", "village", "township", "borough"):
            states[abbr]["cities"][jname] = {
                "type": jtype,
                "county": jur.get("county_name"),
                "has_own_code": bool(jur.get("has_own_code")),
                "adopted": adoptions,
            }

        elif jtype == "county":
            states[abbr]["counties"][jname] = {
                "type": "county",
                "adopted": adoptions,
            }

        elif jtype == "fire_district":
            states[abbr]["fire_districts"][jname] = {
                "type": "fire_district",
                "county": jur.get("county_name"),
                "adopted": adoptions,
            }

        elif jtype in ("special_district", "utility_district"):
            states[abbr]["special_districts"][jname] = {
                "type": jtype,
                "adopted": adoptions,
            }

    output["jurisdictions"] = states

    # ── Write output ──────────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    size_kb = output_path.stat().st_size / 1024
    print(f"[export] Written to {output_path} ({size_kb:.1f} KB)")
    print(f"[export] {len(states)} states, {len(all_adoptions)} adoptions")

    return {
        "status": "success",
        "output": str(output_path),
        "states": len(states),
        "adoptions": len(all_adoptions),
        "size_kb": round(size_kb, 1),
    }


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_summary_report(db_path: pathlib.Path):
    """Print a text summary of what's in the database."""
    conn = get_connection(db_path)

    print("\n" + "═"*60)
    print("AHJ REGISTRY — DATABASE SUMMARY")
    print("═"*60)

    counts = conn.execute("""
        SELECT jurisdiction_type, COUNT(*) as cnt
        FROM jurisdictions
        GROUP BY jurisdiction_type
        ORDER BY cnt DESC
    """).fetchall()
    print("\nJurisdictions by type:")
    for row in counts:
        print(f"  {row['jurisdiction_type']:30s} {row['cnt']:>6,}")

    code_counts = conn.execute("""
        SELECT code_key, COUNT(DISTINCT jurisdiction_id) as jurs,
               COUNT(*) as total
        FROM code_adoptions
        WHERE status NOT IN ('superseded','withdrawn')
        GROUP BY code_key
        ORDER BY jurs DESC
        LIMIT 20
    """).fetchall()
    print("\nCode adoption coverage:")
    print(f"  {'Code':<15} {'Jurisdictions':>15} {'Rows':>10}")
    print(f"  {'-'*15} {'-'*15} {'-'*10}")
    for row in code_counts:
        print(f"  {row['code_key']:<15} {row['jurs']:>15,} {row['total']:>10,}")

    status_counts = conn.execute("""
        SELECT status, COUNT(*) as cnt
        FROM code_adoptions
        GROUP BY status ORDER BY cnt DESC
    """).fetchall()
    print("\nAdoption status breakdown:")
    for row in status_counts:
        print(f"  {row['status']:25s} {row['cnt']:>8,}")

    ingest_runs = conn.execute("""
        SELECT scraper_name, status, started_at, rows_inserted
        FROM ingest_runs ORDER BY started_at DESC LIMIT 10
    """).fetchall()
    print("\nRecent ingest runs:")
    for row in ingest_runs:
        print(f"  {row['scraper_name']:30s} {row['status']:10s} {row['started_at']} +{row['rows_inserted']} rows")

    print("═"*60)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="AHJ Registry — Master Ingest Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (state-level only, fast)
  python orchestrator.py

  # Full pipeline including municipal scraping
  python orchestrator.py --include-municipal

  # Use a pre-downloaded ICC PDF
  python orchestrator.py --icc-pdf /tmp/icc_chart.pdf

  # Export only (already have data)
  python orchestrator.py --export-only

  # Custom database and output
  python orchestrator.py --db /data/ahj.db --output /www/ahj_data.json
        """
    )
    ap.add_argument("--db",                default=str(DB_PATH), help="SQLite DB path")
    ap.add_argument("--output",            default=str(DEFAULT_EXPORT), help="JSON export path")
    ap.add_argument("--icc-pdf",           default=None, help="Local ICC chart PDF")
    ap.add_argument("--municipal-csv",     default=None, help="CSV of municipalities to scrape")
    ap.add_argument("--include-municipal", action="store_true", help="Run municipal scraper")
    ap.add_argument("--skip-icc",          action="store_true")
    ap.add_argument("--skip-nec",          action="store_true")
    ap.add_argument("--skip-iecc",         action="store_true")
    ap.add_argument("--export-only",       action="store_true", help="Skip ingestion; only export JSON")
    ap.add_argument("--no-export",         action="store_true", help="Skip JSON export")
    ap.add_argument("--summary",           action="store_true", help="Print DB summary and exit")
    args = ap.parse_args()

    db = pathlib.Path(args.db)
    out = pathlib.Path(args.output)

    if args.summary:
        print_summary_report(db)
        sys.exit(0)

    if not args.export_only:
        run_results = run_all_scrapers(
            db_path=db,
            skip_icc=args.skip_icc,
            skip_nec=args.skip_nec,
            skip_iecc=args.skip_iecc,
            skip_municipal=not args.include_municipal,
            municipal_csv=pathlib.Path(args.municipal_csv) if args.municipal_csv else None,
            pdf_path=pathlib.Path(args.icc_pdf) if args.icc_pdf else None,
        )

    if not args.no_export:
        export_result = export_to_json(db, out)
        print(f"\n[orchestrator] Export complete: {export_result}")

    print_summary_report(db)
    print("\n✓ Pipeline complete.")
