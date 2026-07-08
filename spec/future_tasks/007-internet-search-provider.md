# Future Task: Internet Search Provider

## Goal

Build a modular internet search tool that the Python app can use to discover official company websites, careers pages, internship pages, and similar companies.

## Why This Exists

The app should be able to search the internet when run from Python, not only while using Cursor. This module should provide that capability behind a clean interface so other tools can use it.

## Possible Providers

- Tavily
- SerpAPI
- Bing Search API
- Google Custom Search
- Direct page fetching with `httpx` or `requests`
- Browser automation with Playwright only when needed

## Requirements

- Accept a search query and return structured search results.
- Prefer official company domains when looking for careers pages.
- Support queries such as `BlackRock summer 2027 internship careers`.
- Keep provider credentials in `.env` or another ignored local secret store.
- Make the provider replaceable so the project is not locked into one search API.
- Include rate limit and error handling.
- Keep this separate from AI scoring and job collection logic.

## Output

- A reusable module that returns search results with title, URL, snippet, provider, and date searched.

## Acceptance Criteria

- The search provider can be called from the CLI or another module.
- It can find candidate careers pages for at least one seed company.
- It can be disabled or mocked in tests.
