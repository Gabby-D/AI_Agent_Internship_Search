# Completed Task: Build Company Source Registry

## Completed Outcome

Implemented a modular source registry builder that turns seed companies from the private company list into structured career-source records.

## Implemented Files

- `src/internship_search/source_registry.py`
- `src/internship_search/cli.py`
- `tests/test_source_registry.py`

## Generated Local Output

- `data/source_registry.json`

This file is generated locally and ignored by git through the existing `data/` ignore rule.

## Registry Fields

- `company`
- `website`
- `careers_url`
- `source_type`
- `origin`
- `has_connection`
- `notes`

## Seed Sources Added

- PWC
- BlackRock
- Bain
- Bakar Bio Labs
- McKinsey & Co

## CLI

Use this command to rebuild and inspect the source registry:

```powershell
uv run internship-search build-source-registry
```

## Verification

```powershell
uv run pytest
```

Result: `10 passed`.
