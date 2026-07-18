# Completed Task: Weekly Recommended-Company Discovery

Added independent Windows Task Scheduler automation for refreshing recommended companies every Monday before collection and weekly email delivery.

## Behavior

- Runs `discover-companies` every Monday at 8:30 AM.
- Saves refreshed suggestions to the existing ignored discovery outputs.
- Writes timestamped console output under `data/scheduled_run_output/`.
- Uses `StartWhenAvailable` so missed runs start after the laptop becomes available.
- Does not automatically add suggestions to the monitored-company registry; the user reviews them in the Companies tab first.

## Verification

- The registration and verification scripts include all three automation tasks.
- PowerShell scripts pass parser validation.
- Automated tests cover the discovery task names, schedule, command, and log naming.
