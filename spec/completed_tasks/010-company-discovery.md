# Completed Task: Similar Company Discovery

## Completed Outcome

Implemented the local, non-AI version of company discovery. The tool suggests similar companies for review before they are added to active collection.

## Implemented Files

- `src/internship_search/company_discovery.py`
- `src/internship_search/cli.py`
- `tests/test_company_discovery.py`

## Generated Local Outputs

- `data/discovered_companies.json`
- `data/discovered_companies.md`

These files are generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Uses the private seed company list, industries, and preferences.
- Expands beyond the original seed companies.
- Suggests companies based on industries and preferences loaded from ignored private inputs.
- Includes official websites and careers pages from a local curated list.
- Marks suggestions with `origin = discovered`.
- Keeps suggestions reviewable and separate from the active source registry by default.
- Avoids duplicates already present in seed companies or the source registry.
- Avoids suggestions that primarily match disliked work areas.

## CLI

Generate reviewable suggestions:

```powershell
uv run internship-search discover-companies
```

Optionally merge suggestions into the active source registry:

```powershell
uv run internship-search discover-companies --update-registry
```

The default command does not update the registry because the intended workflow is to review suggestions first.

## Known Limitation

This implementation uses a local curated list for company suggestions. Use `internet-search` to validate careers pages before adding companies to the registry. A future enhancement can call the internet search provider directly from company discovery.

## Latest Local Run

- Suggested companies: 13.
- Wrote suggestions to `data/discovered_companies.json`.
- Wrote review report to `data/discovered_companies.md`.
- Source registry update: skipped for review.

## Verification

```powershell
uv run pytest
```

Result: `38 passed`.
