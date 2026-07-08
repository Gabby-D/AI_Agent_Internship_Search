# Completed Task: Load Private Inputs

## Completed Outcome

Implemented a modular private input loader that parses the local private files into structured data for future search, filtering, scoring, and reporting tools.

## Implemented Files

- `src/internship_search/private_inputs.py`
- `src/internship_search/cli.py`
- `tests/test_private_inputs.py`

## Inputs Covered

- `private/list_of_companies.md`
- `private/preferences.md`
- `private/mcgill_class_list.md`
- `private/connections.md`
- `private/Resume - Gabrielle Dar.pdf`

## Behavior

- Parses company names, websites, and connection status.
- Parses industries of interest from the company file.
- Parses likes and dislikes from preferences.
- Parses program information and coursework from the McGill course list.
- Allows missing or empty optional connections notes.
- Detects whether the resume PDF exists without reading or exposing resume contents.
- Provides clear `PrivateInputError` messages for malformed required inputs.

## CLI

Use this command to view a safe summary of parsed private inputs:

```powershell
uv run internship-search show-inputs
```

## Verification

```powershell
uv run pytest
```

Result: `5 passed`.
