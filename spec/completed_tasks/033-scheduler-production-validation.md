# Scheduler Production Validation

## Completed outcome

Validated the Windows Task Scheduler setup, its wrapper scripts, and local diagnostic outputs on July 15, 2026.

## Scheduler configuration

- `AI Agent Internship Search` is registered, ready, and scheduled daily at 9:00 AM.
- `AI Agent Internship Weekly Email` is registered, ready, and scheduled weekly on Monday at 10:00 AM.
- Both tasks have `StartWhenAvailable` enabled, so a missed run starts when the computer next becomes available.
- The collection task's next run is July 16, 2026 at 9:00 AM; the weekly email task's next run is July 20, 2026 at 10:00 AM.

## Validation

- Manually ran `config/run_scheduled_collection.ps1 --include-job-boards`.
- The wrapper finished with exit code 0 and wrote `data/scheduled_run_output/run_20260715_130855.log`.
- The workflow recorded its structured result in `data/scheduled_collection_runs.jsonl`: 70 sources registered, 12 candidates collected, 1 included posting, and 1 local email draft selected without sending email.
- `config/verify_automation.ps1` confirmed email environment variables are present, both tasks are ready, and recent wrapper logs are available.
- The weekly-email wrapper log from July 13, 2026 shows exit code 0 and a successful delivery to the configured recipient.

## Notes

- The collection task's prior scheduled attempt returned `3221225786` (`0xC000013A`), which indicates an interrupted or cancelled process rather than a workflow failure. The manual wrapper validation completed successfully afterward.
- Automatic weekly email remains enabled because SMTP configuration and a real scheduled delivery have both been verified.
- External collection source warnings remain expected and are recorded in each run's local diagnostics.

## Acceptance checks

- [x] Selected scheduled tasks are registered with the intended frequency.
- [x] Manual collection-wrapper validation completed successfully and produced logs.
- [x] The latest structured run log identifies every workflow step and outcome.
- [x] Weekly email delivery and recipient configuration were validated before automatic email remained enabled.
