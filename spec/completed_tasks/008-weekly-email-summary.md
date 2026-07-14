# Completed Task: Weekly Email Summary

## Completed Outcome

Implemented a modular weekly email summary generator that creates a local email-ready Markdown draft for internships that have not been included in a previous weekly email summary.

## Implemented Files

- `src/internship_search/email_summary.py`
- `src/internship_search/cli.py`
- `tests/test_email_summary.py`

## Generated Local Output

- `data/weekly_email_summary.md`
- `data/email_sent_history.json`

These files are generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Sends draft metadata to `gabrielle.dar@gmail.com` by default.
- Selects scored internships whose URLs are not already in `data/email_sent_history.json`.
- Avoids repeating internship URLs already included in a previous weekly email summary.
- Groups roles by company and fit level.
- Includes title, location, link, placeholder deadline, score, fit explanation, and gaps.
- Highlights companies where the source registry says there is a known connection.
- Includes recommended next actions.
- Saves the draft locally for review before any future real sending step.

## CLI

Use this command after collection, new-posting detection, filtering, and scoring:

```powershell
uv run internship-search weekly-email-summary
```

## Known Problem

The task goal says to send a real weekly email, but no SMTP/API email provider or credentials have been configured yet. The implemented version produces a local draft only. Real sending should be added after choosing an email provider and storing credentials in `.env` or another ignored secret store.

## Latest Local Run

- Generated `data/weekly_email_summary.md`.
- Default recipient: `gabrielle.dar@gmail.com`.
- First no-repeat run selected 4 unsent internships.
- Follow-up no-repeat check selected 0 internships, confirming previously included URLs are excluded.
- Send status: draft only.

## Verification

```powershell
uv run pytest
```

Result: `32 passed`.
