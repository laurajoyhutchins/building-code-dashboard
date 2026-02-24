# AHJ Code Adoption Registry

A combined data pipeline and frontend dashboard for U.S. building code adoption research.

The project ingests adoption data (state and optional local), stores it in SQLite, exports a dashboard-ready JSON file, and serves a searchable UI for jurisdiction lookups.

## What It Includes

- Static dashboard UI (`index.html`, `src/css/styles.css`, `src/js/app.js`)
- Python ingestion pipeline (`src/py/orchestrator.py`)
- Scrapers for ICC, NEC, IECC, and optional municipal ordinance sources
- Normalized SQLite schema with ingest provenance and amendment tracking
- Test suite for schema, parser behavior, extraction logic, and export correctness

## Repository Layout

```text
building-code-dashboard/
|-- index.html
|-- README.md
`-- src/
    |-- css/
    |   `-- styles.css
    |-- js/
    |   `-- app.js
    `-- py/
        |-- orchestrator.py
        |-- db/
        |   `-- schema.py
        |-- scrapers/
        |   |-- icc_chart_parser.py
        |   |-- nec_scraper.py
        |   |-- iecc_scraper.py
        |   `-- municipal_scraper.py
        `-- tests/
            `-- test_suite.py
```

## Requirements

- Python 3.11+ (3.13 is used in local bytecode artifacts)
- Internet access for live scraping runs
- Python packages:
  - `pdfplumber`
  - `beautifulsoup4`
  - `lxml`

Install dependencies:

```bash
pip install pdfplumber beautifulsoup4 lxml
```

## Quick Start

Run from repository root.

1. Run ingest + export (state-level by default):

```bash
python src/py/orchestrator.py
```

2. Start a static server for the frontend:

```bash
python -m http.server 8080
```

3. Open:

- `http://localhost:8080/index.html`

## Pipeline Usage

### Orchestrator

Default run (fast path, municipal scraping skipped):

```bash
python src/py/orchestrator.py
```

Useful options:

```bash
# Include municipal scraping
python src/py/orchestrator.py --include-municipal

# Export only (skip scraping)
python src/py/orchestrator.py --export-only

# Custom DB and export paths
python src/py/orchestrator.py --db C:/data/ahj_registry.db --output C:/data/ahj_data.json

# Print summary from an existing DB
python src/py/orchestrator.py --summary
```

### Individual Scrapers

```bash
# ICC master chart parser
python src/py/scrapers/icc_chart_parser.py --dry-run

# NEC scraper
python src/py/scrapers/nec_scraper.py --fallback

# IECC scraper
python src/py/scrapers/iecc_scraper.py --fallback

# Municipal scraper (targeted run)
python src/py/scrapers/municipal_scraper.py --state TX --cities "Dallas,Austin"
```

## Data Outputs

By default, the orchestrator creates:

- SQLite DB: `src/py/ahj_registry.db`
- Export JSON: `src/ahj_data.json`

The JSON output is structured for direct dashboard consumption and includes:

- Metadata (`generated_at`, counts, source list, disclaimer)
- State-level adoption maps
- Nested city/county/fire district structures when present
- Optional amendment payloads

## Testing

Run the full test suite:

```bash
python src/py/tests/test_suite.py
```

Verbose mode:

```bash
python src/py/tests/test_suite.py --verbose
```

## Notes

- Municipal scraping is intentionally optional and slower due to rate limiting and source variability.
- Some scrapers include curated fallback datasets when live extraction is unavailable.
- Frontend sample data in `src/js/app.js` is currently in-repo and can differ from exported JSON until integration wiring is finalized.

## Disclaimer

This repository is for research/reference workflows. Building code adoption status changes frequently and can vary within the same county or metro area. Always verify current requirements directly with the relevant Authority Having Jurisdiction (AHJ) before design, permitting, or construction decisions.
