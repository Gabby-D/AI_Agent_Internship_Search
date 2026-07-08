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

## Source Code

- `src/internship_search/__init__.py` stores package metadata such as the current version.
- `src/internship_search/cli.py` should stay focused on parsing command line arguments and calling application logic.
- `src/internship_search/private_inputs.py` loads local private inputs into structured data.
- `src/internship_search/source_registry.py` builds and stores company career-source registry entries.
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
