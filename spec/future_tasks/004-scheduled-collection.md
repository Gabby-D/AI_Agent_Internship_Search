# Future Task: Scheduled Collection

## Goal

Run job collection automatically on a recurring schedule.

## Requirements

- Support a weekly or daily collection schedule.
- Log run status, errors, and number of postings collected.
- Avoid emailing if a run fails before producing reliable results.
- Make scheduling optional so local manual runs still work.

## Possible Approaches

- Windows Task Scheduler for local automation.
- GitHub Actions if private data can be handled safely later.
- A small local always-on service only if manual scheduling is not enough.

## Output

- Repeatable scheduled collection runs.
- Run logs saved locally under `data/` or another ignored directory.
