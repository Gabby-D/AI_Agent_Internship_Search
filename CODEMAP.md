# Code Map

This file explains the current project layout and where new functionality should live as the internship search tool grows.

## Entry Points

- `src/internship_search/cli.py` defines the command line interface.
- `src/internship_search/__main__.py` lets the package run with `python -m internship_search`.
- `pyproject.toml` exposes the installed CLI command as `internship-search`.

Current CLI commands:

- `uv run internship-search --version` prints the project version.
- `uv run internship-search show-inputs` prints a safe summary of parsed private inputs.
- `uv run internship-search build-source-registry` builds `data/source_registry.json` from seed companies.
- `uv run internship-search discover-companies` writes reviewable similar-company suggestions.
- `uv run internship-search internet-search` searches for company careers pages and writes structured results.
- `uv run internship-search search-job-boards` searches external job boards for internship posting candidates.
- `uv run internship-search collect` collects posting candidates into `data/postings.jsonl`.
- `uv run internship-search detect-new-postings` updates posting history and writes new/change outputs.
- `uv run internship-search filter-postings` filters posting candidates into included and excluded result files.
- `uv run internship-search report` generates `data/latest_report.md` from filtered results.
- `uv run internship-search score-postings` scores filtered postings against private profile inputs.
- `uv run internship-search weekly-email-summary` generates a local weekly email summary draft for unsent internships.
- `uv run internship-search run-scheduled-collection` runs the full local workflow and writes a run log.
- `uv run internship-search review-ui` starts a local browser dashboard for reviewing postings and preferences.

## Source Code

- `src/internship_search/__init__.py` stores package metadata such as the current version.
- `src/internship_search/cli.py` should stay focused on parsing command line arguments and calling application logic.
- `src/internship_search/private_inputs.py` loads local private inputs into structured data.
- `src/internship_search/source_registry.py` builds and stores company career-source registry entries.
- `src/internship_search/company_discovery.py` suggests similar companies for review before registry expansion.
- `src/internship_search/env_loader.py` loads ignored `.env` values into process environment variables.
- `src/internship_search/job_board_search.py` searches external job boards for internship posting candidates.
- `src/internship_search/job_board_listings.py` normalizes LinkedIn and Indeed listing URLs and records public-search limitations.
- `src/internship_search/internet_search.py` searches the internet for company careers pages through replaceable providers with DuckDuckGo-first Google Custom Search failover.
- `src/internship_search/monitored_companies.py` tracks seed companies with no specific internship openings.
- `src/internship_search/career_collectors.py` runs source-specific career page collectors for difficult sites.
- `src/internship_search/posting_metadata.py` enriches posting titles, company names, and locations from parsers and public ATS APIs.
- `src/internship_search/registry_enrichment.py` improves registry careers URLs from saved internet-search results.
- `src/internship_search/job_collector.py` fetches career source pages and extracts first-pass posting candidates.
- `src/internship_search/posting_history.py` tracks new, seen, changed, missing, and duplicate postings across runs using URL and role-key matching.
- `src/internship_search/internship_listing.py` classifies specific internship listings versus generic program or search pages.
- `src/internship_search/posting_filter.py` filters posting candidates for likely target-cycle internship relevance.
- `src/internship_search/review_report.py` generates a readable local Markdown review report.
- `src/internship_search/fit_scoring.py` scores filtered postings through replaceable AI or local providers.
- `src/internship_search/resume_scoring.py` loads optional resume summaries for opt-in AI scoring.
- `src/internship_search/ai_scoring.py` implements Gemini fit scoring with local fallback.
- `src/internship_search/email_summary.py` generates a local weekly email summary draft, excludes inactive posting URLs from history, and tracks already-sent posting URLs.
- `src/internship_search/email_delivery.py` sends weekly summaries through SMTP.
- `src/internship_search/retry.py` retries transient provider failures with exponential backoff.
- `src/internship_search/scheduled_collection.py` composes the full local workflow for manual or scheduled runs and records per-step diagnostics.
- `src/internship_search/review_state.py` stores posting review status, dashboard filters, email-status classification, and UI-edited preferences.
- `src/internship_search/review_ui.py` serves a local browser dashboard with a simple internship listing table and review status controls.
- Future agent, search, scoring, email, and UI modules should be added under `src/internship_search/`.

