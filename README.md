# AI Agent Internship Search

A Python-based tool to help find open Summer 2027 internships that match my interests, availability, resume, skills, coursework, projects, and experience.

## Goal

Build a simple, useful AI agent that can search internship opportunities, filter them for relevance, and provide a weekly email summary of promising active roles.

## Core Features

- Track the types of internships and companies I am interested in.
- Use my resume, skills, classes, projects, and experience to evaluate fit.
- Search job sites, company career portals, and similar companies for active openings.
- Filter out irrelevant, closed, or duplicate roles.
- Provide a weekly email review of new or high-priority opportunities.
- Include a clean user interface for viewing findings and updating search filters.

## Private Data

The project should support local-only private data that is not committed to git, including:

- Personal profile information.
- Resume details.
- Company and website lists.
- API keys and other credentials.

## Project Structure Goals

- Use Python as the main language.
- Keep the codebase clean, minimal, and easy to understand.
- Avoid over-engineering early versions.
- Include a `spec/` directory for tracking work:
  - `spec/future_tasks/`
  - `spec/current_tasks/`
  - `spec/completed_tasks/`

## Directory Structure

- `.venv/` is the local virtual environment created by `uv sync`. It is ignored by git.
- `config/` contains example non-secret configuration files, such as search preferences and email settings.
- `data/` stores generated outputs, including cached job postings, scored roles, and weekly summaries. Generated files here are ignored by git.
- `private/` stores local-only personal information, resume details, company lists, job site lists, and other sensitive inputs. Real files here are ignored by git.
- `spec/` tracks project planning and implementation notes.
- `spec/future_tasks/` is for planned work that is not ready to build yet.
- `spec/current_tasks/` is for tasks currently being designed or implemented.
- `spec/completed_tasks/` is for finished work and decisions.
- `src/internship_search/` contains the main Python package and application code.
- `tests/` contains automated tests for the project.

Key root files:

- `.env.example` shows the environment variables needed for local setup without storing secrets.
- `.gitignore` keeps private data, generated files, caches, and local environments out of git.
- `.python-version` records the Python version used by `uv`.
- `CODEMAP.md` explains how the codebase is organized and where to add new functionality.
- `pyproject.toml` defines the Python package, CLI command, dependencies, and test settings.
- `uv.lock` locks exact dependency versions for reproducible installs.

## Development Setup

This project uses `uv` for Python environment and dependency management.

Install `uv` on Windows:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Create the virtual environment and install dependencies:

```powershell
uv sync
```

Run the CLI:

```powershell
uv run internship-search --version
```

Show a safe summary of the private inputs:

```powershell
uv run internship-search show-inputs
```

Build the local company source registry:

```powershell
uv run internship-search build-source-registry
```

Run tests:

```powershell
uv run pytest
```

## Current Project Status

- Private inputs can be parsed into structured data.
- Seed companies can be converted into a local source registry.
- The source registry is written to `data/source_registry.json`, which is ignored by git.
- The next implementation task is the first job collector.

## Possible Agent Capabilities

The AI agent may use skills, MCPs, APIs, or browser automation to:

- Search job boards.
- Visit company career pages.
- Identify similar companies.
- Extract relevant internship details.
- Score roles based on my profile and preferences.
- Summarize why each role may or may not be a good fit.

## Open Questions

- Which internship types should the first version prioritize?
- Which locations, remote options, or availability constraints should be included?
- Which job sites and company portals should be searched first?
- What information should be included in the weekly email summary?
- What type of user interface should the first version use: command line, local web app, or simple desktop-style UI?