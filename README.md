# building-code-dashboard

Dashboard + ingestion pipeline for U.S. building code adoption data.

## Current Repository Structure

```text
building-code-dashboard/
|-- index.html
|-- README.md
|-- .gitignore
|-- .claude/
|   `-- settings.local.json
`-- src/
    `-- py/
        |-- __init__.py
        |-- orchestrator.py
        |-- db/
        |   |-- __init__.py
        |   `-- schema.py
        |-- scrapers/
        |   |-- __init__.py
        |   |-- icc_chart_parser.py
        |   |-- nec_scraper.py
        |   |-- iecc_scraper.py
        |   `-- municipal_scraper.py
        `-- tests/
            |-- __init__.py
            `-- test_suite.py
```

## Notes

- `index.html` is the GitHub Pages entrypoint.
- Scraper implementations live only in `src/py/scrapers/`.
- Database schema implementation lives in `src/py/db/schema.py`.
- Tests live in `src/py/tests/test_suite.py`.

## Running From Repo Root

```bash
# Run pipeline
python src/py/orchestrator.py

# Optional flags
python src/py/orchestrator.py --include-municipal
python src/py/orchestrator.py --export-only

# Run tests
python src/py/tests/test_suite.py
```
