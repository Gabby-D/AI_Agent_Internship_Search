# Completed Task: Email Delivery

## Completed Outcome

Implemented SMTP email delivery for the weekly internship summary while keeping draft generation as the source of truth.

## Implemented Files

- `src/internship_search/email_delivery.py`
- `src/internship_search/email_summary.py`
- `src/internship_search/cli.py`
- `src/internship_search/scheduled_collection.py`
- `tests/test_email_delivery.py`
- `tests/test_email_summary.py`

## Generated Local Outputs

- `data/weekly_email_summary.md`
- `data/email_sent_history.json` (updated only after a successful send)

## Behavior

- Reads SMTP credentials from `.env`.
- Uses Gmail-compatible SMTP defaults (`smtp.gmail.com:587` with TLS).
- Generates the local Markdown draft first.
- Sends a plain-text email body when `--send` is requested and credentials are configured.
- Updates `data/email_sent_history.json` only after a successful send.
- Fails safely when credentials are missing or SMTP delivery fails.
- Supports mocked delivery in tests.

## Environment Variables

- `EMAIL_FROM` - sender address.
- `EMAIL_TO` - optional default recipient override.
- `EMAIL_SMTP_HOST` - SMTP host, default `smtp.gmail.com`.
- `EMAIL_SMTP_PORT` - SMTP port, default `587`.
- `EMAIL_SMTP_USER` - SMTP username, defaults to `EMAIL_FROM`.
- `EMAIL_SMTP_PASSWORD` - SMTP password or app password.
- `EMAIL_SMTP_USE_TLS` - `true` by default.

## CLI

Generate a draft only:

```powershell
uv run internship-search weekly-email-summary
```

Send the summary:

```powershell
uv run internship-search weekly-email-summary --send
```

Send from the scheduled workflow:

```powershell
uv run internship-search run-scheduled-collection --send-email
```

## Verification

```powershell
uv run pytest
```

Result: all tests pass, including mocked SMTP delivery tests.

## Notes

For Gmail, use an app password in `EMAIL_SMTP_PASSWORD` rather than your normal account password.