## Modularity Guidance

- Build each project tool as a focused module with clear inputs and outputs.
- Keep collectors, parsers, filters, scoring, reporting, storage, AI calls, email, scheduling, and UI code separable.
- Prefer functions and classes that can be tested without live network calls or private files.
- Let the CLI compose tools into workflows instead of putting core logic directly in the CLI.

Suggested future modules:

- `agent.py` for coordinating AI-assisted search and evaluation steps.
- `config.py` for loading settings from `config/`, `.env`, and private local files.
- `models.py` for shared data structures such as internships, companies, and search results.
- `search/` for job board and company career page search integrations.
- `scoring.py` for ranking roles against the personal profile.
- `email.py` for weekly email summary generation and delivery.
- `ui/` for the eventual user interface.

## Configuration

- `config/settings.example.toml` is the tracked example configuration.
- Local real configuration should be copied from the example and kept out of git if it contains personal details or secrets.
- `.env.example` documents environment variables without storing real credentials.
- `.env` should contain local API keys and email credentials. It is ignored by git.
- `.python-version` tells `uv` which Python version this project expects.
- `config/register_scheduled_tasks.ps1` registers daily collection and Monday weekly-email tasks with missed-run catch-up.
- `config/run_scheduled_collection.ps1` runs the workflow and writes console logs under `data/scheduled_run_output/`.
- `config/run_weekly_email.ps1` sends the weekly email summary and writes console logs under `data/scheduled_run_output/`.
- `config/windows_task_scheduler.example.ps1` shows how to register a single local scheduled task.

## Local Data

- `private/` is for personal inputs such as resume content, profile notes, skills, classes, projects, company lists, and job site lists.
- `private/README.md` documents suggested private files.
- Real files in `private/` are ignored by git.

## Generated Data

- `data/` is for outputs produced by the app, including raw job postings, filtered roles, scoring results, and weekly summaries.
- `data/README.md` explains the purpose of this directory.
- Generated files in `data/` are ignored by git.

## Specs and Planning

- `spec/future_tasks/` contains ideas and planned work.
- `spec/current_tasks/` contains active tasks.
- `spec/completed_tasks/` contains completed task notes and decisions.

## Tests

- `tests/` contains automated tests.
- `tests/test_cli.py` currently verifies the starter CLI version command.
- New modules should get focused tests in `tests/` as behavior is added.

## Dependency Management

- `uv.lock` records exact dependency versions.
- `pyproject.toml` lists package metadata, dependencies, dev dependencies, and pytest settings.
- Use `uv sync` to create or update the virtual environment.
- Use `uv run pytest` to run tests.
- Use `uv run internship-search --version` to run the starter CLI.
- Use `uv run internship-search show-inputs` to inspect parsed private inputs.
- Use `uv run internship-search build-source-registry` to build the local source registry.
- Use `uv run internship-search discover-companies` to generate similar-company suggestions.
- Use `uv run internship-search internet-search --company BlackRock` to search for careers pages.
- Use `uv run internship-search collect` to collect posting candidates.
- Use `uv run internship-search detect-new-postings` to update local posting history.
- Use `uv run internship-search filter-postings` to filter posting candidates.
- Use `uv run internship-search report` to generate the local review report.
- Use `uv run internship-search score-postings` to score filtered postings.
- Use `uv run internship-search weekly-email-summary` to generate a local weekly email draft.
- Use `uv run internship-search run-scheduled-collection` to run the full repeatable workflow.
- Use `uv run internship-search review-ui` to start the local review dashboard.
