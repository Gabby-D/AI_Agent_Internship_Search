# Installation and Running

This repository is a standard Python package using a `pyproject.toml`, setuptools, a `src/` layout, and an installed `internship-search` command. Python 3.10 or newer is required.

Gitignored runtime files are **not** in the git clone. They live on Google Drive at:

`G:\My Drive\none_git_files\AI_Agent_Internship_Search`

That folder contains `.env`, `private/`, and `data/`. The app, CLI, scheduled tasks, and packaged Windows exe all read and write there. Run commands from the git repository root.

## New laptop

1. Install [Google Drive for desktop](https://www.google.com/drive/download/) and sign in so `G:\My Drive` is available. Wait until `G:\My Drive\none_git_files\AI_Agent_Internship_Search` has finished syncing (`.env`, `private/`, and `data/` should be present).
2. Clone this repository to a local folder such as `C:\Users\<you>\Projects\AI_Agent_Internship_Search`.
3. Install Python 3.10 or newer, then install the package from the repository root:

```powershell
cd C:\path\to\AI_Agent_Internship_Search
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

4. Confirm the app can see Drive files:

```powershell
.\.venv\Scripts\internship-search.exe show-inputs
```

5. Build the windowed dashboard and register Windows tasks:

```powershell
powershell -ExecutionPolicy Bypass -File config\build_windows_app.ps1 -Clean
powershell -ExecutionPolicy Bypass -File config\register_scheduled_tasks.ps1
```

Do not copy `.env` or `private/` into the git clone. Those files already exist on Drive. If Google Drive is mapped to a letter other than `G:`, remap it or the app will not find the files.

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

The executable contains program code only. Keep it in the repository's `app/` folder. At runtime it reads `private/`, `data/`, and `.env` from `G:\My Drive\none_git_files\AI_Agent_Internship_Search`.

## Build a wheel and source distribution

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe -m build
```

Artifacts are written to `dist/`, which is git-ignored. `MANIFEST.in` explicitly excludes `.env`, `private/`, `data/`, virtual environments, caches, and packaged-app output from source distributions. The wheel is built only from the package under `src/internship_search/`.

Always inspect an artifact before sharing it. Personal data should remain only in the Google Drive runtime folder.

## Verify the installation

```powershell
.\.venv\Scripts\internship-search.exe --version
.\.venv\Scripts\internship-search.exe show-inputs
.\.venv\Scripts\python.exe -m pytest -q
```

See `README.md` for application configuration and `private/README.md` for private-input formats.
