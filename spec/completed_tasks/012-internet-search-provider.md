# Completed Task: Internet Search Provider

## Completed Outcome

Implemented a modular internet search layer that can discover company careers pages from Python and the CLI.

## Implemented Files

- `src/internship_search/env_loader.py`
- `src/internship_search/internet_search.py`
- `src/internship_search/cli.py`
- `tests/test_internet_search.py`

## Generated Local Outputs

- `data/internet_search_results.jsonl`

This file is generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Accepts a search query and returns structured results with title, URL, snippet, provider, query, and date searched.
- Supports a company shortcut that builds a careers-focused query such as `BlackRock summer 2027 internship careers`.
- Ranks results to prefer official company and careers domains over social or blocked domains.
- Loads optional credentials from `.env` without adding new dependencies.
- Uses DuckDuckGo HTML search by default.
- Uses Tavily automatically when `TAVILY_API_KEY` is set and `INTERNET_SEARCH_PROVIDER=auto`.
- Includes rate limiting and provider error handling.
- Can be mocked in tests by injecting fetch functions.

## CLI

Search with an explicit query:

```powershell
uv run internship-search internet-search --query "BlackRock summer 2027 internship careers"
```

Search for a seed company:

```powershell
uv run internship-search internet-search --company BlackRock
```

Force a provider:

```powershell
uv run internship-search internet-search --company BlackRock --provider duckduckgo_html
```

## Environment Variables

- `TAVILY_API_KEY` - optional Tavily API key.
- `INTERNET_SEARCH_PROVIDER` - `auto`, `duckduckgo_html`, or `tavily`.

## Verification

```powershell
uv run pytest
```

Result: `55 passed`, including mocked provider tests.

## Latest Local Run

- Query: `BlackRock summer 2027 internship careers`
- Provider: `duckduckgo_html`
- Results: 5
- Top hit: `https://careers.blackrock.com/job/new-york/2027-summer-internship-program-amers/...`

## Next Step

Company discovery can now use this provider to validate careers pages and find fresher companies. AI provider integration remains in `spec/future_tasks/008-ai-provider-integration.md`.
