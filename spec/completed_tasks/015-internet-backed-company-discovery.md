# Completed Task: Internet-Backed Company Discovery

## Completed Outcome

Extended company discovery to use the modular internet search provider for fresher suggestions and careers-page evidence, while keeping the curated list as fallback.

## Implemented Files

- `src/internship_search/company_discovery.py`
- `src/internship_search/cli.py`
- `tests/test_company_discovery.py`
- `tests/test_company_discovery_internet.py`

## Generated Local Outputs

- `data/discovered_companies.json`
- `data/discovered_companies.md`

## Behavior

- Runs up to 5 internet searches based on industries, seed companies, and preferences.
- Reuses `internet_search.search_internet` and provider rate limiting.
- Adds suggestions with evidence title, URL, and snippet when found online.
- Merges internet results with the curated list and deduplicates by company name.
- Enriches curated entries with validated careers URLs when internet search finds stronger evidence.
- Falls back to curated suggestions when internet search fails or returns nothing useful.
- Preserves review workflow and `--update-registry` behavior.

## CLI

```powershell
uv run internship-search discover-companies
```

Use curated suggestions only:

```powershell
uv run internship-search discover-companies --no-internet
```

## Verification

```powershell
uv run pytest
```

Result: `89 passed`, including mocked internet discovery tests.

## Latest Local Run

- Suggested companies: 13 curated, 0 internet (DuckDuckGo returned no results during this run).
- Curated fallback preserved full suggestion list.
