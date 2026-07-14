# Completed Task: Verify Email and Scheduled Runs

## Goal

Confirm the project works end to end in daily use: scheduled collection, Monday email delivery, and reliable run logs.

## What Was Verified

- `.env` email settings present (`EMAIL_FROM`, `EMAIL_TO`, `EMAIL_SMTP_PASSWORD`; SMTP host/port use Gmail defaults).
- Live `weekly-email-summary --send` delivered successfully to the configured recipient.
- `data/email_sent_history.json` updated with 14 posting URLs after the first successful send; a second send with zero unsent postings still succeeded without duplicating history entries.
- Windows scheduled tasks registered and **Ready** (`AI Agent Internship Search`, `AI Agent Internship Weekly Email`).
- Structured collection run logged in `data/scheduled_collection_runs.jsonl` with `status: partial` and successful score/email steps.
- Weekly email wrapper script produced `data/scheduled_run_output/weekly_email_*.log` with exit code `0`.

## Changes Made

- Added `config/verify_automation.ps1` for local email, task, and log checks without printing secrets.
- Fixed `Join-Path` usage in wrapper scripts for Windows PowerShell 5.x compatibility.
- Added `is_scheduled_run_operationally_successful()` so useful `partial` collection runs exit `0` when scoring and email steps succeed.
- Documented operational checklist and troubleshooting in `README.md`.

## Operational Checklist

1. Run `powershell -ExecutionPolicy Bypass -File config/verify_automation.ps1`
2. Send a test email: `uv run internship-search weekly-email-summary --send`
3. Confirm `data/email_sent_history.json` changes only after `Email sent to ...`
4. After collection, inspect the latest line in `data/scheduled_collection_runs.jsonl`
5. On failures, read the newest log in `data/scheduled_run_output/`

## Notes

- Collection task last scheduler result may show non-zero when a prior run was interrupted; wrapper logs and `scheduled_collection_runs.jsonl` are the source of truth.
- Partial exit-code behavior also covers future task `030-partial-run-exit-status.md`.
