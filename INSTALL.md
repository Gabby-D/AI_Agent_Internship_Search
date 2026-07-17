# Installation and Running

This repository is a standard Python package using a `pyproject.toml`, setuptools, a `src/` layout, and an installed `internship-search` command. Python 3.10 or newer is required.

Run commands from the repository root so the program can locate the ignored `private/`, `data/`, and `.env` paths.

## Standard Python and pip

Create a virtual environment and install the package in editable mode:

```powershell
cd C:\path\to\AI_Agent_Internship_Search
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Run the dashboard with either standard entry point:

```powershell
.\.venv\Scripts\internship-search.exe review-ui
.\.venv\Scripts\python.exe -m internship_search review-ui
```

Install optional tools only when needed:

```powershell
# Tests
.\.venv\Scripts\python.exe -m pip install -e ".[test]"

# Windows app builder
.\.venv\Scripts\python.exe -m pip install -e ".[app]"

# Python package builder
.\.venv\Scripts\python.exe -m pip install -e ".[build]"

# All development tools
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Using uv

`uv` is optional. It uses the same standard `pyproject.toml` package metadata:

```powershell
uv sync
uv run internship-search review-ui
```

For tests and packaging tools:

```powershell
uv sync --extra dev
uv run pytest
```

## One-click Windows app

Install the `app` extra, then build:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[app]"
powershell -ExecutionPolicy Bypass -File config\build_windows_app.ps1 -Clean
```

Double-click `app/Internship Search.exe` or the Desktop shortcut. No terminal is required while using the packaged app.

The executable contains program code only. It must remain in the repository's `app/` folder because it reads the existing local `private/` and `data/` folders at runtime.

## Build a wheel and source distribution

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe -m build
```

Artifacts are written to `dist/`, which is git-ignored. `MANIFEST.in` explicitly excludes `.env`, `private/`, `data/`, virtual environments, caches, and packaged-app output from source distributions. The wheel is built only from the package under `src/internship_search/`.

Always inspect an artifact before sharing it. Personal data should remain only in ignored local files.

## Verify the installation

```powershell
.\.venv\Scripts\internship-search.exe --version
.\.venv\Scripts\python.exe -m pytest -q
```

See `README.md` for application configuration and `private/README.md` for local input formats.
