# AHJ Code Adoption Registry — Ingest Pipeline

A production-grade data ingestion system for US building code adoption data.
Populates a SQLite database from authoritative public sources and exports
a structured JSON file consumable by the dashboard.

---

## Architecture

```
ahj-ingest/
├── db/
│   └── schema.py              — SQLite DDL, table definitions, FTS setup
├── scrapers/
│   ├── icc_chart_parser.py    — ICC Master Adoption Chart PDF parser
│   ├── nec_scraper.py         — NEC/NFPA 70 state adoption scraper
│   ├── iecc_scraper.py        — IECC / ASHRAE 90.1 energy code scraper
│   └── municipal_scraper.py   — Municode/eCode360 local ordinance scraper
├── tests/
│   └── test_suite.py          — 32-test unit + integration suite
└── orchestrator.py            — Master pipeline runner + JSON exporter
```

---

## Data Sources

| Scraper | Source | Update Frequency | Auth Required |
|---------|--------|-----------------|---------------|
| `icc_chart_parser` | [ICC Master Adoption Chart PDF](https://www.iccsafe.org/wp-content/uploads/Master-I-Code-Adoption-Chart.pdf) | Monthly | No |
| `nec_scraper` | [CITEL NEC Table](https://citel.us/en/where-is-the-national-electrical-code-in-effect-as-of-2025) + embedded fallback | ~Annually | No |
| `iecc_scraper` | [DOE BECP energycodes.gov](https://www.energycodes.gov/status) + NAHB fallback | ~Annually | No |
| `municipal_scraper` | [Municode Library API](https://library.municode.com) + [eCode360](https://ecode360.com) | Per-jurisdiction | No |

### Why Embedded Fallbacks?

`energycodes.gov` is a React SPA — state portal data requires JS execution (Playwright).
The embedded fallback data was compiled from authoritative sources in November 2024 / February 2025
and is refreshed manually or via the live scrapers when network access is available.

---

## Database Schema

### `jurisdictions`
Every AHJ: state, county, city, town, fire district, etc.
FIPS codes, jurisdiction type, population, governance flags.

### `code_adoptions`
One row per `(jurisdiction × code_book)`.
Captures edition year, mandatory status, effective date, supersession chain.

Status values: `adopted`, `adopted_stretch`, `local_only`, `not_adopted`,
`own_code`, `pending`, `superseded`, `withdrawn`

### `amendments`
Local amendments attached to a code adoption.
Type: `addition`, `modification`, `deletion`, `substitution`, `clarification`, `exception`

### `ingest_runs`
Full provenance log: scraper name, timestamps, row counts, errors.

### `source_urls`
Canonical source links per jurisdiction × source type.

---

## Quick Start

```bash
# Install dependencies
pip install pdfplumber beautifulsoup4 lxml requests

# Run the full state-level pipeline (fast, ~5 seconds)
python orchestrator.py

# Include municipal scraping (~minutes, requires network)
python orchestrator.py --include-municipal

# Use a pre-downloaded ICC PDF (skip network download)
python orchestrator.py --icc-pdf /path/to/Master-I-Code-Adoption-Chart.pdf

# Export only (already have data in DB)
python orchestrator.py --export-only

# Custom paths
python orchestrator.py --db /data/ahj.db --output /www/ahj_data.json

# Print DB summary
python orchestrator.py --summary

# Run tests
python -m tests.test_suite --verbose
```

---

## Running Individual Scrapers

```bash
# ICC chart — downloads PDF, parses all 50 states × 17 I-Codes
python -m scrapers.icc_chart_parser
python -m scrapers.icc_chart_parser --pdf /local/chart.pdf --dry-run

# NEC — 50 states + NYC/Chicago special cases
python -m scrapers.nec_scraper
python -m scrapers.nec_scraper --fallback    # use embedded data only

# IECC / ASHRAE 90.1 — residential + commercial energy codes
python -m scrapers.iecc_scraper
python -m scrapers.iecc_scraper --live       # attempt live scraping

# Municipal — Municode / eCode360 ordinance text extraction
python -m scrapers.municipal_scraper --state TX --cities "Dallas,Austin,Houston"
python -m scrapers.municipal_scraper --csv /path/to/jurisdictions.csv --max 200
```

---

## Adding New Jurisdictions (Municipal CSV)

Create a CSV with these columns:

```csv
state_abbr,jurisdiction_name,jurisdiction_type,county_name
TX,Dallas,city,Dallas County
TX,Austin,city,Travis County
CA,Los Angeles,city,Los Angeles County
FL,Miami-Dade County,county,
FL,Miami,city,Miami-Dade County
CO,Denver Fire Department,fire_district,Denver County
```

Valid `jurisdiction_type` values:
`state`, `county`, `city`, `town`, `village`, `township`, `borough`,
`fire_district`, `utility_district`, `special_district`, `tribal`,
`territory`, `consolidated_city_county`

---

## Refreshing Live Data

### ICC Chart (monthly)
The ICC updates its PDF roughly monthly. The scraper always downloads
from the canonical URL and detects changes via SHA-256 hash.

```bash
# Will re-download if content has changed
python -m scrapers.icc_chart_parser
```

### NEC (annually / when states update)
```bash
# Live scrape from CITEL table
python -m scrapers.nec_scraper

# If CITEL is unavailable, update the NEC_FALLBACK list in nec_scraper.py
# then run with --fallback
```

### IECC / ASHRAE (annually)
Live scraping from `energycodes.gov` requires Playwright (the site is React-rendered):

```bash
pip install playwright
playwright install chromium

# Then modify iecc_scraper.py to use Playwright for JS-rendered pages
python -m scrapers.iecc_scraper --live
```

For now, update the `IECC_FALLBACK` dict in `iecc_scraper.py` from:
- [DOE BECP State Portal](https://www.energycodes.gov/status)
- [NAHB IECC tracking](https://www.nahb.org/advocacy/top-priorities/building-codes)

---

## Integrating with the Dashboard

The `export_to_json` function produces a file matching the dashboard's
expected data structure:

```json
{
  "meta": { "generated_at": "...", "total_jurisdictions": 53 },
  "jurisdictions": {
    "CO": {
      "name": "Colorado",
      "adopted": {
        "IBC": { "year": 2021, "status": "adopted", "amendments": [] },
        "NEC": { "year": 2023, "status": "adopted" },
        "IECC-R": { "year": 2021, "status": "adopted" }
      },
      "cities": {
        "Denver": {
          "adopted": { "IBC": { "year": 2021, ... } }
        }
      }
    }
  }
}
```

In the dashboard `building-codes.html`, replace the hardcoded `JURISDICTION_DB`
with a fetch from this file:

```javascript
let JURISDICTION_DB = {};
fetch('/ahj_data.json')
  .then(r => r.json())
  .then(data => { JURISDICTION_DB = data.jurisdictions; });
```

---

## Known Limitations

- **ICC chart is state-level only.** Local amendments require the municipal scraper.
- **energycodes.gov is JS-rendered.** Full live scraping requires Playwright.
- **Municode rate limits.** The municipal scraper enforces 1.2s delays; large
  batches (500+ cities) take hours.
- **NYC and Chicago** use proprietary codes — the dashboard should display them
  with appropriate `own_code` / `PROPRIETARY` badges rather than I-Code versions.
- **No NFPA 13/72/101.** Fire suppression and life safety codes are not yet
  covered. Add patterns to `CODE_DETECTION_PATTERNS` in `municipal_scraper.py`.

---

## Cron Schedule (Recommended)

```cron
# Monthly: refresh ICC chart + export
0 3 1 * * cd /app/ahj-ingest && python orchestrator.py --skip-nec --skip-iecc

# Quarterly: full refresh
0 2 1 1,4,7,10 * cd /app/ahj-ingest && python orchestrator.py

# Weekly: run tests
0 4 * * 1 cd /app/ahj-ingest && python -m tests.test_suite
```
